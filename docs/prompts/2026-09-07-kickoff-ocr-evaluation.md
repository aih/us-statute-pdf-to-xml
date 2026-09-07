# Kickoff prompt: OCR pipeline evaluation (WP8 to WP11)

Paste the block below into a new Claude Code session opened in this repository, on the
`downloader-rewrite` branch after the 2026-09-07 plan PR is merged into it.

```
Implement docs/plans/2026-09-07-ocr-pipeline-evaluation-plan.md, work packages WP8 through WP11.

Read the plan in full first, then docs/architecture.md and the WP6 report in data/reports/. The
plan's section 1 lists four defects (F1 to F4) with the granules that demonstrate them; reproduce
each on its granule before fixing it, and keep the reproduction as a pytest case.

Sequence and delegation:
1. WP8 yourself, on a branch wp8-benchmark-repair off downloader-rewrite. It touches
   pipeline/uslm.py, pipeline/profiles.py, benchmark/metrics.py, and benchmark/sample.py, which
   every later package depends on. Rerun the baseline (python -m benchmark.evaluate --spec
   benchmark/sample.yaml --no-judge) and commit the report. Do not start WP9 until the WP8
   acceptance line in the plan holds.
2. WP9 and WP10 in parallel, each in its own git worktree off the WP8 branch, using subagents:
   - one agent per profile family for WP9: (a) textlayer + tesseract + rapidocr + easyocr,
     (b) the Docling VLM profiles and the HF Jobs runner, (c) the Claude transcription profile
     and the hybrid builder. Each agent owns its files under pipeline/ and adds its rows to
     benchmark/evaluate.py through the profile registry, never by editing another agent's
     module.
   - one agent for WP10 (benchmark/gold.py and benchmark/gold/).
   Merge the worktrees in that order and run the full comparison once.
3. WP11 yourself: write the decision document with the matrix and the projection.

Constraints:
- A fetch_historical uploader may still be running in statute-pdf-to-xml-app-1. Do not stop it
  and do not touch data/historical/. Check `python -m downloader.fetch_historical reconcile`
  before reading any volume from the Hub.
- Docling and Tesseract run in the container (docker compose exec app ...). The container has 10
  CPUs, 8 GB, and no GPU; keep --workers at 2 for OCR profiles. VLM profiles run on HF Jobs
  (hf jobs run; load the hf-cli skill first) or on the Mac with the MLX specs; never in the
  container.
- Claude calls: load the claude-api skill before writing pipeline/claude_ocr.py or changing
  benchmark/judge.py. Model claude-opus-5 by default, adaptive thinking, streaming, structured
  output, fallbacks "default"; the Batch API when --batch is passed. Log usage and cost per call.
  Set ANTHROPIC_WORKSPACE_ID in .env before the first call (the key is not workspace-scoped).
- Never let the builder drop text. Add a test that asserts generated body characters are at
  least 80% of the Docling text characters for every fixture in tests/.
- Secrets stay in .env. Nothing under data/ is committed except data/reports/.
- Report at the end of each package: what passed, what failed with the output, what was skipped.

Deliverables: the code and tests, the rerun baseline report, the profile comparison report, the
gold set, and docs/plans/2026-09-XX-ocr-decision.md.
```
