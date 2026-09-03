import pytest
from pydantic import ValidationError

from model.ChainJsonModel import QualifiedUnitTestMenu, UnitTestMenu
from service.unitReferenceService import encode_unit_menu, parse_unit_reference


def _menu_with_same_named_functions():
    return QualifiedUnitTestMenu.model_validate(
        {
            "subsystem_menu": {"subsystem_test": False, "subsystem_list": []},
            "module_menu": {"module_test": False, "module_list": []},
            "class_menu": {"class_test": False, "class_list": []},
            "function_menu": {
                "function_test": True,
                "function_list": [
                    {
                        "display_name": "create方法",
                        "qualified_name": "order.OrderService.create(request)",
                        "source_hint": "订单模块/OrderService",
                    },
                    {
                        "display_name": "create方法",
                        "qualified_name": "invoice.InvoiceService.create(request)",
                        "source_hint": "发票模块/InvoiceService",
                    },
                ],
            },
        }
    )


def test_qualified_same_named_functions_keep_distinct_stable_values():
    encoded = encode_unit_menu(_menu_with_same_named_functions())

    values = encoded.function_menu.function_list
    assert len(values) == 2
    assert values[0] != values[1]
    assert "order.OrderService.create(request)" in values[0]
    assert "invoice.InvoiceService.create(request)" in values[1]

    first = parse_unit_reference(values[0], "函数单元测试")
    assert first.display_name == "create方法"
    assert first.qualified_name == "order.OrderService.create(request)"
    assert first.source_hint == "订单模块/OrderService"
    assert first.retrieval_query.startswith("函数单元测试 create方法")


def test_encoding_deduplicates_exact_references_but_accepts_legacy_strings():
    raw = _menu_with_same_named_functions().model_dump()
    raw["function_menu"]["function_list"].append(
        raw["function_menu"]["function_list"][0]
    )

    encoded = encode_unit_menu(QualifiedUnitTestMenu.model_validate(raw))
    assert len(encoded.function_menu.function_list) == 2

    legacy_value = {
        "subsystem_menu": {"subsystem_test": False, "subsystem_list": []},
        "module_menu": {"module_test": False, "module_list": []},
        "class_menu": {
            "class_test": True,
            "class_list": ["LegacyService类", "LegacyService类"],
        },
        "function_menu": {"function_test": False, "function_list": []},
    }
    with pytest.raises(ValidationError):
        QualifiedUnitTestMenu.model_validate(legacy_value)
    legacy_menu = UnitTestMenu.model_validate(legacy_value)
    legacy_encoded = encode_unit_menu(legacy_menu)

    assert legacy_encoded.class_menu.class_list == ["LegacyService类"]
    legacy = parse_unit_reference("LegacyService类", "类单元测试")
    assert legacy.display_name == "LegacyService类"
    assert legacy.qualified_name == "LegacyService类"
    assert legacy.source_hint == ""
