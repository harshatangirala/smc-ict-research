# Deployment Notes (Task 15/16)

## What is deployment-ready right now

- `app.py` — Gradio dashboard entry point, verified to import and build
  (`python -c "import app"`) without error against real pipeline output.
- `requirements.txt` — pinned to what was actually installed and used to
  produce every result in this repository (verified via a real `pip
  install` + full pipeline run, not aspirational).
- `README.md` — carries Hugging Face Spaces YAML frontmatter
  (`sdk: gradio`, `app_file: app.py`, etc.) at the top, which HF Spaces
  reads automatically when this repo is pushed there.
- `environment.yml` — conda alternative to `requirements.txt`.
- Local end-to-end run completed: ingestion, detection, backtest, and
  analytics all ran against the real S&P 500 universe on this machine (see
  commit history for exact figures at each stage).

## What is genuinely blocked, and why

Two of Task 16's steps require credentials this environment does not have
and a non-interactive session cannot obtain:

1. **Push to a Hugging Face Space.** Creating/pushing to a Space requires an
   authenticated `huggingface-cli login` (an HF access token) or a
   `git remote` already pointing at a Space repo with credentials
   configured. Neither exists in this session, and the system I'm running
   in cannot run an interactive OAuth/login flow. I have not fabricated a
   Space URL — there isn't one yet.
2. **Push to a GitHub repository.** Requirement 21 says "push to the GitHub
   repository that I specify" — none has been specified, and per the
   project's own earlier instruction this was deliberately deferred
   ("hold off on GitHub for now"). Inventing a destination and pushing to
   it would be actively wrong, not just incomplete.

## To actually deploy, from a machine/session with the right access

```bash
# GitHub
git remote add origin <your-github-url>
git push -u origin master
git tag v1.0.0 -m "SMC/ICT statistical edge research v1.0.0"
git push origin v1.0.0

# Hugging Face Spaces (requires `pip install huggingface_hub` + `huggingface-cli login`)
huggingface-cli login
git remote add space https://huggingface.co/spaces/<your-username>/<space-name>
git push space master
```

Once pushed, HF Spaces will read the YAML frontmatter in `README.md`,
install `requirements.txt`, and run `app.py` automatically — no additional
configuration files are needed for a pure-Gradio Space.

## Pre-flight checklist for whoever runs the push

- [ ] Confirm `data/cache/*.parquet` and `results/*.parquet` are **not**
      committed (both are gitignored; verify with `git status` before
      pushing — the trades table alone is ~760MB and must never enter git
      history).
- [ ] Run `python main.py all` once on the target machine/Space build step
      if `results/` needs to be regenerated rather than shipped as static
      files (HF Spaces free tier has ephemeral storage and limited CPU —
      a full `python main.py all` run took roughly 15-20 minutes on this
      development machine for the full S&P 500 universe; consider whether
      the Space should ship precomputed `results/*.csv` instead of
      recomputing on every Space restart).
- [ ] Run `pytest tests/ -v` and confirm all tests pass on the target
      environment before pushing.
