"""检查 Redis Lua 未变，以及 adapter 的 fence、幂等与回放契约。"""
import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock
import pytest
from ezllmtest.modules.agent.infrastructure import coordinator as module
from ezllmtest.modules.agent.ports.coordination import AgentRedisSettings, LeaseHandle, LeaseLostError
from ezllmtest.modules.agent.domain.contracts import RunBudget, UsageCounters, _validated_usage

# 对比固定 Redis Lua 契约，防止迁移或说明改动误改原子状态逻辑。
def test_redis_atomic_scripts_unchanged():
    expected=json.loads((Path(__file__).parent/"fixtures/redis-scripts.json").read_text(encoding="utf-8"))
    assert len(expected)>5
    assert {name:getattr(module,name) for name in expected}==expected

# 用人工计数验证预算累计不倒退且有明确上限，不产生真实模型费用。
def test_budget_counters_are_monotonic_and_bounded():
    budget=RunBudget(max_steps=2,max_elapsed_ms=1000,max_input_tokens=10,max_output_tokens=10,max_model_calls=2,max_embedding_calls=2,max_tool_calls=2,max_estimated_cost_units=10)
    previous=UsageCounters(tool_calls=1)
    assert _validated_usage(previous,UsageCounters(tool_calls=2),budget).tool_calls==2
    with pytest.raises(ValueError,match="monotonic"): _validated_usage(previous,UsageCounters(),budget)
    with pytest.raises(ValueError,match="budget exceeded"): _validated_usage(previous,UsageCounters(tool_calls=3),budget)

# 用协调器替身覆盖失租约、幂等冲突、取消和事件游标边界。
def test_fence_conflicts_cancel_and_cursor_contracts():
    # 用 Redis 替身模拟 fencing 冲突、幂等冲突、排他重放游标及取消控制写入，不连接真实 Redis。
    async def exercise():
        redis=AsyncMock()
        settings=AgentRedisSettings(prefix="offline:test")
        service=module.AgentRedisCoordinator(settings,redis=redis)
        redis.eval.return_value=3
        lease=await service.acquire_lease("scope","graph","thread","owner")
        assert lease.fence==3 and lease.value=="owner:3"
        assert service.storage_id("scope","graph","thread")!=service.storage_id("other","graph","thread")
        foreign=LeaseHandle("foreign",lease.storage_id,"owner",3)
        with pytest.raises(LeaseLostError): await service.renew_lease(foreign)
        redis.eval.return_value=[-1]
        with pytest.raises(LeaseLostError):
            await service.reserve_idempotency(lease,idempotency_key="call",operation="unit_menu",persisted=True)
        redis.eval.return_value=[-2]
        with pytest.raises(ValueError,match="conflicts"):
            await service.reserve_idempotency(lease,idempotency_key="call",operation="unit_menu",persisted=True)
        redis.xrange.return_value=[(b"8-0",{b"kind":b"completed",b"data":b'{"saved":true}'})]
        events=await service.replay_events(lease,7)
        assert events[0].sequence==8 and events[0].data=={"saved":True}
        assert redis.xrange.call_args.kwargs["min"]=="(7-0"
        assert redis.xrange.call_args.kwargs["count"]==2000
        await service.put_control("offline:test:cancel","1",ex=30)
        redis.set.assert_awaited_once_with("offline:test:cancel","1",ex=30)
    asyncio.run(exercise())
