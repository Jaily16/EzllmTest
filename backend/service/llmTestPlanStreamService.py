"""Compatibility façade for canonical streamed test plans."""

import sys as _sys
from importlib import import_module as _import_module

_sys.modules[__name__] = _import_module("service.workflow.test_plan_stream")
