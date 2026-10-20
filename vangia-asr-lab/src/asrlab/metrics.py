"""Deterministic edit alignment; raw and historically compatible normalized scores."""
import unicodedata
from collections import defaultdict
from statistics import mean

NORMALIZATION='nfkc-casefold-punctuation-to-space-v1'


def normalize(text):
    text=unicodedata.normalize('NFKC',text).casefold().replace('’',"'")
    return ' '.join(''.join(' ' if unicodedata.category(c).startswith('P') and c!="'" else c for c in text).split())


def align(ref,hyp):
    # One byte per backpointer; rolling integer rows. Ties prefer substitution, deletion, insertion.
    n,m=len(ref),len(hyp)
    if (n+1)*(m+1)>30_000_000: raise ValueError('Alignment too large; score by reference utterance')
    back=[bytearray([2]*(m+1)) for _ in range(n+1)]
    previous=list(range(m+1))
    for i,a in enumerate(ref,1):
        current=[i]+[0]*m; back[i][0]=1
        for j,b in enumerate(hyp,1):
            costs=(previous[j-1]+(a!=b),previous[j]+1,current[j-1]+1)
            op=min(range(3),key=costs.__getitem__)
            current[j]=costs[op]; back[i][j]=op
        previous=current
    rows=[]; i,j=n,m
    while i or j:
        op=back[i][j] if i and j else (1 if i else 2)
        if op==0:
            rows.append({'op':'equal' if ref[i-1]==hyp[j-1] else 'S','reference_index':i-1,'hypothesis_index':j-1,'reference':ref[i-1],'hypothesis':hyp[j-1]}); i-=1;j-=1
        elif op==1:
            rows.append({'op':'D','reference_index':i-1,'hypothesis_index':None,'reference':ref[i-1],'hypothesis':None}); i-=1
        else:
            rows.append({'op':'I','reference_index':None,'hypothesis_index':j-1,'reference':None,'hypothesis':hyp[j-1]}); j-=1
    return list(reversed(rows))


def distance(ref,hyp):
    if not ref: return len(hyp)
    masks={}
    for i,c in enumerate(ref): masks[c]=masks.get(c,0)|(1<<i)
    pos,neg,dist=~0,0,len(ref); last=1<<(len(ref)-1)
    for c in hyp:
        equal=masks.get(c,0); xv=equal|neg
        xh=(((equal&pos)+pos)^pos)|equal
        ph=neg|~(xh|pos); mh=pos&xh
        dist+=bool(ph&last)-bool(mh&last)
        ph=(ph<<1)|1; mh<<=1
        pos=mh|~(xv|ph); neg=ph&xv
    return dist


def score(reference,hypothesis,normalize=True):
    raw_ref,raw_hyp=reference,hypothesis
    if normalize:
        reference=globals()['normalize'](reference); hypothesis=globals()['normalize'](hypothesis)
    ref,hyp=reference.split(),hypothesis.split(); alignment=align(ref,hyp)
    counts={op:sum(x['op']==op for x in alignment) for op in ('S','D','I')}
    chars_ref=''.join(ref) if normalize else raw_ref
    chars_hyp=''.join(hyp) if normalize else raw_hyp
    ce=distance(chars_ref,chars_hyp); errors=sum(counts.values())
    return {**counts,'N':len(ref),'errors':errors,'wer':errors/len(ref) if ref else None,
            'cer':ce/len(chars_ref) if chars_ref else None,'character_errors':ce,'reference_characters':len(chars_ref),
            'alignment':alignment,'reference_tokens':ref,'hypothesis_tokens':hyp,
            'hallucinated_words':len(hyp) if not ref else 0,'definition_version':NORMALIZATION if normalize else 'raw-whitespace-v1'}


def _index(rows):
    result={}
    for r in rows:
        if r['sample_id'] in result: raise ValueError('duplicate sample ID')
        result[r['sample_id']]=r
    return result


def _aggregate(rows):
    n=sum(r['N'] for r in rows); errors=sum(r['errors'] for r in rows)
    nc=sum(r['reference_characters'] for r in rows); ce=sum(r['character_errors'] for r in rows)
    nonempty=[r['wer'] for r in rows if r['wer'] is not None]
    domains=defaultdict(list)
    for r in rows: domains[r.get('domain','unknown')].append(r)
    bydomain={k:sum(x['errors'] for x in v)/sum(x['N'] for x in v) if sum(x['N'] for x in v) else None for k,v in domains.items()}
    return {'wer_micro':errors/n if n else None,'wer_macro_utterance':mean(nonempty) if nonempty else None,
            'wer_macro_domain':mean(v for v in bydomain.values() if v is not None) if any(v is not None for v in bydomain.values()) else None,
            'domains':bydomain,'numerator':errors,'denominator':n,'cer':ce/nc if nc else None,
            'character_errors':ce,'reference_characters':nc,
            **{op:sum(r[op] for r in rows) for op in ('S','D','I')}}


