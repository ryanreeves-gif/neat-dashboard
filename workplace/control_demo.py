"""Local-only control scenarios and graphics; never a gateway or forecast."""
from base64 import b64encode
import json
from math import exp, isfinite
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KINDS = {"warm": "AC temperature", "light": "Lighting", "purge": "Air purge"}


def scenario(kind, duration, temperature=21.0, brightness=20, boost=80, start_temperature=26.0):
    if kind not in KINDS:
        raise ValueError("Unknown simulation action.")
    for value, low, high in [(duration, 5, 60), (temperature, 16, 28), (brightness, 0, 100),
                             (boost, 20, 100), (start_temperature, 10, 40)]:
        if isinstance(value, bool) or not isfinite(value) or not low <= value <= high:
            raise ValueError("Simulation setting outside its demo range.")
    return {"kind": kind, "duration": int(duration), "temperature": float(temperature),
            "brightness": int(brightness), "boost": int(boost), "start_temperature": float(start_temperature),
            "baseline_light": 80, "baseline_setpoint": 24.0, "baseline_fan": 30,
            "baseline_air_indicator": 100, "basis": "Invented scenario; not a calibrated response model",
            "command_sent": False, "measured_saving": None}


def preview_state(settings, minute):
    """A deterministic teaching animation. Minutes and room responses are invented.

    At expiry, controls restore to their assumed schedule. The illustrative room
    temperature/air indicator do not jump back: controller and sensor are distinct.
    """
    duration = settings["duration"]
    minute = min(duration, max(0.0, float(minute)))
    active = 0 < minute < duration
    temperature = settings["start_temperature"]
    air = float(settings["baseline_air_indicator"])
    if settings["kind"] == "warm":
        temperature += (settings["temperature"] - temperature) * (1 - exp(-minute / 12))
    if settings["kind"] == "purge":
        air *= exp(-minute * settings["boost"] / 100 / 12)
    return {"minute": round(minute, 2), "active": active, "expired": minute >= duration,
            "room_temperature": round(temperature, 1), "air_indicator": round(air, 1),
            "light": settings["brightness"] if active and settings["kind"] == "light" else settings["baseline_light"],
            "setpoint": settings["temperature"] if active and settings["kind"] == "warm" else settings["baseline_setpoint"],
            "fan": settings["boost"] if active and settings["kind"] == "purge" else settings["baseline_fan"]}


def animation_html(settings, room_name, run_id=None):
    payload = {**settings, "room_name": str(room_name), "running": bool(run_id), "run_id": run_id,
               "frames": [preview_state(settings, settings["duration"] * i / 120) for i in range(121)]}
    # Configuration is data, never executable markup, even for unusual room names.
    encoded = json.dumps(payload).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    font = b64encode((ROOT / "assets/MaisonNeue-Book.woff2").read_bytes()).decode()
    bold = b64encode((ROOT / "assets/MaisonNeue-Bold.woff2").read_bytes()).decode()
    return ((ROOT / "assets/control-demo.html").read_text().replace("__CONFIG__", encoded)
            .replace("__FONT__", font).replace("__BOLD_FONT__", bold))
