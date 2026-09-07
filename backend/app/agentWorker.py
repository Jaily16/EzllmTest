"""Module entry point: ``python -m app.agentWorker``."""

from service.agent.worker import main


if __name__ == "__main__":
    raise SystemExit(main())
