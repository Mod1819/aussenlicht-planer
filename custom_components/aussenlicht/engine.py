"""Reine Planungslogik (ohne HA-Abhängigkeit, vollständig testbar).

Prinzip: Der Sollzustand eines Bereichs zu einem Zeitpunkt ergibt sich aus dem
letzten fälligen Schritt (gestern + heute, damit Nacht-Zeiträume über Mitternacht
funktionieren). Saisons legen für eine Dauer ab bestimmten Einschalt-Schritten ein
WLED-Preset fest, sonst gilt das Standard-Preset.
"""
from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime, time, timedelta, tzinfo
from typing import Any

SunFor = Callable[[date], dict[str, datetime | None]]


def season_active(season: dict[str, Any], day: date) -> bool:
    md = day.strftime("%m-%d")
    start, end = season["start"], season["end"]
    if start <= end:
        return start <= md <= end
    return md >= start or md <= end  # über den Jahreswechsel


def step_time(step: dict[str, Any], day: date, sun_for: SunFor, tz: tzinfo) -> datetime | None:
    if step["anchor"] == "time":
        hh, mm = (int(x) for x in step["time"].split(":"))
        return datetime.combine(day, time(hh, mm), tzinfo=tz)
    base = sun_for(day).get(step["anchor"])
    if base is None:
        return None
    return base.astimezone(tz) + timedelta(minutes=step["offset_min"])


def zone_events(zone: dict[str, Any], day: date, sun_for: SunFor, tz: tzinfo) -> list[tuple[datetime, dict]]:
    out = []
    for step in zone["steps"]:
        t = step_time(step, day, sun_for, tz)
        if t is not None:
            out.append((t, step))
    out.sort(key=lambda x: x[0])
    return out


def _events_around(zone, now: datetime, sun_for, tz) -> list[tuple[datetime, dict]]:
    today = now.astimezone(tz).date()
    ev = zone_events(zone, today - timedelta(days=1), sun_for, tz) + zone_events(zone, today, sun_for, tz)
    ev.sort(key=lambda x: x[0])
    return ev


def season_window(
    cfg: dict[str, Any], zone_id: str, now: datetime, sun_for: SunFor, tz: tzinfo
) -> dict[str, Any] | None:
    """Aktives Saison-Fenster für den Bereich zum Zeitpunkt now (oder None)."""
    zone = cfg["zones"][zone_id]
    events = _events_around(zone, now, sun_for, tz)
    best = None
    for season in cfg["seasons"].values():
        if not season["enabled"] or season["zone_id"] != zone_id:
            continue
        for t, step in events:
            if step["id"] not in season["steps"] or t > now:
                continue
            if not season_active(season, t.date()):
                continue
            end = t + timedelta(minutes=season["duration_min"])
            if now >= end:
                continue
            # Ein Ausschalten zwischen Start und jetzt beendet das Fenster.
            if any(step2["action"] == "off" and t < t2 <= now for t2, step2 in events):
                continue
            if best is None or t > best["start"]:
                best = {"name": season["name"], "preset": season["preset"], "start": t, "end": end}
    return best


def desired_state(
    cfg: dict[str, Any], zone_id: str, now: datetime, sun_for: SunFor, tz: tzinfo
) -> dict[str, Any] | None:
    zone = cfg["zones"][zone_id]
    past = [(t, s) for t, s in _events_around(zone, now, sun_for, tz) if t <= now]
    if not past:
        return None
    since, step = past[-1]
    state = {
        "action": step["action"],
        "brightness_pct": step["brightness_pct"] if step["action"] == "dim" else None,
        "preset": None,
        "since": since,
        "step_id": step["id"],
    }
    if step["action"] != "off" and zone["wled_presets"]:
        win = season_window(cfg, zone_id, now, sun_for, tz)
        if win:
            state["preset"] = win["preset"]
        elif zone["default_preset"]:
            state["preset"] = zone["default_preset"]
    return state


def timeline(zone: dict[str, Any], day: date, sun_for: SunFor, tz: tzinfo) -> list[dict[str, Any]]:
    from .const import ANCHOR_LABELS

    out = []
    for t, step in zone_events(zone, day, sun_for, tz):
        label = ANCHOR_LABELS[step["anchor"]]
        if step["anchor"] != "time" and step["offset_min"]:
            label += f" {step['offset_min']:+d} min"
        out.append(
            {
                "time": t,
                "step_id": step["id"],
                "action": step["action"],
                "brightness_pct": step["brightness_pct"],
                "label": label,
            }
        )
    return out


def describe(state: dict[str, Any] | None) -> str:
    if state is None:
        return "kein Schritt fällig"
    txt = {"on": "an", "off": "aus", "dim": f"gedimmt {state['brightness_pct']} %"}[state["action"]]
    if state["preset"]:
        txt += f", Preset „{state['preset'].strip()}“"
    return txt
