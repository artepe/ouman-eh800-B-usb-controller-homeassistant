"""Fixtures for Home Assistant level OpenLVI tests.

Uses pytest-homeassistant-custom-component. No network or hardware: every
transport is replaced by an in-memory fake.
"""
from pathlib import Path
import sys

import pytest

# Claim the top-level "custom_components" name for this repository before
# Home Assistant mounts the plugin's own testing config directory.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import custom_components  # noqa: E402,F401

pytest_plugins = "pytest_homeassistant_custom_component"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Let Home Assistant load custom_components/openlvi in every test."""
    yield
