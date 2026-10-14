#!/usr/bin/env python3
"""Author-labelled synthetic control-selection curriculum, separate from the pilot.

Template families and entity pools are split before training. Development selects
the checkpoint; calibration fits probabilities; test_ood is untouched until final
evaluation. These constructed labels need independent enterprise review.
"""
import argparse
import hashlib
import json
from pathlib import Path
import random
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'generator'))
import decider_agent as da
import control_library

# Positions 0..3=train, 4=dev, 5=cal, 6=test_ood. No template crosses splits.
TEXT = {
 'egress_profile': [
  'Limit {workload} outbound connections to approved dependencies.',
  'Deny east-west traffic from {namespace} except for the documented database path.',
  'The {workload} service may reach only approved egress destinations.',
  'Block connections from {workload} to unrelated namespaces.',
  'Keep the dependency paths available but isolate other traffic originating in {namespace}.',
  'Allow {workload} to talk to its database and monitoring endpoints, then deny remaining destinations.',
  'Fence communication from {namespace} to its agreed service peers.'
 ],
 'deny_privilege_escalation': [
  'Prevent container privilege escalation in {namespace}.',
  'Reject privileged containers for {workload}.',
  'Every container in {namespace} must set allowPrivilegeEscalation to false.',
  'Disallow privileged mode in the {workload} Pod.',
  'Containers in {namespace} must not gain additional operating-system privileges.',
  'Reject a newly created {workload} Pod if any init container permits privilege escalation.',
  'Prevent a container in {namespace} from elevating its Linux privileges.'
 ],
 'restrict_registry': [
  'Allow images only from the approved internal registry for {namespace}.',
  'Reject public-registry images used by {workload}.',
  'Require the {workload} container image to come from our approved registry.',
  'Block container image sources outside the registry allowlist in {namespace}.',
  'A {workload} deployment must not pull its image from an unapproved host.',
  'Constrain the image source for {namespace} to our corporate mirror.',
  'Admit {workload} only when its image is sourced from the sanctioned container repository.'
 ],
 'restrict_api_access': [
  'Remove {workload} permission to list Kubernetes secrets.',
  'Reduce the compromised workload identity permissions on the Kubernetes API.',
  'Restrict RBAC roles for the service account used by {workload}.',
  'Revoke {workload} access to secret objects in {namespace}.',
  'Narrow the API authorization of the suspected {workload} principal.',
  'The {workload} account must lose its get and watch permissions for Kubernetes secrets.',
  'Trim the effective RoleBindings of the identity running {workload}.'
 ],
 'deny_sa_token_for_agent_sidecars': [
  'The assistant sidecar in {workload} must not mount the Pod service-account token.',
  'Disable automatic Kubernetes token mounting for Pods containing an AI sidecar.',
  'Do not expose the Pod Kubernetes identity to the {workload} agent sidecar.',
  'Agent sidecars in {namespace} must not receive the service-account credential.',
  'Turn off automatic token injection in Pods marked as containing an assistant.',
  'Keep the Kubernetes service-account token out of the assistant container in {workload}.',
  'Prevent automatic exposure of the Pod authentication token to its AI companion container.'
 ],
 'deny_agent_mutation_outside_namespace': [
  'The ops agent may change workloads only in {namespace}.',
  'Block the agent from modifying deployments outside its home namespace.',
  'Deny cross-namespace workload writes made by the {namespace} assistant.',
  'Confine the agent mutation scope to its own namespace.',
  'The automation identity must not patch workloads belonging to another namespace.',
  'Prevent our operations bot from scaling a deployment outside {namespace}.',
  'Keep writes performed by the operations assistant inside its assigned namespace boundary.'
 ],
 'require_ticket_on_agent_changes': [
  'Every agent change to {workload} must carry a ticket reference.',
  'Require a change annotation on workload updates performed by the ops agent.',
  'Agent mutations in {namespace} must include the change-request identifier.',
  'A deployment patch from the assistant needs a linked ticket.',
  'Before accepting a bot workload update, check that its change reference is present.',
  'Attach the approved change-record identifier to agent edits of {workload}.',
  'Automation updates must identify the change-management record in an annotation.'
 ],
 'audit_replica_surge': [
  'Flag agent changes that increase {workload} replicas above the agreed limit.',
  'Audit deployments with replica counts exceeding the approved threshold.',
  'Observe sudden increases in the number of {workload} replicas.',
  'Report deployment scale requests that exceed the replica ceiling.',
  'Warn when the assistant expands {workload} beyond its approved replica budget.',
  'Record deployments requesting more replicas than the service capacity baseline.',
  'Surface an unexpected deployment scale-up beyond the established replica bound.'
 ],
 'process': [
  'Roll the policy out through audit, warning and enforcement stages.',
  'Require an accountable owner and an expiry for every exception.',
  'Keep the change reversible and preserve service availability.',
  'Time-box temporary overrides during the incident.',
  'Delay enforcement until the service owner approves the rollout window.',
  'Rehearse rollback before promoting the proposed restrictions.',
  'Maintain an availability floor while gradually tightening the incident posture.'
 ],
 'not_implementable': [
  'Preserve a memory image of the existing {workload} process before stopping it.',
  'Prevent the assistant from invoking an unapproved application tool.',
  'Stop the running agent from disclosing customer data in its chat output.',
  'Alert when a process already running in {workload} opens a shell.',
  'Require a human to verify the forensic evidence custodian identity.',
  'Validate that the assistant runtime rejects unauthorized tool calls.',
  'Capture the current process memory and hash the evidence before containment.'
 ]
}