def corpus_score(references,predictions):
    refs,preds=_index(references),_index(predictions)
    if refs.keys()!=preds.keys(): raise ValueError('Corpus must be paired on identical sample IDs; include explicit failed rows')
    output={}; missing=[]
    for normalized in (True,False):
        rows=[]
        for key,ref in refs.items():
            pred=preds[key]
            if pred.get('status') in ('failed','blocked','cancelled'):
                if normalized: missing.append({'sample_id':key,'reason':pred.get('error',pred['status'])})
                continue
            rows.append({'sample_id':key,'domain':ref.get('domain','unknown'),'session_id':ref.get('session_id'),
                         'pcm_sha256':ref.get('pcm_sha256'),'reference_revision':ref.get('reference_revision'),
                         **score(ref['text'],pred['text'],normalize=normalized)})
        agg=_aggregate(rows)
        if normalized: output['conditional_success']=dict(agg)
        if missing: agg={**agg,'wer_micro':None,'missing_reason':'incomplete_corpus'}
        output['normalized' if normalized else 'raw']={**agg,'per_sample':rows}
    return {**output,'missing':missing,'completion_fraction':(len(refs)-len(missing))/len(refs) if refs else 0,
            'definition_version':NORMALIZATION,'evidence_class':'I'}


def paired_score_rows(references,predictions):
    """Keep failed observations even when both compared configurations fail on the same IDs."""
    refs,preds=_index(references),_index(predictions)
    if refs.keys()!=preds.keys():raise ValueError('Corpus must be paired; retain failed rows')
    rows=[]
    for sid,ref in refs.items():
        pred=preds[sid];status=pred.get('status','completed')
        counts=score(ref['text'],pred['text']) if status=='completed' else {
            'N':len(normalize(ref['text']).split()),'errors':None,'missing_reason':pred.get('error',status)}
        rows.append({k:v for k,v in {
            'sample_id':sid,'session_id':ref.get('session_id'),'pcm_sha256':ref.get('pcm_sha256'),
            'reference_revision':ref.get('reference_revision'),'status':status,**counts}.items()
            if k not in ('alignment','reference_tokens','hypothesis_tokens')})
    return rows


def term_metrics(reference,hypothesis,glossary):
    def occurrences(text,alternatives):
        tokens=normalize(text).split();spans=set()
        for alternative in alternatives:
            term=normalize(alternative).split()
            if not term:raise ValueError('Empty glossary term')
            for i in range(len(tokens)-len(term)+1):
                if tokens[i:i+len(term)]==term:spans.add((i,i+len(term)))
        return len(spans)
    tp=fp=fn=0;terms=[]
    for term,equivalents in glossary.items():
        n=occurrences(reference,[term]+equivalents);p=occurrences(hypothesis,[term]+equivalents)
        matched=min(n,p);tp+=matched;fp+=max(0,p-n);fn+=max(0,n-p)
        terms.append({'term':term,'reference_occurrences':n,'hypothesis_occurrences':p,'TP':matched})
    return {'TP':tp,'FP':fp,'FN':fn,'precision':tp/(tp+fp) if tp+fp else None,
            'recall':tp/(tp+fn) if tp+fn else None,'terms':terms,
            'method':'normalized occurrence counts; equivalence glossary explicit; no semantic inference'}


def semantic_metrics(annotations,reference_words):
    adjudicated=[a for a in annotations if a['review_status']=='adjudicated' and a.get('adjudicator_id')]
    severe=[a for a in adjudicated if a['severity'] in ('material_meaning_change','critical')]
    return {'adjudicated_count':len(adjudicated),'unadjudicated_count':len(annotations)-len(adjudicated),
            'meaning_changing_errors_per_1000_words':len(severe)*1000/reference_words if reference_words else None,
            'critical_count':sum(a['severity']=='critical' for a in adjudicated),
            'categories':{k:sum(a['category']==k for a in adjudicated) for k in ('term','number','unit','negation','silence_hallucination','whole_turn_omission')},
            'reference_words':reference_words,'sampling_caveat':'Rate refers to reviewed spans; report review sampling coverage separately'}
