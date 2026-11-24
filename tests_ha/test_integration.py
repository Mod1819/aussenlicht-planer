from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_mock_service

from custom_components.aussenlicht.const import DOMAIN

TZ = ZoneInfo("Europe/Berlin")

CONFIG = {
    "zones": {
        "gaube": {
            "name": "Gaube",
            "entities": ["switch.gaube"],
            "wled_presets": ["select.w4", "select.w5"],
            "default_preset": "Gaube1",
            "steps": [
                {"id": "abend", "anchor": "sunset", "offset_min": 0, "action": "on"},
                {"id": "aus", "anchor": "sunrise", "offset_min": 0, "action": "off"},
            ],
        },
        "einfahrt": {
            "name": "Einfahrt",
            "entities": ["light.einfahrt"],
            "steps": [
                {"id": "a", "anchor": "sunset", "offset_min": -120, "action": "dim", "brightness_pct": 20},
                {"id": "d", "anchor": "sunset", "offset_min": 0, "action": "off"},
            ],
        },
    },
    "seasons": {
        "xmas": {"name": "Weihnachten", "zone_id": "gaube", "start": "12-01", "end": "01-06",
                 "preset": "Weihnachten", "duration_min": 120, "steps": ["abend"]},
    },
    "settings": {"dry_run": False, "notify_service": "notify.test", "notify_level": "all", "wled_delay_s": 0},
}


@pytest.fixture
async def setup(hass: HomeAssistant, hass_ws_client):
    await hass.config.async_update(time_zone="Europe/Berlin", latitude=51.48, longitude=7.21)
    hass.states.async_set("switch.gaube", "off")
    hass.states.async_set("light.einfahrt", "off")
    for e in ("select.w4", "select.w5"):
        hass.states.async_set(e, "Gaube1", {"options": ["Gaube1", "Weihnachten "]})
    calls = {
        "sw_on": async_mock_service(hass, "switch", "turn_on"),
        "sw_off": async_mock_service(hass, "switch", "turn_off"),
        "li_on": async_mock_service(hass, "light", "turn_on"),
        "li_off": async_mock_service(hass, "light", "turn_off"),
        "notify": async_mock_service(hass, "notify", "test"),
    }
    sel_calls = []

    async def _select(call):
        sel_calls.append(call)
        old = hass.states.get(call.data["entity_id"])
        hass.states.async_set(call.data["entity_id"], call.data["option"], old.attributes)

    hass.services.async_register("select", "select_option", _select)
    calls["select"] = sel_calls
    entry = MockConfigEntry(domain=DOMAIN, unique_id=DOMAIN)
    entry.add_to_hass(hass)
    with patch("custom_components.aussenlicht.runner.WLED_VERIFY_S", 0):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        ws = await hass_ws_client(hass)
        yield hass, ws, calls, entry


async def _ws(ws, **msg):
    await ws.send_json_auto_id(msg)
    return await ws.receive_json()


async def test_save_invalid_and_valid(setup):
    hass, ws, calls, entry = setup
    bad = {**CONFIG, "seasons": {"x": {**CONFIG["seasons"]["xmas"], "zone_id": "nope"}}}
    r = await _ws(ws, type="aussenlicht/config/save", config=bad)
    assert not r["success"] and r["error"]["code"] == "invalid"
    r = await _ws(ws, type="aussenlicht/config/save", config=CONFIG)
    assert r["success"], r
    r = await _ws(ws, type="aussenlicht/config")
    assert r["result"]["config"]["zones"]["gaube"]["default_preset"] == "Gaube1"


async def test_christmas_evening(setup, freezer: FrozenDateTimeFactory):
    hass, ws, calls, entry = setup
    freezer.move_to(datetime(2026, 12, 10, 17, 0, tzinfo=TZ))  # nach Sonnenuntergang (~16:20)
    assert (await _ws(ws, type="aussenlicht/config/save", config=CONFIG))["success"]
    with patch("custom_components.aussenlicht.runner.WLED_VERIFY_S", 0):
        r = await _ws(ws, type="aussenlicht/apply_now")
        assert r["success"]
        await hass.async_block_till_done()
    assert {c.data["entity_id"] for c in calls["sw_on"]} == {"switch.gaube"}
    assert {c.data["option"] for c in calls["select"]} == {"Weihnachten "}  # Leerzeichen-Toleranz
    assert {c.data["entity_id"] for c in calls["li_off"]} == {"light.einfahrt"}
    assert calls["notify"]
    n_on = len(calls["sw_on"])

    st = (await _ws(ws, type="aussenlicht/status"))["result"]
    assert st["zones"]["gaube"]["season"]["name"] == "Weihnachten"
    assert st["zones"]["gaube"]["desired"]["preset"] == "Weihnachten"
    assert len(st["zones"]["einfahrt"]["timeline"]) == 2
    assert st["log"][0]["ok"]

    # 2 h später: nur Preset-Wechsel, kein erneutes Einschalten
    freezer.move_to(datetime(2026, 12, 10, 18, 40, tzinfo=TZ))
    with patch("custom_components.aussenlicht.runner.WLED_VERIFY_S", 0):
        await entry.runtime_data.runner.async_tick()
        await hass.async_block_till_done()
    assert len(calls["sw_on"]) == n_on  # kein erneutes Einschalten
    assert calls["select"][-1].data["option"] == "Gaube1"


async def test_dry_run_switches_nothing(setup, freezer):
    hass, ws, calls, entry = setup
    freezer.move_to(datetime(2026, 11, 24, 15, 0, tzinfo=TZ))
    cfg = {**CONFIG, "settings": {**CONFIG["settings"], "dry_run": True}}
    assert (await _ws(ws, type="aussenlicht/config/save", config=cfg))["success"]
    await _ws(ws, type="aussenlicht/apply_now")
    await hass.async_block_till_done()
    assert not calls["li_on"] and not calls["sw_on"] and not calls["sw_off"] and not calls["select"]
    log = (await _ws(ws, type="aussenlicht/status"))["result"]["log"]
    assert any(e["dry_run"] and e["zone"] == "Einfahrt" and "20 %" in e["text"] for e in log)
    assert calls["notify"] and calls["notify"][0].data["message"].startswith("[Test]")


async def test_unavailable_device_reports_once(setup, freezer):
    hass, ws, calls, entry = setup
    freezer.move_to(datetime(2026, 11, 24, 15, 0, tzinfo=TZ))
    hass.states.async_set("light.einfahrt", "unavailable")
    cfg = {**CONFIG, "settings": {**CONFIG["settings"], "notify_level": "errors"}}
    assert (await _ws(ws, type="aussenlicht/config/save", config=cfg))["success"]
    runner = entry.runtime_data.runner
    for _ in range(3):
        await runner.async_apply_now("einfahrt")
        await hass.async_block_till_done()
    assert len(calls["notify"]) == 1
    hass.states.async_set("light.einfahrt", "off")
    await runner.async_tick()
    await hass.async_block_till_done()
    assert calls["li_on"][-1].data["brightness_pct"] == 20


async def test_unload_and_reload_keeps_config(setup):
    hass, ws, calls, entry = setup
    assert (await _ws(ws, type="aussenlicht/config/save", config=CONFIG))["success"]
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert "gaube" in entry.runtime_data.store.data["zones"]
