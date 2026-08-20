# Contributing

Thanks for looking. This repository is a contest submission with an unusual constraint, so it is
worth being explicit about what can and cannot change.

## The submission is frozen

Everything under `submission/` is the artifact that was evaluated on 2026-08-13, identified by
hash in [RESULTS.md](RESULTS.md) and asserted by `tests/test_submission_identity.py`. It is a
record, not a codebase. **Pull requests that modify it will be declined**, including ones that fix
real bugs — the value of those files is that they are exactly what scored 318.254.

If you want to build on the optimizer, fork it and say so in your README. That is what the
Apache-2.0 license is for, and it is the outcome the open-sourcing requirement was written to
produce.

## What changes are welcome

- **Corrections to the documentation.** If something in `docs/` is wrong, unclear, or contradicted
  by the code, that is worth a pull request or an issue. Claims in this repository are supposed to
  be checkable.
- **`tools/`** — `pack.py` and `harness_timeline.py` are meant to be useful to future contest
  entrants. Portability fixes, better log-format coverage, and tests are all welcome.
- **`benchmarks/heldout/`** — more designs in classes that are under-represented (anything that is
  not a RISC-V core is under-represented).
- **`tests/`** — the tests must run without Vivado, RapidWright, or an FPGA. That constraint is
  not negotiable; it is what makes CI meaningful for people who do not have a licensed toolchain.

## Working agreements

**Measure before you claim.** This project has a documented history of expensive mistakes made by
reading numbers that looked authoritative and were not — see
[docs/measurement-notes.md](docs/measurement-notes.md). If a change is justified by a measurement,
say how it was measured, what the control was, and what confounder you ruled out.

**One concern per pull request.** Small, reviewable changes with a clear reason in the description.

**Commit messages say why, not what.** The diff already says what changed.

## Development setup

```bash
python -m venv .venv && . .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
pre-commit install

pytest -q
ruff check .
ruff format --check .
```

CI runs the same three commands on Linux, macOS and Windows across supported Python versions. It
needs no FPGA toolchain.

## Reporting a security issue

Do not open a public issue. See [SECURITY.md](SECURITY.md).

## License

By contributing you agree that your contributions are licensed under the Apache License 2.0, the
same terms that cover this repository. See [LICENSE](LICENSE) and [NOTICE](NOTICE).
