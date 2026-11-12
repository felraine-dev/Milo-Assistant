"""Read-only git inspection and conventional commit drafts."""

from __future__ import annotations

import os
import subprocess

from milo.safety import tool

_MAX_DIFF_CHARS = 8000


def _run_git(repo_path: str, args: list[str]) -> tuple[bool, str]:
    if not os.path.isdir(repo_path):
        return False, f"Directory not found: {repo_path}"
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=repo_path,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=True,
            shell=False,
        )
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or str(exc)).strip()
        return False, f"Git error: {detail}"
    except FileNotFoundError:
        return False, "Git executable not found."
    return True, result.stdout.strip()


def _truncate(text: str) -> str:
    if len(text) <= _MAX_DIFF_CHARS:
        return text
    return text[:_MAX_DIFF_CHARS] + "\n...[diff truncated]"


def _parse_porcelain(payload: str) -> list[tuple[str, str]]:
    records = payload.split("\0")
    parsed: list[tuple[str, str]] = []
    index = 0
    while index < len(records):
        entry = records[index]
        if not entry:
            index += 1
            continue
        status = entry[:2]
        path = entry[3:] if len(entry) > 3 else entry[2:].lstrip()
        if "R" in status or "C" in status:
            index += 1
            original = records[index] if index < len(records) else ""
            path = f"{original} -> {path}"
        parsed.append((status, path.replace("\\", "/")))
        index += 1
    return parsed


def _new_path(path: str) -> str:
    return path.split(" -> ")[-1]


def _is_test_path(path: str) -> bool:
    parts = path.lower().split("/")
    filename = parts[-1]
    if filename.startswith("test_") or filename.endswith("_test.py"):
        return True
    return any(part in {"test", "tests", "testing"} for part in parts[:-1])


def _commit_type(files: list[tuple[str, str]]) -> str:
    paths = [_new_path(path).lower() for _, path in files]

    def every(predicate) -> bool:
        return bool(paths) and all(predicate(path) for path in paths)

    if every(lambda path: path.endswith(".md") or path.startswith("docs/")):
        return "docs"
    if every(_is_test_path):
        return "test"
    build_names = {
        "pyproject.toml",
        "requirements.txt",
        "package.json",
        "package-lock.json",
        "dockerfile",
    }
    if every(lambda path: path.split("/")[-1] in build_names):
        return "build"
    if every(lambda path: path.startswith(".github/") or path.startswith("ci/")):
        return "ci"
    if any(status[0] in {"A", "?"} or status[1] in {"A", "?"} for status, _ in files):
        return "feat"
    return "fix"


def _scope(paths: list[str]) -> str | None:
    if any("/" not in path for path in paths):
        return None
    tops = {path.split("/")[0] for path in paths}
    if len(tops) == 1:
        return next(iter(tops))
    return None


@tool()
def check_git_status(repo_path: str = ".") -> str:
    """Show modified and untracked files for a repository.

    Args:
        repo_path: Path to the local git repository. Defaults to the current directory.
    """
    ok, output = _run_git(repo_path, ["status", "-s"])
    if not ok:
        return output
    return output or "Working tree clean. No uncommitted changes."


@tool()
def get_git_history(repo_path: str = ".") -> str:
    """Show the current branch and the last five commits.

    Args:
        repo_path: Path to the local git repository. Defaults to the current directory.
    """
    ok, branch = _run_git(repo_path, ["branch", "--show-current"])
    if not ok:
        return branch
    branch_name = branch or "detached HEAD"

    ok, logs = _run_git(repo_path, ["log", "-n", "5", "--oneline"])
    if not ok:
        if "does not have any commits" in logs:
            return f"Current Branch: {branch_name}\n\nNo commits yet."
        return logs
    return f"Current Branch: {branch_name}\n\nRecent Commits:\n{logs or '(none)'}"


@tool()
def summarize_git_diff(repo_path: str = ".", staged: bool = False) -> str:
    """Summarize a repository diff with file stats and a truncated patch.

    Read-only. Use the result to explain the change in plain language.

    Args:
        repo_path: Path to the local git repository. Defaults to the current directory.
        staged: When true, summarize the staged diff instead of the working tree.
    """
    diff_args = ["diff", "--cached"] if staged else ["diff"]
    which = "staged" if staged else "unstaged"
    ok, stat = _run_git(repo_path, [*diff_args, "--stat"])
    if not ok:
        return stat
    ok, numstat = _run_git(repo_path, [*diff_args, "--numstat"])
    if not ok:
        return numstat
    if not stat and not numstat:
        return f"No {which} diff."

    insertions = 0
    deletions = 0
    file_count = 0
    for line in numstat.splitlines():
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        file_count += 1
        if parts[0].isdigit():
            insertions += int(parts[0])
        if parts[1].isdigit():
            deletions += int(parts[1])

    ok, patch = _run_git(repo_path, [*diff_args, "-U1"])
    if not ok:
        return patch
    header = (
        f"{which.capitalize()} diff: {file_count} files, "
        f"+{insertions} / -{deletions}"
    )
    return f"{header}\n\n{stat}\n\nPatch:\n{_truncate(patch or '(no patch text)')}"


@tool()
def draft_conventional_commit(repo_path: str = ".") -> str:
    """Draft a Conventional Commits message from the working tree.

    Does not stage, commit, or push. The message is a suggestion only.

    Args:
        repo_path: Path to the local git repository. Defaults to the current directory.
    """
    ok, payload = _run_git(repo_path, ["status", "--porcelain=v1", "-z"])
    if not ok:
        return payload
    files = _parse_porcelain(payload)
    if not files:
        return "Working tree clean. No commit message drafted."

    paths = [_new_path(path) for _, path in files]
    commit_type = _commit_type(files)
    scope = _scope(paths)
    all_added = all(status[0] in {"A", "?"} or status[1] in {"A", "?"} for status, _ in files)
    verb = "add" if all_added else "update"
    if len(paths) == 1:
        summary = f"{verb} {paths[0].split('/')[-1]}"
    else:
        summary = f"{verb} {len(paths)} files"
    prefix = f"{commit_type}({scope})" if scope else commit_type
    subject = f"{prefix}: {summary}"
    if len(subject) > 72:
        subject = subject[:69].rstrip() + "..."

    shown = paths[:20]
    body = "\n".join(f"- {path}" for path in shown)
    if len(paths) > 20:
        body += f"\n- ... {len(paths) - 20} more"
    return f"{subject}\n\n{body}\n\nDraft only. Nothing was committed."
