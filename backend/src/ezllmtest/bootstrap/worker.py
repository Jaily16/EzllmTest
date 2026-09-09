"""worker 生命周期装配，队列操作只在显式运行后发生。"""
import argparse
import asyncio
import sys
from ezllmtest.platform import configuration as runtime_values

async def _run(args: argparse.Namespace) -> int:
    """--no-consume 只装配 Redis 连接和独立验收心跳，退出时关闭该连接；普通模式才装配 Agent 服务并消费队列，取消返回 130。"""
    if getattr(args, "no_consume", False):
        from ezllmtest.modules.agent.application.worker_probe import run_probe, validated_probe
        from ezllmtest.modules.agent.infrastructure.worker_probe import RedisWorkerProbe

        probe = None
        try:
            ttl = validated_probe(args.consumer, runtime_values.get("AGENT_WORKER_HEARTBEAT_TTL_SECONDS", "30"))
            probe = RedisWorkerProbe(args.consumer)
            print("worker mode=no-consume", flush=True)
            await run_probe(probe, ttl_seconds=ttl, once=args.once)
            return 0
        except (KeyboardInterrupt, asyncio.CancelledError):
            return 130
        except Exception:
            print("worker mode=no-consume status=unavailable", file=sys.stderr)
            return 1
        finally:
            if probe is not None:
                try:
                    await probe.close()
                except Exception:
                    print("worker mode=no-consume status=close_failed", file=sys.stderr)
                    return 1

    from ezllmtest.bootstrap.agent import build_default_runtime_service
    from ezllmtest.modules.agent.application.worker import AgentCommandWorker
    service = build_default_runtime_service()
    group = runtime_values.get("AGENT_WORKER_GROUP", "ezllm-agent-workers")
    worker = AgentCommandWorker(
        service, group=group, consumer=args.consumer
    )
    try:
        if args.once:
            await worker.run_once()
        else:
            await worker.run_forever()
        return 0
    except (KeyboardInterrupt, asyncio.CancelledError):
        return 130
    except Exception:
        # Do not print tracebacks, Redis URLs, project data, or provider errors.
        print("Agent worker stopped after a safe execution error", file=sys.stderr)
        return 1
    finally:
        await service.coordinator.aclose()
