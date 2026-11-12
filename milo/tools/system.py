"""Local machine health."""

from __future__ import annotations

import psutil

from milo.safety import tool

_DEV_STEMS = {
    "python",
    "pythonw",
    "node",
    "npm",
    "npx",
    "pnpm",
    "yarn",
    "code",
    "cursor",
    "docker",
    "java",
    "go",
    "cargo",
    "rustc",
    "uvicorn",
    "gunicorn",
    "flask",
}


def _stem(name: str) -> str:
    lowered = name.lower()
    if lowered.endswith(".exe"):
        return lowered[:-4]
    return lowered


@tool()
def get_system_health() -> str:
    """Check current CPU usage, RAM usage, and battery percentage."""
    try:
        cpu = psutil.cpu_percent(interval=1)
        ram = psutil.virtual_memory().percent
        battery = psutil.sensors_battery()
    except psutil.Error as exc:
        return f"System health error: {exc}"

    if battery is None:
        battery_text = "N/A"
    else:
        source = "Plugged in" if battery.power_plugged else "On battery"
        battery_text = f"{battery.percent}% ({source})"
    return f"CPU Usage: {cpu}% | RAM Usage: {ram}% | Battery: {battery_text}"


@tool()
def get_disk_usage(path: str = ".") -> str:
    """Report used, free, and total disk space for the volume containing a path.

    Args:
        path: Filesystem path whose volume should be checked. Defaults to the current directory.
    """
    try:
        usage = psutil.disk_usage(path)
    except OSError as exc:
        return f"Disk error: {exc}"

    def gb(num_bytes: int) -> str:
        return f"{num_bytes / (1024 ** 3):.1f} GB"

    return (
        f"Path: {path} | Used: {gb(usage.used)} | Free: {gb(usage.free)} | "
        f"Total: {gb(usage.total)} ({usage.percent}% used)"
    )


@tool()
def get_dev_processes(limit: int = 15) -> str:
    """List running development-related processes, busiest in memory first.

    Args:
        limit: How many matching processes to return, from 1 to 30.
    """
    capped = min(30, max(1, limit))
    rows: list[tuple[int, int, str, str]] = []
    try:
        processes = psutil.process_iter(["pid", "name", "memory_info", "status"])
    except psutil.Error as exc:
        return f"Process error: {exc}"

    for proc in processes:
        try:
            info = proc.info
            name = info.get("name") or ""
            stem = _stem(name)
            if stem not in _DEV_STEMS and not stem.startswith("python"):
                continue
            memory = info.get("memory_info")
            rss = memory.rss if memory else 0
            rows.append((rss, info.get("pid") or 0, name, info.get("status") or "?"))
        except (psutil.Error, KeyError):
            continue

    if not rows:
        return "No development-related processes found."

    rows.sort(reverse=True)
    lines = [f"Development processes: {len(rows)} found. Showing {min(capped, len(rows))}."]
    for rss, pid, name, status in rows[:capped]:
        lines.append(f"PID {pid} | {name} | {status} | {rss / (1024 ** 2):.0f} MB")
    return "\n".join(lines)
