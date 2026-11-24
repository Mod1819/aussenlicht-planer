from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
import voluptuous as vol

from aussenlicht.engine import desired_state, season_active, season_window, timeline
from aussenlicht.models import validate_config

TZ = ZoneInfo("Europe/Berlin")


def sun_for(day: date):
    # vereinfachte feste Sonnenzeiten
    return {
        "sunrise": datetime(day.year, day.month, day.day, 8, 0, tzinfo=TZ),
        "sunset": datetime(day.year, day.month, day.day, 16, 30, tzinfo=TZ),
    }


def cfg(**season_over):
    raw = {
        "zones": {
            "gaube": {
                "name": "Gaube",
                "entities": ["switch.gaube"],
                "wled_presets": ["select.w4", "select.w5"],
                "default_preset": "Gaube1",
                "steps": [
                    {"id": "abend", "anchor": "sunset", "offset_min": 0, "action": "on"},
                    {"id": "frueh", "anchor": "sunrise", "offset_min": -120, "action": "on"},
                    {"id": "aus", "anchor": "sunrise", "offset_min": 0, "action": "off"},
                ],
            },
            "einfahrt": {
                "name": "Einfahrt",
                "entities": ["light.einfahrt"],
                "steps": [
                    {"id": "a", "anchor": "sunset", "offset_min": -120, "action": "dim", "brightness_pct": 20},
                    {"id": "b", "anchor": "sunset", "offset_min": -60, "action": "dim", "brightness_pct": 15},
                    {"id": "c", "anchor": "sunset", "offset_min": -30, "action": "dim", "brightness_pct": 9},
                    {"id": "d", "anchor": "sunset", "offset_min": 0, "action": "off"},
                ],
            },
        },
        "seasons": {
            "xmas": {
                "name": "Weihnachten", "zone_id": "gaube", "start": "12-01", "end": "01-06",
                "preset": "Weihnachten ", "duration_min": 120, "steps": ["abend"], **season_over,
            }
        },
    }
    return validate_config(raw)


def at(y, m, d, hh, mm):
    return datetime(y, m, d, hh, mm, tzinfo=TZ)


def test_season_active_over_new_year():
    s = {"start": "12-01", "end": "01-06"}
    assert season_active(s, date(2026, 12, 24))
    assert season_active(s, date(2027, 1, 6))
    assert not season_active(s, date(2027, 1, 7))
    assert not season_active(s, date(2026, 11, 30))
    assert season_active({"start": "03-01", "end": "03-31"}, date(2026, 3, 15))


def test_gaube_overnight_and_morning():
    c = cfg()
    assert desired_state(c, "gaube", at(2026, 12, 10, 12, 0), sun_for, TZ)["action"] == "off"
    st = desired_state(c, "gaube", at(2026, 12, 11, 2, 0), sun_for, TZ)  # Nacht, Schritt von gestern
    assert st["action"] == "on" and st["step_id"] == "abend"
    st = desired_state(c, "gaube", at(2026, 12, 11, 6, 30), sun_for, TZ)
    assert st["step_id"] == "frueh"
    assert desired_state(c, "gaube", at(2026, 12, 11, 8, 0), sun_for, TZ)["action"] == "off"


def test_christmas_preset_two_hours_then_default():
    c = cfg()
    assert desired_state(c, "gaube", at(2026, 12, 10, 16, 30), sun_for, TZ)["preset"] == "Weihnachten "
    assert desired_state(c, "gaube", at(2026, 12, 10, 18, 29), sun_for, TZ)["preset"] == "Weihnachten "
    assert desired_state(c, "gaube", at(2026, 12, 10, 18, 30), sun_for, TZ)["preset"] == "Gaube1"
    # Morgens (Schritt "frueh" ist kein Startschritt) -> Standard
    assert desired_state(c, "gaube", at(2026, 12, 11, 6, 30), sun_for, TZ)["preset"] == "Gaube1"
    # Aus -> kein Preset
    assert desired_state(c, "gaube", at(2026, 12, 11, 12, 0), sun_for, TZ)["preset"] is None


def test_outside_season_default_preset():
    c = cfg()
    assert desired_state(c, "gaube", at(2026, 11, 24, 17, 0), sun_for, TZ)["preset"] == "Gaube1"


def test_season_disabled():
    c = cfg(enabled=False)
    assert desired_state(c, "gaube", at(2026, 12, 10, 17, 0), sun_for, TZ)["preset"] == "Gaube1"


