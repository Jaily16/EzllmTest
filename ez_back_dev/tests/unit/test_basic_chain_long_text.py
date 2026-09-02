from chain import BasicChain as basic_chain_module


def test_partition_summaries_preserves_order_without_dropping_text(monkeypatch):
    monkeypatch.setattr(
        basic_chain_module.documentTools,
        "num_tokens_from_string",
        len,
    )

    summaries = ["a" * 6, "b" * 6, "c" * 3]
    batches = basic_chain_module._partition_summaries_within_budget(
        summaries,
        max_tokens=10,
    )

    assert batches == [["a" * 6], ["b" * 6, "c" * 3]]
    assert [item for batch in batches for item in batch] == summaries


def test_partition_summaries_rejects_one_oversized_summary(monkeypatch):
    monkeypatch.setattr(
        basic_chain_module.documentTools,
        "num_tokens_from_string",
        len,
    )

    try:
        basic_chain_module._partition_summaries_within_budget(
            ["x" * 11],
            max_tokens=10,
        )
    except ValueError as exc:
        assert str(exc) == "one map summary exceeds the reduce context budget"
    else:
        raise AssertionError("expected oversized summaries to fail explicitly")
