import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import time
import threading
import queue
from holoyomi.ui.subtitle_window import SubtitleWindow
from holoyomi.asr.jp_asr import JapaneseASR
from holoyomi.audio.audio_capture import AudioCapture

# Placeholder classes
# class AudioCapture:
#     def get_chunk(self):
#         time.sleep(1)
#         return b"dummy_audio"

# class Translator:
#     def translate(self, text):
#         return f"EN: {text}"

def run_pipeline():
    audio = AudioCapture()
    asr = JapaneseASR(
        model_path="models/vosk-ja/vosk-model-small-ja-0.22"
    )
    window = SubtitleWindow()

    running = threading.Event()
    running.set()

    text_queue = queue.Queue()
    last_text = ""
    last_update = 0

    def processing_loop():
        while running.is_set():
            try:
                audio_chunk = audio.get_chunk()
                text = asr.recognize(audio_chunk)
                if text and text.strip() and text != last_text and time.time() - last_update > 1.0:
                    text_queue.put(text)
                    last_text = text
                    last_update = time.time()
            except Exception as e:
                text_queue.put("Error in processing")
            time.sleep(0.5)

    def ui_update_loop():
        try:
            while not text_queue.empty():
                text = text_queue.get_nowait()
                window.update_text(text)
        finally:
            window.root.after(100, ui_update_loop)

    processor = threading.Thread(target=processing_loop, daemon=True)
    processor.start()

    window.root.after(100, ui_update_loop)

    try:
        window.run()
    finally:
        running.clear()

if __name__ == "__main__":
    run_pipeline()
