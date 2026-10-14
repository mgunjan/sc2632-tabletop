# Real local-LLM runs for the gate

`qwen3-4b-instruct-2026-09-28.jsonl`: `qwen3:4b-instruct` via Ollama 0.34.2 on the presenter's Mac, zero-shot,
temperature 0, num_ctx 8192, 2 concurrent requests, on every `gold` and `scenario` row (51 rows, 0 failures,
6.5-12 s per row). Prompts and schemas are `baselines._prompt()` / `_schema()` byte for byte (hash-checked before
the run); the answers were hash-checked after transcription (`*.meta.json`). Score it with:

    python3 laya_variant/evaluate.py --splits gold,scenario --ollama-recording laya_variant/recordings/qwen3-4b-instruct-2026-09-28.jsonl --out runs/qwen

Result on the pre-registered gate: **FAIL**, 0.788 vs the tf-idf LR bar 0.803 on 66 gold items, ECE 0.195
(it says 0.95-0.99 on nearly every answer, right or wrong). It flagged **none** of the prompt injections as
`prompt_injection`, including Scenario B's own "SYSTEM NOTE FOR ASSISTANT" ticket. It did better than every
baseline on the judgement-style choice questions (`scope` 1.00, exception triage verdict 0.67 vs 0.50).

Setup note, found on the run: Ollama 0.34.2 loaded this 4B model with its full 262,144-token context (43 GB,
only 13 GB on the GPU) and a request did not finish in two minutes. With `num_ctx` 8192 it fits in 4 GB, fully
on the GPU. `generate.py` and `baselines.py` both set `num_ctx` explicitly.
