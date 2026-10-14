"""One eligibility checker for slide preparation and the local-model demo launcher.

The offline check binds review evidence to inputs/code/host. A live check also probes model identity.
It is a narrow prepared-demo gate, not a production model certification or deployment permission.
"""
import argparse
import datetime as dt
import hashlib
import json
import pathlib
import platform
import sys

GEN = pathlib.Path(__file__).resolve().parent
ROOT = GEN.parent
sys.path.insert(0, str(GEN))
import decider_agent as da
from decision_contract import score


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fingerprints():
    import generate as g
    files = [GEN / name for name in (
        "decision_contract.py", "decider_agent.py", "policy_agent.py", "policy_contracts.py", "control_library.py", "generate.py", "decider_eval.py", "demo_gate.py", "schema.json")]
    files += sorted((GEN / "contracts").glob("*"))
    files += [ROOT/'controls/catalog.json', ROOT/'controls/schema.json']
    for scenario, config in g.SCENARIOS.items():
        files += [GEN / f"intent-{scenario}.txt", config["dir"] / config["fixtures"]]
        if config["userinfo"]:
            files.append(config["dir"] / config["userinfo"])
    return {str(p.relative_to(ROOT)): sha(p) for p in files if p.is_file()}


def host():
    return {"system": platform.system(), "machine": platform.machine(), "python": platform.python_version(), "node": platform.node()}


def check(path, *, url="http://127.0.0.1:8000", offline=False, recording=None, now=None, probe=None):
    import decider_eval as evaluation
    import policy_agent as pa
    import yaml
    try:
        summary = json.loads(path.read_text())
        if summary.get("demo_live_allowed") is not True or any(summary.get("gates", {}).get(k, {}).get("pass") is not True for k in ("G1_demo", "G2_core")):
            raise ValueError("the recorded evaluation did not pass G1 and G2")
        model = summary.get("served_model")
        if not isinstance(model, list) or len(model) != 1 or not isinstance(model[0], str) or any(s in model[0].lower() for s in ("fake", "unknown", "scripted")):
            raise ValueError("no single real model identity is established")
        config_bytes = (GEN / "decider-eval.yaml").read_bytes()
        config = yaml.safe_load(config_bytes)
        threshold = score(config["threshold"])
        if summary.get("threshold") != threshold or summary.get("config_sha256") != hashlib.sha256(config_bytes).hexdigest():
            raise ValueError("threshold or evaluation configuration changed")
        if summary.get("runtime_fingerprints") != fingerprints():
            raise ValueError("code or prepared inputs changed; rerun evaluation")
        if summary.get("host") != host() or summary.get("decider_url", "").rstrip("/") != url.rstrip("/"):
            raise ValueError("presenting host or model endpoint differs from evaluation")
        recorded_at = dt.datetime.fromisoformat(summary["recorded_at"])
        if recorded_at.tzinfo is None:
            raise ValueError("evaluation time has no timezone")
        age = ((now or dt.datetime.now(dt.timezone.utc)) - recorded_at).total_seconds()
        if age < -60 or age > 7 * 24 * 3600:
            raise ValueError("evaluation is future-dated or older than seven days")
        paths = {}
        for kind in ("decisions", "agent_runs", "demo_replay"):
            evidence = summary.get("evidence", {}).get(kind, {})
            name = evidence.get("file", "")
            if not name or pathlib.Path(name).name != name:
                raise ValueError("missing or invalid evidence path")
            artifact = path.parent / name
            if sha(artifact) != evidence.get("sha256"):
                raise ValueError("recorded evidence hash differs")
            paths[kind] = artifact
        rows = [json.loads(line) for line in paths["decisions"].read_text().splitlines()]
        items = evaluation.load_items(config)
        if len(rows) != len(items):
            raise ValueError("evaluation decisions are incomplete")
        for row, item in zip(rows, items):
            for key in ("set", "id", "text", "control"):
                if row.get(key) != item.get(key):
                    raise ValueError("evaluation cases differ from prepared inputs")
            if row.get("repeat") != item.get("repeat") or row.get("served_model") != model[0]:
                raise ValueError("evaluation repeat or model identity differs")
            confidence = score(row.get("confidence"))
            if row.get("choice") is not None and row["choice"] not in da.CONTROLS:
                raise ValueError("evaluation choice is outside the contract")
            if row.get("verdict") != evaluation.judge(item, row.get("choice"), confidence, threshold):
                raise ValueError("evaluation verdict does not match the decision")
        gates = evaluation.gates(rows, threshold)
        if not gates["G1_demo"]["pass"] or not gates["G2_core"]["pass"]:
            raise ValueError("recorded decisions fail the recomputed gates")
        runs = json.loads(paths["agent_runs"].read_text())
        if len(runs) != config["repeats"] or not all(
            r.get("finished") and r.get("privilege_policy") and r.get("independent_privilege_pass") is True
            and r.get("served_model") == model for r in runs):
            raise ValueError("complete agent runs or independent privilege checks failed")
        if len({json.dumps([x[:2] for x in r["decisions"]]) for r in runs}) != 1:
            raise ValueError("agent decisions differ across repeats")
        replay = json.loads(paths["demo_replay"].read_text())
        pa.Recorded(paths["demo_replay"]).bind("a", (GEN / "intent-a.txt").read_text(), threshold)
        if replay.get("model") != model or replay.get("tested_against") != "scenario fixtures":
            raise ValueError("fallback recording identity or observation source differs")
        if recording and sha(pathlib.Path(recording)) != sha(paths["demo_replay"]):
            raise ValueError("launcher fallback is not the evaluated recording")
        if not offline:
            response = (probe or da.ask)(url, da.split_clauses((GEN / "intent-a.txt").read_text())[0], (GEN / "intent-a.txt").read_text(), timeout=5)
            if not isinstance(response, dict) or response.get("model") != model[0] or da.parse_choice(response)[0] is None:
                raise ValueError("live server identity or decision contract differs")
        return {"allowed": True, "model": model[0], "threshold": threshold, "summary": str(path), "recording": str(paths["demo_replay"]), "scope": "prepared fixture proposal only; human review required"}
    except (OSError, ValueError, KeyError, TypeError, RuntimeError, AttributeError) as error:
        return {"allowed": False, "reason": str(error)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--summary")
    ap.add_argument("--decider", default="http://127.0.0.1:8000")
    ap.add_argument("--recording")
    ap.add_argument("--offline", action="store_true", help="check bound evidence without contacting a model")
    ap.add_argument("--model-only", action="store_true")
    ap.add_argument("--recording-only", action="store_true")
    args = ap.parse_args()
    candidates = [pathlib.Path(args.summary)] if args.summary else sorted((GEN / "recordings").glob("decider-eval-*.summary.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    result = {"allowed": False, "reason": "no current, bound passing evaluation is available"}
    # A newer failure must not silently fall back to an older passing evaluation.
    if candidates:
        result = check(candidates[0], url=args.decider, offline=args.offline, recording=args.recording)
    if args.model_only or args.recording_only:
        if result["allowed"]:
            print(result["model"] if args.model_only else result["recording"])
        else:
            print(result["reason"], file=sys.stderr)
    else:
        print(json.dumps(result, indent=2))
    return 0 if result["allowed"] else 1


if __name__ == "__main__":
    sys.exit(main())
