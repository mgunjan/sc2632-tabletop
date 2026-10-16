# Price, time and setup cost per run

October 13 update: [the local trained-Laya pilot](../2026-10-13/REVIEW.md) took 57 seconds of head training and a median 0.975 seconds per complete fixture proposal. It incurred no API charge; local compute is unpriced. Its proposal remained incomplete and its accuracy did not improve, so this does not establish cost per accepted secure change.

## Measured complete proposal runs

Three complete Scenario A runs per hosted provider were newly measured after the screening pilot. A run starts before the first intent decision and ends after model decisions, deterministic policy compilation, Kyverno fixture simulation and local proposal-file creation. It excludes human review, deployment, recovery and live cluster observation. All six runs generated the required privilege policy.

| Metric | Jev 1.13.0 | Claude Opus 5.5, medium effort |
|---|---:|---:|
| Median elapsed time / run | 1.82 seconds | 24.18 seconds |
| Observed elapsed range | 1.69–2.05 seconds | 19.41–28.39 seconds |
| Median estimated API price / run | $0.000191 | $0.037952 |
| Observed estimated price range | $0.000191–$0.000191 | $0.036832–$0.047508 |
| API calls / run | 8 | 8–9 |
| Input tokens / run | 4,552 | 6,483–7,222 |
| Output tokens / run | 634 | 545–931 |
| Items escalated to a human / run | 4 | 1 |
| Exception requests / run | 0 | 0–1 |

The medians of cost and elapsed time are calculated separately; they need not come from the same run. Three repeats are descriptive, not a p95, load test or service-level guarantee. Requests within a run are sequential. Both provider clients were launched concurrently; Jev finished its three runs while Claude's first run was in progress. Shared local compilation resources and changing service load can affect timing. No causal model-architecture speed claim is made.

Claude's dependency choices and extra simulation-resolution call varied between repeats. Model variation can alter both the number of calls and the resulting proposal. The extra API call is included in the complete-run cost and time. Warm-up is not charged to these run measurements, and no retries occurred; an actual cold start or retry adds cost. Do not extrapolate this scenario's call count to all incidents.

Prices are estimates calculated from provider-reported usage at documented list prices checked October 12, 2026:

- Jev: input tokens × $0.042 / 1,000,000; output tokens free.
- Claude Opus 5.5: input tokens × $4 / 1,000,000 + output tokens × $20 / 1,000,000. These runs reported no cache reads/writes.

These are not invoices or a measured total cost of ownership. Raw API calls, model IDs, token usage and elapsed measurements are retained in benchmark/workflow-cost/{jev,claude}/. The runnable measuring client is benchmark/run_workflow_cost.py. The earlier 37-question pilot's price is a different unit: approximately $0.000987 for Jev and $0.183092 for Claude, excluding its warm-up and full agent calls.

## Laya complete-run measurements

The real Laya typed-decisions checkpoint was also measured for three Scenario A runs on MPS, with the same harness and threshold. Median elapsed time was 0.41 seconds (range 0.41–0.74), with four in-process decisions per run. Every run escalated all four intent clauses and generated no enabled guardrail, including no privilege policy. It did less work than the hosted candidates; speed does not establish a successful change.

There was no API charge. Compute, energy, hardware amortization and operations are unpriced; token usage is not reported by the adapter. Model import/loading took 3.33 seconds in this invocation, excluded from per-run elapsed time. This is cached checkpoint initialization, not measured installation or initial download time. The loader's temperature warning and lack of local calibration still apply. Raw measurements and actual device are under benchmark/workflow-cost/laya-mps/.

An initial sandboxed run fell back to CPU, with a 1.21-second median and the same all-escalation result. It is retained under benchmark/workflow-cost/laya/ as a separate configuration and is not mixed into the MPS result. The earlier Laya pilot measured 16/33 choices and approximately 89 ms per in-process decision. Neither result establishes a lower cost per accepted secure change because these full runs produced no guardrail.

## Setup and operating cost

| Component | Hosted inference | Local inference |
|---|---|---|
| Setup work | Account/billing, secure credentials, outbound connectivity, provider adapter; Claude multi-workspace key also needs the workspace header | Runtime dependencies, checkpoint download/cache, device and precision selection, memory capacity, serving and monitoring |
| Shared project work | Compiler, policy/test fixtures, authorization, secret handling, evaluation, review workflow and observability | Same |
| Recurring inference | Metered API usage, plus retries and failed calls where billable | Owned CPU/GPU/memory, energy, capacity, patching and operations |
| Availability planning | Provider timeout/rate-limit handling, fallback and data-handling requirements | Hardware/process failures, serving capacity, checkpoint/runtime updates |
| Human work | Label adjudication, calibration, unmet intent, exceptions and approval | Same |

Setup duration and engineering rates were not measured. No setup-cost winner is claimed. Local pilot inference used an existing Apple-silicon Mac with 18 GiB RAM; there is no quoted purchase price or measured energy charge. A zero API invoice is not zero operating cost. Hosted inference avoids locally owning the model's serving GPU but still requires integration and operational work. The portable Kubernetes controls and deterministic compiler are shared across provider choices.

Use this accounting unit for a production decision:

**Cost per accepted change = amortized setup + inference + compute/operations + human review + failure/rework.**

As an explicit illustration, at an assumed expert rate of $120/hour, one extra minute of review costs $2. That exceeds the approximately $0.0378 API-price difference between these median Scenario A runs. Jev escalated four items versus Claude one, but item count is not measured review time. We cannot conclude which has lower total cost without timing real review and evaluating the resulting containment quality.

## Expert challenge

MODEL-DECISION-REVIEW.pdf provides three difficult, frozen decisions for teams to answer before revealing model results. Split a six-person table into pairs and give each pair one question; the table locks its three answers within three minutes. Compare accepted choices and abstentions; discuss rationale and enforcement boundaries separately. Jev scored 0/3 and Claude 2/3 on this selected teaching subset, versus 30/33 and 32/33 on the full pilot.

The cases were selected after observing errors, so room results do not establish that humans generally beat models. Human discussion/reading time and model API wall time cover different work. The storage label assumes backup criticality that the supplied text does not establish; disagreement is not proof of unsafe preservation. If the audience disputes a reference label, preserve its explanation and evaluate the dispute independently rather than editing the benchmark to manufacture a win.

Sources: [Jev models and pricing](https://docs.typesafe.ai/models), [Claude models and pricing](https://platform.claude.com/docs/en/models/overview). Full correctness, confidence and policy-test context is in HOSTED-COMPARISON.md; broader production evaluation and algorithm changes are specified in PRODUCTION-COMPARISON.md.
