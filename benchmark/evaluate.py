"""Run the benchmark over a sample spec: fetch -> split ground truth -> convert -> metrics -> judge -> report.

    python -m benchmark.evaluate --spec benchmark/sample.yaml --no-judge
    python -m benchmark.evaluate --spec benchmark/sample.yaml --profiles scanned,scanned:psm6 --tier B
    python -m benchmark.evaluate --spec benchmark/sample.yaml --profiles scanned,textlayer --tier A,B --no-judge
    python -m benchmark.evaluate --spec benchmark/sample.yaml --judge --judge-limit 2

Profiles come from the registry in pipeline.profiles (`family[:variant]`); `auto` (the default) is the
per-volume profile (`scanned` up to volume 116, `digital` after). Tier B scores the granule PDF against
the GovInfo USLM slice. Tier A rasterizes the born-digital granules (benchmark.rasterize) and runs the
profile on the page images only; its rows carry `tier` A and the raster variant (`--variant`).

Each stage skips work that is already done: granule PDFs whose size matches GovInfo, volume USLM
already split, conversions whose input sha256 is unchanged, and benchmarks rows for the same run id,
profile, and generated XML sha256. Granules the splitter cannot pair (F4) are reported as skipped.
Results go to the `benchmarks` table and to data/reports/<date>-<run id>.md with a profile-by-era matrix.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime
from pathlib import Path
from statistics import mean, median
from typing import Optional

from downloader import db, state
from downloader.config import DATA_DIR, LOG_DIR, exit_on_missing_env, govinfo_api_key, setup_logging
from downloader.fetch_granules import load_spec, process_granule
from downloader.govinfo import GovInfoClient
from pipeline import convert as conv
from pipeline import profiles, split_uslm
from pipeline.profiles import profile_for_volume
from benchmark import metrics

logger = logging.getLogger("evaluate")

REPORTS_DIR = DATA_DIR / "reports"
JUDGE_MODULE = "claude-judge"
TIERS = ("A", "B")


# ---------------------------------------------------------------------------- inputs


def ensure_granules(entries: list[dict], workers: int = 4) -> dict[str, dict]:
    """Download missing granule PDFs/MODS; return granules rows by id."""
    rows: dict[str, dict] = {}
    with db.connection() as conn, conn.cursor() as cur:
        for e in entries:
            cur.execute("SELECT * FROM granules WHERE granule_id = %s", (e["granule_id"],))
            row = cur.fetchone()
            if row and row["pdf_local_path"] and Path(row["pdf_local_path"]).exists():
                rows[e["granule_id"]] = dict(row)
    missing = [e for e in entries if e["granule_id"] not in rows]
    if missing:
        logger.info("fetching %d granule(s)", len(missing))
        with GovInfoClient(govinfo_api_key()) as client, ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(process_granule, client, e, DATA_DIR / "granules", 2): e["granule_id"] for e in missing}
            for fut in as_completed(futures):
                gid = futures[fut]
                try:
                    rows[gid] = fut.result()
                except Exception as exc:
                    logger.error("%s: fetch failed: %s", gid, exc)
    return rows


VOLUME_XML_DIR = DATA_DIR / "volumes" / "xmls"


def volume_xml_path(volume: int) -> Path:
    return VOLUME_XML_DIR / f"STATUTE-{volume}.xml"


def ensure_volume_xml(volume: int, client: GovInfoClient) -> Optional[Path]:
    """The volume USLM for ground truth: a copy still under data/historical (the uploader's directory, never
    written here), else the Hub dataset (HF_REPO_ID), else GovInfo."""
    path = volume_xml_path(volume)
    if path.exists():
        return path
    historical = DATA_DIR / "historical" / "xmls" / f"STATUTE-{volume}.xml"
    if historical.exists():
        return historical
    repo_id = os.getenv("HF_REPO_ID", "").strip()
    if repo_id:
        try:
            from huggingface_hub import hf_hub_download

            logger.info("STATUTE-%d: downloading volume USLM from %s", volume, repo_id)
            got = hf_hub_download(repo_id, f"xmls/STATUTE-{volume}.xml", repo_type="dataset",
                                  local_dir=str(VOLUME_XML_DIR.parent), token=os.getenv("HF_TOKEN") or None)
            got = Path(got)
            if got != path:
                path.parent.mkdir(parents=True, exist_ok=True)
                got.replace(path)
            return path
        except Exception as exc:
            logger.warning("STATUTE-%d: Hub download failed (%s); falling back to GovInfo", volume, exc)
    summary = client.package_summary(f"STATUTE-{volume}")
    url = (summary or {}).get("download", {}).get("uslmLink")
    if not url:
        return None
    logger.info("STATUTE-%d: downloading volume USLM from GovInfo for ground truth", volume)
    client.download_ranged(url, path, parts=4)
    return path


def ensure_split(volume: int, client: GovInfoClient) -> Optional[Path]:
    """Split the volume USLM into per-granule files once; return the output directory."""
    out = DATA_DIR / "granules" / f"STATUTE-{volume}" / "uslm"
    if (out / "index.json").exists():
        return out
    xml = ensure_volume_xml(volume, client)
    if xml is None:
        return None
    granules = split_uslm.load_granules(str(DATA_DIR / "granules" / f"STATUTE-{volume}" / "granules.json"),
                                        f"STATUTE-{volume}", fetch=True)
    report = split_uslm.split_volume(xml, out, granules, volume)
    logger.info("STATUTE-%d: %s", volume, split_uslm.summarize(report).replace("\n", " | "))
    return out


def sha256_text(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ---------------------------------------------------------------------------- benchmarks rows


def existing_benchmark(conn, granule_id: str, run_id: str, generated_sha: str, profile: str, tier: str) -> Optional[dict]:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT * FROM benchmarks WHERE granule_id = %s AND run_id = %s AND COALESCE(profile, '') = %s "
            "AND COALESCE(tier, 'B') = %s AND evaluation_details LIKE %s ORDER BY benchmark_date DESC LIMIT 1",
            (granule_id, run_id, profile, tier, f'%"generated_sha256": "{generated_sha}"%'),
        )
        row = cur.fetchone()
    return dict(row) if row else None


def write_benchmark(conn, row: dict) -> int:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO benchmarks (granule_id, package_id, era, ground_truth_xml_path, generated_xml_path, score,
                                    vlm_judge_model, evaluation_details, cer, wer, metrics, judge, judge_cost_usd, run_id,
                                    profile, tier)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id
            """,
            (
                row["granule_id"], row["package_id"], row["era"], row["ground_truth_xml_path"], row["generated_xml_path"],
                row.get("score"), row.get("vlm_judge_model"), json.dumps(row["details"]), row["cer"], row["wer"],
                db.jsonb(row["metrics"]), db.jsonb(row.get("judge")), row.get("judge_cost_usd"), row["run_id"],
                row.get("profile"), row.get("tier", "B"),
            ),
        )
        new_id = cur.fetchone()[0]
    conn.commit()
    return new_id


