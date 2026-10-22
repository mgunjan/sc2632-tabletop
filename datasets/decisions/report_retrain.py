#!/usr/bin/env python3
"""Audit matched retraining and report before/after against retained Claude predictions."""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import random
import shutil
import sys

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE));sys.path.insert(0,str(HERE.parents[1]/'laya_variant'))
from build import DISPOSITIONS,digest
from compare_hosted import identities,load_run
import train


def selected_loss(receipt):
    epoch=receipt['selected_epoch']
    if epoch is None:raise ValueError('A trained checkpoint was not selected')
    return next(r['cal_loss'] for r in receipt['history'] if r.get('epoch')==epoch)


def draws(data,receipt,selected_steps):
    rows=[json.loads(l) for l in (data/'train.jsonl').read_text().splitlines()]
    groups=[[{'label':DISPOSITIONS.index(r['labels']['q']),'row':r['id']}] for r in rows]
    rng=random.Random(19);indices=[]
    for _ in range(3):indices+=train.sample_indices(groups,rng,True,360)
    actual=indices[:receipt['total_completed_steps']*4]
    label_counts=Counter(str(groups[i][0]['label']) for i in actual)
    unique={rows[i]['id'] for i in actual}
    if dict(label_counts)!=receipt['label_draw_counts'] or len(unique)!=receipt['unique_training_assessments_seen']:
        raise ValueError('Replay of the seeded sampler differs from actual training accounting')
    selected={rows[i]['id'] for i in indices[:selected_steps*4]}
    source=[r for r in rows if r['id'] in unique and r.get('source_record_id')]
    selected_source=[r for r in rows if r['id'] in selected and r.get('source_record_id')]
    return {'scope':'Seeded sampler replay checked against actual draw counts and unique-input count; not an independent per-step trace',
            'unique_training_assessments_full_run':len(unique), 'unique_training_assessments_at_selected_checkpoint':len(selected),
            'unique_model_visible_states_full_run':len({r['state'] for r in rows if r['id'] in unique}),
            'unique_model_visible_states_at_selected_checkpoint':len({r['state'] for r in rows if r['id'] in selected}),
            'source_record_ids_full_run':sorted({r['source_record_id'] for r in source}),
            'source_record_ids_at_selected_checkpoint':sorted({r['source_record_id'] for r in selected_source}),
            'selected_assessment_ids':sorted(selected),'full_run_assessment_ids':sorted(unique),
            'source_text_present':json.loads((data/'MANIFEST.json').read_text()).get('reference_text_present_in_training',False)}


def case_outcomes(rows):
    groups=defaultdict(list)
    for r in rows:groups[r['case_id']].append(r)
    return {k:{'family':v[0]['family_id'],'correct':all(r['prediction']==r['expected'] for r in v)} for k,v in groups.items()}


def paired_interval(before,after):
    a,b=case_outcomes(before),case_outcomes(after)
    if set(a)!=set(b):raise ValueError('Unpaired cases')
    groups=defaultdict(list)
    for k in a:
        if a[k]['family']!=b[k]['family']:raise ValueError('Unpaired families')
        groups[a[k]['family']].append(int(b[k]['correct'])-int(a[k]['correct']))
    rng=random.Random(19);keys=sorted(groups);values=[]
    for _ in range(2000):
        sample=[v for key in rng.choices(keys,k=len(keys)) for v in groups[key]]
        values.append(sum(sample)/len(sample))
    values.sort()
    return {'delta_exact_plan_rate':sum(int(b[k]['correct'])-int(a[k]['correct']) for k in a)/len(a),
            'family_bootstrap_95_low':values[50],'family_bootstrap_95_high':values[1949],
            'replicates':2000,'seed':19,'limitation':'Only five authored families; not a population or production guarantee'}


