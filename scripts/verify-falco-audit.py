#!/usr/bin/env python3
"""Exercise real Falco audit-plugin matching with synthetic loopback webhook events.

No kernel capture, Kubernetes access, provider call or automatic response. The
test-only receipt rule uses all-rule matching to establish that every input was
parsed, independently of whether a project detection rule matched it.
"""
import argparse
import collections
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
import urllib.error
import urllib.request
import uuid

ROOT = Path(__file__).resolve().parents[1]
IMAGE = "falcosecurity/falco:0.45.0"
PROJECT_TAGS = {"quarantine-q1", "quarantine-q2"}
GAP_TAG = "audit-visibility-gap"
WITNESS_TAG = "sc2632-test-witness"


def docker(*args, timeout=20):
    return subprocess.run(["docker", *args], capture_output=True, text=True, timeout=timeout)


def records(text):
    result = []
    for line in text.splitlines():
        try:
            item = json.loads(line)
        except ValueError:
            continue
        if isinstance(item, dict) and "rule" in item:
            result.append(item)
    return result


def fingerprint(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plugins", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--rules", type=Path, default=ROOT / "runtime/falco-rules-k8saudit.yaml")
    args = parser.parse_args()
    plugins, out, rules = args.plugins.resolve(), args.out.resolve(), args.rules.resolve()
    if out.exists():
        parser.error("output exists; preserve evidence and use a fresh directory")
    for path in [rules, plugins / "libk8saudit.so", plugins / "libjson.so"]:
        if not path.is_file():
            parser.error(f"required file unavailable: {path.name}")
    out.mkdir(parents=True)
    contract_path = ROOT / "ci/falco-audit-events.json"
    contract = json.loads(contract_path.read_text())
    (out / "contract.json").write_bytes(contract_path.read_bytes())
    (out / "rules.yaml").write_bytes(rules.read_bytes())
    (out / "witness.yaml").write_text("""- rule: SC2632 synthetic input receipt
  desc: Test-only input witness, separate from project detection rules.
  source: k8s_audit
  condition: ka.auditid exists
  output: "Synthetic receipt (auditid=%ka.auditid stage=%ka.stage target=%ka.target.name)"
  priority: DEBUG
  tags: [sc2632-test-witness]
""")
    (out / "falco.yaml").write_text("""engine:
  kind: nodriver
load_plugins: [k8saudit, json]
plugins:
  - name: k8saudit
    library_path: /plugins/libk8saudit.so
    init_config: ""
    open_params: "http://:9765/k8s-audit"
  - name: json
    library_path: /plugins/libjson.so
rules_files: []
json_output: true
json_include_output_property: true
json_include_tags_property: true
stdout_output:
  enabled: true
syslog_output:
  enabled: false
webserver:
  enabled: false
log_stderr: true
log_syslog: false
buffered_outputs: false
priority: debug
rule_matching: all
""")
    container = "sc2632-falco-audit-" + uuid.uuid4().hex[:12]
    started = time.monotonic()
    result = {"status": "ERROR", "scope": contract["scope"]}
    launched = False
    try:
        cmd = ["run", "--detach", "--name", container, "--network", "bridge",
               "--env", "HOST_ROOT=/", "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
               "--read-only", "--tmpfs", "/tmp:rw,noexec,nosuid,size=16m",
               "--publish", "127.0.0.1::9765",
               "--mount", f"type=bind,src={out},dst=/check,readonly",
               "--mount", f"type=bind,src={plugins},dst=/plugins,readonly",
               "--entrypoint", "/usr/bin/falco", IMAGE, "-c", "/check/falco.yaml",
               "-r", "/check/rules.yaml", "-r", "/check/witness.yaml", "--enable-source", "k8s_audit"]
        start = docker(*cmd)
        if start.returncode:
            raise RuntimeError("Falco container did not start: " + start.stderr.strip())
        launched = True
        info = docker("port", container, "9765/tcp")
        address = info.stdout.strip()
        if info.returncode or not address.startswith("127.0.0.1:"):
            raise RuntimeError("expected a loopback-only audit endpoint")
        port = int(address.rsplit(":", 1)[1])
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
        endpoint = f"http://127.0.0.1:{port}"
        deadline = time.monotonic() + 10
        while True:
            state = docker("inspect", "--format", "{{.State.Running}}", container)
            if state.stdout.strip() != "true":
                raise RuntimeError("Falco exited before audit HTTP readiness")
            try:
                with opener.open(endpoint + "/sc2632-readiness", timeout=0.5):
                    break
            except urllib.error.HTTPError as error:
                if error.code in (404, 405):
                    break
                raise
            except OSError:
                if time.monotonic() > deadline:
                    raise TimeoutError("audit HTTP listener did not become ready")
                time.sleep(0.1)
        events = [event for case in contract["cases"] for event in case["events"]]
        payload = json.dumps({"kind": "EventList", "apiVersion": "audit.k8s.io/v1", "items": events}).encode()
        request = urllib.request.Request(endpoint + "/k8s-audit", data=payload,
                                         headers={"Content-Type": "application/json"})
        with opener.open(request, timeout=5) as response:
            http_status = response.status
            if not 200 <= http_status < 300:
                raise RuntimeError("audit webhook refused the synthetic batch")
        expected_receipts = collections.Counter((e["auditID"], e["stage"]) for e in events)
        deadline = time.monotonic() + 5
        while True:
            parsed = records(docker("logs", container).stdout)
            receipts = collections.Counter((p["output_fields"]["ka.auditid"], p["output_fields"]["ka.stage"])
                                           for p in parsed if WITNESS_TAG in p.get("tags", []))
            if receipts == expected_receipts:
                break
            if time.monotonic() > deadline:
                raise TimeoutError("not every synthetic event reached the independent receipt rule")
            time.sleep(0.1)
        stopped = docker("stop", "--time", "3", container)
        finished = docker("wait", container, timeout=5)
        if stopped.returncode or finished.returncode or finished.stdout.strip() != "0":
            raise RuntimeError("Falco did not shut down cleanly")
        raw = docker("logs", container)
        for version in ["Falco version: 0.45.0", "k8saudit@0.18.0", "json@0.7.4"]:
            if version not in raw.stderr:
                raise RuntimeError("loaded engine/plugin identity differs from the pinned contract")
        alerts = records(raw.stdout)
        checks = []
        for case in contract["cases"]:
            matching = [a for a in alerts if a["output_fields"].get("ka.target.name") == case["target_name"]
                        and WITNESS_TAG not in a.get("tags", [])]
            observed = sorted(t for a in matching for t in a.get("tags", []) if t in PROJECT_TAGS)
            gaps = sorted(t for a in matching for t in a.get("tags", []) if t == GAP_TAG)
            passed = observed == case["expected_alert_tags"] and gaps == case["expected_evidence_gap_tags"]
            checks.append({"id": case["id"], "classification": case["classification"],
                           "expected_alerts": case["expected_alert_tags"], "observed_alerts": observed,
                           "expected_evidence_gaps": case["expected_evidence_gap_tags"],
                           "observed_evidence_gaps": gaps, "passed": passed})
        image_info = docker("image", "inspect", IMAGE, "--format", "{{.Id}} {{.Os}}/{{.Architecture}}")
        result.update(status="PASS" if all(c["passed"] for c in checks) else "FAIL",
                      case_count=len(checks), passed_cases=sum(c["passed"] for c in checks),
                      events_received=sum(receipts.values()), webhook_http_status=http_status, checks=checks,
                      image=IMAGE, image_identity=image_info.stdout.strip(),
                      rules_sha256=fingerprint(rules), contract_sha256=fingerprint(contract_path),
                      harness_sha256=fingerprint(__file__),
                      plugin_sha256={n: fingerprint(plugins / n) for n in ["libk8saudit.so", "libjson.so"]})
    except Exception as error:
        result.update(status="ERROR", error=f"{type(error).__name__}: {error}")
    finally:
        if launched:
            raw = docker("logs", container)
            (out / "falco.stdout.jsonl").write_text(raw.stdout)
            (out / "falco.stderr.txt").write_text(raw.stderr)
            removed = docker("rm", "--force", container)
            result["container_removed"] = removed.returncode == 0
            if removed.returncode:
                result.update(status="ERROR", error="test container cleanup failed")
        result.update(elapsed_seconds=round(time.monotonic() - started, 3),
                      kernel_capture=False, cluster_contacted=False, automatic_containment=False,
                      matching_mode="all, for the test-only input receipt rule")
        (out / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
