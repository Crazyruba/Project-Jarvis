import subprocess
import platform
from datetime import datetime


def get_time():
    """Return the current date and time as a friendly string."""
    now = datetime.now()
    return now.strftime("Het is %A %d %B %Y, %H:%M uur.")


def open_app(app_name: str):
    """Open an application on the laptop by name."""
    system = platform.system()
    try:
        if system == "Windows":
            subprocess.Popen(["cmd", "/c", "start", "", app_name], shell=False)
        elif system == "Darwin":  # macOS
            subprocess.Popen(["open", "-a", app_name])
        else:  # Linux
            subprocess.Popen([app_name])
        return f"Ik open {app_name}."
    except Exception as e:
        return f"Ik kon {app_name} niet openen: {e}"


def register_basic_tools(registry):
    """Register all basic tools into the given registry."""
    registry.register(
        name="get_time",
        func=get_time,
        description="Geef de huidige datum en tijd.",
    )
    registry.register(
        name="open_app",
        func=open_app,
        description="Open een programma op de laptop op naam, bijvoorbeeld firefox of code.",
        parameters={
            "type": "object",
            "properties": {
                "app_name": {
                    "type": "string",
                    "description": "Naam van het programma.",
                }
            },
            "required": ["app_name"],
        },
    )