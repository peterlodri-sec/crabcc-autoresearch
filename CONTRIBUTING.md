# contributing

Two components, one rule: **tests first, always.**

---

## prerequisites

| tool | version | install |
|------|---------|---------|
| `uv` | latest | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| `task` | ≥3.0 | `brew install go-task` |
| `python` | ≥3.11 | managed by uv |
| `sqlite3` | any | system |

---

## local setup

```bash
git clone https://github.com/peterlodri-sec/crabcc-autoresearch
cd crabcc-autoresearch

cd receiver && uv sync --dev
cd ../worker && uv sync --dev
```

No docker. No `.env` files. No external services needed to run the test suite.

---

## project structure

Two independent Python projects — each has its own `pyproject.toml`, `.venv`, and test suite. They share no code at import time; the contract between them is the HTTP API.

```
receiver/   fastapi receiver + sqlite store
worker/     telemetry client + gpu tooling
nix/        nixos module snippet (not a python project)
```

---

## workflow

**tdd — no exceptions.**

```
write failing test → run it (confirm fail) → implement → run again (confirm pass) → commit
```

Every non-trivial behaviour lives in a test before the implementation. The plan in `docs/superpowers/plans/` shows the expected test output for each task — match it.

**small commits.** one logical change per commit. the diff should be readable in one sitting.

---

## running tests

```bash
# receiver (12 tests)
cd receiver && task test

# worker (9 tests)
cd worker && task test
```

Both suites use an in-memory / temp-file SQLite instance — no side effects, no cleanup.

---

## linting

```bash
# check
cd receiver && uv run ruff check . && uv run ruff format --check .
cd worker  && uv run ruff check . && uv run ruff format --check .

# fix
cd receiver && uv run ruff check --fix . && uv run ruff format .
cd worker  && uv run ruff check --fix . && uv run ruff format .
```

CI blocks on any ruff violation. Run locally before pushing.

---

## commit format

```
type(scope): short imperative description
```

| type | when |
|------|------|
| `feat` | new behaviour |
| `fix` | bug fix |
| `test` | test-only change |
| `chore` | deps, config, ci |
| `docs` | markdown only |

**scope** is one of: `receiver`, `worker`, `nix`, `ci`, or omit for cross-cutting changes.

examples:

```
feat(receiver): add /health endpoint
fix(worker): handle nvidia-smi absent on cpu-only instance
chore(ci): pin ruff to 0.4.x
```

---

## adding an endpoint (receiver)

1. write a failing test in `receiver/tests/test_api.py`
2. add the route + model to `receiver/main.py`
3. if the schema changes, update `receiver/schema.sql` (use `IF NOT EXISTS` guards — schema is applied idempotently at startup)
4. run `task test` — all 12+ tests must pass
5. run ruff
6. commit

---

## adding a telemetry function (worker)

1. write a failing test in `worker/tests/test_telemetry.py` using `unittest.mock.patch`
2. add the function to `worker/telemetry.py` — all network calls go through `_post()`, which swallows every exception silently
3. run `task test` — all 9+ tests must pass
4. run ruff
5. commit

---

## what we don't do

— no retries in telemetry — fire-and-forget is intentional; a missed row is acceptable  
— no auth on the telemetry endpoint — tailscale mesh trust is the perimeter  
— no database connection pooling — sqlite, single writer, not needed  
— no backwards-compatibility shims — change the code, don't layer over it  
— no comments explaining what the code does — name things clearly instead  

---

## pr checklist

- [ ] tests pass locally (`task test` in both components)
- [ ] ruff clean (`ruff check . && ruff format --check .`)
- [ ] commit messages follow the format above
- [ ] no new files that aren't tested or aren't pure config/docs
- [ ] `deploy.md` updated if the startup sequence changes
