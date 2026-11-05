import datetime
import os
import platform


def _gui():
    """
    pyautogui pas laden wanneer het nodig is.

    Bovenaan importeren laat de hele assistent omvallen op een machine zonder
    scherm (headless start, SSH-sessie), terwijl de andere tools dan prima
    zouden werken.
    """
    import pyautogui
    return pyautogui


def take_screenshot():
    """Capture the screen and save it with a timestamp."""
    try:
        os.makedirs("data/screenshots", exist_ok=True)
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        path = f"data/screenshots/shot_{ts}.png"
        img = _gui().screenshot()
        img.save(path)
        return f"Schermafbeelding opgeslagen in {path}."
    except Exception as e:
        return f"Ik kon geen schermafbeelding maken: {e}"


def set_volume(direction: str):
    """Increase, decrease, or mute system volume."""
    try:
        gui = _gui()
        direction = direction.lower()
        if direction == "up":
            for _ in range(5):
                gui.press("volumeup")
            return "Volume omhoog."
        elif direction == "down":
            for _ in range(5):
                gui.press("volumedown")
            return "Volume omlaag."
        elif direction == "mute":
            gui.press("volumemute")
            return "Geluid gedempt of hersteld."
        return "Gebruik 'up', 'down' of 'mute'."
    except Exception as e:
        return f"Ik kon het volume niet aanpassen: {e}"


def lock_screen():
    """Lock the computer screen."""
    try:
        system = platform.system()
        if system == "Windows":
            import ctypes
            ctypes.windll.user32.LockWorkStation()
        elif system == "Darwin":
            os.system("pmset displaysleepnow")
        else:
            os.system("xdg-screensaver lock")
        return "Scherm vergrendeld."
    except Exception as e:
        return f"Ik kon het scherm niet vergrendelen: {e}"


def register_system_tools(registry):
    registry.register(
        name="take_screenshot",
        func=take_screenshot,
        description="Maak een schermafbeelding.",
    )

    registry.register(
        name="set_volume",
        func=set_volume,
        description="Pas het volume aan. direction is 'up', 'down' of 'mute'.",
        parameters={
            "type": "object",
            "properties": {
                "direction": {
                    "type": "string",
                    "description": "Een van: up, down, mute.",
                }
            },
            "required": ["direction"],
        },
    )

    registry.register(
        name="lock_screen",
        func=lock_screen,
        description="Vergrendel het scherm.",
        sensitive=True,   # 🔐 disruptive -> confirm first
    )