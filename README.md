# Holoyomi — Phase 1 Prototype

Phase 1: Single-stream MVP (Japanese → English real-time translation)

## Project Structure

holoyomi/
├── main.py                # Entry point
├── config.py              # Language, font size, opacity (later)
├── audio/audio_capture.py # Mic / stream audio
├── asr/jp_asr.py          # Japanese speech-to-text
├── translate/jp_to_en.py  # Translation logic
├── ui/subtitle_window.py  # Floating text window
└── pipeline/runner.py     # Connects everything

## Quick start

- Install dependencies: `pip install -r requirements.txt`
- Run: `python holoyomi/main.py`

## Notes

- Phase 1 goals: single-stream real-time translation with low latency.