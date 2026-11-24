"""Konfigurationsmodell + Validierung (ohne HA-Abhängigkeit, testbar)."""
from __future__ import annotations

import re
from typing import Any

import voluptuous as vol

from .const import ACTIONS, ANCHORS, NOTIFY_LEVELS

_TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
_MD_RE = re.compile(r"^(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])$")
_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,40}$")


def _hhmm(v: Any) -> str:
    v = str(v).strip()
    m = re.match(r"^(\d{1,2}):(\d{2})(?::\d{2})?$", v)
    if m:
        v = f"{int(m.group(1)):02d}:{m.group(2)}"
    if not _TIME_RE.match(v):
        raise vol.Invalid(f"Ungültige Uhrzeit '{v}' (erwartet HH:MM)")
    return v


def _md(v: Any) -> str:
    v = str(v).strip()
    if not _MD_RE.match(v):
        raise vol.Invalid(f"Ungültiges Datum '{v}' (erwartet MM-TT)")
    return v


def _ident(v: Any) -> str:
    v = str(v)
    if not _ID_RE.match(v):
        raise vol.Invalid(f"Ungültige ID '{v}'")
    return v


def _entity(domains: tuple[str, ...]):
    def check(v: Any) -> str:
        v = str(v).strip()
        if "." not in v or v.split(".", 1)[0] not in domains:
            raise vol.Invalid(f"'{v}' ist keine gültige Entität ({', '.join(domains)})")
        return v
    return check


STEP_SCHEMA = vol.Schema(
    {
        vol.Required("id"): _ident,
        vol.Required("anchor"): vol.In(ANCHORS),
        vol.Optional("offset_min", default=0): vol.All(vol.Coerce(int), vol.Range(-720, 720)),
        vol.Optional("time", default=None): vol.Any(None, _hhmm),
        vol.Required("action"): vol.In(ACTIONS),
        vol.Optional("brightness_pct", default=None): vol.Any(
            None, vol.All(vol.Coerce(int), vol.Range(1, 100))
        ),
    }
)

ZONE_SCHEMA = vol.Schema(
    {
        vol.Required("name"): vol.All(str, vol.Length(min=1, max=60)),
        vol.Optional("enabled", default=True): bool,
        vol.Optional("entities", default=list): [_entity(("switch", "light"))],
        vol.Optional("wled_presets", default=list): [_entity(("select",))],
        vol.Optional("default_preset", default=""): str,
        vol.Optional("steps", default=list): [STEP_SCHEMA],
    }
)

SEASON_SCHEMA = vol.Schema(
    {
        vol.Required("name"): vol.All(str, vol.Length(min=1, max=60)),
        vol.Optional("enabled", default=True): bool,
        vol.Required("zone_id"): _ident,
        vol.Required("start"): _md,
        vol.Required("end"): _md,
        vol.Required("preset"): vol.All(str, vol.Length(min=1)),
        vol.Optional("duration_min", default=120): vol.All(vol.Coerce(int), vol.Range(1, 1440)),
        vol.Optional("until_mode", default="duration"): vol.In(("duration", "time")),
        vol.Optional("until_time", default=None): vol.Any(None, _hhmm),
        vol.Optional("steps", default=list): [_ident],
    }
)

SETTINGS_SCHEMA = vol.Schema(
    {
        vol.Optional("dry_run", default=True): bool,
        vol.Optional("notify_service", default=""): str,
        vol.Optional("notify_level", default="errors"): vol.In(NOTIFY_LEVELS),
        vol.Optional("wled_delay_s", default=10): vol.All(vol.Coerce(int), vol.Range(0, 120)),
    }
)

CONFIG_SCHEMA = vol.Schema(
    {
        vol.Optional("zones", default=dict): {_ident: ZONE_SCHEMA},
        vol.Optional("seasons", default=dict): {_ident: SEASON_SCHEMA},
        vol.Optional("settings", default=dict): SETTINGS_SCHEMA,
    }
)


def default_config() -> dict[str, Any]:
    return CONFIG_SCHEMA({})


def validate_config(raw: Any) -> dict[str, Any]:
    """Schema prüfen + Querbezüge. Wirft vol.Invalid mit deutscher Meldung."""
    cfg = CONFIG_SCHEMA(raw)
    for zid, zone in cfg["zones"].items():
        ids = set()
        for step in zone["steps"]:
            if step["id"] in ids:
                raise vol.Invalid(f"Bereich '{zone['name']}': Schritt-ID doppelt")
            ids.add(step["id"])
            if step["anchor"] == "time" and not step["time"]:
                raise vol.Invalid(f"Bereich '{zone['name']}': Uhrzeit fehlt bei einem Schritt")
            if step["action"] == "dim" and step["brightness_pct"] is None:
                raise vol.Invalid(f"Bereich '{zone['name']}': Helligkeit fehlt beim Dimmen")
            if step["action"] == "dim" and not any(e.startswith("light.") for e in zone["entities"]):
                raise vol.Invalid(
                    f"Bereich '{zone['name']}': Dimmen geht nur mit einer light.*-Entität"
                )
    for season in cfg["seasons"].values():
        zone = cfg["zones"].get(season["zone_id"])
        if zone is None:
            raise vol.Invalid(f"Saison '{season['name']}': Bereich existiert nicht")
        if not zone["wled_presets"]:
            raise vol.Invalid(
                f"Saison '{season['name']}': Bereich '{zone['name']}' hat keine WLED-Presets"
            )
        step_ids = {s["id"] for s in zone["steps"] if s["action"] in ("on", "dim")}
        unknown = [s for s in season["steps"] if s not in step_ids]
        if unknown:
            raise vol.Invalid(
                f"Saison '{season['name']}': Startschritt gehört nicht (mehr) zu '{zone['name']}'"
            )
        if season["until_mode"] == "time" and not season["until_time"]:
            raise vol.Invalid(f"Saison '{season['name']}': Uhrzeit für das Ende fehlt")
        if not season["steps"]:
            raise vol.Invalid(f"Saison '{season['name']}': mindestens einen Startschritt wählen")
    return cfg
