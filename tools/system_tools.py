import subprocess
import psutil

def get_system_health() -> str:
    """Checks the laptop's current CPU usage, RAM usage, and battery percentage."""
    cpu = psutil.cpu_percent(interval=1)
    ram = psutil.virtual_memory().percent
    battery = psutil.sensors_battery()
    
    bat_str = f"{battery.percent}% ({'Plugged in' if battery.power_plugged else 'On battery'})" if battery else "N/A"
    
    return f"CPU Usage: {cpu}% | RAM Usage: {ram}% | Battery: {bat_str}"

def check_git_status(repo_path: str = ".") -> str:
    """Runs 'git status -s' in the specified directory to see modified or untracked files.
    
    Args:
        repo_path: Path to the local git repository. Defaults to current directory ('.').
    """
    try:
        result = subprocess.run(
            ["git", "status", "-s"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=True
        )
        output = result.stdout.strip()
        return output if output else "Working tree clean. No uncommitted changes."
    except subprocess.CalledProcessError as e:
        return f"Git error: {e.stderr.strip()}"
    except FileNotFoundError:
        return f"Directory not found: {repo_path}"