def build(out, seed=13):
    control_library.load()
    if set(TEXT) != set(da.CONTROLS) or any(len(v) != 7 for v in TEXT.values()): raise ValueError('Incomplete curriculum')
    out = Path(out)
    if out.exists() and any(out.iterdir()): raise ValueError('Data output already contains evidence')
    out.mkdir(parents=True, exist_ok=True)
    rng = random.Random(seed)
    split_templates = {'train': range(4), 'dev': [4], 'cal': [5], 'test_ood': [6]}
    pools = {'train': ['checkout', 'invoice', 'report', 'search', 'events', 'batch'],
             'dev': ['fulfillment', 'routing', 'gateway'], 'cal': ['inventory', 'catalog', 'telemetry'],
             'test_ood': ['dispatch', 'orders', 'notification']}
    pilot = json.loads((ROOT/'submission/2026-10-12/benchmark/cases.json').read_text())
    frozen_states = {r['state'] for r in pilot}
    rows_by = {}
    for split, positions in split_templates.items():
        rows = []
        for control, templates in TEXT.items():
            for i in positions:
                for n in range(12 if split == 'train' else 6):
                    name = pools[split][n % len(pools[split])]
                    namespace = f'{name}-{n//len(pools[split])+1}'
                    workload = name+'-worker'
                    clause = templates[i].format(namespace=namespace, workload=workload)
                    intent = f'Incident response for {namespace}. {clause}'
                    state = da._state(clause, intent)
                    if state in frozen_states: raise ValueError('Training corpus overlaps frozen pilot')
                    rows.append({'id': hashlib.sha256(state.encode()).hexdigest()[:16], 'task': 'policy_control',
                                 'split': split, 'template': f'{control}-{i}', 'source': 'author-labelled synthetic',
                                 'state': state, 'labels': {'q': control}})
        rng.shuffle(rows); rows_by[split] = rows
        (out/f'{split}.jsonl').write_text(''.join(json.dumps(r, sort_keys=True)+'\n' for r in rows))
    seen = set()
    for split, rows in rows_by.items():
        states = {r['state'] for r in rows}
        if seen & states: raise ValueError('State leakage across splits')
        seen |= states
    # Choice order is part of the model input; preserve the inference vocabulary order.
    (out/'questions.json').write_text(json.dumps({'policy_control': {'q': da.QUESTION['control']}}, indent=2)+'\n')
    manifest = {'seed': seed, 'catalog_sha256': hashlib.sha256(control_library.CATALOG.read_bytes()).hexdigest(),
                'questions_sha256': hashlib.sha256((out/'questions.json').read_bytes()).hexdigest(),
                'frozen_pilot_sha256': hashlib.sha256((ROOT/'submission/2026-10-12/benchmark/cases.json').read_bytes()).hexdigest(),
                'split_protocol': 'Train templates 0-3; dev 4; cal 5; test_ood 6. Distinct entities. No independent real-world labels.',
                'splits': {s: {'rows': len(rows), 'sha256': hashlib.sha256((out/f'{s}.jsonl').read_bytes()).hexdigest()} for s, rows in rows_by.items()}}
    (out/'MANIFEST.json').write_text(json.dumps(manifest, indent=2)+'\n')
    return manifest


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('--out', required=True); ap.add_argument('--seed', type=int, default=13)
    a = ap.parse_args(); print(json.dumps(build(a.out, a.seed), indent=2))
