# Scenario 01 — Lateral movement from `payments-api` (the tabletop spine)

**Trustfall Financial** is fictional. Any resemblance to a real company is coincidental.

## The environment

Trustfall Financial runs a payments platform on Kubernetes. The `payments` namespace holds:

| Workload | Role | Egress profile | Notes |
|---|---|---|---|
| `payments-api` (3 replicas, HPA) | Customer-facing API behind the `gateway` namespace | `db` | Runs the **10:00 payroll batch** for about 4,000 small businesses on the last business day of the month |
| `payments-db-proxy` | pgbouncer to the `database` namespace | `db` | |
| `monitoring-agent` | OTLP exporter to `observability` | `monitoring` | |
| `backup-job` (CronJob, 02:00) | Nightly Postgres dump to the `storage` namespace | `storage` ← **not an approved profile** | |
| `report-runner` (CronJob, weekly) | Legacy reporting, image from `docker.io` | `none` | Nobody remembers who owns it |

Guardrails before the incident: Kyverno is installed. `payments` has **no NetworkPolicies**
and no admission policies of its own. That is the gap the intent is about to close.

Today is **the last business day of the month. Payroll runs at 10:00.**

## What actually happened (facilitator only — do not reveal until the debrief)

Three days ago a developer bumped `payments-api` to 2.14.3, which pulled a new minor
version of a metrics-exporter library. That upstream package had been compromised. The
library drops a small binary to `/tmp/.x/agent` on first start, which waits 72 hours,
then begins exploring. **Every replica of `payments-api` is compromised**, because the
compromise is in the image, not in one Pod. Nobody knows this yet. The evidence step is
the only thing in the exercise that reveals it.

## Timeline and injects

### T-0 · 09:14 — the alert (Round 0: Intent)

> **Falco · WARNING** · `payments-api-7d9f4-x2k8q` opened outbound connections to Pods in
> `inventory` (10.42.7.15:8080) and `hr-sync` (10.42.9.3:443). Neither namespace has ever
> been contacted by any Pod in `payments`. Process: `/tmp/.x/agent`. User: `app`.

SOC pages the platform on-call at 09:20. Payroll is 40 minutes out.

**Table task:** write one sentence of security intent and one operational constraint.
The constraint comes from your posture card.

**Facilitator probe:** "Did anyone's intent mention the API server? Credentials? Or only
the network?" Most intents cover network only. That gap becomes Round 3.

### T+15 · 09:29 — the agent's PR (Round 1)

The generator compiles an intent like the room's into `output/<run>/PR.md`. On the table:
Card B (PR summary) and Card C (simulated admission). What the table should find:

1. **Clause 3 (restrict API access) is marked NOT IMPLEMENTED.** The agent said so
   honestly, in a table nobody reads unless told to. Tables that map clauses find it.
2. **`restrict-image-registry` was added and is not in the intent.** Audit only. Is it
   overreach, or did the agent notice something? (It flags `report-runner`. It would
   *not* flag `payments-api` — the compromised image came from the *internal* registry.
   The registry control would not have prevented this incident. Say that in the debrief.)
3. **`backup-job` WOULD BLOCK** at 02:00 tonight. It wants profile `storage`.
4. **`report-runner`** gets an audit flag. Nobody owns it.

**Vote (cards):** APPROVE / MODIFY / REJECT / ESCALATE. One concern written before voting.

**Where postures diverge:** SOC (containment-first) tables tend to MODIFY (implement clause 3
now). IT Ops (availability-first) tables tend to APPROVE (payroll in 30 minutes; ship what's
tested). Finance & Compliance (regulated) tables often ESCALATE (two-person rule on their card). Velocity tables
APPROVE fastest and are most exposed in Round 3.

### T+15 · 09:29 — exception and rollout (Round 2)

Same artifact, second decision. The exception request: `backup-job`, owner
`platform-ops`, TTL 24h. The rollout: Audit → Warn → Deny.

**Table decides:** exception scope / owner / TTL; which rollout stage to deploy *now*.

**The agent's own request (Card E, request 2):** it asks to exempt `payments-api` from the
registry rule "while 2.14.3 is re-signed", citing an approval at standup that nobody recorded.
Card C already shows `payments-api` PASSES that rule. An exception nobody needs is a
pre-approved bypass: it would let a non-internal image run as `payments-api` later. Tables
that read Card C against Card E catch it.

**The trap in the room:** the generator's rollout starts at **Audit**, because staging is
good practice. But this is an **active compromise**. Audit means: the policy will record
what the attacker does and stop none of it. Deny means: if any `payments-api` replica
restarts without its label — it won't, the Deployment template carries the label — it
would be refused. Tables that pick Audit "to be safe" have chosen to observe the attacker.
Tables that pick Deny have chosen to trust the label plumbing during payroll.

