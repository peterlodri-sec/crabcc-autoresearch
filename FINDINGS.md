# findings

Running record of what the autoresearch loop discovers across nightly runs.
Updated after each batch of runs — not every run, just the ones that move something.

---

## format

Each entry: run reference → what changed → whether it held up on subsequent runs.

```
## YYYY-MM  (month)

### run <RUN_ID>  best val_bpb: X.XX
- [mutation that worked] — e.g. "dropout=0.0 consistently beats dropout=0.1 on SEP terms"
- [architecture note]   — e.g. "wider MLP (4× → 6× hidden) improves SN/SEP boundary"
- [negative result]     — e.g. "rotary embeddings tried in 3 runs, no consistent gain"
```

---

## research goal

The loop trains a small transformer to classify λ-term normalization status
(**SN** / **SEP** / **NWN** / **UND**) from the
[lambda-normalization-census](https://github.com/peterlodri-sec/lambda-normalization-census)
dataset. A learned classifier that generalises beyond the n>16 decidability horizon
would be a genuine research contribution.

Baseline `val_bpb`: _TBD — first run pending_

---

## 2026-06

_first runs scheduled pending $500/month sponsor threshold — see roadmap in README_
