"""人工角色配置、路径、公开字段和脱敏规则回归。"""
import os
from pathlib import Path
import subprocess
import sys
import pytest
from ezllmtest.platform import configuration_schema as schema
from ezllmtest.bootstrap.settings import load_process, activate
from ezllmtest.platform import configuration
from ezllmtest.platform.files import document_path

# 只在隔离临时目录写人工角色配置，不复制原地 .env 或秘密文件。
def sources(tmp_path):
    values = {
        "backend": "DATABASE_URL=mysql+pymysql://fake:synthetic@127.0.0.1:3306/fake\nAGENT_REDIS_URL=redis://127.0.0.1:6379/14\nAGENT_REDIS_PREFIX=offline-check\n",
        "frontend": "VUE_APP_API_BASE_URL=http://127.0.0.1:8230\nVUE_APP_AGENT_API_BASE_URL=http://127.0.0.1:8231\nVUE_APP_OBSERVABILITY_API_BASE_URL=http://127.0.0.1:8140\nFRONTEND_PORT=8180\n",
        "observability": "OBSERVABILITY_DATABASE_PATH=synthetic.sqlite3\nAGENT_TELEMETRY_ENABLED=true\n",
    }
    result={}
    for name, text in values.items():
        path=tmp_path/(name+".config")
        path.write_text(text.replace("synthetic.sqlite3", str(tmp_path / "data" / "synthetic.sqlite3")), encoding="utf-8")
        result[name]=str(path)
    return result

# 以人工配置逐角色核对字段投影，不允许跨角色读取秘密。
@pytest.mark.parametrize("role,selected", [
    ("product-api", ("backend","frontend")), ("agent-api", ("backend","frontend","observability")),
    ("worker", ("backend","observability")), ("mcp", ("backend",)),
    ("observability-api", ("frontend","observability"))])
def test_role_projection(tmp_path, role, selected):
    paths=sources(tmp_path)
    result=load_process(role,str(tmp_path),**{k:paths[k] for k in selected})
    if role=="observability-api":
        assert "DATABASE_URL" not in result.values and "AGENT_REDIS_URL" not in result.values
    if role in {"worker","agent-api"}:
        assert result.values["AGENT_TELEMETRY_ENABLED"]=="true"
    assert "synthetic" not in repr(result)
    with pytest.raises(schema.RuntimeConfigurationError):
        load_process(role,str(tmp_path),**{k:v for k,v in paths.items() if k not in selected})

# 验证前端仅接收公开字段，非法输入报错不回显秘密值。
@pytest.mark.parametrize("lines", [
    ["FRONTEND_PORT=8180", "FRONTEND_PORT=8181"],
    ["DATABASE_URL=do-not-display"], ["FRONTEND_PORT=0"],
    ["VUE_APP_API_BASE_URL=https://example.com"], ["invalid-line"],
    ["VUE_APP_API_BASE_URL='unterminated"]])
def test_frontend_rejects_invalid_and_redacts(lines):
    with pytest.raises(schema.RuntimeConfigurationError) as caught:
        schema.parse_env_lines(lines,schema.FRONTEND_FIELDS)
    assert "do-not-display" not in str(caught.value)

# 验证直接值与 _FILE 冲突及路径校验，配置检查不读取秘密引用正文。
def test_secret_conflict_and_reference_check_without_read(tmp_path,monkeypatch):
    paths=sources(tmp_path)
    path=Path(paths["backend"])
    path.write_text(path.read_text()+"DATABASE_URL_FILE="+str(tmp_path/"not-read.secret")+"\n")
    with pytest.raises(schema.RuntimeConfigurationError):
        load_process("product-api",str(tmp_path),backend=str(path),frontend=paths["frontend"],resolve_secrets=False)

# 模拟父环境污染与不同 CWD，确认显式配置和数据根保持优先。
def test_parent_environment_and_data_cwd(tmp_path,monkeypatch):
    paths=sources(tmp_path)
    config=load_process("product-api",str(tmp_path),backend=paths["backend"],frontend=paths["frontend"])
    monkeypatch.setenv("DATABASE_URL","parent-pollution")
    monkeypatch.setenv("EZLLMTEST_OBSERVABILITY_INGEST_TOKEN","parent-pollution")
    monkeypatch.setenv("PYTHONPATH","parent-pollution")
    activate(config)
    assert configuration.get("DATABASE_URL")==config.values["DATABASE_URL"]
    assert "DATABASE_URL" not in os.environ and "PYTHONPATH" not in os.environ
    expected=tmp_path/"backend/static/projects/EzOffline/file.md"
    first=document_path("static/projects/EzOffline/file.md")
    other=tmp_path/"other";other.mkdir();monkeypatch.chdir(other)
    assert document_path("static/projects/EzOffline/file.md")==first==expected
    assert not expected.exists()
    with pytest.raises(ValueError,match="outside_data_boundary"):
        document_path("../../outside")

# 从隔离目录运行五入口 --help，确认无需配置即可退出；父子进程应使用一致文本编码。
@pytest.mark.parametrize("entry",["product_api","agent_api","observability_api","agent_worker","mcp_server"])
def test_entry_help_needs_no_configuration(entry,tmp_path):
    env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1",PYTHON_DOTENV_DISABLED="true")
    result=subprocess.run([sys.executable,"-B","-m","ezllmtest.entrypoints."+entry,"--help"],cwd=tmp_path,env=env,capture_output=True,text=True,timeout=20)
    assert result.returncode==0
    assert "--repo-root" in result.stdout

