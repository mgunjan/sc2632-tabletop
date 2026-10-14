#!/usr/bin/env python3
"""Fast static lint of runtime/falco-rules-*.yaml: structure, every trustfall_* macro/list is
defined, every field is one checked against Falco's documented field lists, k8s_audit rules
declare their source. Not a substitute for `falco --validate` (CI runs that)."""
import re, sys, pathlib, yaml
ROOT = pathlib.Path(__file__).resolve().parent.parent
KNOWN = {
  "syscall": {"evt.type","evt.dir","evt.is_open_read","fd.typechar","fd.l4proto","fd.snet","fd.sip","fd.sport","fd.name",
              "k8s.ns.name","k8s.pod.name","container.name","proc.name","proc.pname","proc.cmdline","user.name"},
  "k8s_audit": {"ka.user.name","ka.verb","ka.target.resource","ka.target.subresource","ka.target.namespace","ka.target.name",
                "ka.response.code","ka.req.binding.subjects","ka.req.binding.role"},
}
bad = 0
for name, src in [("falco-rules-syscall.yaml", "syscall"), ("falco-rules-k8saudit.yaml", "k8s_audit")]:
    path = ROOT / "runtime" / name
    docs = yaml.safe_load(path.read_text())
    lists = {d["list"] for d in docs if "list" in d}; macros = {d["macro"] for d in docs if "macro" in d}
    for d in docs:
        text = " ".join(str(d.get(k, "")) for k in ("condition", "output"))
        for m in re.findall(r"\btrustfall_\w+", text):
            if m not in lists | macros: print(f"{name}: undefined {m}"); bad += 1
        for f in re.findall(r"%?\b((?:evt|fd|k8s|container|proc|user|ka)\.[a-z0-9_.]+)", text):
            if f.lstrip("%") not in KNOWN[src]: print(f"{name}: unknown field {f}"); bad += 1
        if "rule" in d:
            missing = {"desc", "condition", "output", "priority"} - d.keys()
            if missing: print(f"{name}: rule '{d['rule']}' missing {missing}"); bad += 1
            if src == "k8s_audit" and d.get("source") != "k8s_audit": print(f"{name}: rule '{d['rule']}' needs source: k8s_audit"); bad += 1
    print(f"{name}: {sum('rule' in d for d in docs)} rules ok" if not bad else f"{name}: problems")
sys.exit(1 if bad else 0)
