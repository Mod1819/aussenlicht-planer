"""Persistente Speicherung über den HA-Storage-Helper (.storage/aussenlicht.config)."""
from __future__ import annotations

import asyncio
import copy
import logging
from collections.abc import Callable
from typing import Any

import voluptuous as vol
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.storage import Store

from .const import SAVE_DELAY, STORAGE_KEY, STORAGE_VERSION
from .models import default_config, validate_config

_LOGGER = logging.getLogger(__name__)

Listener = Callable[[dict[str, Any]], None]


class ConfigStore:
    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self._store = Store(hass, STORAGE_VERSION, STORAGE_KEY, atomic_writes=True)
        self._data: dict[str, Any] = default_config()
        self._listeners: list[Listener] = []
        self._lock = asyncio.Lock()

    async def async_load(self) -> None:
        raw = await self._store.async_load()
        if raw is None:
            self._data = default_config()
            return
        try:
            self._data = validate_config(raw)
        except vol.Invalid as err:
            _LOGGER.error("Gespeicherte Konfiguration ungültig (%s) – Original gesichert", err)
            await Store(self.hass, STORAGE_VERSION, f"{STORAGE_KEY}.invalid_backup").async_save(raw)
            self._data = default_config()

    @property
    def data(self) -> dict[str, Any]:
        return copy.deepcopy(self._data)

    async def async_replace(self, new_data: dict[str, Any]) -> dict[str, Any]:
        async with self._lock:
            validated = validate_config(new_data)
            if validated == self._data:
                return self.data
            self._data = validated
            self._store.async_delay_save(lambda: self._data, SAVE_DELAY)
        for listener in list(self._listeners):
            try:
                listener(self.data)
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Fehler in Konfigurations-Listener")
        return self.data

    async def async_flush(self) -> None:
        await self._store.async_save(self._data)

    async def async_remove(self) -> None:
        await self._store.async_remove()

    @callback
    def async_add_listener(self, listener: Listener) -> Callable[[], None]:
        self._listeners.append(listener)

        @callback
        def remove() -> None:
            if listener in self._listeners:
                self._listeners.remove(listener)

        return remove
