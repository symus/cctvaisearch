"""Check that this machine can run CCTV AI Search.

Usage (from the repo root, with the backend venv active):
    python scripts/check_env.py
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

OK, WARN, FAIL = "OK  ", "WARN", "FAIL"
problems = 0


def report(level: str, msg: str) -> None:
    global problems
    if level == FAIL:
        problems += 1
    print(f"[{level}] {msg}")


def main() -> int:
    v = sys.version_info
    if v >= (3, 12):
        report(OK, f"Python {v.major}.{v.minor}.{v.micro}")
    else:
        report(FAIL, f"Python {v.major}.{v.minor} found; 3.12 or newer is required")

    try:
        from app.config import get_settings
        from app.services.hardware import detect_hardware
    except ImportError as exc:
        report(FAIL, f"Backend dependencies missing ({exc.name}). Run: pip install -r backend\\requirements.txt")
        return 1

    s = get_settings()
    hw = detect_hardware(s.ffmpeg_path, s.ffprobe_path)
    for tool in hw.tools:
        if tool.available:
            report(OK, f"{tool.name}: {tool.version}")
        else:
            report(FAIL, f"{tool.name} not found. Install FFmpeg and add its bin folder to PATH (see README)")

    ram_gb = hw.ram_total_mb / 1024
    report(OK if ram_gb >= 15 else WARN, f"RAM: {ram_gb:.1f} GB total, {hw.ram_available_mb / 1024:.1f} GB free")
    report(OK, f"CPU: {hw.cpu} ({hw.cpu_logical_cores} logical cores)")
    if hw.gpus:
        for g in hw.gpus:
            report(OK, f"NVIDIA GPU: {g.name} ({g.memory_mb} MB, driver {g.driver})")
    else:
        report(OK, "No NVIDIA GPU detected - CPU inference will be used (supported)")
    report(OK, f"Inference provider: {hw.inference_provider.upper()} - {hw.inference_provider_reason}")
    report(OK, "AI models: none installed yet (added in Milestones 4-5; never auto-downloaded)")

    data = s.data_dir
    try:
        data.mkdir(parents=True, exist_ok=True)
        free_gb = shutil.disk_usage(data).free / 1024**3
        report(OK if free_gb > 20 else WARN, f"Data folder {data} ({free_gb:.0f} GB free)")
    except OSError as exc:
        report(FAIL, f"Cannot create data folder {data}: {exc}")

    if sys.platform == "win32":
        try:
            import winreg

            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\FileSystem")
            enabled = winreg.QueryValueEx(key, "LongPathsEnabled")[0] == 1
        except OSError:
            enabled = False
        report(OK if enabled else WARN,
               "Windows long paths " + ("enabled" if enabled else "disabled - paths over 260 chars may fail (see README)"))

    print()
    print("All required checks passed." if problems == 0 else f"{problems} required check(s) failed.")
    return 0 if problems == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
