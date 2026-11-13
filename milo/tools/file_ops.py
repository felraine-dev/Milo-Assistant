import os
import difflib
from pathlib import Path
from milo.safety import RISK_HIGH, tool, confirm

WORKSPACE_ROOT = Path(os.getcwd()).resolve()

def _validate_path(file_path: str) -> Path:
    """Ensure the target path stays strictly inside the workspace root."""
    target_path = (WORKSPACE_ROOT / file_path).resolve()
    if not target_path.is_relative_to(WORKSPACE_ROOT):
        raise ValueError(f"Security Error: Access denied for path outside workspace: {file_path}")
    return target_path

def _safe_read_text(file_path: Path) -> str:
    """Safely read text handling various encodings, BOMs, and legacy formats."""
    for enc in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            return file_path.read_text(encoding=enc)
        except UnicodeDecodeError:
            continue
    # Ultimate fallback if all decoders fail
    return file_path.read_bytes().decode("latin-1", errors="replace")

def _colorize_diff(diff_text: str) -> str:
    """Transform a plain unified diff into a GitHub-style colored terminal diff."""
    colored_lines = []
    for line in diff_text.splitlines():
        if line.startswith("+") and not line.startswith("+++"):
            # Green for added lines
            colored_lines.append(f"\033[32m{line}\033[0m")
        elif line.startswith("-") and not line.startswith("---"):
            # Red for deleted lines
            colored_lines.append(f"\033[31m{line}\033[0m")
        elif line.startswith("@@"):
            # Cyan for chunk/hunk location headers
            colored_lines.append(f"\033[36m{line}\033[0m")
        elif line.startswith("---") or line.startswith("+++"):
            # Bold for file paths
            colored_lines.append(f"\033[1m{line}\033[0m")
        else:
            # Dim gray for unchanged context lines
            colored_lines.append(f"\033[90m{line}\033[0m")
    return "\n".join(colored_lines)

def _get_diff(old_content: str, new_content: str, filepath: str) -> str:
    """Generate a GitHub-style colored unified diff between old and new content."""
    diff = difflib.unified_diff(
        old_content.splitlines(),
        new_content.splitlines(),
        fromfile=f"a/{filepath}",
        tofile=f"b/{filepath}",
        lineterm=""
    )
    raw_diff = "\n".join(diff)
    if not raw_diff:
        return "(No textual differences)"
    return _colorize_diff(raw_diff)

@tool(risk=RISK_HIGH)
def write_file(path: str, content: str) -> str:
    """
    Create a new file or completely overwrite an existing file with new content.
    Marked as RISK_HIGH to require manual user confirmation and diff preview.
    """
    try:
        file_path = _validate_path(path)
        
        if file_path.exists():
            old_content = _safe_read_text(file_path)
            diff_text = _get_diff(old_content, content, path)
            action_desc = f"OVERWRITE FILE: {path}\n\n--- Diff Preview ---\n{diff_text}\n--------------------"
        else:
            action_desc = f"CREATE NEW FILE: {path} ({len(content)} characters)"

        if not confirm(action_desc):
            return f"Cancelled: User aborted writing to {path}."
            
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")
        return f"Successfully wrote {len(content)} characters to {path}"
    except Exception as e:
        return f"Error writing file {path}: {str(e)}"

@tool(risk=RISK_HIGH)
def patch_code(path: str, target: str, replacement: str) -> str:
    """
    Perform a precise search-and-replace code patch on an existing file.
    Marked as RISK_HIGH to require manual user confirmation and diff preview.
    """
    try:
        file_path = _validate_path(path)
        if not file_path.exists():
            return f"Error: File {path} does not exist."
            
        original_content = _safe_read_text(file_path)
        
        if target not in original_content:
            return f"Error: Target text block not found in {path}. Make sure the target string matches exactly."
            
        updated_content = original_content.replace(target, replacement, 1)
        
        diff_text = _get_diff(original_content, updated_content, path)
        action_desc = f"PATCH FILE: {path}\n\n--- Diff Preview ---\n{diff_text}\n--------------------"
        
        if not confirm(action_desc):
            return f"Cancelled: User aborted patching {path}."
            
        file_path.write_text(updated_content, encoding="utf-8")
        
        return f"Successfully patched {path}."
    except Exception as e:
        return f"Error patching file {path}: {str(e)}"

@tool(risk=RISK_HIGH)
def delete_file(path: str) -> str:
    """
    Permanently delete a file from the workspace.
    Marked as RISK_HIGH to require manual user confirmation.
    """
    try:
        file_path = _validate_path(path)
        if not file_path.exists():
            return f"Error: File {path} does not exist."
        if not file_path.is_file():
            return f"Error: {path} is not a valid file."
            
        action_desc = f"Permanently delete file: {path}"
        if not confirm(action_desc):
            return f"Cancelled: User aborted deleting {path}."
            
        file_path.unlink()
        return f"Successfully deleted {path}."
    except Exception as e:
        return f"Error deleting file {path}: {str(e)}"