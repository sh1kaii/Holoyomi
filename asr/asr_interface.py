from abc import ABC, abstractmethod


class IAutomaticSpeechRecognition(ABC):
    @abstractmethod
    def recognize(self, audio_chunk) -> str:
        """Transcribe the given audio file and return the text."""
        pass