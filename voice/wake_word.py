import time
import numpy as np
import sounddevice as sd
from openwakeword.model import Model
import config


class WakeWordListener:
    """Always-on 'Hey Jarvis' listener with anti-feedback protection."""

    def __init__(self):
        print("🎙️  Wake word-model laden…")
        self.model = Model(
            wakeword_models=[config.WAKE_WORD_MODEL],
            inference_framework="onnx",
        )
        self.chunk = 1280  # 80ms @ 16kHz
        print("✅ Wake word klaar. Zeg 'Hey Jarvis'.")

    def _reset_model(self):
        """Clear openWakeWord's internal prediction buffer to stop stale re-triggers."""
        try:
            self.model.reset()
        except Exception:
            # Fallback for versions without reset(): manually clear buffers
            for k in self.model.prediction_buffer:
                self.model.prediction_buffer[k].clear()

    def wait_for_wake(self, warmup_frames: int = 15, should_stop=None):
        """
        Wacht op het wake word.

        `should_stop` wordt tussen de audioblokjes door gepolst; geeft die True
        terug, dan stopt het wachten en komt False terug. Zo kan push-to-talk
        of afsluiten ertussen komen in plaats van eeuwig te blijven hangen.
        """
        # 1. 🧠 Reset stale buffer so old audio can't re-trigger
        self._reset_model()

        with sd.InputStream(
            samplerate=config.SAMPLE_RATE,
            channels=1,
            dtype="int16",
            blocksize=self.chunk,
        ) as stream:
            # 2. 🚿 Flush leftover mic audio (JARVIS's own voice tail, echo)
            for _ in range(warmup_frames):
                stream.read(self.chunk)
            self._reset_model()  # reset again after flushing

            # 3. 👂 Now actually listen
            while True:
                if should_stop is not None and should_stop():
                    return False

                audio, _ = stream.read(self.chunk)
                audio = np.frombuffer(audio, dtype=np.int16)

                prediction = self.model.predict(audio)
                score = prediction.get(config.WAKE_WORD_MODEL, 0)

                if score >= config.WAKE_THRESHOLD:
                    print(f"   🔔 Wake word gehoord (score: {score:.2f})")
                    # 4. 🕒 Small cooldown so the trigger word itself
                    #    doesn't bleed into the command recording
                    time.sleep(0.3)
                    return True