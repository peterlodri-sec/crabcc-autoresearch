# Research Constraints

## Goal

Train the most data-efficient character-level transformer possible. Minimise
`val_bpb` (validation bits-per-byte) on the provided text corpus. This is the
classic autoresearch task — a pure architecture and optimisation benchmark with
no domain-specific structure.

## Task

**Input:** raw UTF-8 text from `data/input.txt`  
**Output:** next-character prediction  
**Framing:** autoregressive character-level language model  
**Metric:** `val_bpb` on a held-out 10 % split of the corpus

## Why this task

Running the general LM task in parallel with the λ-normalization task lets us
separate domain-specific gains from general architectural improvements. Any
mutation that reduces `val_bpb` on both tasks simultaneously is a general
improvement worth keeping; one that helps only λ-normalization may be exploiting
task structure. The split also doubles the number of training experiments per
GPU-night at no extra hardware cost.

## Rules

- Do not modify `prepare.py` or the evaluation harness
- Do not change the model architecture beyond what `train.py` exposes
- Muon optimizer is allowed; do not remove it
- Each mutation must be a single, coherent change to `train.py`
- Do not change the dataset or the train/val split

## Baseline

Starting from the reference `train.py` checked into this commit.  
Validation target: beat the baseline `val_bpb` by at least 0.005 within 8 hours.
