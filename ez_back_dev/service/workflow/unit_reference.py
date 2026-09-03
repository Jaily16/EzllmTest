"""Canonical, backward-compatible references for selectable test units."""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import ValidationError

from model.ChainJsonModel import (
    QualifiedUnitReference,
    QualifiedUnitTestMenu,
    UnitTestMenu,
)


UNIT_REFERENCE_SEPARATOR = " ｜ "


def _clean_part(value: str) -> str:
    return " ".join(value.replace(UNIT_REFERENCE_SEPARATOR.strip(), "/").split())


def _encode_reference(value: QualifiedUnitReference) -> str:
    display_name = _clean_part(value.display_name)
    qualified_name = _clean_part(value.qualified_name) or display_name
    source_hint = _clean_part(value.source_hint)
    parts = [display_name, qualified_name]
    if source_hint:
        parts.append(source_hint)
    return UNIT_REFERENCE_SEPARATOR.join(parts)


def _unique_references(values: list[QualifiedUnitReference]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        encoded = _encode_reference(value)
        if not encoded or encoded in seen:
            continue
        seen.add(encoded)
        result.append(encoded)
    return result


def _unique_legacy_values(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value.strip() for value in values if value.strip()))


def _normalize_legacy_menu(menu: UnitTestMenu) -> UnitTestMenu:
    value = menu.model_dump()
    for section_name, list_name in (
        ("subsystem_menu", "subsystem_list"),
        ("module_menu", "module_list"),
        ("class_menu", "class_list"),
        ("function_menu", "function_list"),
    ):
        value[section_name][list_name] = _unique_legacy_values(
            value[section_name][list_name]
        )
    return UnitTestMenu.model_validate(value)


def encode_unit_menu(
    menu: QualifiedUnitTestMenu | UnitTestMenu | dict,
) -> UnitTestMenu:
    if isinstance(menu, UnitTestMenu):
        return _normalize_legacy_menu(menu)
    if isinstance(menu, QualifiedUnitTestMenu):
        qualified = menu
    else:
        try:
            qualified = QualifiedUnitTestMenu.model_validate(menu)
        except ValidationError:
            return _normalize_legacy_menu(UnitTestMenu.model_validate(menu))
    return UnitTestMenu.model_validate(
        {
            "subsystem_menu": {
                "subsystem_test": qualified.subsystem_menu.subsystem_test,
                "subsystem_list": _unique_references(
                    qualified.subsystem_menu.subsystem_list
                ),
            },
            "module_menu": {
                "module_test": qualified.module_menu.module_test,
                "module_list": _unique_references(
                    qualified.module_menu.module_list
                ),
            },
            "class_menu": {
                "class_test": qualified.class_menu.class_test,
                "class_list": _unique_references(
                    qualified.class_menu.class_list
                ),
            },
            "function_menu": {
                "function_test": qualified.function_menu.function_test,
                "function_list": _unique_references(
                    qualified.function_menu.function_list
                ),
            },
        }
    )


@dataclass(frozen=True)
class UnitReferenceTarget:
    canonical_value: str
    unit_type: str
    display_name: str
    qualified_name: str
    source_hint: str

    @property
    def retrieval_query(self) -> str:
        values: list[str] = []
        for value in (
            self.unit_type,
            self.display_name,
            self.qualified_name,
            self.source_hint,
        ):
            if value and value not in values:
                values.append(value)
        return " ".join(values)

    @property
    def prompt_label(self) -> str:
        details = [self.unit_type] if self.unit_type else []
        if self.qualified_name != self.display_name:
            details.append(self.qualified_name)
        if self.source_hint:
            details.append(f"来源：{self.source_hint}")
        return (
            f"{self.display_name}（{'；'.join(details)}）"
            if details
            else self.display_name
        )


def parse_unit_reference(value: str, unit_type: str = "") -> UnitReferenceTarget:
    canonical = value.strip()
    parts = [part.strip() for part in canonical.split(UNIT_REFERENCE_SEPARATOR)]
    display_name = parts[0] if parts and parts[0] else canonical
    qualified_name = parts[1] if len(parts) > 1 and parts[1] else display_name
    source_hint = parts[2] if len(parts) > 2 else ""
    return UnitReferenceTarget(
        canonical_value=canonical,
        unit_type=unit_type.strip(),
        display_name=display_name,
        qualified_name=qualified_name,
        source_hint=source_hint,
    )
