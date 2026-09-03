"""Compatibility façade for the canonical project repository."""

import sys as _sys
from importlib import import_module as _import_module

_sys.modules[__name__] = _import_module("infrastructure.persistence.project_repository")
