"""Immutable pre-registration binds held-out inputs and declared configuration choices."""
from .common import canonical,digest,utcnow,write_json,read_json


def configuration_identity(config):
    identity={k:v for k,v in config.items() if k not in ('out','resume','preregistration')}
    if config.get('artifact_provenance'):identity['frozen_artifact_identity']=read_json(config['artifact_provenance'])
    return identity


def preregister(path,dataset,configs,primary_outcomes,owner):
    if dataset['split']!='holdout':raise ValueError('Only a locked holdout split can be preregistered')
    if not owner or not primary_outcomes or not configs:raise ValueError('Owner, configurations and primary outcomes required')
    record={'version':'1.0','owner':owner,'created_utc':utcnow(),'dataset_sha256':dataset['sha256'],
            'configuration_sha256':[digest(configuration_identity(c)) for c in configs],
            'primary_outcomes':primary_outcomes,'missing_result_policy':'retain all failures; no successful-only winner',
            'comparison_direction':'candidate minus baseline','evidence_class':'P'}
    record['registration_sha256']=digest(record);write_json(path,record,exclusive=True);return record


def check_registration(record,dataset,config):
    core={k:v for k,v in record.items() if k!='registration_sha256'}
    if digest(core)!=record.get('registration_sha256'):raise ValueError('Registration integrity mismatch')
    if dataset['sha256']!=record['dataset_sha256']:raise ValueError('Registered dataset hash changed')
    if digest(configuration_identity(config)) not in record['configuration_sha256']:raise ValueError('Configuration differs from frozen registration')
    return True
