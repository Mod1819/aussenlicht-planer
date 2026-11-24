# Außenlicht-Planer (Home Assistant Custom Integration)

Version **0.2.0**: zentrale Zeitsteuerung der Außenbeleuchtung mit eigener Oberfläche (Seitenleiste „Außenlicht“).

- **Bereiche** (z. B. Gaube, Einfahrt) mit beliebig vielen Schritten. Jeder Schritt hängt an Sonnenuntergang oder Sonnenaufgang ± Minuten oder an einer festen Uhrzeit. Aktionen: An, Aus oder Dimmen in %.
- **WLED-Presets** pro Bereich mit einem Standard-Preset.
- **Saisons** mit Datumsbereich, auch über den Jahreswechsel. Wenn der Bereich bei einem gewählten Schritt angeht, läuft ein Sonder-Preset, wahlweise für eine Dauer (z. B. 2 h „Weihnachten“) oder bis zu einer festen Uhrzeit (z. B. 22:00). Danach springt er automatisch auf das Standard-Preset zurück.
- **Nach einem Neustart** wird der Sollzustand berechnet und wiederhergestellt, auch über Mitternacht hinweg.
- **Testmodus** (Standard: an): Es wird nichts geschaltet, alles landet nur im Protokoll. So kann der Planer parallel zu bestehenden Automationen geprüft werden.
- **Benachrichtigungen:** Aus, nur Fehler oder alles, über einen beliebigen Dienst (z. B. `rest_command.telegram_daniel`).
- **Fehlerbehandlung:** Nicht erreichbare Geräte werden alle 30 s erneut versucht und nur einmal gemeldet. WLED-Presets werden nach dem Setzen überprüft, bei Bedarf bis zu 3 Mal wiederholt.

> ⚠️ Vor dem Abschalten des Testmodus die alten Automationen für **dieselben Geräte** deaktivieren, sonst schalten zwei Systeme gegeneinander.

## Installation (HACS)
1. HACS → ⋮ → **Benutzerdefinierte Repositories** → `https://github.com/Mod1819/aussenlicht-planer`, Typ **Integration**
2. „Außenlicht-Planer“ herunterladen → Home Assistant neu starten
3. Einstellungen → Geräte & Dienste → Integration hinzufügen → **Außenlicht-Planer**
4. In der Seitenleiste erscheint **Außenlicht** (nur für Admins, ggf. Strg+F5)

## Entwicklung
```
pytest tests          # reine Planungslogik
pytest tests_ha       # Integration (pytest-homeassistant-custom-component)
```
