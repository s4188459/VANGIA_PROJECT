"""Exact-checkpoint adapters. Dependencies and weights are always local and explicit."""
import gc
import importlib.metadata
import importlib.util
import os
import platform
import sys
from pathlib import Path
from .common import model_record,sha256,digest,read_json

MODULES={'faster-whisper':'faster_whisper','nemo':'nemo','qwen-asr':'qwen_asr','transformers-ctc':'transformers'}


def discover(backend):
    return {'batch':backend in MODULES,'independent_chunks':backend in MODULES,'native_streaming':False,
            'native_streaming_reason':'No locally validated stateful adapter; independent chunking is explicitly distinct',
            'timestamp_output':backend=='faster-whisper','required_accelerator':'backend/device dependent',
            'worker_platform':platform.system(),'backend_installed':bool(importlib.util.find_spec(MODULES[backend]))}


def preflight(config):
    model=model_record(config['model_id'])
    if config.get('language','en')!='en':raise ValueError('English only')
    if 'diagnostic_retry' in model['roles'] and not config.get('diagnostic_retry'):
        raise ValueError('Deferred checkpoint requires explicit diagnostic_retry opt-in')
    backend=config.get('backend',model['legacy_backend'])
    if backend!=model['legacy_backend']:raise ValueError('Backend substitution is not supported; use the recorded family adapter')
    caps=discover(backend);reasons=[]
    mode=config.get('mode','batch_file')
    if mode=='native_streaming':reasons.append('native_streaming not supported by this local adapter')
    elif mode not in ('batch_file','paced_replay','live_microphone','live_loopback'):raise ValueError('Unsupported run mode')
    if mode in ('live_microphone','live_loopback'):
        if not config.get('capture_consent_record_id'):reasons.append('Explicit capture consent required')
        if config.get('capture_device') is None:reasons.append('Explicit capture device required')
        if not 0<config.get('capture_duration_s',0)<=3600:reasons.append('Capture duration must be (0,3600] seconds')
        if not importlib.util.find_spec('sounddevice'):reasons.append('Missing capture package sounddevice')
        if mode=='live_loopback':reasons.append('BLOCKED: WASAPI loopback capture is not supported by the sounddevice input adapter; use explicit audio replay')
        if config.get('vad'):reasons.append('Adaptive VAD for live capture is unavailable; use fixed windows or paced VAD replay')
    if not config.get('worker_python') and not caps['backend_installed']:reasons.append(f'Missing backend package: {backend}')
    if config.get('worker_python') and not Path(config['worker_python']).is_file():reasons.append('Missing worker Python executable')
    weights=Path(config.get('weights_path','__missing_weights__'))
    if not weights.exists():reasons.append('Missing local weights_path; automatic downloads disabled')
    provenance=config.get('artifact_provenance')
    if not provenance:reasons.append('Missing artifact_provenance: checkpoint, immutable revision and expected file hashes')
    elif weights.exists():
        try:
            identity=read_json(provenance)
            if identity['model_id']!=model['canonical_model_id']:raise ValueError('checkpoint mismatch')
            if not identity.get('revision') or identity['revision'] in ('main','latest'):raise ValueError('immutable revision required')
            files=identity.get('files',{})
            if not files:raise ValueError('weight file hashes required')
            base=weights if weights.is_dir() else weights.parent
            for name,expected in files.items():
                p=(base/name).resolve()
                if not p.is_relative_to(base.resolve()) or not p.is_file() or sha256(p)!=expected:raise ValueError(f'artifact hash mismatch: {name}')
            actual={p.relative_to(base).as_posix() for p in (weights.rglob('*') if weights.is_dir() else [weights]) if p.is_file()}
            if not actual.issubset(files):raise ValueError('All model artifact files must be hashed')
        except (KeyError,ValueError,OSError) as exc:reasons.append(f'Invalid weights provenance: {exc}')
    if config.get('device','cpu') not in ('cpu','cuda'):raise ValueError('device must be cpu or cuda')
    if config.get('context_policy','none')!='none':reasons.append('Requested history/context adapter is unsupported')
    return {'status':'BLOCKED' if reasons else 'READY','reasons':reasons,'capabilities':caps,'backend':backend,'model_id':model['canonical_model_id']}


