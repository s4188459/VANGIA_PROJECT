"""PCM-only audio scheduling, deliberate overlap merging and consented capture."""
import math
import time
import wave
from .common import sha256,write_json
from pathlib import Path
from .metrics import normalize


def read_pcm(path):
    if Path(path).suffix.lower()!='.wav':raise ValueError('Audio WAV required; video is excluded')
    with wave.open(str(path),'rb') as f:
        if (f.getnchannels(),f.getsampwidth(),f.getframerate())!=(1,2,16000):raise ValueError('Require mono PCM16 16 kHz WAV')
        return f.readframes(f.getnframes()),f.getframerate()


def write_pcm(path,pcm,rate=16000):
    with wave.open(str(path),'wb') as f:
        f.setparams((1,2,rate,0,'NONE','not compressed'));f.writeframes(pcm)


def windows(pcm,rate,chunk_s,overlap_s=0):
    if not math.isfinite(chunk_s) or not math.isfinite(overlap_s) or chunk_s<=0 or not 0<=overlap_s<chunk_s:
        raise ValueError('Require 0 <= overlap < positive chunk seconds')
    size=max(1,round(chunk_s*rate));hop=max(1,round((chunk_s-overlap_s)*rate));n=len(pcm)//2
    for start in range(0,n,hop):
        end=min(start+size,n)
        yield {'start_sample':start,'end_sample':end,'sample_rate_hz':rate,'pcm':pcm[start*2:end*2]}
        if end==n:break


def adaptive_windows(pcm,rate,min_s=.5,max_s=3,silence_s=.3,threshold=.015):
    """Declared RMS-energy VAD boundary heuristic; retains silence and every original sample."""
    from array import array
    if not 0<min_s<=max_s or silence_s<=0 or not 0<=threshold<=1:raise ValueError('Invalid VAD settings')
    samples=array('h',pcm);frame=max(1,int(rate*.02));start=0;silent=0
    for pos in range(0,len(samples),frame):
        block=samples[pos:pos+frame];end=pos+len(block)
        rms=math.sqrt(sum(v*v for v in block)/len(block))/32768
        silent=silent+len(block) if rms<threshold else 0
        if end-start>=int(max_s*rate) or (end-start>=int(min_s*rate) and silent>=int(silence_s*rate)):
            yield {'start_sample':start,'end_sample':end,'sample_rate_hz':rate,'pcm':pcm[start*2:end*2],
                   'segmentation_policy':'rms-energy-vad-v1'}
            start=end;silent=0
    if start<len(samples):yield {'start_sample':start,'end_sample':len(samples),'sample_rate_hz':rate,'pcm':pcm[start*2:],
                                 'segmentation_policy':'rms-energy-vad-v1'}


def paced_chunks(path,chunk_s=2,overlap_s=0,cancel=None,vad=None):
    pcm,rate=read_pcm(path);origin=time.monotonic_ns()
    if vad and overlap_s:raise ValueError('VAD adaptive overlap is unsupported; use zero overlap')
    scheduled=adaptive_windows(pcm,rate,**vad) if vad else windows(pcm,rate,chunk_s,overlap_s)
    for c in scheduled:
        target=origin+int(c['end_sample']/rate*1e9)
        while time.monotonic_ns()<target:
            if cancel and cancel():return
            time.sleep(min(.02,(target-time.monotonic_ns())/1e9) if target>time.monotonic_ns() else 0)
        yield {**c,'input_mode':'paced_replay','capture_origin_ns':origin,'captured_ns':target,'released_ns':time.monotonic_ns()}


def merge(previous,current,overlap=False):
    left,right=previous.split(),current.split();k=0
    if overlap:
        for n in range(1,min(len(left),len(right))+1):
            if [normalize(w) for w in left[-n:]]==[normalize(w) for w in right[:n]]:k=n
    return {'text':' '.join(left+right[k:]),'deduplicated_tokens':k,
            'policy':'prefix-dedupe-v1' if overlap else 'plain-concat-v1',
            'uncertainty':'lexical overlap can remove genuine repetition; review seams' if k else None}


def capture(path,seconds,consent_record_id,device=None,source='microphone'):
    if not consent_record_id:raise ValueError('Recording requires explicit consent')
    if source!='microphone':raise ValueError('BLOCKED: loopback requires explicit supported WASAPI device worker')
    if not 0<seconds<=3600:raise ValueError('Duration must be between 0 and 3600 s')
    if Path(path).exists():raise FileExistsError(path)
    import sounddevice as sd
    frames=[];gaps=[];origin=time.monotonic_ns()
    def callback(indata,count,time_info,status):
        frames.append(bytes(indata))
        if status:gaps.append({'monotonic_ns':time.monotonic_ns(),'status':str(status)})
    with sd.RawInputStream(samplerate=16000,channels=1,dtype='int16',device=device,callback=callback):
        time.sleep(seconds)
    write_pcm(path,b''.join(frames))
    return {'source':source,'input_mode':'live_microphone','capture_origin_ns':origin,'gaps':gaps,
            'consent_record_id':consent_record_id,'clock_uncertainty':'device transport not calibrated'}


