"""Killable LIVE inference. The child owns Whisper and endpoint VAD, never files/UI."""
from __future__ import annotations

import multiprocessing as mp
import threading

from .transcription import LocalEnglishTranscriber, speech_has_ended


def _serve(connection, model_path, factory):
    try:
        model = factory(model_path)
        while True:
            operation, payload = connection.recv()
            if operation == "transcribe":
                result = model.transcribe(payload)
            elif operation == "boundary":
                samples, rate, pause = payload
                result = speech_has_ended(samples, rate, pause_s=pause)
            else:
                raise ValueError(f"Unknown inference operation: {operation}")
            connection.send((True, result))
    except (EOFError, BrokenPipeError):
        pass
    except Exception as exc:
        try:
            connection.send((False, f"{type(exc).__name__}: {exc}"))
        except (EOFError, BrokenPipeError, OSError):
            pass
    finally:
        connection.close()


class ProcessEnglishTranscriber:
    def __init__(self, model_path, *, model_factory=LocalEnglishTranscriber):
        # Obtain the existing settings without loading a native model in the UI process.
        self.configuration = dict(LocalEnglishTranscriber(model_path, model=object()).configuration)
        self.configuration.update(execution="spawn_process", stop_policy="cancel_without_flush")
        self._closed = False
        self._cancelled = threading.Event()
        self._rpc_lock = threading.Lock()
        context = mp.get_context("spawn")
        self._connection, child = context.Pipe()
        self._process = context.Process(target=_serve, args=(child, str(model_path), model_factory),
                                        name="live-whisper", daemon=True)
        try:
            self._process.start()
        except BaseException:
            self._connection.close()
            raise
        finally:
            child.close()

    def _request(self, operation, payload):
        with self._rpc_lock:
            if self._cancelled.is_set():
                raise RuntimeError("LIVE inference cancelled")
            self._connection.send((operation, payload))
            while not self._cancelled.is_set():
                if self._connection.poll(.025):
                    ok, result = self._connection.recv()
                    if not ok:
                        raise RuntimeError(result)
                    return result
                if not self._process.is_alive():
                    raise RuntimeError("LIVE inference process exited unexpectedly")
            raise RuntimeError("LIVE inference cancelled")

    def transcribe(self, chunk):
        return self._request("transcribe", chunk)

    def speech_boundary(self, samples, sample_rate, *, pause_s):
        return self._request("boundary", (samples, sample_rate, pause_s))

    def cancel(self):
        # Do not acquire the RPC lock: an inference/send may be blocked there.
        self._cancelled.set()
        if self._closed: return
        if self._process.is_alive():
            self._process.terminate()

    def close(self):
        if self._closed: return
        self.cancel()
        self._process.join(.5)
        if self._process.is_alive():
            self._process.kill()
            self._process.join(.5)
        if self._process.is_alive():
            raise RuntimeError("LIVE inference process could not be terminated")
        self._connection.close()
        self._process.close()
        self._closed = True
