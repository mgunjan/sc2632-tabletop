#!/usr/bin/env python3
"""Bounded presenter proposal demo. No kubectl, deployment, automatic exception or hosted fallback."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
GEN = ROOT / "generator"
BENCHMARK = ROOT / "submission/2026-10-12/benchmark"


def preflight():
    missing = [name for name in ("yaml", "jsonschema") if importlib.util.find_spec(name) is None]
    binary = shutil.which("kyverno")
    version = "unavailable"
    if binary:
        try:
            check = subprocess.run([binary, "version"], capture_output=True, text=True, timeout=5)
            version = check.stdout.strip().splitlines()[0] if check.returncode == 0 and check.stdout.strip() else "unavailable"
        except (OSError, subprocess.TimeoutExpired):
            pass
    result = {"python": sys.version.split()[0], "missing_python_modules": missing, "kyverno_path": binary,
              "kyverno": version, "expected_kyverno": "1.19.1", "cluster_required": False,
              "hosted_api_required_for_reference_or_replay": False}
    parsed_version = re.fullmatch(r"Version:\s*v?(\d+\.\d+\.\d+)", version)
    result["ready"] = not missing and parsed_version is not None and parsed_version[1] == "1.19.1" and sys.version_info >= (3, 10)
    return result


def worker(args):
    sys.path.insert(0, str(GEN))
    import generate as compiler
    import policy_agent as agent
    import policy_contracts
    out = Path(args.out)
    proposal = out / "proposal"
    intent = (GEN / f"intent-{args.scenario}.txt").read_text()
    if args.mode == "reference":
        subprocess.run([sys.executable, str(GEN / "generate.py"), "--scenario", args.scenario,
                        "--from-spec", str(GEN / f"spec-{args.scenario}.json"), "--out", str(out / "compiled"), "--no-classify"],
                       cwd=ROOT, check=True, capture_output=True, text=True)
        compiled = list((out / "compiled").glob(f"{args.scenario}-*"))
        if len(compiled) != 1:
            raise RuntimeError("expected one reference compilation")
        compiled[0].rename(proposal)
        (out / "compiled").rmdir()
        spec = json.loads((proposal / "spec.json").read_text())
        review = policy_contracts.evaluate(args.scenario, intent, spec, [], proposal)
        with (proposal / "PR.md").open("a") as stream:
            stream.write(policy_contracts.pr_section(review))
    else:
        if args.mode == "replay":
            recording = Path(args.recording) if args.recording else BENCHMARK / "expanded/jev-jev-1.13.0/agent-a/agent-run.json"
            provider = agent.Recorded(recording)
        else:
            sys.path.insert(0, str(BENCHMARK))
            from provider_clients import ClaudeProvider, JevProvider, load_credentials
            if args.env_file:
                load_credentials(args.env_file, args.mode)
            if args.workspace_file:
                os.environ["ANTHROPIC_WORKSPACE_ID"] = Path(args.workspace_file).read_text().strip()
            provider = JevProvider() if args.mode == "jev" else ClaudeProvider()
        rec = agent.Agent(args.scenario, intent, "", 0.6, False, proposal, asker=provider, echo=lambda *_: None).run()
        review = rec["readiness"]
    return review


def terminate(process):
    """The worker and its policy-tool children have their own process group."""
    try:
        if os.name == "posix":
            os.killpg(process.pid, signal.SIGTERM)
        else:
            process.terminate()
        process.communicate(timeout=2)
    except subprocess.TimeoutExpired:
        if os.name == "posix":
            os.killpg(process.pid, signal.SIGKILL)
        else:
            process.kill()
        process.communicate()
    except ProcessLookupError:
        pass


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("reference", "replay", "jev", "claude"), default="reference")
    parser.add_argument("--scenario", choices=("a", "b", "c"), default="a")
    parser.add_argument("--out", help="fresh output directory; existing evidence is never overwritten")
    parser.add_argument("--recording", help="required for B/C replay; default A replay is the frozen Jev recording")
    parser.add_argument("--env-file")
    parser.add_argument("--workspace-file")
    parser.add_argument("--kyverno", help="explicit executable named kyverno; also used by compiler/test subprocesses")
    parser.add_argument("--deadline", type=float, default=15, help="whole-run seconds, including compiler/tests; 1..60")
    parser.add_argument("--check", action="store_true", help="read-only dependency preflight; no inference or cluster access")
    parser.add_argument("--_worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.kyverno:
        binary = Path(args.kyverno).expanduser().absolute()
        if binary.name != "kyverno" or not binary.is_file() or not os.access(binary, os.X_OK):
            parser.error("--kyverno must point to an executable file named kyverno")
        os.environ["PATH"] = str(binary.parent) + os.pathsep + os.environ.get("PATH", "")
    if args.check:
        result = preflight()
        print(json.dumps(result, indent=2))
        return 0 if result["ready"] else 2
    if not 1 <= args.deadline <= 60:
        parser.error("deadline must be finite and between 1 and 60 seconds")
    if not args.out:
        parser.error("--out is required; use a fresh output/congress-2026/<run-name> directory")
    if args.mode == "replay" and args.scenario != "a" and not args.recording:
        parser.error("B/C replay requires an explicit matching recording")
    if args._worker:
        try:
            worker(args)
            return 0
        except Exception as error:
            # Only the exception class is printed: provider payloads and credential values stay off the projector.
            print(f"Proposal worker failed: {type(error).__name__}", file=sys.stderr)
            return 1
    out = Path(args.out).resolve()
    if out.exists():
        parser.error("output already exists; preserve it and choose a fresh run name")
    if not preflight()["ready"]:
        parser.error("dependency preflight failed; run --check before rehearsal")
    out.mkdir(parents=True)
    labels = {"reference": "REFERENCE SPEC: supplied answer; compiler and fixture tests run now",
              "replay": "REPLAY: recorded model answers; compiler and fixture tests run now",
              "jev": "LIVE JEV: prepared fixture proposal; human review required",
              "claude": "LIVE CLAUDE: prepared fixture proposal; human review required"}
    print(labels[args.mode], flush=True)
    started = time.monotonic()
    command = [sys.executable, str(Path(__file__).resolve()), *sys.argv[1:], "--_worker"]
    process = subprocess.Popen(command, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               text=True, start_new_session=(os.name == "posix"))
    status = "FAILED"; exit_code = 1
    try:
        stdout, stderr = process.communicate(timeout=args.deadline)
        if process.returncode == 0:
            status = "COMPLETE_REVIEW_PROPOSAL"; exit_code = 0
        else:
            print("Proposal did not complete. Use the reference run or the prepared slides.")
    except subprocess.TimeoutExpired:
        terminate(process)
        status = "DEADLINE_EXCEEDED"; exit_code = 124
        print("Time limit reached. Use the reference run or the prepared slides.")
    except KeyboardInterrupt:
        terminate(process)
        status = "INTERRUPTED"; exit_code = 130
        print("Demonstration interrupted; no deployment occurred.")
    run = {"status": status, "mode": args.mode, "scenario": args.scenario,
           "elapsed_seconds": round(time.monotonic() - started, 3), "deadline_seconds": args.deadline,
           "deployment_performed": False, "api_calls_possible": args.mode in ("jev", "claude")}
    if exit_code != 0 and (out / "proposal").exists():
        (out / "proposal").rename(out / "partial-proposal-do-not-use")
    (out / "demo-run.json").write_text(json.dumps(run, indent=2) + "\n")
    if exit_code == 0:
        proposal = out / "proposal"
        review = json.loads((proposal / "readiness.json").read_text())
        print(f"Review status: {review['status']}; automatic promotion: disabled")
        print(f"Independent privilege checks: {review['independent_behavior']['status']}")
        for requirement in review["requirements"]:
            print(f"  Clause {requirement['id']}: {requirement['status']} ({requirement['layer']})")
        print(f"Open: {proposal / 'PR.md'}")
        print(f"Complete run: {run['elapsed_seconds']:.2f}s. No GitHub PR or cluster change was made.")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
