import numpy as np
from pydub import AudioSegment

class AudioFileCapture:
    def __init__(self, filename, chunk_duration=1.0, samplerate=16000):
        self.filename = filename
        self.samplerate = samplerate
        self.chunk_size = int(chunk_duration * samplerate)
        # Load audio file (mp3, wav, mp4, etc.)
        audio = AudioSegment.from_file(filename)
        audio = audio.set_channels(1).set_frame_rate(samplerate)
        self.samples = np.array(audio.get_array_of_samples()).astype(np.float32) / 32768.0
        self.total_samples = len(self.samples)
        self.position = 0

    def get_chunk(self):
        if self.position >= self.total_samples:
            return None
        end = min(self.position + self.chunk_size, self.total_samples)
        chunk = self.samples[self.position:end]
        self.position = end
        return chunk
