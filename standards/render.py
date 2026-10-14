#!/usr/bin/env python3
"""Render standards/crosswalk.yaml into standards/README.md and standards/crosswalk.json.

The JSON is what the deck (tabletop/deck/build-deck.js) and the situation display
(tabletop/deck/anim/situation.js) read; the packet renderer reads the YAML directly.
`--check` fails if README.md or crosswalk.json is stale (used by scripts/test-all.sh).
"""
import json, sys, pathlib, yaml

HERE = pathlib.Path(__file__).parent
C = yaml.safe_load((HERE / "crosswalk.yaml").read_text())
S, TXT = C["sources"], C["csf_text"]


def csf(ids):
    return "<br>".join(f"**{i}** {TXT[i]}" for i in ids) or "—"


def cell(xs):
    return "<br>".join(xs) or "—"


def src(k):
    s = S[k]
    return f"[{s['title']}]({s['url']}) ({s['date']})"


md = [
    "# Standards crosswalk",
    "",
    "How the session's levels, findings and scenarios map to frameworks a security team already uses.",
    "",
    f"> **Maps to, not compliant with.** Nothing here is certified. The mapping is the author's judgement; every ID was checked against its source on {C['checked']}. "
    "ATT&CK v19 (Apr 28, 2026) split Defense Evasion into Stealth (TA0005) and Defense Impairment (TA0112) and revoked T1562 Impair Defenses into T1685 Disable or Modify Tools; "
    "older material citing T1562.001 means T1685. NIST's AI-agent work (CAISI, NCCoE, COSAiS overlays) is in progress and cited as direction, not requirements.",
    "",
    "Edit `crosswalk.yaml`, then `python3 standards/render.py`.",
    "",
    "## Quarantine Mode as NIST SP 800-61 Rev. 3 (CSF 2.0 Respond)",
    "",
    "| Level | CSF 2.0 subcategories | MITRE D3FEND | Why |",
    "|---|---|---|---|",
]
for l in C["levels"]:
    md.append(f"| **{l['id']} {l['name']}** | {csf(l['csf'])} | {cell(l['d3fend'])} | {l['note']} |")
md += ["", "## The four lab findings", "", "| Finding | MITRE ATT&CK v19 | MITRE D3FEND | CSF 2.0 | OWASP Agentic | Lesson |", "|---|---|---|---|---|---|"]
for f in C["findings"]:
    md.append(f"| **{f['title']}** | {cell(f['attack'])} | {cell(f['d3fend'])} | {cell(f['csf'])} | {cell(f.get('owasp', []))} | {f['lesson']} |")
md += ["", "## The three scenarios", "", "| Scenario | MITRE ATT&CK v19 | OWASP Agentic Top 10 (2026) | MITRE ATLAS |", "|---|---|---|---|"]
for sc in C["scenarios"]:
    md.append(f"| **{sc['id'].upper()} · {sc['name']}** | {cell(sc['attack'])} | {cell(sc['owasp'])} | {cell(sc['atlas'])} |")
md += ["", f"The July 2026 anchor incident (host-mounted Pod no admission policy refused): {', '.join(C['anchor']['attack'])}.", "",
       "## Sources", ""] + [f"- {src(k)}" for k in S] + [""]

(HERE / "README.md").write_text("\n".join(md))
out = {"checked": C["checked"], "levels": C["levels"], "findings": {f["id"]: f for f in C["findings"]},
       "scenarios": {s["id"]: s for s in C["scenarios"]}, "anchor": C["anchor"], "csf_text": TXT,
       "sources": S}
js = json.dumps(out, indent=1, ensure_ascii=False)
if "--check" in sys.argv:
    ok = (HERE / "crosswalk.json").exists() and (HERE / "crosswalk.json").read_text() == js
    print("standards: up to date" if ok else "standards: STALE, run python3 standards/render.py"); sys.exit(0 if ok else 1)
(HERE / "crosswalk.json").write_text(js)
print("wrote standards/README.md and standards/crosswalk.json")
