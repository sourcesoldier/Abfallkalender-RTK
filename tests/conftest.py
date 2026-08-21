"""Test bootstrap.

Exposes the integration's HA-free modules (parser, url, const) under the
lightweight package alias `ackrtk`, bypassing the package __init__ which imports
Home Assistant. This keeps the pure-logic tests runnable without a HA install.
"""

from __future__ import annotations

import pathlib
import sys
import types

_PKG_DIR = (
    pathlib.Path(__file__).parent.parent
    / "custom_components"
    / "abfallkalender_rtk"
)

if "ackrtk" not in sys.modules:
    alias = types.ModuleType("ackrtk")
    alias.__path__ = [str(_PKG_DIR)]
    sys.modules["ackrtk"] = alias
