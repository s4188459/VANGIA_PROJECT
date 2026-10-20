"""Opt-in real decoder smoke on generated silence, never a speech benchmark."""
import csv
import uuid
from pathlib import Path
from .adapters import preflight
from .audio import write_pcm
from .common import digest,utcnow,write_json
from .events import EventLog
from .storage import create_run,seal,write_jsonl
from .worker_client import WorkerClient


def smoke(config):
    checked=preflight({**config,'mode':'batch_file'});path=Path(config['out']);run_id=uuid.uuid4().hex
    manifest={'run_id':run_id,'schema_version':'1.0','language':'en','dataset_id':'generated-silence-diagnostic',
        'dataset_split':'synthetic_fixture','input_mode':'synthetic_fixture','created_utc':utcnow(),
        'evidence_class':'SYNTHETIC','status':'planned','model_id':checked['model_id'],'config':config,
        'model_config_id':digest(config),'source_urls':[],
        'missing_reasons':['no_real_speech','no_accuracy_evidence','no_live_presentation']}
    create_run(path,manifest);log=EventLog(path/'events.jsonl')
    def emit(kind,**kw):return log.emit(kind,run_id,'diagnostic','synthetic_fixture',**kw)
    metrics={'wer':None,'live_lag_p95_s':None,'evidence_class':'SYNTHETIC',
             'notice':'Real decoder on generated one-second silence only; no speech accuracy claim'}
    worker=None
    if checked['status']=='BLOCKED':state={'status':'blocked','reasons':checked['reasons'],'evidence_class':'SYNTHETIC'}
    else:
        audio=path/'generated-silence.wav';write_pcm(audio,b'\x00\x00'*16000)
        try:
            emit('model_load_started');worker=WorkerClient(config.get('worker_python'),path)
            loaded=worker.request('load',timeout=config.get('load_timeout_s',180),config=config)
            emit('model_loaded',payload=loaded['result']);write_json(path/'worker_provenance.json',loaded['result'])
            emit('inference_queued',chunk_id='silence');emit('inference_started',chunk_id='silence')
            response=worker.request('transcribe',timeout=config.get('inference_timeout_s',60),audio=str(audio.resolve()))
            emit('inference_finished',chunk_id='silence',payload={'service_ns':response['service_ns']})
            write_jsonl(path/'predictions.jsonl',[{'sample_id':'generated-silence','status':'completed',
                        'provenance_type':'simulated_fixture',**response['result']}])
            metrics.update(load_s=loaded['service_ns']/1e9,service_s=response['service_ns']/1e9,
                           output_word_count=len(response['result']['text'].split()))
            state={'status':'completed','evidence_class':'SYNTHETIC','actual_decoder_executed':True}
        except (RuntimeError,TimeoutError,OSError,ValueError) as exc:
            state={'status':'failed','reason':str(exc),'evidence_class':'SYNTHETIC'}
            emit('inference_error',payload={'reason':str(exc)})
        finally:
            if worker:
                write_json(path/'worker_resources.json',worker.resources)
                worker.close()
    emit('run_finished',payload=state);write_json(path/'state.json',state);write_json(path/'metrics.json',metrics)
    from .reports import report
    report(path);seal(path);return state
