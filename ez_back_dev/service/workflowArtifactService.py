"""Compatibility façade for canonical workflow artifact services."""

import sys as _sys
from importlib import import_module as _import_module

_sys.modules[__name__] = _import_module("service.workflow.artifacts")
