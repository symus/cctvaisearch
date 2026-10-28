"""Hardware and tool detection, reported at startup and via /api/system-info."""

from __future__ import annotations

import importlib.util
import os
import platform
import shutil
import sys
from dataclasses import asdict, dataclass, field

import psutil

from .subproc import run


@dataclass
class ToolInfo:
    name: str
    available: bool
    path: str | None = None
    version: str | None = None


@dataclass
class GpuInfo:
    name: str
    memory_mb: int | None = None
    driver: str | None = None


@dataclass
class HardwareInfo:
    os: str
    python: str
    cpu: str
    cpu_logical_cores: int
    ram_total_mb: int
    ram_available_mb: int
    gpus: list[GpuInfo] = field(default_factory=list)
    onnxruntime_providers: list[str] = field(default_factory=list)
    inference_provider: str = "cpu"
    inference_provider_reason: str = ""
    tools: list[ToolInfo] = field(default_factory=list)

    def as_dict(self) -> dict:
        return asdict(self)


def detect_tool(executable: str, version_flag: str = "-version") -> ToolInfo:
    path = shutil.which(executable)
    if not path:
        return ToolInfo(name=executable, available=False)
    version = None
    try:
        proc = run([path, version_flag], timeout=10)
        first = proc.stdout.decode("utf-8", "replace").splitlines()
        version = first[0].strip() if first else None
    except (OSError, TimeoutError, Exception):  # noqa: BLE001 - version is best-effort
        pass
    return ToolInfo(name=executable, available=True, path=path, version=version)


def _detect_nvidia_gpus() -> list[GpuInfo]:
    smi = shutil.which("nvidia-smi")
    if not smi:
        return []
    try:
        proc = run(
            [smi, "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader,nounits"],
            timeout=10,
        )
    except Exception:  # noqa: BLE001
        return []
    gpus = []
    for line in proc.stdout.decode("utf-8", "replace").splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) == 3:
            mem = int(parts[1]) if parts[1].isdigit() else None
            gpus.append(GpuInfo(name=parts[0], memory_mb=mem, driver=parts[2]))
    return gpus


def _onnxruntime_providers() -> list[str]:
    if importlib.util.find_spec("onnxruntime") is None:
        return []
    try:
        import onnxruntime  # type: ignore[import-not-found]

        return list(onnxruntime.get_available_providers())
    except Exception:  # noqa: BLE001
        return []


def choose_provider(providers: list[str]) -> tuple[str, str]:
    """Pick the inference execution provider. GPU is used only when usable."""
    if "CUDAExecutionProvider" in providers:
        return "cuda", "onnxruntime-gpu reports CUDAExecutionProvider"
    if "DmlExecutionProvider" in providers:
        return "directml", "onnxruntime-directml reports DmlExecutionProvider"
    if providers:
        return "cpu", "onnxruntime installed without a GPU execution provider"
    return "cpu", "onnxruntime not installed yet (installed with the AI models in Milestone 4)"


def detect_hardware(ffmpeg: str = "ffmpeg", ffprobe: str = "ffprobe") -> HardwareInfo:
    vm = psutil.virtual_memory()
    providers = _onnxruntime_providers()
    provider, reason = choose_provider(providers)
    return HardwareInfo(
        os=f"{platform.system()} {platform.release()} ({platform.machine()})",
        python=sys.version.split()[0],
        cpu=platform.processor() or platform.machine(),
        cpu_logical_cores=os.cpu_count() or 1,
        ram_total_mb=vm.total // (1024 * 1024),
        ram_available_mb=vm.available // (1024 * 1024),
        gpus=_detect_nvidia_gpus(),
        onnxruntime_providers=providers,
        inference_provider=provider,
        inference_provider_reason=reason,
        tools=[detect_tool(ffmpeg), detect_tool(ffprobe)],
    )
