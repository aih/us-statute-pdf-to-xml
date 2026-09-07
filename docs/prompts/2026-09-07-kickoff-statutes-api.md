# Kickoff prompt: statutes.linkedlegislation.org API (stage 1 and 2)

Paste the block below into a new Claude Code session opened in an empty directory next to
`uscode-redesign` and `statute-pdf-to-xml`.

```
Build stages 1 and 2 of ../statute-pdf-to-xml/docs/plans/2026-09-07-statutes-api-design.md in a
new repository named statutes-linkedlegislation.

Before writing code, read the design in full, then in ../uscode-redesign read CLAUDE.md,
api/routes.py, params.py, storage/repository.py, storage/classification.py, and ADR-0009,
0010, 0018, 0029, 0067, 0074. Copy that repository's conventions: one Repository protocol, no
SQL outside storage/, served_note / not_found / cache_control in params.py, pytest with
fixtures of real source XML, a Makefile, docker compose with Postgres and Caddy.

Inputs:
- STATUTE volume USLM from the Hub dataset dreamproit/us-statutes-at-large (xmls/STATUTE-{n}.xml).
  Start with volumes 64, 72, 124, and 137; the loader must handle all 137.
- COMPS from the GovInfo API (collections/COMPS, packages/{id}/summary, packages/{id}/uslm).
  Start with COMPS-1630, COMPS-973, COMPS-3055, and one Social Security Act title file.
- The GovInfo key comes from .env (GOVINFO_API_KEY); never write it into source.

Sequence and delegation:
1. Yourself: schema (db/migrations), the Repository protocol, and the STATUTE loader with the
   identifier rules from ../statute-pdf-to-xml/docs/plans/2026-09-07-ocr-pipeline-evaluation-plan.md
   section 7. Load volume 64 and 124 and record the unit counts in docs/verification/.
2. Two subagents in worktrees: (a) the /api/v1 routes for /us/pl, /us/pvtl, /us/act, /us/stat,
   labels, status, with the response shape of design section 4 and the notes of section 4
   verbatim; (b) the COMPS poller, comp_versions, and the /us/sComp route with the compiled
   view. Each writes its own tests; neither edits storage/ without a message to you.
3. Yourself: alternatives between the two views, ETag and Cache-Control per design section 5,
   the /app redirect by Accept, and a docs/adr/ entry for every decision that departs from the
   design.

Report faithfully at the end of each stage: what passed, what failed with the output, what was
skipped. Deliverables: the repository with tests passing under make test, a README that states
what is served and what is not yet, and docs/verification/ counts for the loaded volumes.
```
