"""Compatibility façade for canonical LLM selection helpers."""

import sys as _sys
from importlib import import_module as _import_module

_sys.modules[__name__] = _import_module("infrastructure.llm.selection")