def render(runs,old,claude,out,classical=None):
    runs,old,claude,out=map(Path,(runs,old,claude,out))
    status=json.loads((runs/'RUN-STATUS.json').read_text())
    if status['state']!='RUNS_FINISHED' or any(r['returncode'] for r in status['runs']):
        raise ValueError('All six training and evaluation runs must finish')
    jobs={r['name']:r for r in status['runs'] if r['phase']=='train'}
    if len(jobs)!=6:raise ValueError('Incomplete experimental conditions')
    # Choose using development loss before opening any new test predictions.
    receipts={};configs={};manifests={}
    for name,job in jobs.items():
        weights=Path(job['weights']);receipt=json.loads((weights/'TRAINING-RUN.json').read_text())
        config=json.loads((weights/'rl_agent_config.json').read_text())
        source=digest(runs/'TRAINER.py.txt')
        if receipt['training_source_sha256']!=source or digest(weights/'TRAINER.py.txt')!=source:
            raise ValueError('The trainer changed between conditions')
        if receipt['total_completed_steps']!=270 or receipt['actual_device']!='mps' or receipt['label_draw_counts']!={'0':270,'1':270,'2':270,'3':270}:
            raise ValueError('Optimizer budgets, device or label balance differ from protocol')
        if receipt['selection_split']!='dev' or receipt['selection_metric']!='macro-loss' or receipt['objective']!='cross-entropy':
            raise ValueError('Checkpoint selection differs from the registered recipe')
        manifest=json.loads((Path(job['data'])/'MANIFEST.json').read_text())
        if receipt['training_manifest_sha256']!=digest(Path(job['data'])/'MANIFEST.json'):
            raise ValueError('Training data changed after execution')
        if receipt['head_learning_rate']!=.0001 or receipt['encoder_learning_rate']!=(.00002 if job['regime']=='adapted' else None):
            raise ValueError('Learning rates differ from the matched recipe')
        expected_encoder_changed=job['regime']=='adapted'
        meta=config['trustfall_variant']
        if (meta['encoder_before']['sha256']!=meta['encoder_after']['sha256'])!=expected_encoder_changed:
            raise ValueError('Encoder adaptation or freezing is not supported by fingerprints')
        receipts[name]=receipt;configs[name]=config;manifests[name]=manifest
    primary=min((n for n in jobs if n.startswith('source-')),key=lambda n:(selected_loss(receipts[n]),n))
    overall=min(jobs,key=lambda n:(selected_loss(receipts[n]),n))
    out.mkdir(parents=True,exist_ok=False)
    selection={'rule':'Lowest selected development macro-cross-entropy; no test score used',
               'primary_source_candidate':primary,'lowest_dev_loss_candidate':overall,
               'development_loss':{n:selected_loss(r) for n,r in receipts.items()}}
    (out/'SELECTION.json').write_text(json.dumps(selection,indent=2)+'\n')
    results=[];states=None;cal_states=None;benchmark=None;draw_audits={}
    extra=[]
    if classical:
        classical=Path(classical)
        extra_status=json.loads((classical/'RUN-STATUS.json').read_text())
        if extra_status['state']!='RUNS_FINISHED' or any(r['returncode'] for r in extra_status['runs']):raise ValueError('Incomplete classical controls')
        extra=[(r['name'],classical/r['name']) for r in extra_status['runs']]
    for label,root in [(n,old/n) for n in ('starting','head','adapted','rules','context-retrieval','candidate-lr')]+[('claude-opus-5-5',claude)]+[(n,runs/n) for n in jobs]+extra:
        summary,cal,test=load_run(root)
        if states is None:states=identities(test);cal_states=identities(cal);benchmark=summary['benchmark_sha256']
        if identities(test)!=states or identities(cal)!=cal_states or summary['benchmark_sha256']!=benchmark:
            raise ValueError('Candidates do not share exact held-out states, labels and scoring source')
        if label in jobs:
            manifest=manifests[label]
            for key in ('dev.jsonl','cal.jsonl','test_authored.jsonl','questions.json'):
                if manifest['files'][key]['sha256']!=manifests['balanced-head']['files'][key]['sha256']:
                    raise ValueError('A held-out split or question changed')
            if summary['data_manifest_sha256']!=receipts[label]['training_manifest_sha256']:
                raise ValueError('Training/evaluation data manifest mismatch')
            weights=Path(jobs[label]['weights']);root.mkdir(exist_ok=True)
            with (weights/'model.safetensors').open('rb') as stream:
                actual_weights_sha256=hashlib.file_digest(stream,'sha256').hexdigest()
            if summary['candidate']['model_sha256']!=actual_weights_sha256 or summary['candidate']['config_sha256']!=digest(weights/'rl_agent_config.json'):
                raise ValueError('Evaluated checkpoint or configuration changed')
            shutil.copyfile(weights/'TRAINING-RUN.json',root/'TRAINING-RUN.json')
            shutil.copyfile(weights/'rl_agent_config.json',root/'CHECKPOINT-CONFIG.json')
            usage=draws(Path(jobs[label]['data']),receipts[label],configs[label]['trustfall_variant']['completed_steps'])
            draw_audits[label]=usage
            (root/'TRAINING-DRAWS.json').write_text(json.dumps(usage,indent=2)+'\n')
        if label in {'source-candidate-lr','no-reference-candidate-lr'}:
            corresponding=label.removesuffix('-candidate-lr')+'-head'
            if summary['candidate']['candidate']!='candidate-lr' or summary['data_manifest_sha256']!=receipts[corresponding]['training_manifest_sha256']:
                raise ValueError('A classical control did not train on its named expanded condition')
        results.append((label,summary,test,root))
    by_name={n:(s,rows) for n,s,rows,_ in results}
    predictions={name:dict(Counter(r['prediction'] for r in rows)) for name,_,rows,_ in results}
    for regime in ('head','adapted'):
        if draw_audits['source-'+regime]['full_run_assessment_ids']!=draw_audits['no-reference-'+regime]['full_run_assessment_ids']:
            raise ValueError('Source and no-reference runs did not expose matching seeded assessment IDs')
    contrasts={}
    for regime in ('head','adapted'):
        contrasts[regime+'_source_vs_no_reference']=paired_interval(by_name['no-reference-'+regime][1],by_name['source-'+regime][1])
        contrasts[regime+'_expanded_no_reference_vs_balanced']=paired_interval(by_name['balanced-'+regime][1],by_name['no-reference-'+regime][1])
    contrasts['primary_source_vs_previous_adapted']=paired_interval(by_name['adapted'][1],by_name[primary][1])
    contrasts['primary_source_vs_claude']=paired_interval(by_name['claude-opus-5-5'][1],by_name[primary][1])
    if extra:
        contrasts['classical_source_vs_original']=paired_interval(by_name['candidate-lr'][1],by_name['source-candidate-lr'][1])
        contrasts['classical_source_vs_no_reference']=paired_interval(by_name['no-reference-candidate-lr'][1],by_name['source-candidate-lr'][1])
    import os
    def link(path):return Path(os.path.relpath(path.resolve(),out.resolve())).as_posix()
    s=by_name[primary][0];m=s['metrics'];old_m=by_name['adapted'][0]['metrics'];cm=by_name['claude-opus-5-5'][0]['metrics']
    text=['# System1 balanced retraining: before and after','',
          '**Completed local experiment on the frozen authored regression set. Independent qualification remains incomplete.**','',
          f"Development loss selected **{primary}** as the primary source-trained candidate. It matched **{m['exact_plan_cases']}/15 complete plans**, compared with **{old_m['exact_plan_cases']}/15** for the previous adapted model and **{cm['exact_plan_cases']}/15** for saved Claude Opus 5.5. Required-control omissions were **{m['missed_required_controls']}/23**, compared with **{old_m['missed_required_controls']}/23** previously. These are authored labels, not independently established truth.",'',
          '| Candidate | Exact plans | Missed required | Wrong recommendations | Reviews correct | Handoffs correct | Accepted / wrong accepted | Case p50 seconds |',
          '|---|---:|---:|---:|---:|---:|---:|---:|']
    for name,summary,_,root in results:
        x=summary['metrics'];r=x['routing']
        text.append(f"| [{name}]({link(root/'summary.json')}) | {x['exact_plan_cases']}/15 | {x['missed_required_controls']}/23 | {x['wrong_recommendations']} | {x['correct_reviews']}/5 | {x['correct_handoffs']}/8 | {r['accepted_cases']} / {r['wrong_accepted_cases']} | {summary['timing']['full_case_p50_ms']/1000:.3f} |")
    text+=['',f"Primary source candidate output counts: `{json.dumps(predictions[primary],sort_keys=True)}`. An omission means exclude/invalid on a required candidate. Retaining a candidate for review is not the same as recommending it correctly or routing the correct handoff. Reviewing everything is not a correct complete plan.",'',
           '## What the data actually tests','',
           'The source condition contains 1,024 candidate assessments, 256 per label, with 851 source-context rows linked to 202 source records from eight publishers. Original training contributes 173 rows, including every original recommend/review/handoff example. Forty request wordings and their evidence variants are reused across contexts. These rows are dependent programmatic counterfactuals; they are not 1,024 independently labelled incidents. Source excerpts are static context and do not establish an incident-response decision or a live enforcement result.','',
           'The no-reference condition has the same row IDs, labels and seeded draws, with only the reference excerpts removed. It has 357 unique model-visible states after masking, so its aliases are not independent examples. Compare source with no-reference to evaluate the additional source-text effect. Compare no-reference with balanced to evaluate the curated decision examples. The balanced condition also controls for the revised cross-entropy, sampling, learning-rate and checkpoint-selection recipe. A gain over the October 18 model alone cannot identify which change caused it.','',
           ('Secondary candidate-conditioned TF-IDF/logistic-regression controls use the expanded source and no-reference sets with unchanged hyperparameters. They test the data with a different architecture and do not share neural optimizer budgets. Their additional protocol was specified before the new regression evaluation.' if extra else 'No secondary classical controls were supplied to this report.'),'',
           '| Paired contrast | Exact-plan rate change | Exploratory family-bootstrap 95% range |',
           '|---|---:|---:|']
    for name,c in contrasts.items():
        text.append(f"| {name} | {100*c['delta_exact_plan_rate']:+.1f} pp | {100*c['family_bootstrap_95_low']:+.1f} to {100*c['family_bootstrap_95_high']:+.1f} pp |")
    text+=['','The intervals resample only five authored families. They do not establish enterprise generalization, production risk bounds or a universal model-family winner. This test was previously examined; it is a regression comparison. No test score selected a checkpoint or changed the frozen labels.','',
           '## Training and operational accounting','',
           '| Condition | Selected epoch | Dev macro cross-entropy | Steps completed | Unique IDs / model-visible states drawn | Full training seconds | Encoder changed |',
           '|---|---:|---:|---:|---:|---:|---|']
    for name,r in receipts.items():
        text.append(f"| {name} | {r['selected_epoch']} | {selected_loss(r):.4f} | {r['total_completed_steps']} | {r['unique_training_assessments_seen']} / {draw_audits[name]['unique_model_visible_states_full_run']} | {r['full_run_elapsed_seconds']:.2f} | {'yes' if name.endswith('adapted') else 'no'} |")
    text+=['',f"All six runs used the real MPS device, seed 19, 270 optimizer steps, four assessments per step, and 270 label draws per disposition. Full training wall time summed to {sum(r['full_run_elapsed_seconds'] for r in receipts.values())/60:.2f} minutes, excluding separate evaluation. Selected checkpoints can predate the final epoch; full-run draw totals are not the selected checkpoint's exposure. See each TRAINING-DRAWS.json for seeded replay checked against actual accounting.",'',
           'Local API charge was $0; hardware, electricity, maintenance and human review are unpriced. There were no new hosted calls. Saved Claude usage remains $1.964736 for its entire 301-call study, $0.06495 per ten-control test case and 26.57 seconds median case latency. These are list-price estimates rather than invoices or total operating cost. Sequential case timings exclude human review, deployment and containment; no batching optimization was measured.','',
           '## Evidence and remaining limits','',
           f"The typed question and original development/calibration/test files remain unchanged. All candidates' saved calibration and test state hashes, labels, case/family IDs and benchmark source hashes were checked. Executed benchmark SHA256: `{benchmark}`.",'',
           'The independent review pack remains pending. Some catalog entries overlap, and canonical exact-match labels may exclude reasonable alternatives. Original labels and responses are preserved. The new training labels also require review. A useful regression gain is not an industry-leading or production-qualified model claim.','',
           '[Selection rule and development losses](SELECTION.json), [machine-readable contrasts and audit](AUDIT.json), [frozen experiment protocol](../PROTOCOL.md).']
    (out/'COMPARISON.md').write_text('\n'.join(text)+'\n')
    audit={'status':'PASSED_PAIRED_RETRAINING_AUDIT','candidates':len(results),'new_training_runs':6,
           'selection':selection,'contrasts':contrasts,'new_hosted_calls':0,
           'prediction_counts':predictions,
           'benchmark_sha256':benchmark,'trainer_sha256':digest(runs/'TRAINER.py.txt'),
           'new_checkpoint_sha256':{n:s['candidate']['model_sha256'] for n,s,_,_ in results if n in jobs},
           'protocol_sha256':digest(runs/'PROTOCOL.md'),'reporter_sha256':digest(Path(__file__)),
           'heldout_file_hashes':{n:manifests['balanced-head']['files'][n]['sha256'] for n in ('dev.jsonl','cal.jsonl','test_authored.jsonl','questions.json')},
           'qualification':'AUTHORED_REGRESSION_NOT_INDEPENDENT_GENERALIZATION'}
    (out/'AUDIT.json').write_text(json.dumps(audit,indent=2)+'\n')
    return audit


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    for key in ('runs','old','claude','out'):ap.add_argument('--'+key,type=Path,required=True)
    ap.add_argument('--classical',type=Path)
    a=ap.parse_args();print(json.dumps(render(a.runs,a.old,a.claude,a.out,a.classical),indent=2))
