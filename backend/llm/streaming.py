"""Compatibility façade for the canonical LLM stream adapter."""

import sys as _sys
from importlib import import_module as _import_module

_sys.modules[__name__] = _import_module("infrastructure.llm.stream")
