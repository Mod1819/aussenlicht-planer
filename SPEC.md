# Außenlicht-Planer – Schnittstelle (Backend ↔ Panel)

Domain: `aussenlicht`. Sprache UI: Deutsch. Panel = eine Web-Component ohne Build-Schritt
(`custom_components/aussenlicht/www/aussenlicht-panel.js`, Element-Name `aussenlicht-panel`),
bekommt von HA die Property `hass` (und `narrow`, `panel`). Alle Daten nur über WebSocket:
`this.hass.callWS({type: "...", ...})`.

## Konfiguration (vollständiges Objekt)
```json
{
  "zones": {
    "<zone_id>": {
      "name": "Gaube",
      "enabled": true,
      "entities": ["switch.shellyplus1_cc7b5c8648bc_switch_0"],
      "wled_presets": ["select.wled_voreinstellung_4", "select.wled_voreinstellung_5"],
      "default_preset": "Gaube1",
      "steps": [
        {"id": "s1", "anchor": "sunset", "offset_min": 0, "time": null, "action": "on", "brightness_pct": null},
        {"id": "s2", "anchor": "sunrise", "offset_min": -120, "time": null, "action": "on", "brightness_pct": null},
        {"id": "s3", "anchor": "sunrise", "offset_min": 0, "time": null, "action": "off", "brightness_pct": null}
      ]
    }
  },
  "seasons": {
    "<season_id>": {
      "name": "Weihnachten",
      "enabled": true,
      "zone_id": "<zone_id>",
      "start": "12-01",
      "end": "01-06",
      "preset": "Weihnachten ",
      "duration_min": 120,
      "until_mode": "duration",
      "until_time": null,
      "steps": ["s1"]
    }
  },
  "settings": {
    "dry_run": true,
    "notify_service": "rest_command.telegram_daniel",
    "notify_level": "errors",
    "wled_delay_s": 10
  }
}
```
Feldregeln:
- `anchor`: `sunset` | `sunrise` | `time`. Bei `time` ist `time` = "HH:MM" Pflicht, `offset_min` wird ignoriert. Bei Sonne: `offset_min` −720…720 (negativ = vorher).
- `action`: `on` | `off` | `dim`. Bei `dim` ist `brightness_pct` 1–100 Pflicht (nur für `light.*` sinnvoll).
- `entities`: `switch.*` oder `light.*`. `wled_presets`: `select.*` (WLED-Voreinstellung). `default_preset` darf "" sein.
- Season: `start`/`end` "MM-DD" (Jahreswechsel erlaubt, z. B. 12-01 bis 01-06). `steps` = IDs der Schritte des Bereichs,
  bei deren Einschalten das Saison-Preset für `duration_min` Minuten läuft; danach `default_preset`.
- `notify_level`: `off` | `errors` | `all`. `notify_service` "domain.service" oder "" (aus). `wled_delay_s` 0–120.
- IDs erzeugt das Panel selbst (z. B. `Math.random().toString(36).slice(2,8)`).

## WebSocket-Befehle
- `aussenlicht/config` → `{ "config": <Konfiguration> }`
- `aussenlicht/config/save` `{ "config": <Konfiguration> }` → `{ "config": <validiert> }`; bei Fehler Error mit `code: "invalid"` und lesbarer `message` (im Panel anzeigen).
- `aussenlicht/status` →
```json
{
  "now": "ISO",
  "sun": {"sunrise": "ISO", "sunset": "ISO"},
  "dry_run": true,
  "zones": {
    "<zone_id>": {
      "name": "Gaube", "enabled": true,
      "desired": {"action": "on", "brightness_pct": null, "preset": "Weihnachten ", "since": "ISO"} ,
      "timeline": [{"time": "ISO", "step_id": "s1", "action": "on", "brightness_pct": null, "label": "Sonnenuntergang"}],
      "season": {"name": "Weihnachten", "preset": "Weihnachten ", "start": "ISO", "end": "ISO"}
    }
  },
  "log": [{"time": "ISO", "zone": "Gaube", "text": "an", "dry_run": true, "ok": true}]
}
```
  `desired` und `season` können `null` sein. `timeline` = heutige Schritte, chronologisch. `log` = neueste zuerst.
- `aussenlicht/apply_now` `{ "zone_id"?: "<id>" }` → `{ "ok": true }` (Sollzustand sofort neu anwenden).
