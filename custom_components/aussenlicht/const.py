"""Konstanten für den Außenlicht-Planer."""
from __future__ import annotations

from typing import Final

DOMAIN: Final = "aussenlicht"
NAME: Final = "Außenlicht-Planer"

STORAGE_KEY: Final = f"{DOMAIN}.config"
STORAGE_VERSION: Final = 1
SAVE_DELAY: Final = 1

TICK_SECONDS: Final = 30
STARTUP_DELAY_S: Final = 30  # nach HA-Start warten, bis Geräte verfügbar sind
LOG_SIZE: Final = 100
WLED_RETRIES: Final = 3
WLED_VERIFY_S: Final = 5

ANCHORS: Final = ("sunset", "sunrise", "time")
ACTIONS: Final = ("on", "off", "dim")
NOTIFY_LEVELS: Final = ("off", "errors", "all")
ANCHOR_LABELS: Final = {"sunset": "Sonnenuntergang", "sunrise": "Sonnenaufgang", "time": "Uhrzeit"}
