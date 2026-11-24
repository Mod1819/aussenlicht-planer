"""WebSocket-API für das Panel (Lesen: angemeldete Benutzer, Ändern: Admins)."""
from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .engine import desired_state, season_window, timeline


@callback
def async_register(hass: HomeAssistant) -> None:
    for handler in (ws_config, ws_save, ws_status, ws_apply_now):
        websocket_api.async_register_command(hass, handler)


def _data(hass: HomeAssistant):
    entries = hass.config_entries.async_loaded_entries(DOMAIN)
    return entries[0].runtime_data if entries else None


def _iso(v):
    return v.isoformat() if v is not None else None


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/config"})
@callback
def ws_config(hass, connection, msg) -> None:
    data = _data(hass)
    if data is None:
        connection.send_error(msg["id"], "not_loaded", "Integration nicht geladen")
        return
    connection.send_result(msg["id"], {"config": data.store.data})


@websocket_api.require_admin
@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/config/save", vol.Required("config"): dict})
@websocket_api.async_response
async def ws_save(hass, connection, msg) -> None:
    data = _data(hass)
    if data is None:
        connection.send_error(msg["id"], "not_loaded", "Integration nicht geladen")
        return
    try:
        cfg = await data.store.async_replace(msg["config"])
    except vol.Invalid as err:
        connection.send_error(msg["id"], "invalid", str(err))
        return
    connection.send_result(msg["id"], {"config": cfg})


def build_status(hass: HomeAssistant, data) -> dict[str, Any]:
    cfg = data.store.data
    runner = data.runner
    now = dt_util.now()
    tz = dt_util.get_default_time_zone()
    sun = runner.sun_for(now.date())
    zones = {}
    for zid, zone in cfg["zones"].items():
        st = desired_state(cfg, zid, now, runner.sun_for, tz)
        win = season_window(cfg, zid, now, runner.sun_for, tz) if st and st["action"] != "off" else None
        zones[zid] = {
            "name": zone["name"],
            "enabled": zone["enabled"],
            "desired": None if st is None else {
                "action": st["action"],
                "brightness_pct": st["brightness_pct"],
                "preset": st["preset"],
                "since": _iso(st["since"]),
            },
            "timeline": [
                {**e, "time": _iso(e["time"])} for e in timeline(zone, now.date(), runner.sun_for, tz)
            ],
            "season": None if win is None else {
                "name": win["name"], "preset": win["preset"],
                "start": _iso(win["start"]), "end": _iso(win["end"]),
            },
        }
    return {
        "now": now.isoformat(),
        "sun": {"sunrise": _iso(sun["sunrise"]), "sunset": _iso(sun["sunset"])},
        "dry_run": cfg["settings"]["dry_run"],
        "zones": zones,
        "log": list(runner.log),
    }


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/status"})
@callback
def ws_status(hass, connection, msg) -> None:
    data = _data(hass)
    if data is None:
        connection.send_error(msg["id"], "not_loaded", "Integration nicht geladen")
        return
    connection.send_result(msg["id"], build_status(hass, data))


@websocket_api.require_admin
@websocket_api.websocket_command(
    {vol.Required("type"): f"{DOMAIN}/apply_now", vol.Optional("zone_id"): str}
)
@websocket_api.async_response
async def ws_apply_now(hass, connection, msg) -> None:
    data = _data(hass)
    if data is None:
        connection.send_error(msg["id"], "not_loaded", "Integration nicht geladen")
        return
    await data.runner.async_apply_now(msg.get("zone_id"))
    connection.send_result(msg["id"], {"ok": True})
