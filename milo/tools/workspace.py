"""Workspace inspection, virtualenv setup, and allowlisted launchers."""

from __future__ import annotations

import json
import os
import shutil
import sys

from milo.safety import RISK_HIGH, execute, spawn_console, tool

_PYTHON_MARKERS = ("pyproject.toml", "requirements.txt", "setup.py", "Pipfile")


def _directory(path: str) -> str | None:
    resolved = os.path.abspath(path)
    if os.path.isdir(resolved):
        return resolved
    return None


def _is_python_project(path: str) -> bool:
    return any(os.path.isfile(os.path.join(path, name)) for name in _PYTHON_MARKERS)


def _venv_python(path: str) -> str | None:
    for folder in ("venv", ".venv"):
        if os.name == "nt":
            candidate = os.path.join(path, folder, "Scripts", "python.exe")
        else:
            candidate = os.path.join(path, folder, "bin", "python")
        if os.path.isfile(candidate):
            return candidate
    return None


def _package_scripts(path: str) -> tuple[dict[str, str] | None, str | None]:
    package_path = os.path.join(path, "package.json")
    if not os.path.isfile(package_path):
        return None, None
    try:
        with open(package_path, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        return None, f"Could not read package.json: {exc}"
    scripts = data.get("scripts")
    if not isinstance(scripts, dict):
        return {}, None
    cleaned = {
        str(name): value.strip()
        for name, value in scripts.items()
        if isinstance(value, str) and value.strip()
    }
    return cleaned, None


def _report(path: str) -> str:
    python_project = _is_python_project(path)
    venv_python = _venv_python(path)
    scripts, package_error = _package_scripts(path)
    has_manage = os.path.isfile(os.path.join(path, "manage.py"))
    lines = [
        f"Path: {path}",
        f"Python project: {'yes' if python_project else 'no'}",
        f"Virtualenv: {venv_python or 'missing'}",
    ]
    if package_error:
        lines.append(package_error)
    elif scripts is None:
        lines.append("Node: no package.json")
    else:
        listed = ", ".join(sorted(scripts)) or "(none)"
        lines.append(f"Node scripts: {listed}")
    lines.append(f"Django manage.py: {'yes' if has_manage else 'no'}")
    return "\n".join(lines)


def _launcher(path: str, target: str) -> tuple[list[str] | None, str, str]:
    scripts, package_error = _package_scripts(path)
    has_manage = os.path.isfile(os.path.join(path, "manage.py"))
    npm_script = None
    if scripts:
        if "dev" in scripts:
            npm_script = "dev"
        elif "start" in scripts:
            npm_script = "start"

    if target not in {"auto", "npm", "django"}:
        return None, "", "target must be auto, npm, or django."
    if package_error and target in {"auto", "npm"}:
        return None, "", package_error

    want_npm = target == "npm" or (target == "auto" and npm_script and not has_manage)
    want_django = target == "django" or (target == "auto" and has_manage and not npm_script)
    if target == "auto" and npm_script and has_manage:
        return None, "", (
            "Both a Node dev/start script and manage.py exist. "
            "Ask which to start, then call launch_workspace with target 'npm' or 'django'."
        )
    if want_npm:
        if not npm_script or scripts is None:
            return None, "", "No npm dev or start script found."
        if shutil.which("npm") is None:
            return None, "", "npm was not found on PATH. Nothing was started."
        command = ["npm", "run", "dev"] if npm_script == "dev" else ["npm", "start"]
        detail = (
            f"--- LAUNCH WORKSPACE (NODE) ---\n"
            f"Directory: {path}\n"
            f"Command: {' '.join(command)}\n"
            f"package.json script: {scripts[npm_script]}\n"
            f"----------------------------"
        )
        return command, detail, " ".join(command)
    if want_django:
        if not has_manage:
            return None, "", "manage.py was not found."
        python_exe = _venv_python(path) or sys.executable
        command = [python_exe, "manage.py", "runserver"]
        detail = (
            f"--- LAUNCH WORKSPACE (DJANGO) ---\n"
            f"Directory: {path}\n"
            f"Command: {python_exe} manage.py runserver\n"
            f"-------------------------------"
        )
        return command, detail, "manage.py runserver"
    return None, "", "No allowlisted launcher found. Nothing was started."


@tool()
def inspect_workspace(path: str = ".") -> str:
    """Describe a project and which setup or launch actions are available.

    Read-only. Does not create files or start processes.

    Args:
        path: Project directory. Defaults to the current directory.
    """
    resolved = _directory(path)
    if resolved is None:
        return f"Directory not found: {path}"
    report = _report(resolved)
    _, _, launch_note = _launcher(resolved, "auto")
    return f"{report}\nLauncher: {launch_note}"


@tool(risk=RISK_HIGH)
def prepare_workspace(path: str = ".") -> str:
    """Create a virtualenv for a Python project that does not have one.

    Does not install dependencies, run package scripts, or execute arbitrary commands.
    Confirmation is required before the virtualenv is created.

    Args:
        path: Project directory. Defaults to the current directory.
    """
    resolved = _directory(path)
    if resolved is None:
        return f"Directory not found: {path}"
    report = _report(resolved)
    if not _is_python_project(resolved):
        return f"{report}\n\nNo Python project markers found. No changes made."
    if _venv_python(resolved):
        return f"{report}\n\nVirtualenv already present. No changes made."

    venv_path = os.path.join(resolved, "venv")
    action = (
        f"--- PREPARE WORKSPACE (VENV) ---\n"
        f"Directory: {resolved}\n"
        f"Command: {sys.executable} -m venv venv\n"
        f"Target: {venv_path}\n"
        f"Dependencies will not be installed.\n"
        f"--------------------------------"
    )
    result = execute([sys.executable, "-m", "venv", "venv"], cwd=resolved, action=action)
    return f"{report}\n\n{result}"


@tool(risk=RISK_HIGH)
def launch_workspace(path: str = ".", target: str = "auto") -> str:
    """Start an allowlisted dev server in a new console after confirmation.

    Allowlist: `npm run dev`, `npm start`, or `python manage.py runserver`.
    The command argument is never taken from the model as a shell string.

    Args:
        path: Project directory. Defaults to the current directory.
        target: auto, npm, or django. auto refuses when both Node and Django match.
    """
    resolved = _directory(path)
    if resolved is None:
        return f"Directory not found: {path}"
    command, detail, unavailable = _launcher(resolved, target)
    if command is None:
        return unavailable
    return spawn_console(command, cwd=resolved, action=detail)