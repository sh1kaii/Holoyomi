<<<<<<< HEAD
"""
Holoyomi Configuration
"""
import os

## AUDIO SETTINGS
AUDIO_FILE = r"e:\ホロライブ\holocon_events\sample.mp4"
CHUNK_DURATION = 1.0
SAMPLERATE = 16000

## ASR SETTINGS
ASR_MODEL_PATH = r"E:/Holoyomi Project/Phase 1 Prototype/vosk-model-small-ja-0.22"
if not os.path.exists(ASR_MODEL_PATH):
    print(f"[WARNING] ASR model not found at: {ASR_MODEL_PATH}")

## TRANSLATION SETTINGS
USE_TRANSLATION = True
DEEPL_API_KEY = os.environ.get("DEEPL_API_KEY")
if USE_TRANSLATION and not DEEPL_API_KEY:
    print("[WARNING] Translation enabled but DEEPL_API_KEY not set")

## UI SETTINGS
DEFAULT_FONT_SIZE = 26
DEFAULT_TEXT_OPACITY = 1.0
DEFAULT_SUBTITLE_MARGIN = 0.05
DEFAULT_VOLUME = 80
DEFAULT_WINDOW_WIDTH = 960
DEFAULT_WINDOW_HEIGHT = 600

## DEBUG SETTINGS
DEBUG_MODE = True
SHOW_ASR_OUTPUT = True
SHOW_TRANSLATION_OUTPUT = True

## ADVANCED SETTINGS
TRANSLATION_MAX_RETRIES = 2
TRANSLATION_TIMEOUT = 10
USE_TRANSLATION_CACHE = True
TEMP_AUDIO_SUFFIX = "_holoyomi_temp.wav"

## VALIDATION
def validate_config():
    """Validate configuration and print warnings."""
    issues = []
    if USE_TRANSLATION and not DEEPL_API_KEY:
        issues.append("Translation enabled but DEEPL_API_KEY not set")
    if not os.path.exists(ASR_MODEL_PATH):
        issues.append(f"ASR model not found: {ASR_MODEL_PATH}")
    if CHUNK_DURATION <= 0:
        issues.append("CHUNK_DURATION must be positive")
    if SAMPLERATE != 16000:
        issues.append("SAMPLERATE should be 16000 for Vosk")
    if issues:
        print("[CONFIG WARNINGS]")
        for issue in issues:
            print(f"  - {issue}")
        return False
    print("[CONFIG] All settings validated successfully")
    return True
if __name__ != "__main__":
    if DEBUG_MODE:
        validate_config()
=======
# Configuration settings
>>>>>>> 4c3e32737f364236d02eb6f18f7d604f08a93f41
