# Research Constraints

## Goal
Minimize val_bpb on the standard autoresearch benchmark within the 5-minute wall-clock budget.

## Rules
- Do not modify `prepare.py` or the evaluation harness
- Do not change the model architecture beyond what `train.py` exposes
- Muon optimizer is allowed; do not remove it
- Each mutation must be a single, coherent change to `train.py`

## Baseline
Starting from the reference `train.py` checked into this commit.
Validation target: beat the baseline val_bpb by at least 0.005 within 8 hours.
