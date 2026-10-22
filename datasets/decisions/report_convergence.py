#!/usr/bin/env python3
"""Audit the development-driven convergence extension without rewriting the pilot."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys

HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE))
from build import digest
from compare_hosted import identities,load_run


def render(run,old,pilot,claude):
    run,old,pilot,claude=map(Path,(run,old,pilot,claude))
    status=json.loads((run/'RUN-STATUS.json').read_text())
    if status['state']!='RUNS_FINISHED' or any(r['returncode'] for r in status['runs']):raise ValueError('Convergence extension did not finish')
    weights=Path(status['weights']);data=Path(status['data'])
    receipt=json.loads((weights/'TRAINING-RUN.json').read_text());cfg=json.loads((weights/'rl_agent_config.json').read_text())
    if receipt['total_completed_steps']!=768 or receipt['unique_training_assessments_seen']!=1024 or receipt['label_draw_counts']!={str(i):768 for i in range(4)}:
        raise ValueError('The extension did not complete three full balanced passes')
    if receipt['selection_split']!='dev' or receipt['selection_metric']!='macro-loss' or receipt['objective']!='cross-entropy':
        raise ValueError('Selection or objective changed')
    if receipt['training_source_sha256']!=digest(run/'TRAINER.py.txt') or receipt['training_source_sha256']!=digest(weights/'TRAINER.py.txt'):
        raise ValueError('Training source snapshot changed')
    if receipt['training_manifest_sha256']!=digest(data/'MANIFEST.json'):raise ValueError('Training inputs changed')
    if receipt['actual_device']!='mps' or cfg['trustfall_variant']['encoder_before']['sha256']==cfg['trustfall_variant']['encoder_after']['sha256']:
        raise ValueError('Actual encoder adaptation on MPS was not established')
    results=[];test_identity=None;cal_identity=None;benchmark=None
    for name,folder in (('previous-adapted',old/'adapted'),('pilot-source-adapted',pilot/'source-adapted'),
                         ('three-full-passes',run/'evaluation'),('claude-opus-5-5',claude),('rules',old/'rules')):
        s,c,t=load_run(folder)
        if test_identity is None:test_identity=identities(t);cal_identity=identities(c);benchmark=s['benchmark_sha256']
        if identities(t)!=test_identity or identities(c)!=cal_identity or s['benchmark_sha256']!=benchmark:raise ValueError('Unpaired frozen comparison')
        results.append((name,s,folder))
    current=next(s for n,s,_ in results if n=='three-full-passes')
    with (weights/'model.safetensors').open('rb') as stream:actual_hash=hashlib.file_digest(stream,'sha256').hexdigest()
    if current['candidate']['model_sha256']!=actual_hash or current['candidate']['config_sha256']!=digest(weights/'rl_agent_config.json'):
        raise ValueError('Checkpoint identity differs from the evaluated one')
    if current['data_manifest_sha256']!=receipt['training_manifest_sha256']:raise ValueError('Training and inference data differ')
    for src,dst in (('TRAINING-RUN.json','TRAINING-RUN.json'),('rl_agent_config.json','CHECKPOINT-CONFIG.json')):
        shutil.copyfile(weights/src,run/dst)
    import os
    def link(path):return Path(os.path.relpath(path.resolve(),run.resolve())).as_posix()
    text=['# Supplemental three-full-pass System1 result','',
          '**Development-driven extension after a negative matched-budget pilot. This is an examined authored regression, not an independently blind result.**','',
          '| Candidate | Exact plans | Required omitted | Wrong recommendations | Reviews correct | Handoffs correct | Accepted / wrong accepted | Case p50 seconds |',
          '|---|---:|---:|---:|---:|---:|---:|---:|']
    for name,s,folder in results:
        m=s['metrics'];r=m['routing']
        text.append(f"| [{name}]({link(folder/'summary.json')}) | {m['exact_plan_cases']}/15 | {m['missed_required_controls']}/23 | {m['wrong_recommendations']} | {m['correct_reviews']}/5 | {m['correct_handoffs']}/8 | {r['accepted_cases']} / {r['wrong_accepted_cases']} | {s['timing']['full_case_p50_ms']/1000:.3f} |")
    text+=['','## Training exposure and interpretation','',
           f"The extension completed **768 optimizer steps**, **3,072 draws**, **768 per label**. All **1,024 distinct training assessments** were seen. This is three full passes over the balanced source-context set, rather than the pilot's 270-step matched budget. Training ran on real MPS for **{receipt['full_run_elapsed_seconds']/60:.2f} minutes**, selected epoch **{receipt['selected_epoch']}** using the unchanged original dev macro-cross-entropy. No new hosted calls occurred. Hardware/energy/human costs remain unpriced.",'',
           '| Epoch | Steps | Dev macro cross-entropy | Dev pooled accuracy |','|---|---:|---:|---:|']
    for h in receipt['history']:text.append(f"| {h.get('epoch',0)} | {h['step']} | {h['cal_loss']:.4f} | {h['cal_acc']:.4f} |")
    text+=['','The extension was justified by weak training-set fit in the pilot and a four-example overfit check reaching 100%. The sanity check deliberately reused its four training examples for selection and is not generalization evidence. It was never scored as a final candidate.','',
           'This longer run changes training exposure and optimizer budget; the existing warmup/decay schedule also scales with the total step budget. Any gain relative to the pilot cannot be attributed to source excerpts alone. The pilot source/no-reference conditions remain the equal-step ablation. The source labels remain programmatic counterfactuals with repeated request/evidence templates; they are not independent upstream incident-response labels.','',
           'All scored candidates share exact calibration/test states, labels, case/family identities and scoring-source hashes. Original labels and Claude recordings were not changed. Five authored families and 15 examined cases cannot establish industry leadership, production risk or generalization to new enterprise incidents.','',
           '[Convergence protocol](PROTOCOL.md), [pilot comparison](../comparison-v1/COMPARISON.md), [audit](AUDIT.json).']
    (run/'COMPARISON.md').write_text('\n'.join(text)+'\n')
    audit={'status':'PASSED_THREE_FULL_PASS_AUDIT','steps':768,'unique_assessments_seen':1024,'draws':3072,
           'training_source_sha256':receipt['training_source_sha256'],'data_manifest_sha256':receipt['training_manifest_sha256'],
           'checkpoint_sha256':actual_hash,'benchmark_sha256':benchmark,'protocol_sha256':digest(run/'PROTOCOL.md'),
           'reporter_sha256':digest(Path(__file__)),'new_hosted_calls':0,'qualification':'EXAMINED_AUTHORED_REGRESSION_PENDING_INDEPENDENT_VALIDATION'}
    (run/'AUDIT.json').write_text(json.dumps(audit,indent=2)+'\n');return audit


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    for key in ('run','old','pilot','claude'):ap.add_argument('--'+key,type=Path,required=True)
    a=ap.parse_args();print(json.dumps(render(a.run,a.old,a.pilot,a.claude),indent=2))
