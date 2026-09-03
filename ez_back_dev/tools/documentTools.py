"""Compatibility façade for canonical project document helpers."""

import sys as _sys
from importlib import import_module as _import_module

_sys.modules[__name__] = _import_module("service.project.documents")
