#!/usr/bin/env python3
"""Create the matched no-reference ablation without editing held-out data."""
import argparse
import json
from pathlib import Path
from source_curriculum import mask_reference

if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source',type=Path,required=True);ap.add_argument('--out',type=Path,required=True)
    a=ap.parse_args();m=mask_reference(a.source,a.out)
    print(json.dumps({'version':m['version'],'unique_model_visible_training_states':m['unique_model_visible_training_states']},indent=2))
