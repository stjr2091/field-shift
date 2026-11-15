"""Validation checks for voice requests; model runtimes are not required."""

from __future__ import annotations

import io
import unittest
import wave

import voice


def make_wav(sample_rate=voice.SAMPLE_RATE, channels=1, sample_width=2, frames=160):
    output = io.BytesIO()
    with wave.open(output, "wb") as wav_file:
        wav_file.setnchannels(channels)
        wav_file.setsampwidth(sample_width)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(b"\0" * frames * channels * sample_width)
    return output.getvalue()


class ReadWavTests(unittest.TestCase):
    def test_reads_mono_16khz_pcm(self):
        frames, sample_rate = voice.read_wav(make_wav())
        self.assertEqual(len(frames), 320)
        self.assertEqual(sample_rate, 16_000)

    def test_rejects_wrong_sample_rate(self):
        with self.assertRaisesRegex(voice.VoiceRequestError, "sample rate"):
            voice.read_wav(make_wav(sample_rate=48_000))

    def test_rejects_stereo_audio(self):
        with self.assertRaisesRegex(voice.VoiceRequestError, "mono"):
            voice.read_wav(make_wav(channels=2))

    def test_rejects_invalid_wav(self):
        with self.assertRaisesRegex(voice.VoiceRequestError, "valid WAV"):
            voice.read_wav(b"not audio")

    def test_rejects_long_recordings(self):
        with self.assertRaisesRegex(voice.VoiceRequestError, "30 seconds"):
            voice.read_wav(make_wav(frames=voice.SAMPLE_RATE * 31))


if __name__ == "__main__":
    unittest.main()