class Adapter:
    def __init__(self,config):
        self.config=config; self.record=model_record(config['model_id'])
        self.backend=config.get('backend',self.record['legacy_backend']);self.model=None

    def load(self):
        # Refuse all network resolution, including ancillary tokenizer/VAD downloads.
        os.environ['HF_HUB_OFFLINE']='1';os.environ['TRANSFORMERS_OFFLINE']='1';os.environ['HF_HUB_DISABLE_TELEMETRY']='1'
        c=self.config; target=str(Path(c['weights_path']).resolve());device=c.get('device','cpu')
        if self.backend=='faster-whisper':
            from faster_whisper import WhisperModel
            self.model=WhisperModel(target,device=device,compute_type=c.get('precision','int8'),
                                   cpu_threads=c.get('threads',4),local_files_only=True)
        else:
            import torch
            torch.set_num_threads(c.get('threads',4))
            if device=='cuda' and not torch.cuda.is_available():raise RuntimeError('CUDA unavailable')
            dtype=getattr(torch,c.get('precision','float32'))
            if self.backend=='qwen-asr':
                from qwen_asr import Qwen3ASRModel
                self.model=Qwen3ASRModel.from_pretrained(target,dtype=dtype,device_map=device,
                          max_inference_batch_size=1,max_new_tokens=c.get('max_new_tokens',4096))
            elif self.backend=='nemo':
                import nemo.collections.asr as asr
                p=Path(target)
                if p.is_dir():
                    files=list(p.glob('*.nemo'))
                    if len(files)!=1:raise ValueError('NeMo requires exactly one local .nemo archive')
                    p=files[0]
                self.model=asr.models.ASRModel.restore_from(str(p),map_location=device).to(device=device,dtype=dtype).eval()
            else:
                from transformers import AutoProcessor,AutoModelForCTC
                self.processor=AutoProcessor.from_pretrained(target,local_files_only=True,trust_remote_code=False)
                self.model=AutoModelForCTC.from_pretrained(target,local_files_only=True,trust_remote_code=False,torch_dtype=dtype).to(device).eval()
                self.processor.tokenizer.set_target_lang('eng')
                self.model.load_adapter('eng',local_files_only=True)
        identity=read_json(c['artifact_provenance'])
        distribution={'nemo':'nemo_toolkit','transformers-ctc':'transformers'}.get(self.backend,self.backend)
        return {'model_id':self.record['canonical_model_id'],'revision':identity['revision'],'weights_sha256':digest(identity['files']),
                'backend':self.backend,'backend_version':importlib.metadata.version(distribution),
                'python':sys.version,'platform':platform.platform(),'native_streaming':False}

    def transcribe_file(self,path,settings=None):
        c=settings or self.config
        if self.backend=='faster-whisper':
            segments,info=self.model.transcribe(str(path),language='en',task='transcribe',
                beam_size=c.get('beam_size',5),vad_filter=c.get('vad_filter',False),
                word_timestamps=True,condition_on_previous_text=c.get('condition_on_previous_text',False))
            rows=[{'start_s':s.start,'end_s':s.end,'text':s.text,
                   'words':[{'word':w.word,'start_s':w.start,'end_s':w.end,'probability':w.probability} for w in (s.words or [])]} for s in segments]
            return {'text':' '.join(s['text'].strip() for s in rows),'segments':rows,'word_timestamps_quality':'model_estimated'}
        if self.backend=='qwen-asr':
            rows=self.model.transcribe(audio=str(path),language='English')
            return {'text':' '.join(r.text for r in rows),'segments':None,'word_timestamps_quality':'not_supported'}
        if self.backend=='nemo':
            kwargs={'batch_size':1}
            if self.record['key']=='canary_v2':kwargs.update(source_lang='en',target_lang='en',task='asr',pnc=True)
            rows=self.model.transcribe([str(path)],**kwargs)
            if isinstance(rows,tuple):rows=rows[0]
            return {'text':' '.join(r if isinstance(r,str) else r.text for r in rows),'segments':None,'word_timestamps_quality':'not_measured'}
        import numpy as np
        import torch
        from .audio import read_pcm
        pcm,rate=read_pcm(path);audio=np.frombuffer(pcm,dtype='<i2').astype('float32')/32768
        texts=[]
        for start in range(0,len(audio),30*rate):
            inputs=self.processor(audio[start:start+30*rate],sampling_rate=rate,return_tensors='pt')
            inputs={k:v.to(device=self.model.device,dtype=self.model.dtype) if v.is_floating_point() else v.to(self.model.device) for k,v in inputs.items()}
            with torch.inference_mode():ids=self.model(**inputs).logits.argmax(-1)
            texts.append(self.processor.batch_decode(ids,skip_special_tokens=True)[0])
        return {'text':' '.join(texts),'segments':None,'word_timestamps_quality':'not_supported','internal_chunk_s':30}

    def transcribe_chunk(self,path,state=None):return self.transcribe_file(path)
    def health(self):return {'loaded':self.model is not None,'backend':self.backend}
    def unload(self):self.model=None;gc.collect()