def test_long_duration_window_across_midnight_and_off_ends_it():
    c = cfg(duration_min=24 * 60)
    assert desired_state(c, "gaube", at(2026, 12, 11, 2, 0), sun_for, TZ)["preset"] == "Weihnachten "
    # nach dem Aus um 8:00 und neuem Einschalten wäre das Fenster beendet
    assert season_window(c, "gaube", at(2026, 12, 11, 8, 1), sun_for, TZ) is None


def test_einfahrt_dimming():
    c = cfg()
    assert desired_state(c, "einfahrt", at(2026, 11, 24, 14, 29), sun_for, TZ)["action"] == "off"
    st = desired_state(c, "einfahrt", at(2026, 11, 24, 14, 30), sun_for, TZ)
    assert (st["action"], st["brightness_pct"]) == ("dim", 20)
    assert desired_state(c, "einfahrt", at(2026, 11, 24, 15, 45), sun_for, TZ)["brightness_pct"] == 15
    assert desired_state(c, "einfahrt", at(2026, 11, 24, 16, 10), sun_for, TZ)["brightness_pct"] == 9
    assert desired_state(c, "einfahrt", at(2026, 11, 24, 16, 30), sun_for, TZ)["action"] == "off"
    assert desired_state(c, "einfahrt", at(2026, 11, 24, 16, 30), sun_for, TZ)["preset"] is None


def test_fixed_time_step():
    c = cfg()
    c["zones"]["gaube"]["steps"].append({"id": "nacht", "anchor": "time", "offset_min": 0, "time": "23:00", "action": "off", "brightness_pct": None})
    c = validate_config(c)
    assert desired_state(c, "gaube", at(2026, 12, 10, 23, 30), sun_for, TZ)["action"] == "off"
    assert desired_state(c, "gaube", at(2026, 12, 11, 7, 0), sun_for, TZ)["action"] == "on"


def test_polar_no_sun_is_skipped():
    c = cfg()
    assert desired_state(c, "gaube", at(2026, 12, 10, 12, 0), lambda d: {"sunrise": None, "sunset": None}, TZ) is None


def test_timeline_sorted_with_labels():
    tl = timeline(cfg()["zones"]["einfahrt"], date(2026, 11, 24), sun_for, TZ)
    assert [e["step_id"] for e in tl] == ["a", "b", "c", "d"]
    assert tl[0]["label"] == "Sonnenuntergang -120 min"


@pytest.mark.parametrize("mut,msg", [
    (lambda r: r["zones"]["einfahrt"]["steps"][0].pop("brightness_pct"), "Helligkeit"),
    (lambda r: r["seasons"]["xmas"].update(zone_id="weg"), "existiert nicht"),
    (lambda r: r["seasons"]["xmas"].update(steps=["aus"]), "Startschritt"),
    (lambda r: r["seasons"]["xmas"].update(start="13-01"), "Datum"),
    (lambda r: r["zones"]["gaube"]["steps"].append({"id": "t", "anchor": "time", "action": "on"}), "Uhrzeit"),
    (lambda r: r["zones"]["gaube"].update(entities=["sensor.x"]), "Entität"),
    (lambda r: r["zones"]["gaube"]["steps"].append({"id": "d", "anchor": "sunset", "action": "dim", "brightness_pct": 5}), "light"),
])
def test_validation_errors(mut, msg):
    raw = cfg()
    mut(raw)
    with pytest.raises(vol.Invalid, match=msg):
        validate_config(raw)


def test_defaults():
    c = validate_config({})
    assert c["settings"]["dry_run"] is True
    assert c["settings"]["notify_level"] == "errors"


def test_season_until_fixed_time():
    c = cfg(until_mode="time", until_time="22:00")
    assert desired_state(c, "gaube", at(2026, 12, 10, 21, 59), sun_for, TZ)["preset"] == "Weihnachten "
    assert desired_state(c, "gaube", at(2026, 12, 10, 22, 0), sun_for, TZ)["preset"] == "Gaube1"
    w = season_window(c, "gaube", at(2026, 12, 10, 18, 0), sun_for, TZ)
    assert w["end"] == at(2026, 12, 10, 22, 0)


def test_season_until_time_after_midnight():
    c = cfg(until_mode="time", until_time="01:00")
    assert desired_state(c, "gaube", at(2026, 12, 11, 0, 30), sun_for, TZ)["preset"] == "Weihnachten "
    assert desired_state(c, "gaube", at(2026, 12, 11, 1, 0), sun_for, TZ)["preset"] == "Gaube1"


def test_season_until_time_missing():
    raw = cfg()
    raw["seasons"]["xmas"]["until_mode"] = "time"
    raw["seasons"]["xmas"]["until_time"] = None
    with pytest.raises(vol.Invalid, match="Uhrzeit für das Ende"):
        validate_config(raw)