def frame_windows(frames,rate,chunk_s,overlap_s=0):
    if not 0<=overlap_s<chunk_s:raise ValueError('Invalid live chunk/overlap')
    size=round(chunk_s*rate);hop=round((chunk_s-overlap_s)*rate)
    if hop<1:raise ValueError('Chunk hop below one sample')
    buffer=bytearray();start=0;last_end=0
    for frame in frames:
        if len(frame)%2:raise ValueError('Incomplete PCM16 frame')
        buffer.extend(frame)
        while len(buffer)>=size*2:
            end=start+size
            yield {'start_sample':start,'end_sample':end,'sample_rate_hz':rate,'pcm':bytes(buffer[:size*2])}
            last_end=end;del buffer[:hop*2];start+=hop
    if buffer and start+len(buffer)//2>last_end:
        yield {'start_sample':start,'end_sample':start+len(buffer)//2,'sample_rate_hz':rate,'pcm':bytes(buffer)}


def live_chunks(path,seconds,consent_record_id,device,chunk_s=2,overlap_s=0,cancel=None):
    """Local microphone PCM recording and chunk release on one measured acquisition clock."""
    if not consent_record_id:raise ValueError('Explicit capture consent required')
    if device is None:raise ValueError('Choose an explicit input device')
    if not 0<seconds<=3600:raise ValueError('Capture duration outside (0,3600]')
    if Path(path).exists():raise FileExistsError(path)
    import sounddevice as sd
    rate=16000;origin=time.monotonic_ns();gaps=[]
    def frames():
        n=0;target=int(seconds*rate)
        with wave.open(str(path),'wb') as recording:
            recording.setparams((1,2,rate,0,'NONE','not compressed'))
            with sd.RawInputStream(samplerate=rate,channels=1,dtype='int16',device=device,blocksize=320) as stream:
                while n<target:
                    if cancel and cancel():break
                    count=min(320,target-n);data,overflow=stream.read(count);data=bytes(data)
                    if overflow:gaps.append({'end_sample':n+count,'reason':'input_overflow','dropped_samples':None})
                    recording.writeframesraw(data);n+=count;yield data
    try:
        for c in frame_windows(frames(),rate,chunk_s,overlap_s):
            yield {**c,'input_mode':'live_microphone','capture_origin_ns':origin,
                   'captured_ns':time.monotonic_ns(),'released_ns':time.monotonic_ns(),
                   'clock_uncertainty':'uncalibrated input device buffering','gaps':list(gaps)}
    finally:
        if Path(path).exists():write_json(str(path)+'.capture.json',{'consent_record_id':consent_record_id,'device':device,
            'source':'microphone','input_mode':'live_microphone','capture_origin_ns':origin,'gaps':gaps,
            'audio_sha256':sha256(path),'clock_uncertainty':'device acquisition buffering uncalibrated'})


def augment_noise(source,noise,out,snr_db,seed):
    """Controlled additive-noise derivative; never changes the clean original."""
    from array import array
    import random
    if Path(out).exists():raise FileExistsError(out)
    pcm,rate=read_pcm(source);np,noise_rate=read_pcm(noise)
    signal=array('h',pcm);background=array('h',np)
    if not signal or not background:raise ValueError('Nonempty source and noise required')
    offset=random.Random(seed).randrange(len(background))
    aligned=[background[(i+offset)%len(background)] for i in range(len(signal))]
    srms=math.sqrt(sum(x*x for x in signal)/len(signal));nrms=math.sqrt(sum(x*x for x in aligned)/len(aligned))
    if not nrms or not srms:raise ValueError('SNR is undefined for silent signal/noise')
    gain=srms/(nrms*10**(snr_db/20));mixed=[round(s+n*gain) for s,n in zip(signal,aligned)]
    clipped=sum(not -32768<=v<=32767 for v in mixed)
    write_pcm(out,array('h',[max(-32768,min(32767,v)) for v in mixed]).tobytes(),rate)
    metadata={'provenance_type':'derived_audio','parent_audio_sha256':sha256(source),'noise_sha256':sha256(noise),
              'audio_sha256':sha256(out),'requested_snr_db':snr_db,'seed':seed,'noise_offset_samples':offset,
              'clipped_samples':clipped,'transform':'additive-noise-pcm16-v1','actual_snr_valid':clipped==0}
    write_json(str(out)+'.augmentation.json',metadata);return metadata
