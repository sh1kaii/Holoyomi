import json
import numpy as np


from asr_interface import IAutomaticSpeechRecognition


from vosk import Model, KaldiRecognizer

class JapaneseASR(IAutomaticSpeechRecognition):
    def __init__(self, model_path):
        self.model = Model(model_path)
        self.recognizer = KaldiRecognizer(self.model, 16000)

    def recognize(self, audio_chunk):
        # audio_chunk: numpy array (float32)
        pcm = (audio_chunk * 32767).astype(np.int16).tobytes()

        if self.recognizer.AcceptWaveform(pcm):
            result = json.loads(self.recognizer.Result())
            return result.get("text", "")
        return ""
    

if __name__ == "__main__":
    asr = JapaneseASR("models/vosk-ja/vosk-model-small-ja-0.22")
    
    
    