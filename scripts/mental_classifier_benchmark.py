#!/usr/bin/env python3
"""Offline, grouped TR/EN/DE routing benchmark; no paid service or user records.

Transformer candidates require an explicitly provisioned, fingerprinted official
snapshot. Missing models are reported as blocked, never silently substituted.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import resource
import re
import statistics
import sys
from time import perf_counter

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'services/core-api'))
from mental_structured import classify,FlowState
from conversation_control import conversation_control
from mental_provider import check_mental_crisis


def scores(expected,predicted):
    tp=sum(len(e&p) for e,p in zip(expected,predicted))
    fp=sum(len(p-e) for e,p in zip(expected,predicted))
    fn=sum(len(e-p) for e,p in zip(expected,predicted))
    precision=tp/(tp+fp) if tp+fp else 0
    recall=tp/(tp+fn) if tp+fn else 0
    return {'precision':round(precision,4),'recall':round(recall,4),'f1':round(2*precision*recall/(precision+recall),4) if precision+recall else 0,
            'exactMatch':round(sum(e==p for e,p in zip(expected,predicted))/len(expected),4),'falsePositiveObjectives':fp,'missedObjectives':fn}


def rule_prediction(row):
    state=FlowState(language=row['language'],lastNode=row.get('contextNode'))
    result=classify(row['text'],state)
    return set(result['fulfilled']),result


def shared_intent(row,result):
    if check_mental_crisis(row['text'],False)['isCrisis']:return 'crisis'
    control=conversation_control(row['text'])
    if control:return control['sessionAction']
    for field,intent in [('listenOnly','listen'),('skip','skip'),('topicChange','topic-change'),('wantsSteps','steps')]:
        if result[field]:return intent
    return 'uncertain' if result['uncertain'] else 'answer'


class SemanticObjectives:
    def __init__(self,path,training):
        os.environ['HF_HUB_OFFLINE']='1';os.environ['TRANSFORMERS_OFFLINE']='1'
        path=Path(path).resolve(strict=True)
        self.manifest=json.loads((path/'verified-model.json').read_text())
        if self.manifest['repository'] not in ('sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2','intfloat/multilingual-e5-small'):
            raise ValueError('UNAPPROVED_SEMANTIC_MODEL')
        if not re.fullmatch('[0-9a-f]{40}',self.manifest['revision']):raise ValueError('IMMUTABLE_REVISION_REQUIRED')
        required={'config.json','model.safetensors','tokenizer.json','tokenizer_config.json','special_tokens_map.json','sentence_bert_config.json'}
        if set(self.manifest['files'])!=required:raise ValueError('COMPLETE_VERIFIED_SNAPSHOT_REQUIRED')
        for name,digest in self.manifest['files'].items():
            file=(path/name).resolve(strict=True)
            if not file.is_relative_to(path):raise ValueError('SEMANTIC_MODEL_PATH')
            with file.open('rb') as stream:actual=hashlib.file_digest(stream,'sha256').hexdigest()
            if actual!=digest:
                raise ValueError('SEMANTIC_MODEL_INTEGRITY')
        import numpy as np
        import torch
        from transformers import AutoModel,AutoTokenizer
        self.np=np;self.torch=torch
        torch.set_num_threads(2)
        self.tokenizer=AutoTokenizer.from_pretrained(str(path),local_files_only=True,trust_remote_code=False)
        self.model=AutoModel.from_pretrained(str(path),local_files_only=True,trust_remote_code=False,use_safetensors=True).eval()
        self.is_e5=self.manifest['repository'].startswith('intfloat/')
        self.labels=[set(row['objectives']) for row in training]
        self.examples=self.encode([r['text'] for r in training])

    def encode(self,texts):
        vectors=[]
        for text in texts:
            # E5 semantic similarity convention uses query: for both sides.
            tokens=self.tokenizer(('query: '+text) if self.is_e5 else text,return_tensors='pt',truncation=True,max_length=128)
            with self.torch.inference_mode():hidden=self.model(**tokens).last_hidden_state
            mask=tokens['attention_mask'].unsqueeze(-1)
            mean=(hidden*mask).sum(1)/mask.sum(1).clamp(min=1)
            vectors.append(self.torch.nn.functional.normalize(mean,p=2,dim=1).numpy()[0])
        return self.np.asarray(vectors)

    def predict(self,row,threshold):
        _,base=rule_prediction(row)
        # Existing crisis and explicit lifecycle/preferences remain higher priority.
        if shared_intent(row,base) not in ('answer','uncertain'):return set(),base
        similarities=self.examples@self.encode([row['text']])[0]
        result={node for node in {n for labels in self.labels for n in labels}
                if max((float(s) for s,labels in zip(similarities,self.labels) if node in labels),default=-1)>=threshold}
        base={**base,'fulfilled':sorted(result),'uncertain':not bool(result)}
        return result,base


def evaluate(rows,predict):
    expected=[];predicted=[];results=[];timings=[]
    for row in rows:
        start=perf_counter();objectives,result=predict(row)
        intent=shared_intent(row,result)
        timings.append((perf_counter()-start)*1000)
        expected.append(set(row['objectives']));predicted.append(objectives)
        results.append({'id':row['id'],'language':row['language'],'expected':row['objectives'],'predicted':sorted(objectives),
                        'expectedIntent':row['intent'],'predictedIntent':intent})
    report=scores(expected,predicted)
    report.update(intentAccuracy=round(sum(r['expectedIntent']==r['predictedIntent'] for r in results)/len(results),4),
                  jointRoutingAccuracy=round(sum(set(r['expected'])==set(r['predicted']) and r['expectedIntent']==r['predictedIntent'] for r in results)/len(results),4),
                  latencyMs={'median':round(statistics.median(timings),3),'p95':round(sorted(timings)[int(len(timings)*.95)],3)},
                  processPeakRSSKiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,results=results)
    report['byLanguage']={lang:scores([set(r['expected']) for r in results if r['language']==lang],[set(r['predicted']) for r in results if r['language']==lang]) for lang in ('tr','en','de')}
    return report


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--corpus',type=Path,default=ROOT/'tests/fixtures/mental-routing-v2.json')
    parser.add_argument('--model',choices=['rules','semantic'],default='rules');parser.add_argument('--model-path',type=Path);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();raw=args.corpus.read_bytes();corpus=json.loads(raw);rows=corpus['rows']
    # Split by scenario group, including every translation, never by individual row.
    groups={split:{r['scenarioId'] for r in rows if r['split']==split} for split in ('train','dev','test')}
    if any(groups[a]&groups[b] for a,b in [('train','dev'),('train','test'),('dev','test')]):raise ValueError('SCENARIO_SPLIT_LEAKAGE')
    test=[r for r in rows if r['split']=='test']
    report={'corpusSHA256':hashlib.sha256(raw).hexdigest(),'provenance':corpus['provenance'],'model':args.model,'paidServices':False,'testUtterances':len(test)}
    if args.model=='rules':report.update(evaluate(test,rule_prediction))
    else:
        if not args.model_path:parser.error('--model-path is required; network inference is not supported')
        started=perf_counter();model=SemanticObjectives(args.model_path,[r for r in rows if r['split']=='train'])
        report['initializationSeconds']=round(perf_counter()-started,3)
        report['torchCPUThreads']=2
        dev=[r for r in rows if r['split']=='dev'];candidates=[]
        for threshold in (.35,.45,.55,.65,.75,.85,.90):
            metric=evaluate(dev,lambda row:model.predict(row,threshold));candidates.append((metric['f1'],metric['precision'],threshold))
        threshold=max(candidates)[2]
        report.update(repository=model.manifest['repository'],revision=model.manifest['revision'],thresholdSelectedOnDev=threshold,
                      **evaluate(test,lambda row:model.predict(row,threshold)))
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k not in ('results','byLanguage')},ensure_ascii=False,indent=2))


if __name__=='__main__':main()
