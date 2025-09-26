# speech/asr_streaming.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Generator, Optional, Iterable
import queue
import os

# Mic
try:
    import pyaudio  # type: ignore
except Exception:
    pyaudio = None  # type: ignore

# Optional VAD (noise/silence gating)
try:
    import webrtcvad  # type: ignore
except Exception:
    webrtcvad = None  # type: ignore


@dataclass
class ASRResult:
    text: str
    is_final: bool
    confidence: float  # 0..1; 0.0 if provider doesnΓÇÖt supply for partials


class _MicStream:
    """16-bit mono PCM microphone stream ΓåÆ byte chunks via a queue."""
    def __init__(self, sample_rate: int = 16000, device_index: Optional[int] = None, chunk_ms: int = 30):
        if pyaudio is None:
            raise RuntimeError("PyAudio is required for streaming mic. Install with: pip install pyaudio")
        self.pa = pyaudio.PyAudio()
        self.rate = int(sample_rate)
        self.device_index = device_index
        self.chunk_ms = int(chunk_ms)
        # 16-bit mono ΓåÆ 2 bytes per frame
        self.chunk_bytes = int(self.rate * 2 * self.chunk_ms / 1000)
        self._q: "queue.Queue[bytes]" = queue.Queue(maxsize=32)
        self._closed = True
        self._stream = None

    def start(self):
        if not self._closed:
            return
        self._closed = False
        frames_per_buffer = self.chunk_bytes // 2  # bytes / 2 bytes-per-frame = frames
        self._stream = self.pa.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=self.rate,
            input=True,
            input_device_index=self.device_index,
            frames_per_buffer=frames_per_buffer,
            stream_callback=self._cb,
        )
        self._stream.start_stream()

    def _cb(self, in_data, frame_count, time_info, status):
        if not self._closed:
            try:
                self._q.put_nowait(in_data)
            except queue.Full:
                # Drop if slow consumer; better than blocking
                pass
        return (None, pyaudio.paContinue)

    def generator(self) -> Iterable[bytes]:
        while not self._closed:
            try:
                chunk = self._q.get(timeout=0.5)
                yield chunk
            except queue.Empty:
                continue

    def stop(self):
        if self._closed:
            return
        self._closed = True
        try:
            if self._stream is not None:
                self._stream.stop_stream()
                self._stream.close()
        finally:
            self._stream = None
            try:
                self.pa.terminate()
            except Exception:
                pass


# -------------------- Vosk Provider --------------------

class _VoskStreamingProvider:
    def __init__(self, language: str, sample_rate: int, model_path: Optional[str] = None):
        try:
            import vosk  # type: ignore
        except Exception as e:
            raise RuntimeError("vosk not available. Install with: pip install vosk") from e
        self.vosk = vosk
        mp = model_path or os.environ.get("VOSK_MODEL_PATH", "")
        if not mp or not os.path.isdir(mp):
            raise RuntimeError(
                "Vosk model not found. Pass model_path=... or set VOSK_MODEL_PATH to a valid directory."
            )
        self.model = self.vosk.Model(mp)
        self.sample_rate = int(sample_rate)
        self.rec = self.vosk.KaldiRecognizer(self.model, self.sample_rate)
        # Allow partials (if supported by model)
        try:
            self.rec.SetWords(True)
        except Exception:
            pass

    def start(self):
        pass

    def stop(self):
        pass

    def stream_results(self, audio_iter: Iterable[bytes]) -> Iterable[ASRResult]:
        import json
        rec = self.rec
        for chunk in audio_iter:
            if rec.AcceptWaveform(chunk):
                j = json.loads(rec.Result())
                txt = (j.get("text") or "").strip()
                if txt:
                    conf = float(j.get("confidence", 0.0) or 0.0)  # some models omit this
                    yield ASRResult(text=txt, is_final=True, confidence=conf)
            else:
                j = rec.PartialResult()
                try:
                    p = json.loads(j).get("partial", "").strip()
                except Exception:
                    p = ""
                if p:
                    yield ASRResult(text=p, is_final=False, confidence=0.0)


# -------------------- StreamingASR facade --------------------

class StreamingASR:
    """
    Provider-agnostic wrapper (Vosk-only build).
    language: e.g. 'en-US', 'hi-IN' (Vosk ignores this and uses the model you load)
    """
    def __init__(
        self,
        provider: str,                    # kept for signature compatibility; must be 'vosk'
        language: str,
        sample_rate: int = 16000,
        device_index: Optional[int] = None,
        enable_webrtc: bool = True,
        vad_level: int = 2,               # 0ΓÇô3 (aggressiveness) if webrtcvad is installed
        vosk_model_path: Optional[str] = None,
        chunk_ms: int = 30,               # 10/20/30 required for webrtcvad
    ):
        # Only Vosk is supported in this build
        if (provider or "vosk").lower() != "vosk":
            raise ValueError("This build supports only 'vosk' as asr_provider.")
        self.language = language or "en-US"
        self.sample_rate = int(sample_rate)
        self.device_index = device_index
        self.enable_webrtc = bool(enable_webrtc)
        self.vad_level = int(max(0, min(3, vad_level)))
        self.vosk_model_path = vosk_model_path

        # Mic
        self._mic = _MicStream(sample_rate=self.sample_rate, device_index=self.device_index, chunk_ms=chunk_ms)

        # VAD (optional)
        self._vad = None
        if self.enable_webrtc and webrtcvad is not None:
            try:
                self._vad = webrtcvad.Vad(self.vad_level)
            except Exception:
                self._vad = None

        # Provider (Vosk)
        self._provider = _VoskStreamingProvider(
            language=self.language,
            sample_rate=self.sample_rate,
            model_path=self.vosk_model_path
        )

        self._running = False

    def _gate_silence(self, chunk: bytes) -> Optional[bytes]:
        """
        If VAD is available, drop non-speech frames. Otherwise pass-through.
        webrtcvad expects 10/20/30ms frames in 16-bit mono at 8/16/32/48 kHz ΓÇö we use 30ms @ 16kHz.
        """
        if not self._vad:
            return chunk
        # Quick energy check to avoid analyzing pure zeros
        try:
            energy = 0
            for i in range(0, len(chunk), 2):
                sample = int.from_bytes(chunk[i:i+2], byteorder="little", signed=True)
                energy += abs(sample)
            if energy < 50 * (len(chunk) // 2):
                return None
            return chunk if self._vad.is_speech(chunk, self.sample_rate) else None
        except Exception:
            return chunk

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._provider.start()
        self._mic.start()

    def stop(self) -> None:
        if not self._running:
            return
        self._running = False
        try:
            self._mic.stop()
        finally:
            try:
                self._provider.stop()
            except Exception:
                pass

    def _audio_iter(self) -> Iterable[bytes]:
        for chunk in self._mic.generator():
            gated = self._gate_silence(chunk)
            if gated:
                yield gated
            if not self._running:
                break

    def results(self) -> Generator[ASRResult, None, None]:
        """
        Yields partial + final ASRResult while running.
        """
        if not self._running:
            raise RuntimeError("StreamingASR not started. Call start() first.")
        for res in self._provider.stream_results(self._audio_iter()):
            if not self._running:
                break
            yield res
