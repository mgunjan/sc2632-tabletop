# Authenticated comparison: Jev and Claude

## Result and recommendation

Jev 1.13 and Claude Opus 5.5 both improved on the local candidates in this screening pilot. Claude answered 32/33 scored questions correctly; Jev answered 30/33. Their paired accuracy difference is inconclusive (exact McNemar p=0.50: two Claude-only successes, zero Jev-only). Jev's median HTTP response was 172 ms versus Claude's 2,369 ms. Both produced the required privilege policy in the complete Scenario A workflow.

This supports testing Jev for frequent bounded decisions and Claude for broader reasoning or fallback. It does **not** prove that a classifier is always best, establish either provider as production-ready for this application, or validate a routing threshold. OpenAI was not run: the supplied frontier credential was Claude, not OpenAI. The prepared OpenAI adapter remains available.

## Measured screening results

| Candidate | Correct choices | Median latency | Selected at 0.6 | Wrong among selected | Privilege policy in Scenario A |
|---|---:|---:|---:|---:|---|
| Jev 1.13.0, hosted | 30/33 | 172 ms | 26/33 | 0/26 | Present |
| Claude Opus 5.5, adaptive / medium | 32/33 | 2,369 ms | 33/33 | 1/33 | Present |
| Strands Decider 2B, local MPS | 24/33 | 486 ms | 18/33 | 2/18 | Missing |
| Qwen3 4B instruct, local Ollama | 21/33 | 1,134 ms | 33/33 | 12/33 | Missing |
| Laya typed-decisions, local MPS | 16/33 | 89 ms* | 1/33 | 0/1 | Missing |

*Laya timing measures in-process inference; other candidates measure HTTP wall time. Local hardware, model size and runtime differ. Hosted latency includes network and service behavior. These are deployment configurations, not isolated causal tests of model architecture. p95 HTTP latency: Jev 216 ms; Claude 4,755 ms. No unreadable answers occurred in the two hosted runs.

All candidates received the same frozen state, question definitions, criterion order and answer options within the standalone pilot. The 33 scored cases comprise 11 core clauses, 16 paraphrases, three dependency decisions and three blocked-workload decisions. Four hostile prompts are report-only, without an invented safety score. The original case hash is e1f61778c0318a4e48e1c4736688772a39381a116668a49dde8b5bf429e92209; labels were unchanged. This small, related, author-labelled set is not an independently adjudicated production test set.

Claude used its Messages API, constrained JSON output, adaptive thinking, medium effort and a 4,096-token output limit. The actual response ID/model and usage are retained. Jev used the versioned System One endpoint. Returned models were claude-opus-5-5 and jev-1.13.0. One excluded warm-up preceded each sequential run. Timings summarize all 37 subsequent requests. Account model-list access was checked; Jev listed aliases but accepted the pinned version. Claude used the account's existing Default workspace with its required workspace header.

## Confidence and workflow behavior

Jev's distribution-derived confidence and Claude's generated self-rating are different signals. The common 0.6 cutoff is the project's existing operating choice, not matched risk. Zero Jev errors among 26 selected cases is encouraging but too little evidence to certify safety. The post-hoc top-17 and top-25 ranking diagnostics contain no errors for either hosted candidate; these are not calibrated routing policies. Both disagreed with the storage dependency reference label, selecting preservation where the frozen label requires denial. The state names backup-job but does not establish its criticality or an approved dependency list; that label assumes a boundary absent from the question. Treat this as an expert-adjudication issue, not proven unsafe behavior. The reported 30/33 and 32/33 preserve the frozen scoring contract.

Both full Scenario A runs selected egress, privilege, API-access and process for the four intent clauses and rendered privilege and egress policies. The agent still marks the API-access control unimplemented: an RBAC handover is required. Jev escalated all dependency profiles, preserving them for human review; its current-fixture report said nothing would block. Claude preserved storage, denied the `none` profile and found report-runner blocked; that became an exception request and a human resolution. Neither run deployed policies or granted an exception.

These differences are useful audience material: admission outcomes on current fixtures do not establish complete intent coverage, and a dependency decision can change containment even when the selected control is correct. The same compiler cannot compensate for a missed requirement or unsupported enforcement layer.

## Independent privilege behavior check

After observing the model outputs, six fixed expectations were authored independently of their generated tests and run against each generated privilege policy using Kyverno CLI 1.19.1:

- Safe Pod passes.
- Privileged container fails.
- Explicit privilege escalation fails.
- Missing allowPrivilegeEscalation setting fails.
- Privileged init container fails.
- A Pod outside payments is skipped.

Both policies passed all six expectations. These are focused offline admission checks, not live cluster enforcement or a pre-registered broad gate. The resources, expected outcomes, test manifests and actual results are retained in benchmark/independent-privilege-contract/. They do not test RBAC, current network connections, runtime detection, expiry cleanup or recovery. The earlier unchanged Strands gate remains failed; these hosted runs do not override it.

## Cost estimate and production limits

Across the 37 pilot requests, Jev reported 23,495 input and 4,172 output tokens; Claude reported 34,103 input and 2,334 output tokens, with no cache reads/writes. At documented list prices checked October 12, 2026, estimated inference cost is $0.000987 for Jev ($0.042/M input; outputs free) and $0.183092 for Claude ($4/M input, $20/M output). These are calculated estimates, not invoices. Excluded warm-up and complete-agent requests add billing. They exclude owned hardware, engineering, review, retries and operational overhead.

The adapters have validation tests but are benchmark clients. They do not establish production rate-limit handling, retries, failover, p99 latency, drift monitoring, permission controls or calibrated risk. Next evaluate an independently labelled calibration/test set, repeat/order robustness, rules baseline, security-critical omissions and the improved requirement-ledger algorithm specified in PRODUCTION-COMPARISON.md. Compare specialist-only, frontier-only and a fixed calibrated cascade before choosing a deployment configuration.

## Reproduction and sources

Seven offline adapter contract tests passed. Run from the repository root with credentials kept outside tracked source:

```bash
python3 submission/2026-10-12/benchmark/run_provider.py --provider jev --model jev-1.13.0 --env-file .env.jev --agent
# Multi-workspace Claude keys also require ANTHROPIC_WORKSPACE_ID in the environment.
python3 submission/2026-10-12/benchmark/run_provider.py --provider claude --model claude-opus-5-5 --effort medium --env-file .env.claude --agent
```

The runner refuses to overwrite prior recordings. Raw responses, summaries and complete agent proposals are under benchmark/expanded/jev-jev-1.13.0/ and benchmark/expanded/claude-claude-opus-5-5-medium/. Local results remain in BENCHMARK-RESULTS.md and the Laya directory. No secrets are written to results.

Primary sources: [Claude models and list prices](https://platform.claude.com/docs/en/models/overview), [Claude structured outputs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs), [Claude workspace scoping](https://platform.claude.com/docs/en/manage-claude/workspaces), [Jev models and pricing](https://docs.typesafe.ai/models), [Jev confidence](https://docs.typesafe.ai/confidence).

Complete per-run price/time measurements are now in [RUN-COST-ANALYSIS.md](RUN-COST-ANALYSIS.md): Jev median 1.82 seconds / $0.000191 estimated API cost; Claude 24.18 seconds / $0.037952, across three complete Scenario A runs each. Review and deployment are excluded.

Laya full workflow timing is now measured separately on MPS: three-run median 0.41 seconds, four escalations and no generated guardrail in each run. No API charges; compute and operations unpriced. Its 0.41-second run is not comparable successful work to a hosted run producing policies. See RUN-COST-ANALYSIS.md.
