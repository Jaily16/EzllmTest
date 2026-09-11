"""可选 runner 只装配命令；用假进程检查路径交接与秘密隔离。"""
import runpy
from pathlib import Path
from types import SimpleNamespace
from test_configuration import sources

ROOT=Path(__file__).resolve().parents[2]

# 用人工配置与假进程检查 runner 命令和环境隔离，不启动产品或停止用户进程。
def test_runner_synthetic_config_and_child_commands(tmp_path,monkeypatch):
    namespace=runpy.run_path(str(ROOT/"ops/modular_runtime.py"))
    globals_=namespace["_start"].__globals__
    paths=sources(tmp_path)
    synthetic=tmp_path/"repository"
    for directory in ("backend","observability","frontend/tools","infrastructure/runtime"):
        (synthetic/directory).mkdir(parents=True,exist_ok=True)
    (synthetic/"infrastructure/runtime/modular-runtime-contract.json").write_bytes((ROOT/"infrastructure/runtime/modular-runtime-contract.json").read_bytes())
    (synthetic/"frontend/tools/frontend.mjs").write_text("// synthetic executable placeholder")
    obs=synthetic/"observability/observability.config"
    obs.write_text("OBSERVABILITY_DATABASE_PATH="+str(synthetic/"observability/data/synthetic.sqlite3")+"\nAGENT_TELEMETRY_ENABLED=true\n")
    paths["observability"]=str(obs)
    kwargs={"env_file":None,"backend_env_file":paths["backend"],"frontend_env_file":paths["frontend"],"observability_env_file":paths["observability"]}
    assert namespace["_config_check"](synthetic,**kwargs)["status"]=="ready"
    calls=[]
    monkeypatch.setitem(globals_,"_external_preflight",lambda *a:{"database":{"status":"ok"},"redis":{"status":"ok"}})
    monkeypatch.setitem(globals_,"_ports_available",lambda *a:True)
    monkeypatch.setitem(globals_,"_state_root",lambda *a:tmp_path/"fake-run")
    monkeypatch.setitem(globals_,"_write_state",lambda *a:None)
    monkeypatch.setitem(globals_,"_wait_http",lambda *a,**k:{"status":"ok","http_status":200})
    monkeypatch.setitem(globals_,"_process_identity",lambda pid:{"creation_time":"synthetic","command_line":"offline-command"})
    # 捕获 runner 构造的命令与环境并返回假 PID，测试不创建真实产品子进程。
    def fake_process(command,**options):
        calls.append((command,options["env"]))
        return SimpleNamespace(pid=12345,poll=lambda:None)
    monkeypatch.setattr(globals_["subprocess"],"Popen",fake_process)
    monkeypatch.setenv("DATABASE_URL","inherited-private")
    monkeypatch.setenv("EZLLMTEST_OBSERVABILITY_INGEST_TOKEN","inherited-private")
    result=namespace["_start"](synthetic,None,paths["frontend"],1,backend_env_file=paths["backend"],observability_env_file=paths["observability"])
    assert result["status"]=="ready" and len(calls)==5
    roles=[("observability","frontend"),("backend","frontend"),("backend","frontend","observability"),("backend","observability")]
    for (command,environment),selected in zip(calls,roles):
        assert "--repo-root" in command
        assert all(("--"+role+"-env-file" in command)==(role in selected) for role in ("backend","frontend","observability"))
        assert "DATABASE_URL" not in environment and "EZLLMTEST_OBSERVABILITY_INGEST_TOKEN" not in environment
    assert "tools" in calls[-1][0][1] and "--env-file" in calls[-1][0]
    assert "--no-consume" not in calls[3][0]
    # 固定路径模式展开为原有完整参数，复用同一启动实现与五角色隔离。
    for source, path in paths.items():
        (synthetic/source/".env").write_bytes(Path(path).read_bytes())
    calls.clear()
    monkeypatch.setitem(globals_,"_state_root",lambda *a:tmp_path/"fake-local-run")
    monkeypatch.chdir(tmp_path)
    assert namespace["main"](["--repo-root", str(synthetic), "start", "--local-config"]) == 0
    assert len(calls) == 5 and "--no-consume" not in calls[3][0]
    for (command, environment), selected in zip(calls, roles):
        for source in selected:
            assert command[command.index(f"--{source}-env-file")+1] == str(synthetic/source/".env")
        assert "EZLLMTEST_OBSERVABILITY_INGEST_TOKEN" not in environment


def test_runner_local_config_rejects_mixed_modes_before_io(tmp_path,monkeypatch):
    """快捷模式不能混用新旧配置选择器；帮助和非法组合不探测外部服务。"""
    import pytest
    namespace=runpy.run_path(str(ROOT/"ops/modular_runtime.py"))
    def forbidden(*a, **k): pytest.fail("invalid selectors reached external preflight")
    monkeypatch.setitem(namespace["main"].__globals__, "_external_preflight", forbidden)
    for command in ("config-check", "preflight", "start"):
        for flag, value in (("--env-file","unused"),("--backend-env-file","unused"),("--frontend-env-file","unused"),("--observability-env-file","unused"),("--model-env-file","unused"),("--moonshot-model","kimi-k3"),("--frontend-port","8180")):
            assert namespace["main"](["--repo-root",str(tmp_path),command,"--local-config",flag,value]) == 2
        assert namespace["main"](["--repo-root",str(tmp_path),command,"--local-config"]) == 2
        with pytest.raises(SystemExit) as caught:
            namespace["main"]([command,"--help"])
        assert caught.value.code == 0
    for root_value in ("relative", str(tmp_path/"missing")):
        assert namespace["main"](["--repo-root",root_value,"preflight","--local-config"]) == 2
