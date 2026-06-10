# Research Constraints

## Goal

Train a small transformer to classify λ-term normalization status using the
[`lambda-normalization-census`](https://github.com/peterlodri-sec/lambda-normalization-census)
dataset as training data. Every mutation the loop proposes should aim to reduce
`val_bpb` on this specific task — not a generic benchmark.

## Task

**Input:** a λ-term encoded in natural-size de Bruijn notation (as in the census)  
**Output:** predicted normalization class — `SN` / `SEP` / `NWN` / `UND`  
**Framing:** character/token-level language model; terms + labels encoded as sequences,
model learns to predict the class token given the term. Lower `val_bpb` = better classifier.  
**Dataset:** `data/census_dataset.csv` from the census repo (exact rows n≤16, Monte-Carlo to n=55)

## Why this task

A learned normalization classifier that generalises beyond the decidability horizon
(n>16 where exact enumeration is intractable) would be a genuine research contribution —
useful for type-checkers, proof assistants, and anyone reasoning about λ-calculus reduction.
The autoresearch loop is the engine that finds the architecture and training recipe that
minimises classification error at scale.

## Rules

- Do not modify `prepare.py` or the evaluation harness
- Do not change the model architecture beyond what `train.py` exposes
- Muon optimizer is allowed; do not remove it
- Each mutation must be a single, coherent change to `train.py`
- Mutations that change the task framing or dataset are not allowed

## Baseline

Starting from the reference `train.py` checked into this commit.  
Validation target: beat the baseline `val_bpb` by at least 0.005 within 8 hours.
