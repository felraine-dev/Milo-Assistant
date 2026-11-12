"""Confirmation gates for actions that change the machine or start a process."""

from __future__ import annotations

import os
import shutil
import subprocess
from collections.abc import Callable
from typing import TypeVar

F = TypeVar("F", bound=Callable[..., str])

RISK_LOW = "low"
RISK_HIGH = "high"


def tool(*, risk: str = RISK_LOW) -> Callable[[F], F]:
    """Mark a function for discovery.

    High-risk tools must call execute() or spawn_console() before any side effect.
    Those helpers prompt in the terminal and refuse to continue without a yes.
    """

    def decorator(fn: F) -> F:
        note = (
            "\n\nRisk: high. Any command it runs asks for confirmation in the terminal first."
            if risk == RISK_HIGH
            else "\n\nRisk: low. Read-only."
        )
        fn.__doc__ = (fn.__doc__ or "") + note
        fn._milo_tool = True  # type: ignore[attr-defined]
        fn._milo_risk = risk  # type: ignore[attr-defined]
        return fn

    return decorator


def confirm(action: str) -> bool:
    """Ask the person at the terminal before a high-impact action."""
    print(f"\n[Milo] Confirmation required\n{action.strip()}\n")
    try:
        answer = input("Proceed? [y/N]: ")
    except EOFError:
        print("Cancelled.")
        return False
    approved = answer.strip().lower() in {"y", "yes"}
    if not approved:
        print("Cancelled.")
    return approved


def _validate_argv(argv: list[str]) -> str | None:
    if not argv or not all(isinstance(part, str) and part.strip() for part in argv):
        return "Refusing to run an empty or invalid command."
    return None


def _resolve_argv(argv: list[str]) -> list[str] | str:
    """Resolve the executable. Windows .cmd launchers go through a quoted cmd /c line."""
    resolved = shutil.which(argv[0]) or argv[0]
    if os.name == "nt" and resolved.lower().endswith((".cmd", ".bat")):
        command_line = subprocess.list2cmdline([resolved, *argv[1:]])
        return ["cmd", "/c", command_line]
    if shutil.which(argv[0]) or os.path.isfile(resolved):
        return [resolved, *argv[1:]]
    return f"Executable not found: {argv[0]}"


def execute(argv: list[str], cwd: str, action: str, timeout: int = 120) -> str:
    """Run an allowlisted command after confirmation. Never uses a shell."""
    invalid = _validate_argv(argv)
    if invalid:
        return invalid
    if not os.path.isdir(cwd):
        return f"Directory not found: {cwd}"
    if not confirm(action):
        return f"Cancelled. Did not run: {' '.join(argv)}"

    resolved = _resolve_argv(argv)
    if isinstance(resolved, str):
        return resolved
    try:
        result = subprocess.run(
            resolved,
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=True,
            shell=False,
            timeout=timeout,
        )
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or str(exc)).strip()
        return f"Command failed ({' '.join(argv)}): {detail}"
    except subprocess.TimeoutExpired:
        return f"Command timed out after {timeout}s: {' '.join(argv)}"
    except FileNotFoundError:
        return f"Executable not found: {argv[0]}"

    output = (result.stdout or "").strip()
    return output or f"Completed: {' '.join(argv)}"


def spawn_console(argv: list[str], cwd: str, action: str) -> str:
    """Start an allowlisted command in a new console after confirmation."""
    invalid = _validate_argv(argv)
    if invalid:
        return invalid
    if not os.path.isdir(cwd):
        return f"Directory not found: {cwd}"
    if not confirm(action):
        return f"Cancelled. Did not start: {' '.join(argv)}"

    resolved = _resolve_argv(argv)
    if isinstance(resolved, str):
        return resolved

    popen_kwargs: dict = {"cwd": cwd, "shell": False}
    if os.name == "nt":
        popen_kwargs["creationflags"] = subprocess.CREATE_NEW_CONSOLE
    else:
        popen_kwargs["start_new_session"] = True
    try:
        process = subprocess.Popen(resolved, **popen_kwargs)
    except FileNotFoundError:
        return f"Executable not found: {argv[0]}"
    except OSError as exc:
        return f"Failed to start {' '.join(argv)}: {exc}"
    return f"Started PID {process.pid}: {' '.join(argv)}"
