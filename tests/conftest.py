"""Reine Logik-Tests ohne Home Assistant: Paket ohne __init__ laden."""
import sys
import types
from pathlib import Path

PKG = Path(__file__).resolve().parent.parent / "custom_components" / "aussenlicht"
if "aussenlicht" not in sys.modules:
    mod = types.ModuleType("aussenlicht")
    mod.__path__ = [str(PKG)]
    sys.modules["aussenlicht"] = mod
