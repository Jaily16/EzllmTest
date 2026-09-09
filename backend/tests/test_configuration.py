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