@pytest.mark.parametrize("role", ["product-api","agent-api","observability-api","worker","mcp"])
def test_each_role_assembles_before_lifespan_without_io(tmp_path, role):
    """实际装配五入口的依赖图，但不进入 lifespan、不打开服务或数据库。"""
    from ezllmtest.bootstrap.settings import ROLE_SOURCES
    from ezllmtest.bootstrap.app_factory import create_app
    paths=sources(tmp_path)
    # 装配测试关闭遥测；Windows IPC 生命周期另有人工专项用例。
    obs=Path(paths["observability"])
    obs.write_text(obs.read_text().replace("AGENT_TELEMETRY_ENABLED=true","AGENT_TELEMETRY_ENABLED=false"))
    config=load_process(role,str(tmp_path),**{k:paths[k] for k in ROLE_SOURCES[role]})
    app=create_app(config)
    if role in {"worker","mcp"}: assert app is None
    else: assert app is not None


@pytest.mark.parametrize("role", ["product-api", "agent-api", "observability-api", "worker", "mcp"])
def test_local_cli_matches_explicit_sources_before_assembly(tmp_path, monkeypatch, role):
    """把人工配置放入固定三端位置，捕获装配前的投影；MCP 不读取额外来源，不启动任何服务。"""
    from ezllmtest.bootstrap import app_factory
    from ezllmtest.bootstrap.settings import ROLE_SOURCES
    paths = sources(tmp_path)
    for name, source in paths.items():
        directory = tmp_path / name
        directory.mkdir()
        text = Path(source).read_text().replace(str(tmp_path / "data" / "synthetic.sqlite3"), "data/synthetic.sqlite3")
        (directory / ".env").write_text(text, encoding="utf-8")
    selected = ROLE_SOURCES[role]
    # 删除本角色不允许读取的源，证明快捷模式不会要求或发现这些文件。
    for name in set(paths) - set(selected):
        (tmp_path / name / ".env").unlink()
    actual = []
    class Captured(Exception): pass
    def capture(*args, **kwargs):
        actual.append(load_process(*args, **kwargs))
        raise Captured
    monkeypatch.setattr(app_factory, "load_process", capture)
    other = tmp_path / "other"; other.mkdir(); monkeypatch.chdir(other)
    base = ["--repo-root", str(tmp_path)]
    if role == "worker": base += ["--consumer", "offline"]
    if role == "mcp": base += ["--project-id", "EzOffline"]
    with pytest.raises(Captured): app_factory.main(role, base + ["--local-config"])
    explicit = [part for name in selected for part in (f"--{name}-env-file", str(tmp_path / name / ".env"))]
    with pytest.raises(Captured): app_factory.main(role, base + explicit)
    assert actual[0].values == actual[1].values
    assert actual[0].repo_root == actual[1].repo_root == tmp_path
    with pytest.raises(SystemExit): app_factory.main(role, base + ["--local-config"] + explicit)
    assert len(actual) == 2


def test_local_cli_missing_conflicting_and_invalid_root(tmp_path, monkeypatch):
    """错误选择器在应用装配前失败；缺失固定文件不回退到其他文件或父环境。"""
    from ezllmtest.bootstrap import app_factory
    def forbidden(*args, **kwargs): pytest.fail("invalid configuration reached assembly")
    monkeypatch.setattr(app_factory, "create_app", forbidden)
    with pytest.raises(schema.RuntimeConfigurationError):
        app_factory.main("product-api", ["--repo-root", str(tmp_path), "--local-config"])
    for value in ("relative", str(tmp_path / "missing")):
        with pytest.raises(schema.RuntimeConfigurationError):
            app_factory.main("product-api", ["--repo-root", value, "--local-config"])
    with pytest.raises(SystemExit):
        app_factory.main("product-api", ["--repo-root", str(tmp_path)])


def test_sqlite_paths_are_configuration_relative_and_bounded(tmp_path, monkeypatch):
    """人工 SQLite 路径不打开数据库；跨 CWD、绝对兼容及非法文件位置分别核对。"""
    directory = tmp_path / "observability"; directory.mkdir()
    other = tmp_path / "other"; other.mkdir(); monkeypatch.chdir(other)
    resolve = lambda value: schema.explicit_observability_database_path(value, observability_directory=directory)
    expected = directory / "data" / "offline.sqlite3"
    assert resolve("data/offline.sqlite3") == resolve(str(expected)) == expected
    for value in ("", " ", "../outside.sqlite3", "data/../../outside.sqlite3", "data/file.txt", "C:relative.sqlite3", str(tmp_path / "outside.sqlite3")):
        with pytest.raises(schema.RuntimeConfigurationError): resolve(value)
    invalid = directory / "data" / "directory.sqlite3"; invalid.mkdir(parents=True)
    with pytest.raises(schema.RuntimeConfigurationError): resolve(str(invalid))
    # Windows junction 不依赖符号链接特权，拒绝指向边界内部的链接，防止 resolve 隐藏它。
    link = directory / "linked"
    if os.name == "nt":
        result = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(directory / "data")], capture_output=True)
        assert result.returncode == 0
    else:
        link.symlink_to(directory / "data", target_is_directory=True)
    try:
        with pytest.raises(schema.RuntimeConfigurationError, match="reparse_path_forbidden"):
            resolve("linked/offline.sqlite3")
    finally:
        if os.name == "nt": os.rmdir(link)
        else: link.unlink()


@pytest.mark.parametrize("text", ["", "OBSERVABILITY_DATABASE_PATH=\n"])
def test_sqlite_missing_value_has_no_default(tmp_path, text):
    """便携相对路径只改变解析基准，缺失字段仍不能静默创建默认数据库。"""
    paths = sources(tmp_path)
    Path(paths["observability"]).write_text(text)
    with pytest.raises(schema.RuntimeConfigurationError, match="explicit_value_required"):
        load_process("worker", str(tmp_path), backend=paths["backend"], observability=paths["observability"])
