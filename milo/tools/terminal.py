import sys
import subprocess
from milo.safety import tool, RISK_HIGH

@tool(risk=RISK_HIGH)
def run_pytest(test_path: str = ".") -> str:
    """Run pytest using the active Python interpreter (sys.executable) to inherit virtual environment packages."""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", test_path, "-v"],
            capture_output=True,
            text=True,
            timeout=120
        )
        
        output = f"Exit Code: {result.returncode}\n--- Stdout ---\n{result.stdout}\n--- Stderr ---\n{result.stderr}"
        return output
    except subprocess.TimeoutExpired:
        return "Error: Pytest execution timed out after 120 seconds."
    except Exception as e:
        return f"Error executing pytest: {e!s}"
        
@tool(risk=RISK_HIGH)
def run_linter(path: str = ".") -> str:
    """Run Ruff linter to check codebase formatting and style issues."""
    try:
        result = subprocess.run(
            ["ruff", "check", path],
            check=False,
            capture_output=True,
            text=True,
            timeout=60,
        )
        output = f"Exit Code: {result.returncode}\n--- Linter Output ---\n{result.stdout}\n{result.stderr}"
        return output
    except subprocess.TimeoutExpired:
        return "Error: Linter execution timed out after 60 seconds."
    except Exception as e:
        return f"Error executing linter: {e!s}"
