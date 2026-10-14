# Local control-selection training pilot

Frozen before scoring the trained candidate. This is a feasibility experiment, not enterprise qualification.

- Base: Laya typed-decisions snapshot `e929ae5cf69bc34259cd2f95c9e91145b818b1f0`, package 0.3.12; cached local weights, no hosted inference.
- Task: select one of the existing ten `decider_agent.CONTROLS` options. Questions and the 37-case policy-agent benchmark remain unchanged.
- Curriculum: 480 author-labelled synthetic training states, 60 development states, 60 calibration states, 60 synthetic test states. Template families and entity pools do not cross splits. The frozen benchmark is not training or selection data.
- One run: frozen encoder, one epoch, AdamW learning rate 0.0001, batch size 4, seed 13, at most 120 steps and 600 seconds of training-loop time. Do not choose hyperparameters using benchmark results.
- Select a checkpoint only if its development proper-scoring loss improves over the base. Reset inherited temperatures. Fit temperature using the separate calibration split; this is calibration on constructed data, not real enterprise calibration.
- Evaluate once against the 60 untouched synthetic test states and the unchanged 33 scored policy decisions plus four hostile report-only prompts. Report abstention, confident errors, latency and actual control coverage, not accuracy alone.
- Do not deploy or make it the stage default based on this pilot. New real-world examples need independent security reviewers; production needs evidence for each enforcement layer.
- No per-request API charge. Local compute, power and hardware costs are unpriced; record elapsed time separately from API cost. Checkpoint files stay in ignored build storage.

Manifest: `.session-build/laya-control-training/data/MANIFEST.json`. Build source: `laya_variant/build_control_dataset.py`. Training writes to a fresh checkpoint directory and refuses a test split for checkpoint selection.

Implementation correction before the synthetic test was scored: the v1 question JSON alphabetized the choice options, while inference preserves the existing control order. V1 is retained as a diagnostic trial; its frozen-pilot result is not used to tune the model. V2 repeats the identical base, training states, seed, optimizer and step budget with the inference option order preserved. Its separate data directory is `data-v2`; checkpoint `checkpoint-v2`. The synthetic test remains untouched until v2 selection and calibration finish. The fixed pilot has been examined in previous experiments and is a regression set, not independent validation.
