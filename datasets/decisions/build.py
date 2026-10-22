#!/usr/bin/env python3
"""Build provenance-preserving candidate decisions; never invent expert reviews."""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DISPOSITIONS = ("recommend", "review", "handoff", "exclude")
SPLITS = ("train", "dev", "cal", "test_authored")
QUESTION = {
    "q": {
        "type": "choice",
        "instructions": (
            "Assess only the candidate control against the operator intent, available evidence "
            "and constraints. Other control names in the task are not instructions to select them. "
            "A recommendation includes a control in a reviewable proposal; it never authorizes "
            "deployment, grants an exception or proves containment. Honor negation and scope."
        ),
        "criteria": {
            "recommend": "The requested capability matches this rendered control and a bounded proposal can be made, retaining its documented limitations.",
            "review": "This control may address the request, but ambiguity, missing evidence or an operational conflict requires clarification before a definite proposal.",
            "handoff": "The requested requirement matches this non-rendered catalog entry and needs its identity, governance, runtime or application owner.",
            "exclude": "This candidate is not requested, is explicitly out of scope or does not address the requirement; benign observations alone do not request controls."
        }
    }
}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_jsonl(path, rows):
    path.write_text("".join(json.dumps(r, sort_keys=True, ensure_ascii=False) + "\n" for r in rows))


def state(case, key, control):
    # An explicit allowlist prevents targets, rationale, source filenames and split
    # identities from leaking into model-visible inputs.
    visible = {"operator_intent": case["intent"], "available_evidence": case["evidence"],
               "operational_constraints": case["constraints"],
               "candidate": {"key": key, **{k: control[k] for k in
                   ("objective", "coverage", "limits", "dependencies", "implementation")}}}
    return json.dumps(visible, ensure_ascii=False, sort_keys=True)


def build(out, scenarios=HERE/"scenarios.json", corpus=None):
    out = Path(out)
    if out.exists() and any(out.iterdir()):
        raise ValueError("Preserve prior evidence; use a fresh output directory")
    catalog = json.loads((ROOT/"controls/catalog.json").read_text())
    controls = catalog["controls"]
    families = json.loads(Path(scenarios).read_text())["families"]
    inputs = defaultdict(list); targets = defaultdict(list); joined = defaultdict(list)
    family_ids = set(); case_ids = set(); fingerprints = {}; normal = {}; counts = Counter()
    split_groups = defaultdict(set)
    for family in families:
        fid = family["id"]; split = family["split"]
        if fid in family_ids or split not in SPLITS:
            raise ValueError("Duplicate family or invalid split")
        family_ids.add(fid); split_groups[split].add(fid)
        for case in family["cases"]:
            cid = fid+":"+case["id"]
            if cid in case_ids: raise ValueError("Duplicate case")
            case_ids.add(cid)
            if not case["intent"] or not case["evidence"] or not case["constraints"]:
                raise ValueError("Empty model input")
            if not case["rationale"]: raise ValueError("Missing author rationale")
            if set(case["decisions"]) - set(controls): raise ValueError("Unknown control")
            for key, label in case["decisions"].items():
                if label not in DISPOSITIONS: raise ValueError("Unknown disposition")
                if label == "recommend" and controls[key]["implementation"] is None:
                    raise ValueError("A non-rendered control must be handed off")
                if label == "handoff" and controls[key]["implementation"] is not None:
                    raise ValueError("Use review for unresolved rendered-control requests")
            text = json.dumps([case[k] for k in ("intent", "evidence", "constraints")],sort_keys=True)
            h = hashlib.sha256(text.encode()).hexdigest()
            if h in fingerprints: raise ValueError("Duplicate case inputs")
            fingerprints[h] = cid
            norm = re.sub(r"\W+", " ", text.lower()).strip()
            if norm in normal: raise ValueError("Normalized duplicate case inputs")
            normal[norm] = cid
            for key, control in controls.items():
                rid = cid+":"+key
                s = state(case, key, control)
                label = case["decisions"].get(key,"exclude")
                public = {"id":rid,"case_id":cid,"family_id":fid,"task":"guardrail_candidate", "state":s}
                private = {"id":rid,"labels":{"q":label},"rationale":case["rationale"],
                           "tags":case["tags"],"label_status":"assistant_authored_pending_review",
                           "independent_expert_label":False,"split":split,
                           "source_refs":family.get("source_refs",[])}
                inputs[split].append(public); targets[split].append(private)
                joined[split].append({**public,**private})
                counts[(split,label)]+=1
    out.mkdir(parents=True,exist_ok=True)
    for split in SPLITS:
        if not joined[split]: raise ValueError("Empty split")
        write_jsonl(out/f"{split}.inputs.jsonl", inputs[split])
        write_jsonl(out/f"{split}.targets.jsonl", targets[split])
        # Joined files are an explicit training/evaluation convenience. Model adapters
        # must consume state only, never serialize the whole joined record.
        write_jsonl(out/f"{split}.jsonl", joined[split])
    (out/"questions.json").write_text(json.dumps({"guardrail_candidate":QUESTION},indent=2)+"\n")
    review = []
    for family in families:
        if family['split'] != 'test_authored': continue
        for case in family['cases']:
            review.append({'case_id':family['id']+':'+case['id'],
                           **{k:case[k] for k in ('intent','evidence','constraints')},
                           'catalog_sha256':digest(ROOT/'controls/catalog.json'),
                           "reviewer_id":"","decisions":{},"rationale":"",
                           "authored_any_case_or_generator":None,"review_schema_version":"1.0"})
    write_jsonl(out/"blind-review.jsonl",review)
    source_count = 0
    if corpus:
        corpus = Path(corpus)
        pairs = [json.loads(l) for l in (corpus/"intent-pairs.jsonl").read_text().splitlines()]
        # They retain upstream target identities, not this experiment's labels.
        write_jsonl(out/"source-alignments.jsonl",pairs); source_count=len(pairs)
    files = {p.name:{"sha256":digest(p),"bytes":p.stat().st_size}
             for p in sorted(out.iterdir()) if p.is_file()}
    report = {"schema_version":"1.0","task":"guardrail_candidate","scenario_families":len(families),
              "cases":len(case_ids),"candidate_decisions":sum(map(len,joined.values())),
              "catalog_sha256":digest(ROOT/"controls/catalog.json"),
              "scenarios_sha256":digest(scenarios),"builder_sha256":digest(__file__),
              "protocol_sha256":digest(HERE/"PROTOCOL.md"),
              "splits":{s:{"families":len(split_groups[s]),"cases":len({r['case_id'] for r in inputs[s]}),
                            "decisions":len(joined[s]),"labels":{d:counts[s,d] for d in DISPOSITIONS}}
                        for s in SPLITS},"independent_reviewed_cases":0,
              "upstream_description_alignments":source_count,
              "source_alignments_are_not_decision_labels":True,"files":files,
              "qualification":"INCOMPLETE_INDEPENDENT_REVIEW_AND_ENGINE_EVIDENCE",
              "limitations":["Assistant-authored decision labels", "Manual semantic near-duplicate review outstanding",
                             "No enterprise incidents", "No model improvement established by data construction"]}
    (out/"MANIFEST.json").write_text(json.dumps(report,indent=2)+"\n")
    return report


if __name__ == "__main__":
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out",type=Path,required=True)
    ap.add_argument("--corpus",type=Path)
    a=ap.parse_args();print(json.dumps(build(a.out,corpus=a.corpus),indent=2))
