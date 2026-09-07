# Kickoff prompt: implement the 2026-09-05 plan

Paste the block below into a new Claude Code session opened in this repository.

```
Implement docs/plans/2026-09-05-downloader-and-pipeline-plan.md, work packages WP1 through WP3 first, then WP4 through WP7.

Constraints:
- Read the plan in full before editing anything. Follow its module layout (section 5) and acceptance criteria (section 6).
- A downloader process (python -m downloader.fetch_historical) may still be running in the statute-pdf-to-xml-app-1 container. Do not kill it, and do not delete or move anything under data/ unless a work package says so.
- Work on a new branch off main named downloader-rewrite. One commit per work package with a message that names the package.
- Python only. Concurrency per section 4: threads for network I/O, processes for Docling. Do not introduce Go or a second service.
- Secrets come from .env via env_file. Never write an API key or token into source, compose, or docs. The GovInfo key currently in the tree is compromised; remove every copy.
- Use the anthropic SDK with model claude-opus-5, adaptive thinking, streaming, structured output, and fallbacks "default" in benchmark/judge.py. Load the claude-api skill before writing that file.
- Use huggingface_hub 1.x APIs (HfApi.create_commit, CommitOperationAdd, get_paths_info, list_repo_tree). Verify each API against the installed version in the container before using it.
- Write pytest tests for every acceptance criterion that can run offline (range planning, .part verification, reconcile decisions, USLM splitter, metrics). Run them in the container: docker compose exec app pytest.
- For WP2 and WP3, test end to end on volumes 118 and 119 only (born-digital, under 15 MB each). Do not start the full backfill.
- Before writing pipeline/split_uslm.py, inspect data/historical/xmls/STATUTE-64.xml (or any volume XML present) and one PLAW USLM in data/xmls/ to confirm the element names and page markers, and record what you found in docs/architecture.md.
- Report faithfully at the end of each work package: what passed, what failed with output, and what was skipped.

Deliverables: the code, migrations, tests, updated README, docs/architecture.md, and a final summary listing each work package with its acceptance result.
```
