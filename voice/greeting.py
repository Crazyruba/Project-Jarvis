import os
from datetime import datetime
import config


def maybe_greet(tts):
    """Groet de eigenaar hooguit één keer per dag."""
    today = datetime.now().strftime("%Y-%m-%d")
    last = None

    if os.path.exists(config.GREETING_STATE_PATH):
        with open(config.GREETING_STATE_PATH, "r") as f:
            last = f.read().strip()

    if last != today:
        hour = datetime.now().hour
        if hour < 12:
            part = "Good morning"
        elif hour < 17:
            part = "Good afternoon"
        else:
            part = "Good evening"

        tts.speak(f"{part}, {config.OWNER_NAME}! Ik ben online en klaar om te helpen.")

        os.makedirs(os.path.dirname(config.GREETING_STATE_PATH), exist_ok=True)
        with open(config.GREETING_STATE_PATH, "w") as f:
            f.write(today)