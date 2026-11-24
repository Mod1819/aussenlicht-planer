"""Seitenleisten-Panel „Außenlicht“ (Web-Component ohne Build-Schritt)."""
from __future__ import annotations

import json
import logging
from pathlib import Path

from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

PANEL_URL_PATH = "aussenlicht"
STATIC_URL = f"/{DOMAIN}_static"
WEBCOMPONENT = "aussenlicht-panel"
_STATIC_FLAG = f"{DOMAIN}_static_registered"


def _version() -> str:
    return json.loads((Path(__file__).parent / "manifest.json").read_text(encoding="utf-8"))["version"]


async def async_register_panel(hass: HomeAssistant) -> None:
    if not hass.data.get(_STATIC_FLAG):
        await hass.http.async_register_static_paths(
            [StaticPathConfig(STATIC_URL, str(Path(__file__).parent / "www"), cache_headers=False)]
        )
        hass.data[_STATIC_FLAG] = True
    if "frontend" not in hass.config.components:
        _LOGGER.warning("Frontend nicht geladen – Panel wird nicht angezeigt")
        return
    from homeassistant.components import panel_custom

    version = await hass.async_add_executor_job(_version)
    await panel_custom.async_register_panel(
        hass,
        frontend_url_path=PANEL_URL_PATH,
        webcomponent_name=WEBCOMPONENT,
        sidebar_title="Außenlicht",
        sidebar_icon="mdi:outdoor-lamp",
        module_url=f"{STATIC_URL}/{WEBCOMPONENT}.js?v={version}",
        require_admin=True,
        config={},
    )


def async_remove_panel(hass: HomeAssistant) -> None:
    if "frontend" not in hass.config.components:
        return
    from homeassistant.components import frontend

    frontend.async_remove_panel(hass, PANEL_URL_PATH, warn_if_unknown=False)
