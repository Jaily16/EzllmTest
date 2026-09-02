# Iteration 4 Local Compose Stack

This stack runs the Vite frontend, legacy API, Agent API, worker, MySQL, Redis,
OpenTelemetry Collector, Prometheus, Tempo, and Grafana. It is intended for
loopback development and acceptance testing, not public deployment.

## Prepare local settings

Copy `ops/compose/.env.example` to an ignored file such as
`ops/compose/.env.local`, replace every placeholder with a local-only value,
and keep that file out of Git. Compose commands must always name the env file;
the root `.env` is never loaded implicitly.

The example publishes only these host endpoints:

- frontend: `http://127.0.0.1:8080`
- legacy API: `http://127.0.0.1:8130`
- Agent API: `http://127.0.0.1:8131`
- Grafana: `http://127.0.0.1:3000`
- Prometheus: `http://127.0.0.1:9090`

MySQL, Redis, Collector, and Tempo have no host port. Agent API host validation
still rejects non-loopback browser Host headers.

## Validate and run

From the repository root:

```powershell
docker compose --env-file ops/compose/.env.local config --quiet
docker compose --env-file ops/compose/.env.local -p ezllm-local up --build -d --wait
docker compose --env-file ops/compose/.env.local -p ezllm-local ps
```

Open Grafana with the credentials in the local env file. The provisioned data
sources are `Prometheus` and `Tempo`; the provisioned dashboard is **EzLLM
Agent Overview**. A valid workbench Trace ID can be pasted into Grafana Explore.

Telemetry is enabled only inside the Compose application services. The Agent
health response reports `instrumented` when the SDK records spans; use Tempo
or Collector/Prometheus health to determine whether export and persistence are
also working.

## Stop without deleting user data

```powershell
docker compose --env-file ops/compose/.env.local -p ezllm-local down
```

This preserves the named MySQL, project-file, Prometheus, Tempo, and Grafana
volumes. Do not add `-v` for an ordinary local stack unless deletion of those
exact named volumes is explicitly intended and separately confirmed.

The automated validation flow uses a unique project name and placeholder-only
env file. Only that verified disposable project is torn down with `down -v`.
It never targets a user's normal Compose project or Redis container.

## Safety boundaries

- Do not publish this topology on `0.0.0.0` without a separate security design.
- Do not add OTLP headers or a remote exporter endpoint through local settings.
- Do not enable Collector debug export or content-bearing GenAI attributes.
- Do not bind-mount a real project directory into the validation stack.
- Do not treat container stdout JSON logs as a stable OTel Logs or Loki API.
- Do not use a real provider key for smoke tests, Eval, or benchmarks.
