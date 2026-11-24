"""Außenlicht-Planer – zentrale Zeitsteuerung der Außenbeleuchtung."""
from __future__ import annotations

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from . import panel, websocket
from .const import DOMAIN
from .runner import Runner
from .store import ConfigStore

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


@dataclass
class AussenlichtData:
    store: ConfigStore
    runner: Runner


type AussenlichtConfigEntry = ConfigEntry[AussenlichtData]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    websocket.async_register(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: AussenlichtConfigEntry) -> bool:
    store = ConfigStore(hass)
    await store.async_load()
    runner = Runner(hass, store)
    entry.runtime_data = AussenlichtData(store=store, runner=runner)
    runner.async_start()
    await panel.async_register_panel(hass)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: AussenlichtConfigEntry) -> bool:
    panel.async_remove_panel(hass)
    entry.runtime_data.runner.async_stop()
    await entry.runtime_data.store.async_flush()
    return True


async def async_remove_entry(hass: HomeAssistant, entry: AussenlichtConfigEntry) -> None:
    await ConfigStore(hass).async_remove()