def update_judge(conn, benchmark_id: int, judge: dict, model: str) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE benchmarks SET judge = %s, vlm_judge_model = %s, score = %s, judge_cost_usd = %s WHERE id = %s",
            (db.jsonb(judge), model, judge.get("overall"), judge.get("cost_usd"), benchmark_id),
        )
    conn.commit()


# ---------------------------------------------------------------------------- report


def _fmt(v: Optional[float], digits: int = 3) -> str:
    return "-" if v is None else f"{v:.{digits}f}"


def _group_stats(rs: list[dict]) -> dict:
    cers = [r["cer"] for r in rs]
    wers = [r["wer"] for r in rs]
    ms = [r["metrics"] for r in rs]
    sec = [m.get("section_match", {}).get("recall") for m in ms]
    sec = [x for x in sec if x is not None]
    f1s = [m["identifier_overlap"]["f1"] for m in ms]
    clipped = sum(1 for m in ms if m.get("clip_found") == "both")
    kept = [r["details"].get("kept_ratio") for r in rs if r["details"].get("kept_ratio") is not None]
    secs = [r["details"].get("seconds") for r in rs if r["details"].get("seconds")]
    pages = [r["details"].get("pages") for r in rs if r["details"].get("pages")]
    judged = [r for r in rs if r.get("judge")]
    return {
        "n": len(rs), "mean_cer": mean(cers), "median_cer": median(cers), "mean_wer": mean(wers),
        "section_recall": mean(sec) if sec else None, "id_f1": mean(f1s), "clip_both": clipped,
        "kept_ratio": min(kept) if kept else None, "xsd": sum(1 for r in rs if r["details"].get("xsd_valid")),
        "sec_per_page": (sum(secs) / sum(pages)) if secs and pages and sum(pages) else None,
        "judged": len(judged), "judge_mean": mean(r["judge"]["overall"] for r in judged) if judged else None,
    }


