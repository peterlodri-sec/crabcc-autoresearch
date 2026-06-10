## what

<!-- one sentence: what does this change do -->

## why

<!-- why is this change needed -->

## checklist

- [ ] `cd receiver && task test` passes
- [ ] `cd worker && task test` passes
- [ ] ruff clean (`uv run ruff check . && uv run ruff format --check .` in both)
- [ ] `deploy.md` updated if startup sequence changed
- [ ] no secrets or internal paths in the diff
