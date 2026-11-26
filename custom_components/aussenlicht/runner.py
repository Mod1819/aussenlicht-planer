"""Ausführung in Home Assistant: Takt, Schalten, WLED-Presets, Protokoll, Benachrichtigung."""
from __future__ import annotations

import asyncio
import logging
from collections import deque
from datetime import date, datetime, timedelta
from typing import Any

from homeassistant.const import EVENT_HOMEASSISTANT_STARTED, STATE_UNAVAILABLE
from homeassistant.core import CoreState, HomeAssistant, callback
from homeassistant.helpers.event import async_call_later, async_track_time_interval
from homeassistant.helpers.storage import Store
from homeassistant.helpers.sun import get_astral_event_date
from homeassistant.util import dt as dt_util

from .const import DOMAIN, LOG_SIZE, STARTUP_DELAY_S, TICK_SECONDS, WLED_RETRIES, WLED_VERIFY_S
from .engine import desired_state, describe
from .store import ConfigStore

_LOGGER = logging.getLogger(__name__)


class Runner:
    def __init__(self, hass: HomeAssistant, store: ConfigStore) -> None:
        self.hass = hass
        self.store = store
        self.last: dict[str, tuple] = {}
        self.log: deque[dict[str, Any]] = deque(maxlen=LOG_SIZE)
        self._unsubs: list = []
        self._locks: dict[str, asyncio.Lock] = {}
        self._sun_cache: dict[date, dict[str, datetime | None]] = {}
        self._ready = False
        self._failing: dict[str, str] = {}
        self._forced: set[str] = set()
        self._log_store = Store(hass, 1, f"{DOMAIN}.log")

    async def async_load(self) -> None:
        """Protokoll vom letzten Lauf laden (überlebt Neustarts)."""
        try:
            data = await self._log_store.async_load()
        except Exception:  # noqa: BLE001
            data = None
        if isinstance(data, list):
            self.log.extend(e for e in data[:LOG_SIZE] if isinstance(e, dict))

    async def async_flush(self) -> None:
        await self._log_store.async_save(list(self.log))

    def _in_sync(self, zone: dict, st: dict) -> bool:
        """Entspricht der tatsächliche Gerätezustand bereits dem Sollzustand?"""
        for ent in zone["entities"]:
            s = self.hass.states.get(ent)
            if s is None or s.state in (STATE_UNAVAILABLE, "unknown"):
                return False
            if st["action"] == "off":
                if s.state != "off":
                    return False
                continue
            if s.state != "on":
                return False
            if st["action"] == "dim" and ent.startswith("light."):
                bri = s.attributes.get("brightness")
                if bri is None or abs(round(bri / 2.55) - st["brightness_pct"]) > 2:
                    return False
        if st["preset"] and zone["wled_presets"]:
            exact = 0
            for sel in zone["wled_presets"]:
                s = self.hass.states.get(sel)
                if s is None or s.state == STATE_UNAVAILABLE:
                    return False
                opt = self._match_option(s.attributes.get("options") or [], st["preset"])
                if s.state == opt:
                    exact += 1
                elif s.state != "unknown":  # unknown = per WLED-Sync gesteuert
                    return False
            if not exact:
                return False
        return True

    # ---------- Lebenszyklus ----------
    @callback
    def async_start(self) -> None:
        if self.hass.state is CoreState.running:
            self._unsubs.append(async_call_later(self.hass, STARTUP_DELAY_S, self._begin))
        else:
            @callback
            def _started(_event) -> None:
                self._unsubs.append(async_call_later(self.hass, STARTUP_DELAY_S, self._begin))
            self._unsubs.append(self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, _started))
        self._unsubs.append(self.store.async_add_listener(lambda _cfg: self._schedule_tick()))

    @callback
    def _begin(self, _now=None) -> None:
        self._ready = True
        self._unsubs.append(
            async_track_time_interval(self.hass, self._interval, timedelta(seconds=TICK_SECONDS))
        )
        self._add_log(None, "Planer gestartet – Sollzustand wird hergestellt", ok=True)
        self._schedule_tick()

    @callback
    def async_stop(self) -> None:
        for unsub in self._unsubs:
            try:
                unsub()
            except Exception:  # noqa: BLE001
                pass
        self._unsubs.clear()

    @callback
    def _interval(self, _now) -> None:
        self._schedule_tick()

    @callback
    def _schedule_tick(self) -> None:
        if self._ready:
            self.hass.async_create_task(self.async_tick(), eager_start=False)

    # ---------- Sonne ----------
    def sun_for(self, day: date) -> dict[str, datetime | None]:
        if day not in self._sun_cache:
            if len(self._sun_cache) > 10:
                self._sun_cache.clear()
            self._sun_cache[day] = {
                "sunrise": get_astral_event_date(self.hass, "sunrise", day),
                "sunset": get_astral_event_date(self.hass, "sunset", day),
            }
        return self._sun_cache[day]

    # ---------- Kern ----------
    async def async_tick(self) -> None:
        cfg = self.store.data
        now = dt_util.now()
        tz = dt_util.get_default_time_zone()
        for zid in list(self.last):
            if zid not in cfg["zones"] or not cfg["zones"][zid]["enabled"]:
                self.last.pop(zid, None)
        for zid, zone in cfg["zones"].items():
            if not zone["enabled"]:
                continue
            st = desired_state(cfg, zid, now, self.sun_for, tz)
            if st is None:
                continue
            key = (st["action"], st["brightness_pct"], st["preset"])
            prev = self.last.get(zid)
            if key == prev:
                continue
            forced = zid in self._forced
            self._forced.discard(zid)
            # Nach einem (Neu-)Start: stimmt der Gerätezustand schon, nichts schalten und nichts melden.
            if prev is None and not forced and self._in_sync(zone, st):
                self.last[zid] = key
                self._add_log(zone["name"], f"Neustart: bereits korrekt ({describe(st)})", ok=True,
                              dry=cfg["settings"]["dry_run"])
                continue
            self.last[zid] = key
            self.hass.async_create_task(self._apply(zid, zone, cfg["settings"], st, prev), eager_start=False)

    async def async_apply_now(self, zone_id: str | None = None) -> None:
        if zone_id:
            self.last.pop(zone_id, None)
            self._forced.add(zone_id)
        else:
            self.last.clear()
            self._forced.update(self.store.data["zones"])
        self._ready = True
        await self.async_tick()

    async def _apply(self, zid: str, zone: dict, settings: dict, st: dict, prev: tuple | None) -> None:
        lock = self._locks.setdefault(zid, asyncio.Lock())
        async with lock:
            dry = settings["dry_run"]
            name = zone["name"]
            power_changed = prev is None or prev[:2] != (st["action"], st["brightness_pct"])
            errors: list[str] = []
            if power_changed:
                for ent in zone["entities"]:
                    err = await self._switch(ent, st, dry)
                    if err:
                        errors.append(err)
            preset = st["preset"]
            if preset and (prev is None or power_changed or prev[2] != preset):
                was_off = prev is None or prev[0] == "off"
                if was_off and not dry and settings["wled_delay_s"]:
                    await asyncio.sleep(settings["wled_delay_s"])
                for sel in zone["wled_presets"]:
                    err = await self._preset(sel, preset, dry)
                    if err:
                        errors.append(err)
            text = describe(st)
            if errors:
                text += " – FEHLER: " + "; ".join(errors)
                # beim nächsten Takt erneut versuchen
                if self.last.get(zid) == (st["action"], st["brightness_pct"], st["preset"]):
                    self.last.pop(zid, None)
            # Wiederholte gleiche Fehler (Retry alle 30 s) nur einmal melden.
            if errors and self._failing.get(zid) == text:
                return
            if errors:
                self._failing[zid] = text
            else:
                self._failing.pop(zid, None)
            self._add_log(name, text, ok=not errors, dry=dry)
            await self._notify(settings, f"{'[Test] ' if dry else ''}{name}: {text}", error=bool(errors))

    async def _switch(self, entity_id: str, st: dict, dry: bool) -> str | None:
        domain = entity_id.split(".", 1)[0]
        state = self.hass.states.get(entity_id)
        if state is None or state.state == STATE_UNAVAILABLE:
            return f"{entity_id} nicht verfügbar"
        service = "turn_off" if st["action"] == "off" else "turn_on"
        data: dict[str, Any] = {"entity_id": entity_id}
        if st["action"] == "dim" and domain == "light":
            data["brightness_pct"] = st["brightness_pct"]
        if dry:
            return None
        try:
            await self.hass.services.async_call(domain, service, data, blocking=True)
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("Schalten %s fehlgeschlagen: %s", entity_id, err)
            return f"{entity_id}: {err}"
        return None

    @staticmethod
    def _match_option(options: list[str], wanted: str) -> str | None:
        if wanted in options:
            return wanted
        for opt in options:
            if opt.strip().casefold() == wanted.strip().casefold():
                return opt
        return None

    async def _preset(self, entity_id: str, preset: str, dry: bool) -> str | None:
        for attempt in range(WLED_RETRIES):
            state = self.hass.states.get(entity_id)
            # "unknown" ist normal (z. B. WLED per Sync gesteuert -> kein aktives Preset)
            if state is None or state.state == STATE_UNAVAILABLE:
                if dry:
                    return None
                await asyncio.sleep(WLED_VERIFY_S)
                continue
            option = self._match_option(state.attributes.get("options") or [], preset)
            if option is None:
                return f"{entity_id}: Preset „{preset.strip()}“ unbekannt"
            if dry or state.state == option:
                return None
            try:
                await self.hass.services.async_call(
                    "select", "select_option", {"entity_id": entity_id, "option": option}, blocking=True
                )
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug("Preset %s Versuch %d: %s", entity_id, attempt + 1, err)
            await asyncio.sleep(WLED_VERIFY_S)
            state = self.hass.states.get(entity_id)
            if state is not None and state.state == option:
                return None
        return f"{entity_id}: Preset „{preset.strip()}“ nicht übernommen"

    # ---------- Protokoll / Benachrichtigung ----------
    def _add_log(self, zone: str | None, text: str, *, ok: bool, dry: bool = False) -> None:
        self.log.appendleft(
            {"time": dt_util.now().isoformat(), "zone": zone or "System", "text": text, "dry_run": dry, "ok": ok}
        )
        (_LOGGER.info if ok else _LOGGER.warning)("%s: %s", zone or "System", text)
        self._log_store.async_delay_save(lambda: list(self.log), 5)

    async def _notify(self, settings: dict, message: str, *, error: bool) -> None:
        level, svc = settings["notify_level"], settings["notify_service"]
        if not svc or level == "off" or (level == "errors" and not error) or "." not in svc:
            return
        domain, service = svc.split(".", 1)
        if not self.hass.services.has_service(domain, service):
            _LOGGER.warning("Benachrichtigungsdienst %s existiert nicht", svc)
            return
        try:
            await self.hass.services.async_call(domain, service, {"message": message}, blocking=False)
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("Benachrichtigung fehlgeschlagen: %s", err)