def matrix_table(rows: list[dict]) -> str:
    """Profile x era (and tier) matrix."""
    groups: dict[tuple[str, str, str], list[dict]] = defaultdict(list)
    for r in rows:
        groups[(r.get("profile") or "?", r.get("tier") or "B", r["era"] or "?")].append(r)
    lines = ["| Profile | Tier | Era | Granules | Mean CER | Median CER | Mean WER | Section recall | Id F1 | Clipped both | Min kept | XSD valid | s/page | Judge (n) | Judge mean |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for (profile, tier, era) in sorted(groups):
        rs = groups[(profile, tier, era)]
        g = _group_stats(rs)
        lines.append(
            f"| {profile} | {tier} | {era} | {g['n']} | {_fmt(g['mean_cer'])} | {_fmt(g['median_cer'])} | {_fmt(g['mean_wer'])} | "
            f"{_fmt(g['section_recall'], 2)} | {_fmt(g['id_f1'], 2)} | {g['clip_both']}/{g['n']} | {_fmt(g['kept_ratio'], 2)} | "
            f"{g['xsd']}/{g['n']} | {_fmt(g['sec_per_page'], 1)} | {g['judged']} | {_fmt(g['judge_mean'], 1)} |"
        )
    return "\n".join(lines)


def era_table(rows: list[dict]) -> str:
    """Kept for callers of the WP6 report shape: one row per era over every profile in `rows`."""
    by_era: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_era[r["era"] or "?"].append(r)
    lines = ["| Era | Granules | Mean CER | Mean WER | Median CER | Identifier F1 | XSD valid | Judge (n) | Judge mean |",
             "|---|---|---|---|---|---|---|---|---|"]
    for era in sorted(by_era):
        g = _group_stats(by_era[era])
        lines.append(f"| {era} | {g['n']} | {_fmt(g['mean_cer'])} | {_fmt(g['mean_wer'])} | {_fmt(g['median_cer'])} | "
                     f"{_fmt(g['id_f1'], 2)} | {g['xsd']}/{g['n']} | {g['judged']} | {_fmt(g['judge_mean'], 1)} |")
    return "\n".join(lines)


def granule_table(rows: list[dict]) -> str:
    lines = ["| Granule | Class | Profile | Tier | Pages | CER | CER unclipped | Clip | WER | Sections ref/gen (matched) | Id F1 | Kept | Warn | XSD | Judge |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in sorted(rows, key=lambda r: (r.get("profile") or "", r.get("tier") or "", r["era"] or "", r["granule_id"])):
        m = r["metrics"]
        d = r["details"]
        judge = f"{r['judge']['overall']:.0f}" if r.get("judge") else "-"
        sm = m.get("section_match", {})
        lines.append(
            f"| {r['granule_id']} | {d.get('granule_class') or ''} | {r.get('profile') or ''} | {r.get('tier') or 'B'} | {d.get('pages') or ''} | "
            f"{r['cer']:.3f} | {_fmt(m.get('cer_unclipped'))} | {m.get('clip_found', '-')} | {r['wer']:.3f} | "
            f"{m['structure_reference']['section']}/{m['structure_generated']['section']} ({sm.get('matched', '-')}) | "
            f"{m['identifier_overlap']['f1']:.2f} | {_fmt(d.get('kept_ratio'), 2)} | {d.get('warnings', '-')} | "
            f"{'yes' if d.get('xsd_valid') else 'no'} | {judge} |"
        )
    return "\n".join(lines)


def write_report(rows: list[dict], run_id: str, spec_path: str, skipped: Optional[dict] = None,
                 failures: Optional[dict] = None) -> Path:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORTS_DIR / f"{date.today().isoformat()}-{run_id}.md"
    judged = [r for r in rows if r.get("judge")]
    cost = sum(r["judge"].get("cost_usd", 0) for r in judged)
    profiles_run = sorted({r.get("profile") or "?" for r in rows})
    body = [
        f"# Benchmark {run_id}", "",
        f"Date: {datetime.now().isoformat(timespec='seconds')}. Spec: `{spec_path}`. Rows: {len(rows)} "
        f"({len({r['granule_id'] for r in rows})} granules, profiles {', '.join(profiles_run)}). Judged: {len(judged)} (${cost:.2f}).", "",
        "CER and WER are scored on the generated text clipped to the reference span (F3); `CER unclipped` is the "
        "score over the whole generated body. `Kept` is characters kept in the generated document over characters "
        "Docling produced (F2). Section recall matches sections by number and the first 40 characters.", "",
        "## Profile by era", "", matrix_table(rows), "",
        "## By granule", "", granule_table(rows), "",
    ]
    if skipped:
        body += ["## Skipped", ""] + [f"- {gid}: {why}" for gid, why in sorted(skipped.items())] + [""]
    if failures:
        body += ["## Failed", ""] + [f"- {gid}: {why}" for gid, why in sorted(failures.items())] + [""]
    if judged:
        body += ["## Judge summaries", ""]
        for r in judged:
            body.append(f"- **{r['granule_id']}** [{r.get('profile')}] ({r['judge']['overall']:.0f}): {r['judge']['summary']}")
            for issue in r["judge"].get("issues", [])[:5]:
                body.append(f"  - {issue['severity']} {issue['type']} at {issue['location']}: {issue['description']}")
        body.append("")
    path.write_text("\n".join(body), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------- run


def parse_list(value: Optional[str], default: list[str]) -> list[str]:
    if not value:
        return default
    return [v.strip() for v in value.split(",") if v.strip()]


def unpaired_reason(gt_dir: Optional[Path], gid: str) -> Optional[str]:
    if gt_dir is None:
        return None
    path = gt_dir / "unpaired.json"
    if not path.exists():
        return None
    for entry in json.loads(path.read_text(encoding="utf-8")):
        if entry.get("granule_id") == gid:
            return f"no one-to-one reference ({entry.get('granule_class')}: {entry.get('reason')}; F4)"
    return None


def tier_a_units(units: list[conv.Unit], variant: str, entries_by_id: dict[str, dict]) -> list[conv.Unit]:
    """Tier A: born-digital granules through their rasterized pages (clean or degraded wrapper PDF)."""
    from benchmark import rasterize
    from dataclasses import replace

    out = []
    for u in units:
        entry = entries_by_id.get(u.unit_id, {})
        if entry.get("era") != "digital-2003+":
            continue
        r = rasterize.rasterize(u.pdf, u.unit_id, variants=(variant,))
        out.append(replace(u, pdf=str(r.pdfs[variant]), tag=f"A-{variant}"))
    return out


def run(args) -> int:
    setup_logging("evaluate", args.log_dir)
    db.init_db()
    run_id = args.run_id or datetime.now().strftime("%Y%m%d-%H%M")
    entries = load_spec(args.spec)
    if args.limit:
        entries = entries[: args.limit]
    profile_names = parse_list(args.profiles, ["auto"])
    tiers = [t.upper() for t in parse_list(args.tier, ["B"])]
    for t in tiers:
        if t not in TIERS:
            raise SystemExit(f"unknown tier {t!r}; expected A or B")
    for name in profile_names:
        if name != "auto":
            profiles.get_family(name)
    logger.info("run %s: %d granule(s) from %s, profiles %s, tiers %s", run_id, len(entries), args.spec,
                ", ".join(profile_names), ", ".join(tiers))

    rows = ensure_granules(entries)
    volumes = sorted({int(r["package_id"].split("-")[1]) for r in rows.values()})
    splits: dict[int, Optional[Path]] = {}
    with GovInfoClient(govinfo_api_key()) as client:
        for v in volumes:
            try:
                splits[v] = ensure_split(v, client)
            except Exception as exc:
                logger.error("STATUTE-%d: split failed: %s", v, exc)
                splits[v] = None

    entries_by_id = {e["granule_id"]: e for e in entries}
    keep = set(entries_by_id)
    bench_rows: list[dict] = []
    failures: dict[str, str] = {}
    skipped: dict[str, str] = {}

    for profile_name in profile_names:
        for tier in tiers:
            profile_arg = None if profile_name == "auto" else profile_name
            units = [u for u in conv.units_from_spec(args.spec, None, profile_arg) if u.unit_id in keep]
            if tier == "A":
                if profile_name == "auto":
                    logger.warning("tier A with profile auto runs the digital profile on images; pass --profiles")
                units = tier_a_units(units, args.variant, entries_by_id)
                if not units:
                    logger.warning("tier A: no born-digital granules in the spec")
                    continue
            results = {r.unit_id: r for r in conv.run_units(units, conv.workers_for_container(args.workers), args.force,
                                                              dpi=args.dpi, rebuild=args.rebuild)}
            for unit in units:
                gid = unit.unit_id
                row = rows.get(gid)
                key = f"{gid} [{unit.profile}/{tier}]"
                result = results.get(gid)
                if row is None:
                    failures[key] = "not downloaded"
                    continue
                if result is None or result.status == "failed" or not result.xml_path:
                    failures[key] = (result.error if result else "not converted")
                    continue
                volume = int(row["package_id"].split("-")[1])
                gt_dir = splits.get(volume)
                gt = (gt_dir / f"{gid}.xml") if gt_dir else None
                if gt is None or not gt.exists():
                    why = unpaired_reason(gt_dir, gid)
                    if why:
                        skipped[key] = why
                    else:
                        failures[key] = f"no ground truth slice for {gid}"
                    continue
                gen_path = Path(result.xml_path)
                gen_sha = sha256_text(gen_path)
                with db.connection() as conn:
                    existing = existing_benchmark(conn, gid, run_id, gen_sha, unit.profile, tier)
                if existing and not args.force:
                    bench_rows.append({"id": existing["id"], "granule_id": gid, "package_id": row["package_id"], "era": existing["era"],
                                       "cer": existing["cer"], "wer": existing["wer"], "metrics": existing["metrics"], "judge": existing["judge"],
                                       "details": json.loads(existing["evaluation_details"]), "run_id": run_id,
                                       "generated_xml_path": existing["generated_xml_path"], "profile": unit.profile, "tier": tier,
                                       "ground_truth_xml_path": existing["ground_truth_xml_path"]})
                    continue
                try:
                    comparison = metrics.compare(gt, gen_path)
                except Exception as exc:
                    failures[key] = f"metrics: {exc}"
                    continue
                st = result.stats or {}
                with db.connection() as conn:
                    prev = conv.previous_success(conn, unit) if result.status == "skipped" else None
                if prev:
                    st = {"docling_chars": prev.get("docling_chars"), "kept_chars": prev.get("kept_chars"),
                          "body_chars": prev.get("body_chars"), "warnings": prev.get("warnings"),
                          "kept_ratio": (prev["kept_chars"] / prev["docling_chars"]) if prev.get("docling_chars") and prev.get("kept_chars") is not None else None}
                    result.pages = prev.get("pages") or result.pages
                    result.seconds = prev.get("seconds") or result.seconds
                details = {
                    "generated_sha256": gen_sha, "xsd_valid": result.xsd_valid, "pages": result.pages, "seconds": result.seconds,
                    "granule_class": row.get("granule_class") or entries_by_id[gid].get("granule_class"), "profile": unit.profile,
                    "tier": tier, "variant": args.variant if tier == "A" else None, "input": unit.pdf,
                    "docling_chars": st.get("docling_chars"), "kept_chars": st.get("kept_chars"), "body_chars": st.get("body_chars"),
                    "kept_ratio": st.get("kept_ratio"), "warnings": st.get("warnings"), "start_rule": st.get("start_rule"),
                }
                bench = {
                    "granule_id": gid, "package_id": row["package_id"], "era": row.get("era") or entries_by_id[gid].get("era"),
                    "ground_truth_xml_path": state.relative_to_repo(gt), "generated_xml_path": state.relative_to_repo(gen_path),
                    "cer": comparison.cer, "wer": comparison.wer, "metrics": comparison.as_dict(), "details": details, "run_id": run_id,
                    "profile": unit.profile, "tier": tier,
                }
                with db.connection() as conn:
                    bench["id"] = write_benchmark(conn, bench)
                logger.info("%s [%s/%s]: CER %.3f (unclipped %.3f, clip %s) WER %.3f, sections %d/%d matched %d, kept %s",
                            gid, unit.profile, tier, comparison.cer, comparison.cer_unclipped,
                            comparison.clip.found if comparison.clip else "off", comparison.wer,
                            comparison.structure_reference["section"], comparison.structure_generated["section"],
                            comparison.section_match.get("matched", 0), _fmt(st.get("kept_ratio"), 2))
                bench_rows.append(bench)

    if args.judge:
        from benchmark.judge import Judge

        judge = Judge()
        todo = [b for b in bench_rows if not b.get("judge")]
        if args.judge_limit:
            todo = todo[: args.judge_limit]
        logger.info("judging %d row(s) with %s", len(todo), judge.model)

        def run_judge(b: dict):
            row = rows[b["granule_id"]]
            identity = {"granule_id": b["granule_id"], "package_id": b["package_id"], "era": b["era"],
                        "granule_class": row.get("granule_class"), "congress": row.get("congress"),
                        "law_number": row.get("number"), "citation": row.get("citation"), "page_range": row.get("page_range"),
                        "profile": b.get("profile")}
            generated = Path(b["generated_xml_path"]).read_text(encoding="utf-8")
            return b, judge.judge(row["pdf_local_path"], generated, b["metrics"]["diffs"], identity)

        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = [pool.submit(run_judge, b) for b in todo]
            for fut in as_completed(futures):
                try:
                    b, jr = fut.result()
                except Exception as exc:
                    logger.error("judge failed: %s", exc)
                    continue
                b["judge"] = jr.as_dict()
                with db.connection() as conn:
                    update_judge(conn, b["id"], b["judge"], jr.model)

    if bench_rows:
        report = write_report(bench_rows, run_id, args.spec, skipped, failures)
        print(matrix_table(bench_rows))
        logger.info("report: %s", report)
    for gid, why in sorted(skipped.items()):
        logger.warning("SKIPPED %s: %s", gid, why)
    for gid, err in sorted(failures.items()):
        logger.error("FAILED %s: %s", gid, err)
    logger.info("done: %d row(s) benchmarked, %d skipped, %d failed", len(bench_rows), len(skipped), len(failures))
    return 1 if failures and not bench_rows else 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m benchmark.evaluate", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--spec", required=True)
    g = p.add_mutually_exclusive_group()
    g.add_argument("--judge", action="store_true", help="run the Claude judge on granules without a judge result")
    g.add_argument("--no-judge", action="store_true", help="metrics only (default)")
    p.add_argument("--judge-limit", type=int, default=None, help="judge at most N granules")
    p.add_argument("--limit", type=int, default=None, help="use only the first N granules of the spec")
    p.add_argument("--profiles", default=None, help="comma-separated profiles (family[:variant]); default auto")
    p.add_argument("--tier", default="B", help="A, B, or A,B (default B)")
    p.add_argument("--variant", default="clean", choices=["clean", "degraded"], help="tier A raster variant")
    p.add_argument("--dpi", type=int, default=profiles.DEFAULT_DPI)
    p.add_argument("--workers", type=int, default=None)
    p.add_argument("--force", action="store_true", help="reconvert and recompute metrics")
    p.add_argument("--rebuild", action="store_true", help="rebuild USLM from existing DoclingDocument JSON (no OCR) and recompute metrics")
    p.add_argument("--run-id", default=None)
    p.add_argument("--log-dir", default=str(LOG_DIR))
    return p


@exit_on_missing_env
def main(argv: Optional[list[str]] = None) -> int:
    return run(build_parser().parse_args(argv))


if __name__ == "__main__":
    sys.exit(main())
