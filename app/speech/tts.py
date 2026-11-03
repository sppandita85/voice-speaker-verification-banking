"""Text-to-speech with Piper. One voice model (.onnx + .onnx.json) per language."""
import io
import wave


class PiperTTS:
    def __init__(self, voice_paths: dict[str, str]):
        self.voice_paths = voice_paths
        self._voices = {}

    def _voice(self, language: str):
        if language not in self._voices:
            from piper import PiperVoice

            self._voices[language] = PiperVoice.load(self.voice_paths[language])
        return self._voices[language]

    def synthesize(self, text: str, language: str) -> bytes:
        voice = self._voice(language)
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wav_file:
            if hasattr(voice, "synthesize_wav"):  # piper-tts >= 1.3
                voice.synthesize_wav(text, wav_file)
            else:  # piper-tts 1.2
                voice.synthesize(text, wav_file)
        return buf.getvalue()
