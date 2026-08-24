#!/usr/bin/env python3
"""Measure a production frontend build without third-party dependencies."""

from __future__ import annotations

import argparse
import gzip
import json
import re
from pathlib import Path
from urllib.parse import urlsplit


MAX_LOGO_BYTES = 96 * 1024
MAX_INITIAL_JS_BYTES = 900 * 1024
MAX_INITIAL_JS_GZIP_BYTES = 285 * 1024
MAX_INITIAL_CSS_BYTES = 220 * 1024
MAX_INITIAL_CSS_GZIP_BYTES = 34 * 1024
MAX_INITIAL_TOTAL_BYTES = int(1.20 * 1024 * 1024)
MAX_BUILD_BYTES = 3 * 1024 * 1024

ASSET_REFERENCE = re.compile(r"(?:src|href)=[\"']([^\"']+)[\"']", re.IGNORECASE)


def gzip_size(path: Path) -> int:
    return len(gzip.compress(path.read_bytes(), compresslevel=9, mtime=0))


def referenced_assets(build_dir: Path) -> list[Path]:
    index = build_dir / "index.html"
    if not index.is_file():
        raise ValueError(f"缺少构建入口：{index}")

    assets: list[Path] = []
    for reference in ASSET_REFERENCE.findall(index.read_text(encoding="utf-8")):
        parsed = urlsplit(reference)
        if parsed.scheme or parsed.netloc or not parsed.path:
            continue
        relative = parsed.path.lstrip("/")
        candidate = (build_dir / relative).resolve()
        try:
            candidate.relative_to(build_dir.resolve())
        except ValueError as exc:
            raise ValueError(f"入口引用越出构建目录：{reference}") from exc
        if candidate.is_file() and candidate not in assets:
            assets.append(candidate)
    return assets


def measure_bundle(build_dir: Path) -> dict[str, int]:
    root = build_dir.resolve()
    if not root.is_dir():
        raise ValueError(f"构建目录不存在：{root}")

    all_files = [path for path in root.rglob("*") if path.is_file()]
    initial = referenced_assets(root)
    initial_js = [path for path in initial if path.suffix.lower() == ".js"]
    initial_css = [path for path in initial if path.suffix.lower() == ".css"]
    logos = [path for path in all_files if path.name.startswith("ezlogo-workbench") and path.suffix.lower() == ".png"]

    return {
        "source_map_count": sum(path.suffix.lower() == ".map" for path in all_files),
        "logo_bytes": max((path.stat().st_size for path in logos), default=0),
        "largest_initial_js_bytes": max((path.stat().st_size for path in initial_js), default=0),
        "largest_initial_js_gzip_bytes": max((gzip_size(path) for path in initial_js), default=0),
        "initial_css_bytes": sum(path.stat().st_size for path in initial_css),
        "initial_css_gzip_bytes": sum(gzip_size(path) for path in initial_css),
        "initial_total_bytes": sum(path.stat().st_size for path in initial),
        "build_bytes": sum(path.stat().st_size for path in all_files),
        "file_count": len(all_files),
    }


def budget_failures(metrics: dict[str, int]) -> list[str]:
    checks = (
        ("source_map_count", 0, "source map 数量"),
        ("logo_bytes", MAX_LOGO_BYTES, "工作台 Logo"),
        ("largest_initial_js_bytes", MAX_INITIAL_JS_BYTES, "最大初始 JS"),
        ("largest_initial_js_gzip_bytes", MAX_INITIAL_JS_GZIP_BYTES, "最大初始 JS gzip"),
        ("initial_css_bytes", MAX_INITIAL_CSS_BYTES, "初始 CSS"),
        ("initial_css_gzip_bytes", MAX_INITIAL_CSS_GZIP_BYTES, "初始 CSS gzip"),
        ("initial_total_bytes", MAX_INITIAL_TOTAL_BYTES, "初始资产合计"),
        ("build_bytes", MAX_BUILD_BYTES, "完整构建"),
    )
    failures: list[str] = []
    for key, maximum, label in checks:
        value = metrics[key]
        if value > maximum:
            failures.append(f"{label} 超出预算：{value} > {maximum}")
    if metrics["logo_bytes"] == 0:
        failures.append("构建中未找到 ezlogo-workbench PNG")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description="检查 EzllmTest 前端构建体积预算")
    parser.add_argument("build_dir", type=Path)
    args = parser.parse_args()

    try:
        metrics = measure_bundle(args.build_dir)
        failures = budget_failures(metrics)
    except ValueError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 2

    print(json.dumps({"ok": not failures, "metrics": metrics, "failures": failures}, ensure_ascii=False, indent=2))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
