"""agent-api：显式配置后调用唯一装配入口。"""
from ezllmtest.bootstrap.app_factory import main, configured_app

if __name__ == "__main__":
    raise SystemExit(main('agent-api'))
else:
    app = configured_app('agent-api')
