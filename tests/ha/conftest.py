"""Fixtures for Home Assistant integration tests.

Requires pytest-homeassistant-custom-component (HA test venv). These tests are
skipped automatically when Home Assistant is not installed.
"""

from __future__ import annotations

import pytest

pytest.importorskip("pytest_homeassistant_custom_component")


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Load custom integrations for every test in this package."""
    yield
