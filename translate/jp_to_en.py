<<<<<<< HEAD
import requests
import os
import time
from googletrans import Translator as GoogleTranslator

# Translation cache
_translation_cache = {}

# Translation config
DEEPL_API_KEY = os.environ.get("DEEPL_API_KEY")
DEEPL_URL = "https://api-free.deepl.com/v2/translate"

_google_translator = GoogleTranslator()


def sync_translate_jp_to_en(jp_text: str, max_retries=2) -> str:
    jp_text = jp_text.strip()
    if not jp_text:
        return ""
    if jp_text in _translation_cache:
        return _translation_cache[jp_text]

    if not DEEPL_API_KEY:
        print("[Translation Error] DeepL API key not set. Set DEEPL_API_KEY environment variable.")
        print("Example: export DEEPL_API_KEY='your-key-here'")
        return "[No API Key]"

    for attempt in range(max_retries + 1):
        try:
            params = {
                "auth_key": DEEPL_API_KEY,
                "text": jp_text,
                "source_lang": "JA",
                "target_lang": "EN"
            }
            response = requests.post(DEEPL_URL, data=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            translations = data.get("translations", [])
            if translations:
                en_text = translations[0].get("text", "[No Translation]")
                _translation_cache[jp_text] = en_text
                return en_text
            else:
                print(f"[Translation Warning] No translation returned for: {jp_text}")
                return "[No Translation]"
        except requests.Timeout:
            if attempt < max_retries:
                print(f"[Translation] Timeout, retrying ({attempt + 1}/{max_retries})...")
                time.sleep(0.5)
            else:
                print(f"[Translation Error] Timeout after {max_retries} retries: {jp_text}")
                return "[Translation Timeout]"
        except requests.HTTPError as e:
            if e.response.status_code == 403:
                print("[Translation Error] Invalid API key or quota exceeded")
                return "[Invalid API Key]"
            elif e.response.status_code == 456:
                print("[Translation Error] Quota exceeded")
                return "[Quota Exceeded]"
            else:
                print(f"[Translation Error] HTTP {e.response.status_code}: {e}")
                return f"[HTTP Error {e.response.status_code}]"
        except Exception as e:
            if attempt < max_retries:
                print(f"[Translation] Error, retrying ({attempt + 1}/{max_retries}): {e}")
                time.sleep(0.5)
            else:
                print(f"[Translation Error] Failed after {max_retries} retries: {e}")
                return "[Translation Failed]"
    return "[Translation Failed]"


class JPToENTranslator:
    def __init__(self):
        self.cache = _translation_cache

    def translate(self, jp_text: str) -> str:
        """
        Translate Japanese text to English.
        """
        if not DEEPL_API_KEY:
            print("[WARNING] DeepL API key not set. Translation will fail.")
            print("Set DEEPL_API_KEY environment variable to enable translation.")
        return sync_translate_jp_to_en(jp_text)

    def clear_cache(self):
        """Clear translation cache."""
        global _translation_cache
        _translation_cache.clear()

    def get_cache_size(self):
        """Get number of cached translations."""
        return len(_translation_cache)
=======
# Translation module
>>>>>>> 4c3e32737f364236d02eb6f18f7d604f08a93f41
