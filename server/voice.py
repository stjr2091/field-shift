"""Local DeepSpeech transcription and Piper text-to-speech helpers."""

from __future__ import annotations

import io
import os
import sys
import struct
import threading
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEEPSPEECH_MODEL = Path(
    os.environ.get(
        "DEEPSPEECH_MODEL_PATH",
        str(ROOT / "DeepSpeech" / "deepspeech-0.9.3-models.pbmm"),
    )
)
PIPER_MODEL = Path(
    os.environ.get("PIPER_MODEL_PATH", str(ROOT / "piper" / "etc" / "test_voice.onnx"))
)
PIPER_RUNTIME = ROOT / "piper" / "src" / "python_run"
SAMPLE_RATE = 16_000
MAX_AUDIO_BYTES = 5_000_000
MAX_AUDIO_SECONDS = 30
MAX_SPEECH_CHARACTERS = 1_600


class VoiceRequestError(ValueError):
    """A voice request has invalid or unsupported input."""


class VoiceUnavailableError(RuntimeError):
    """A local speech runtime or its model is unavailable."""


_deepspeech_model = None
_piper_voice = None
_deepspeech_lock = threading.Lock()
_piper_lock = threading.Lock()


def read_wav(payload: bytes) -> tuple[bytes, int]:
    """Validate a browser-produced, mono, 16 kHz, 16-bit PCM WAV file."""
    try:
        with wave.open(io.BytesIO(payload), "rb") as wav_file:
            if wav_file.getcomptype() != "NONE":
                raise VoiceRequestError("Audio must be uncompressed PCM WAV.")
            if wav_file.getnchannels() != 1:
                raise VoiceRequestError("Audio must be mono.")
            if wav_file.getsampwidth() != 2:
                raise VoiceRequestError("Audio must use 16-bit samples.")
            sample_rate = wav_file.getframerate()
            if sample_rate != SAMPLE_RATE:
                raise VoiceRequestError(f"Audio must use a {SAMPLE_RATE} Hz sample rate.")
            frame_count = wav_file.getnframes()
            if frame_count == 0:
                raise VoiceRequestError("The recording contains no audio.")
            if frame_count > SAMPLE_RATE * MAX_AUDIO_SECONDS:
                raise VoiceRequestError(f"Recordings must be {MAX_AUDIO_SECONDS} seconds or shorter.")
            return wav_file.readframes(frame_count), sample_rate
    except (wave.Error, EOFError, struct.error) as error:
        raise VoiceRequestError("The recording is not a valid WAV file.") from error


def _get_deepspeech_model():
    global _deepspeech_model
    if _deepspeech_model is not None:
        return _deepspeech_model

    with _deepspeech_lock:
        if _deepspeech_model is not None:
            return _deepspeech_model
        if not DEEPSPEECH_MODEL.is_file():
            raise VoiceUnavailableError("The configured DeepSpeech model file was not found.")
        try:
            from deepspeech import Model
        except (ImportError, OSError) as error:
            raise VoiceUnavailableError(
                "DeepSpeech is not installed. Install the optional voice dependencies "
                "in a supported Python environment."
            ) from error
        try:
            model = Model(str(DEEPSPEECH_MODEL))
            scorer_path = os.environ.get("DEEPSPEECH_SCORER_PATH")
            if scorer_path:
                if not Path(scorer_path).is_file():
                    raise VoiceUnavailableError("The configured DeepSpeech scorer file was not found.")
                model.enableExternalScorer(scorer_path)
        except VoiceUnavailableError:
            raise
        except Exception as error:
            raise VoiceUnavailableError("DeepSpeech could not load its model or scorer.") from error
        _deepspeech_model = model
        return model


def transcribe(payload: bytes) -> str:
    """Transcribe one validated recording using the configured DeepSpeech model."""
    frames, _ = read_wav(payload)
    model = _get_deepspeech_model()
    with _deepspeech_lock:
        try:
            import numpy as np

            return str(model.stt(np.frombuffer(frames, dtype=np.int16))).strip()
        except VoiceUnavailableError:
            raise
        except Exception as error:
            raise VoiceUnavailableError("DeepSpeech could not transcribe this recording.") from error


def _get_piper_voice():
    global _piper_voice
    if _piper_voice is not None:
        return _piper_voice

    with _piper_lock:
        if _piper_voice is not None:
            return _piper_voice
        if not PIPER_MODEL.is_file():
            raise VoiceUnavailableError("The configured Piper voice model file was not found.")
        if not Path(f"{PIPER_MODEL}.json").is_file():
            raise VoiceUnavailableError("The configured Piper voice configuration file was not found.")
        if not PIPER_RUNTIME.is_dir():
            raise VoiceUnavailableError("The Piper runtime is not present in this project.")
        sys.path.insert(0, str(PIPER_RUNTIME))
        try:
            from piper.voice import PiperVoice

            _piper_voice = PiperVoice.load(PIPER_MODEL)
        except (ImportError, OSError) as error:
            raise VoiceUnavailableError(
                "Piper dependencies are not installed. Install the optional voice dependencies."
            ) from error
        except Exception as error:
            raise VoiceUnavailableError("Piper could not load its voice model.") from error
        return _piper_voice


def synthesize(text: str) -> bytes:
    """Synthesize a short English phrase as WAV audio using Piper."""
    phrase = text.strip()
    if not phrase:
        raise VoiceRequestError("text is required.")
    if len(phrase) > MAX_SPEECH_CHARACTERS:
        raise VoiceRequestError(f"text must be {MAX_SPEECH_CHARACTERS} characters or shorter.")

    voice = _get_piper_voice()
    with _piper_lock:
        try:
            output = io.BytesIO()
            with wave.open(output, "wb") as wav_file:
                voice.synthesize(phrase, wav_file)
            audio = output.getvalue()
        except Exception as error:
            raise VoiceUnavailableError("Piper could not synthesize the requested speech.") from error
    if not audio:
        raise VoiceUnavailableError("Piper returned an empty audio response.")
    return audio
