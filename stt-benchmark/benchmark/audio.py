"""Decode once at import so every model receives the same canonical waveform."""
import io
import wave

AUDIO_EXTENSIONS = {'.wav', '.mp3', '.m4a', '.flac', '.ogg', '.opus', '.aac', '.webm'}
SAMPLE_RATE = 16000
MAX_SECONDS = 600
PREPROCESSING = 'pyav-mono-pcm16-16000-v1'


def canonical_audio(data):
    import av
    # RIFF size catches incomplete ordinary WAVs even if the decoder tolerates
    # missing tail bytes. Other containers are checked by their decoder.
    if data[:4] == b'RIFF' and data[8:12] == b'WAVE':
        if int.from_bytes(data[4:8], 'little') + 8 > len(data):
            raise ValueError('WAV audio data is truncated.')
        try:
            with wave.open(io.BytesIO(data), 'rb') as source:
                if (source.getframerate(), source.getnchannels(), source.getsampwidth()) == (SAMPLE_RATE, 1, 2):
                    count = source.getnframes()
                    if not 0 < count <= SAMPLE_RATE * MAX_SECONDS:
                        raise ValueError('Each sample must be longer than 0 and at most 600 seconds.')
                    if len(source.readframes(count)) != count * 2:
                        raise ValueError('WAV audio data is truncated.')
                    return data, count / SAMPLE_RATE, {'codec':'pcm_s16le', 'sample_rate':SAMPLE_RATE,'channels':1}
        except wave.Error:
            pass  # Float WAV and other encodings are handled by PyAV below.
    try:
        pcm = bytearray()
        with av.open(io.BytesIO(data), mode='r') as container:
            if len(container.streams.audio) != 1:
                raise ValueError('Each file must contain exactly one audio stream; select a track first for multitrack files.')
            stream = container.streams.audio[0]
            metadata = {'codec':stream.codec_context.name, 'sample_rate':stream.codec_context.sample_rate,
                        'channels':stream.codec_context.channels}
            resampler = av.AudioResampler(format='s16', layout='mono', rate=SAMPLE_RATE)
            def append(frames):
                for frame in frames:
                    if len(pcm) + frame.samples * 2 > SAMPLE_RATE * MAX_SECONDS * 2:
                        raise ValueError('Each sample must not exceed 600 seconds after decoding.')
                    pcm.extend(frame.to_ndarray().astype('<i2', copy=False).tobytes())
            for frame in container.decode(stream):
                frame.pts = None
                append(resampler.resample(frame))
            append(resampler.resample(None))
        if not pcm:
            raise ValueError('No audio samples could be decoded.')
        output = io.BytesIO()
        with wave.open(output,'wb') as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(SAMPLE_RATE)
            wav.writeframes(pcm)
        return output.getvalue(), len(pcm)/(2*SAMPLE_RATE), metadata
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError(f'Could not decode audio: {exc}') from exc

