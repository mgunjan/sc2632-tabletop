#!/usr/bin/env python3
"""Render only completed, exactly paired local comparison evidence."""
import argparse
import json
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE))
from build import digest


def render(folder):
    folder=Path(folder);status=json.loads((folder/'RUN-STATUS.json').read_text())
    if status['state']!='RUNS_FINISHED':raise ValueError('Do not publish a partial comparison as complete')
    results=[];identities=None;source_hashes=set();data_hashes=set()
    for run in status['runs']:
        name=run['name'];root=folder/name
        if run['returncode']!=0:raise ValueError('A candidate process failed')
        summary=json.loads((root/'summary.json').read_text())
        records=[json.loads(l) for l in (root/'test-responses.jsonl').read_text().splitlines()]
        if len({r['id'] for r in records})!=len(records):raise ValueError('Duplicate predictions')
        current={r['id']:(r['state_sha256'],r['expected']) for r in records}
        if identities is None:identities=current
        elif current!=identities:raise ValueError('Candidates were not scored on identical states and labels')
        if digest(root/'BENCHMARK.py.txt')!=summary['benchmark_sha256']:
            raise ValueError('Missing or mismatched executed source snapshot')
        source_hashes.add(summary['benchmark_sha256']);data_hashes.add(summary['data_manifest_sha256'])
        results.append((name,summary))
    if len(source_hashes)!=1 or len(data_hashes)!=1:raise ValueError('A comparison must freeze one benchmark and data version')
    first=results[0][1]['metrics']
    text=['# Local guardrail decision comparison','',
          '**Status: authored development study; publication and independent qualification remain incomplete.**','',
          f"All candidates were scored on the same {first['decisions']} candidate assessments from {first['cases']} cases in {first['scenario_families']} authored families. Ten assessments from one case are dependent.",'',
          '| Candidate | Exact plans | Missed required controls | Wrong recommendations | Correct reviews | Correct handoffs | Case p50 / p95 ms |',
          '|---|---:|---:|---:|---:|---:|---:|']
    for name,s in results:
        m=s['metrics'];t=s['timing']
        text.append(f"| [{name}]({name}/summary.json) | {m['exact_plan_cases']}/{m['cases']} | {m['missed_required_controls']}/{m['required_controls']} | {m['wrong_recommendations']} | {m['correct_reviews']}/{m['expected_reviews']} | {m['correct_handoffs']}/{m['expected_handoffs']} | {t['full_case_p50_ms']:.2f} / {t['full_case_p95_ms']:.2f} |")
    text += ['', '## Interpretation limits','',
             'Pooled accuracy can be high while every required control is omitted. A correct individual control does not make an incomplete plan correct. A zero count of wrong recommendations can also mean the candidate recommended nothing.',
             '', 'Confidence routing is selected on the separate calibration set. See each summary for accepted-case coverage, observed risk, calibration, failures and the family bootstrap interval. The small authored sample cannot establish an enterprise risk guarantee.',
             '', 'The rules baseline supplies hard answers without an invented confidence distribution. Generative-model probabilities are generated self-estimates; they are not token probabilities. Ollama client RSS excludes server memory.',
             '', 'This is a local benchmark: API charge is zero. Hardware, energy, setup/maintenance and human review are unpriced, so total operating cost remains null. Per-case timings exclude human review, deployment and real containment.',
             '', 'Independent labels from Vivek and another security colleague are pending. Hosted comparison results and their export authorization are tracked separately in the experiment README. Existing source alignments have not trained these candidates.',
             '', 'These findings do not establish industry leadership, production readiness, real incident containment or that a particular model family cannot improve. Source-grounded data expansion, label-quality review and a new final evaluation remain necessary.',
             '', '## Frozen identities','',f"- Dataset manifest SHA256: `{next(iter(data_hashes))}`",f"- Executed benchmark SHA256: `{next(iter(source_hashes))}`",'',
             'Raw paired predictions, calibration responses, exact executed source snapshots and complete process elapsed times are retained beside the summaries. The two trained candidates start from the same already head-tuned October 13 checkpoint. Their training recipes differ in learning rate; this first study does not isolate encoder adaptation as a causal effect.']
    (folder/'REPORT.md').write_text('\n'.join(text)+'\n')
    return {'candidates':len(results),'test_decisions':len(identities),'report':str(folder/'REPORT.md')}


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--runs',type=Path,required=True)
    a=ap.parse_args();print(json.dumps(render(a.runs),indent=2))
