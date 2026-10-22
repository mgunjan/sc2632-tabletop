#!/usr/bin/env python3
"""Audit repaired training selection and regenerate the paired Claude comparison."""
import argparse
import json
import math
import os
from pathlib import Path
import shutil

from build import digest
from compare_hosted import identities, load_run


def render(run, weights, data, old, pilot, convergence, claude):
    run,weights,data,old,pilot,convergence,claude=map(Path,(run,weights,data,old,pilot,convergence,claude))
    status=json.loads((run/'RUN-STATUS.json').read_text())
    if status['state']!='COMPLETED' or any(r['returncode'] for r in status['runs']):
        raise ValueError('Repair run incomplete')
    receipt=json.loads((weights/'TRAINING-RUN.json').read_text());cfg=json.loads((weights/'rl_agent_config.json').read_text())
    if receipt['selection_metric']!='plan' or receipt['selection_split']!='dev' or receipt['balanced_labels']:
        raise ValueError('Repair training protocol changed')
    if receipt['training_source_sha256']!=digest(run/'TRAINER.py.txt') or receipt['training_source_sha256']!=digest(weights/'TRAINER.py.txt'):
        raise ValueError('Trainer identity changed')
    if receipt['training_manifest_sha256']!=digest(data/'MANIFEST.json'):
        raise ValueError('Dataset identity changed')
    manifest=json.loads((data/'MANIFEST.json').read_text())
    labels=('recommend','review','handoff','exclude')
    expected_draws={str(i):4*manifest['label_counts'][label] for i,label in enumerate(labels)}
    if receipt['total_completed_steps']!=1312 or receipt['unique_training_assessments_seen']!=1310 or receipt['label_draw_counts']!=expected_draws:
        raise ValueError('The prespecified four complete training passes did not finish')
    for name,meta in manifest['files'].items():
        if digest(data/name)!=meta['sha256']:raise ValueError('Changed dataset file: '+name)
    h=receipt['history']
    best=min(h,key=lambda r:(-r['exact_plans'],r['development_error_cost'],r['cal_loss']))
    if best.get('epoch')!=receipt['selected_epoch'] or receipt['actual_device']!='mps':
        raise ValueError('Selection or device mismatch')
    if cfg['trustfall_variant']['encoder_before']['sha256']==cfg['trustfall_variant']['encoder_after']['sha256']:
        raise ValueError('No encoder adaptation')
    fit=json.loads((run/'SELECTED-FIT.json').read_text())
    for key,hkey in [('exact_plans','exact_plans'),('development_error_cost','development_error_cost'),('accuracy','cal_acc'),('cross_entropy','cal_loss')]:
        if not math.isclose(fit['splits']['dev'][key],best[hkey],abs_tol=1e-5):
            raise ValueError('Selected model does not reproduce recorded dev selection: '+key)
    results=[];test_id=cal_id=bench=None
    folders=[('previous-adapted',old/'adapted'),('source-balanced-pilot',pilot/'source-adapted'),
             ('source-three-passes',convergence/'evaluation'),('repaired-system1',run/'evaluation'),
             ('claude-opus-5-5',claude),('repaired-candidate-lr',run/'classical-candidate-lr'),
             ('repaired-context-retrieval',run/'classical-context-retrieval'),
             ('hierarchy-original-data',run/'hierarchy-original-v2'),('hierarchy-repaired-data',run/'hierarchy-repaired-v2'),
             ('original-candidate-lr',old/'candidate-lr'),('original-context-retrieval',old/'context-retrieval'),('original-rules',old/'rules')]
    for name,folder in folders:
        s,c,t=load_run(folder)
        if name.startswith('hierarchy-') and s['candidate']['adapter_sha256']!=digest(folder/'ADAPTER.py.txt'):
            raise ValueError('Hierarchy adapter snapshot changed')
        if test_id is None:test_id,cal_id,bench=identities(t),identities(c),s['benchmark_sha256']
        if (identities(t),identities(c),s['benchmark_sha256'])!=(test_id,cal_id,bench):
            raise ValueError('Comparison is not exactly paired')
        results.append((name,s,folder))
    current=next(s for n,s,_ in results if n=='repaired-system1')
    model_sha=digest(weights/'model.safetensors')
    if current['candidate']['model_sha256']!=model_sha or fit['checkpoint_sha256']!=model_sha or current['candidate']['config_sha256']!=digest(weights/'rl_agent_config.json'):
        raise ValueError('Evaluation checkpoint changed')
    if current['data_manifest_sha256']!=receipt['training_manifest_sha256']:
        raise ValueError('Training/evaluation data mismatch')
    label_audit=json.loads((run/'LABEL-AND-PIPELINE-AUDIT.json').read_text())
    if label_audit['auditor_sha256']!=digest(run/'LABEL-AUDITOR.py.txt'):
        raise ValueError('Label auditor snapshot changed')
    correction=json.loads((run/'DATA-METADATA-CORRECTION.json').read_text())
    if correction['corrected_manifest']['files']!=manifest['files']:
        raise ValueError('Metadata correction changed model input files')
    for src,dst in [('TRAINING-RUN.json','TRAINING-RUN.json'),('rl_agent_config.json','CHECKPOINT-CONFIG.json')]:
        shutil.copyfile(weights/src,run/dst)
    deltas={p.name:digest(p) for p in sorted((weights/'epoch-deltas').glob('*.safetensors'))}
    if len(deltas)!=len(h)-1:raise ValueError('Missing rejected/selected epoch delta')
    audit={'status':'PASSED_REPAIR_PAIRED_AUDIT','benchmark_sha256':bench,'checkpoint_sha256':model_sha,
           'data_manifest_sha256':receipt['training_manifest_sha256'],'trainer_sha256':receipt['training_source_sha256'],
           'protocol_sha256':digest(run/'PROTOCOL.md'),'epoch_deltas_sha256':deltas,
           'reporter_sha256':digest(__file__),
           'selected_epoch':receipt['selected_epoch'],'completed_steps':receipt['total_completed_steps'],
           'new_hosted_calls':0,'calibration_rows':len(cal_id),'test_rows':len(test_id),
           'qualification':'EXAMINED_AUTHORED_REGRESSION_PENDING_INDEPENDENT_REVIEW'}
    (run/'AUDIT.json').write_text(json.dumps(audit,indent=2)+'\n')
    (run/'REPORTER.py.txt').write_bytes(Path(__file__).read_bytes())
    def link(p):return Path(os.path.relpath(p.resolve(),run.resolve())).as_posix()
    text=['# System1 pipeline repair and paired Claude comparison','',
          '**Examined authored regression. No test labels were changed. No new Claude calls were made.**','',
          '**Outcome: data-pipeline defects were repaired, but useful Laya recovery was not achieved. The retrain excluded every test candidate, missing all 23 required candidates. Its 2/15 exact plans are the all-exclude baseline.**','',
          '| Candidate | Exact plans | Required omitted | Wrong recommendations | Reviews | Handoffs | Accepted / wrong | Case p50 seconds |',
          '|---|---:|---:|---:|---:|---:|---:|---:|']
    for name,s,folder in results:
        m=s['metrics'];r=m['routing']
        text.append(f"| [{name}]({link(folder/'summary.json')}) | {m['exact_plan_cases']}/15 | {m['missed_required_controls']}/23 | {m['wrong_recommendations']} | {m['correct_reviews']}/5 | {m['correct_handoffs']}/8 | {r['accepted_cases']} / {r['wrong_accepted_cases']} | {s['timing']['full_case_p50_ms']/1000:.3f} |")
    text+=['','## Findings supported by the audit','',
        'The previous balanced expansion deleted 187 original exclusion assessments, reduced exclusion prevalence from 87.5% to 25%, and left zero complete ten-candidate training cases. It contained 1,024 rows but only 357 distinct operative model inputs after removing reference-description aliases. This changed supervision and class priors while the benchmark still required choosing a sparse complete plan. Scalar temperature calibration cannot change the winning class. A training-prior correction on saved calibration predictions alone produced 150 exclusions and missed every required candidate: the weak model had not learned sufficient matching; a prior correction alone is not a repair.', '',
        'The old source-balanced pilot fitted its own training data at only 29.2% accuracy against 25% uniform chance. Training exposure and checkpoint selection were also inadequate diagnostics: the three-pass run selected epoch 2 by macro cross-entropy, rejecting a later epoch with higher pooled accuracy. That does not prove the rejected epoch had better complete plans. Its weights were not retained. The repair saves every epoch and selects using complete development plans and explicit error priorities.', '',
        'There were zero exact operative label conflicts and zero recommend/handoff capability-contract violations in the audited inputs. This is not semantic label validation. Generic unsupported-requirement versus identity/governance ownership and replica-scope approval remain ambiguous. No frozen answer was silently changed, and all labels still await independent review.', '',
        'The repair retains all 360 original rows and trains on 1,310 distinct inputs in 131 complete cases, including paired negation and compound requests. It removes static reference padding, random partial-candidate sampling and global label equalization. These are authored request/evidence counterfactuals; the collected upstream corpus has not supplied independently labelled containment decisions. Data recipe, sampling, selection and exposure changed together, so this experiment does not isolate a single causal factor.', '',
        'The running job retained its original frozen training manifest. A subsequent [metadata correction](DATA-METADATA-CORRECTION.json) fixes inherited aggregate counts and an omitted reference-file count in the builder. Every training, target, question and evaluation file byte is identical; split counts and input hashes were already correct. The original manifest and executed builder snapshot remain unchanged for audit.', '',
        f"Training completed {receipt['total_completed_steps']:,} optimizer steps, saw {receipt['unique_training_assessments_seen']:,} unique assessments and selected epoch {receipt['selected_epoch']} using only the original development split. Actual device: {receipt['actual_device']}; full training elapsed: {receipt['full_run_elapsed_seconds']/60:.2f} minutes. Encoder fingerprints changed. Every completed epoch's trainable tensors are retained locally as deltas.", '',
        '| Epoch | Steps | Training accuracy | Dev accuracy | Dev exact plans | Dev omissions | Dev wrong recommendations | Dev error cost |',
        '|---|---:|---:|---:|---:|---:|---:|---:|']
    for x in h:
        ta='—' if 'train_accuracy' not in x else f"{x['train_accuracy']:.4f}"
        text.append(f"| {x.get('epoch',0)} | {x['step']} | {ta} | {x['cal_acc']:.4f} | {x['exact_plans']}/18 | {x['missed_required']} | {x['wrong_recommendations']} | {x['development_error_cost']} |")
    text+=['','Training accuracy alone can be inflated by exclusions. [Selected-model fit](SELECTED-FIT.json) includes per-class recall, complete plans, confusion counts and runtime parity on development inputs. The two additional CPU controls are diagnostics, not candidates selected after viewing the test.', '',
        '## Cost and limits','',
        'New API spend: $0. The comparison reuses the saved approved Claude run (301 historical requests, $1.964736 estimated total; about $0.06495 per attempted ten-candidate test case). Hardware, energy and human review remain unpriced. Case time excludes deployment and containment.', '',
        'The hierarchy is a separate pair of TF-IDF/logistic models: intent relevance first, then evidence sufficiency for relevant rendered controls. Both original-data and repaired-data variants are shown, without a parameter search. It is not a Laya weight improvement. [Its protocol](HIERARCHICAL-PROTOCOL.md) and development predictions are retained.', '',
        'The hierarchy fitted 100% of both its original and repaired training cases, but only 6/18 and 8/18 development cases respectively. Its 4/15 to 6/15 regression improvement remains small. Training fit and generalization are separate problems; a tiny four-example Laya overfit check cannot establish complete-plan learnability.', '',
        'The selected Laya checkpoint excluded 1,309 of 1,310 training assessments; its one recommendation was wrong. It recognized none of the 147 required training candidates. Its development non-exclude recalls were also zero, and runtime scoring reproduced this failure. This is underfitting in the measured configuration, not a successful classifier whose test accuracy merely drifted. The two-stage model can fit these same labels, but its test generalization is still limited. No further neural optimization is claimed to have solved the remaining fitting problem.', '',
        'The strict authored Claude score remains 10/15. Fifteen examined cases in five families and zero independent reviewer submissions do not establish broad superiority or production safety. A new independently authored and reviewed evaluation is required before promoting a model. Keep the failed runs and any remaining omissions visible.', '',
        '[Protocol](PROTOCOL.md), [label/coverage audit](LABEL-AND-PIPELINE-AUDIT.json), [paired audit](AUDIT.json).']
    (run/'COMPARISON.md').write_text('\n'.join(text)+'\n')
    return audit


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    for k in ('run','weights','data','old','pilot','convergence','claude'):ap.add_argument('--'+k,type=Path,required=True)
    a=ap.parse_args();print(json.dumps(render(**vars(a)),indent=2))