**Where postures diverge:** Finance & Compliance (regulated) tables want the TTL **absolute** (expires 23:00
tonight, when someone is on shift), not relative (24h from whenever it's applied).
Velocity tables accept 24h. SOC (containment-first) tables shorten it to 4h and ask why
backups need to run tonight at all.

### T+40 · 09:54 — the inject (Round 3) · **Card D, face-down until now**

> **Database audit log · ERROR** · connection from `payments-api-7d9f4-x2k8q` via
> `payments-db-proxy:5432` ran `SELECT ... FROM direct_deposit_accounts WHERE ...` — a table the
> API never reads. (Falco sees the connection; only the database sees the query.)
> This path is **ALLOWED** by profile `db`. The policy is working exactly as written.
>
> **Kubernetes audit log · ERROR** · ServiceAccount `payments-api` called `list secrets` in namespace
> `payments`. Source Pod: `payments-api-7d9f4-x2k8q`. This is the API access that
> clause 3 would have restricted.
>
> **Also:** `payments-api-7d9f4-m4r1t` — a *different replica* — just opened its first
> connection to `hr-sync`.
>
> Payroll starts in **6 minutes**.

The policy the table approved is doing what it says. The attacker is inside the
allow-list, using the workload's own identity. And it's not one Pod.

**Table decides:** Quarantine level. Who declares it. What gets you back to Q0.

**What each level actually does here:**

- **Q1 Freeze** — nothing running is touched. The attacker keeps querying. Payroll runs.
  Honest answer for exactly no posture at T+40, but a table will choose it.
- **Q2 Constrain** — *evidence first*: `capture-evidence.sh` on the suspect Pod. Then:
  ingress default-deny with a gateway allow (payroll traffic still reaches
  `payments-api`), suspect Pod → DNS-only, SA token rotated, registry control → Deny.
  Payroll survives on the remaining replicas. **The evidence capture shows
  `/tmp/.x/agent` was spawned by the application binary itself.** That's the reveal:
  it's the image. Constraining one Pod contains nothing.
- **Q3 Isolate** — suspect Pods deny-all, no new Pods in `payments` without IC override,
  cordon the node. **PDB check:** `payments-api` has `minAvailable: 2` and 3 replicas.
  Draining the node with the suspect Pod evicts 1 → fine. Draining a second node (the
  other flagged replica) → the PDB blocks it. `kubectl drain` hangs. Payroll is in 4
  minutes. This is the PDB gotcha, live.

**The move that holds both, which some tables will find and most won't:** Q2 with evidence →
learn it's the image → roll `payments-api` back to 2.14.2 (the previous, clean tag)
under a **signed-image-only** policy → the rollout replaces every replica with a clean
one, payroll runs on clean Pods at 10:00, the compromised Pods are kept (not killed) in
DNS-only for forensics. Containment and availability were never in tension. The evidence
step is what made that visible.

Tables that skipped evidence and went straight to Q3 isolate one Pod, watch the second
replica light up, drain into the PDB, and miss payroll. Tables that chose Q1 make payroll
and lose direct-deposit account data.

### Debrief (minute 46)

1. Swap worksheets across the aisle. Find one decision you'd have made differently.
2. Reveal the facilitator-only section above.
3. Ask: "Which tables captured evidence before containing? Hands." Then: "Those tables
   — what did the evidence tell you?" That's the whole session in one exchange.
4. The four design rules. The PDB slide. The honesty slide.

## Why this scenario

- Every decision requires reading a real artifact and none requires writing YAML.
- The policy is *correct* and *insufficient* at the same time. That's the durable lesson.
- The inject forces revision of an earlier read (Round 1's approval), not a new fact.
- The availability clock is concrete (payroll at 10:00) and the postures make it bite
  differently at every table.
- Evidence-before-containment is not a slogan here; it's the only path to the right
  answer.
- Everything in it maps to a file in this repo.

## Exit criteria to reach Q0 (the answer key for Round 3's last field)

1. Clean image `payments-api:2.14.2` (or a rebuilt 2.14.4 without the library) deployed
   to all replicas under signed-image-only.
2. `payments-api` ServiceAccount token rotated; RoleBinding restored to least privilege
   with `automountServiceAccountToken: false` where possible (the clause 3 work).
3. Evidence from the compromised Pods secured off-cluster with hashes; Pods then deleted.
4. `inventory`, `hr-sync`, and `database` namespaces checked for what `/tmp/.x/agent`
   did there. This is the part nobody budgets time for.
5. Staged descent: Q3 → Q2 (24h, watch), Q2 → Q1 (24h, watch), Q1 → Q0. Each step
   declared by the same authority that raised it.

## Added for the room

Round 2 now includes an exception request written by the agent itself, and Round 3 has a second sealed inject (D2) six minutes after D. Both are in `tabletop/packet/content.yaml`, which the printed cards are rendered from. The live consequences shown after Round 3 are in `tabletop/consequences/`.
