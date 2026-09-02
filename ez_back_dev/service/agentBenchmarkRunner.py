"""Compatibility façade for canonical benchmark runner."""

import sys as _sys
from importlib import import_module as _import_module

_sys.modules[__name__] = _import_module("service.evaluation.benchmark_runner")
