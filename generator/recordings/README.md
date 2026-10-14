# Real policy-agent runs

`spec-<scenario>-qwen3-4b-instruct-2026-09-28.json` is exactly what `qwen3:4b-instruct` (Ollama 0.34.2, on the
presenter's Mac, temperature 0, seed 0, num_ctx 8192) returned for the request `generate.py` sends: same system
prompt, same user message, same JSON schema. The request text was hash-checked against `call_ollama()` before the
call, and each answer was hash-checked after transcription (`*.meta.json`).

What happened, all three scenarios:

- Every spec **passed the JSON schema**. Structured output guarantees shape, not sense.
- Every spec **was refused by the compiler** before any policy was written: each proposes exceptions against a
  control it never enabled (`generate.py` exits 2).
- Read as a reviewer would: A maps "prevent privilege escalation" to `not_implementable` and east-west traffic to
  the agent-mutation control; B maps all four clauses to `restrict_api_access`; C calls the ticket rule
  "not implementable". Several notes are cut off mid-word at the schema's 500-character limit.

So the demo's policy-agent step replays a hand-written reference spec (`generator/spec-*.json`,
`model: none (spec supplied)` in provenance), and the deck says so. The repo's default model,
`qwen3-coder:30b`, has not been run yet: it is not installed on the demo laptop.

Reproduce the check:

    python3 generator/generate.py --scenario a --from-spec generator/recordings/spec-a-qwen3-4b-instruct-2026-09-28.json --no-classify
