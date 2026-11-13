from milo.tools.terminal import run_linter, run_pytest

def test_terminal_tools_callable():
    """Verify that the terminal runner tools are defined and callable."""
    assert callable(run_linter)
    assert callable(run_pytest)

def test_linter_execution():
    """Run linter on a known file and verify output format."""
    output = run_linter("milo/tools/terminal.py")
    assert "Exit Code:" in output