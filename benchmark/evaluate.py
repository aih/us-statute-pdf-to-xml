"""Run the benchmark over a sample spec: fetch -> split ground truth -> convert -> metrics -> judge -> report.

    python -m benchmark.evaluate --spec benchmark/sample.yaml --no-judge
    python -m benchmark.evaluate --spec benchmark/sample.yaml --judge --judge-limit 2

Each stage skips work that is already done: granule PDFs whose size matches GovInfo, volume USLM
already split, conversions whose input sha256 is unchanged, and benchmarks rows for the same run id
and generated XML sha256. Results go to the `benchmarks` table and to data/reports/<date>.md.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from downloader import db, state
from downloader.config import DATA_DIR, LOG_DIR, exit_on_missing_env, govinfo_api_key, setup_logging
from downloader.fetch_granules import load_spec, process_granule
from downloader.govinfo import GovInfoClient
from pipeline import convert as conv
from pipeline import split_uslm
from benchmark import metrics

logger = logging.getLogger("evaluate")

REPORTS_DIR = DATA_DIR / "reports"
JUDGE_MODULE = "claude-judge"


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


def volume_xml_path(volume: int) -> Path:
    return DATA_DIR / "historical" / "xmls" / f"STATUTE-{volume}.xml"


def ensure_volume_xml(volume: int, client: GovInfoClient) -> Optional[Path]:
    path = volume_xml_path(volume)
    if path.exists():
        return path
    summary = client.package_summary(f"STATUTE-{volume}")
    url = (summary or {}).get("download", {}).get("uslmLink")
    if not url:
        return None
    logger.info("STATUTE-%d: downloading volume USLM for ground truth", volume)
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


def existing_benchmark(conn, granule_id: str, run_id: str, generated_sha: str) -> Optional[dict]:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT * FROM benchmarks WHERE granule_id = %s AND run_id = %s AND evaluation_details LIKE %s "
            "ORDER BY benchmark_date DESC LIMIT 1",
            (granule_id, run_id, f'%"generated_sha256": "{generated_sha}"%'),
        )
        row = cur.fetchone()
    return dict(row) if row else None


def write_benchmark(conn, row: dict) -> int:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO benchmarks (granule_id, package_id, era, ground_truth_xml_path, generated_xml_path, score,
                                    vlm_judge_model, evaluation_details, cer, wer, metrics, judge, judge_cost_usd, run_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id
            """,
            (
                row["granule_id"], row["package_id"], row["era"], row["ground_truth_xml_path"], row["generated_xml_path"],
                row.get("score"), row.get("vlm_judge_model"), json.dumps(row["details"]), row["cer"], row["wer"],
                db.jsonb(row["metrics"]), db.jsonb(row.get("judge")), row.get("judge_cost_usd"), row["run_id"],
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


def era_table(rows: list[dict]) -> str:
    by_era: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_era[r["era"] or "?"].append(r)
    lines = ["| Era | Granules | Mean CER | Mean WER | Median CER | Identifier F1 | XSD valid | Judge (n) | Judge mean |",
             "|---|---|---|---|---|---|---|---|---|"]
    for era in sorted(by_era):
        rs = by_era[era]
        cers = sorted(r["cer"] for r in rs)
        wers = [r["wer"] for r in rs]
        f1s = [r["metrics"]["identifier_overlap"]["f1"] for r in rs]
        valid = sum(1 for r in rs if r["details"].get("xsd_valid"))
        judged = [r for r in rs if r.get("judge")]
        jmean = (sum(r["judge"]["overall"] for r in judged) / len(judged)) if judged else None
        lines.append(
            f"| {era} | {len(rs)} | {sum(cers)/len(cers):.3f} | {sum(wers)/len(wers):.3f} | {cers[len(cers)//2]:.3f} | "
            f"{sum(f1s)/len(f1s):.2f} | {valid}/{len(rs)} | {len(judged)} | {f'{jmean:.1f}' if jmean is not None else '-'} |"
        )
    return "\n".join(lines)


def granule_table(rows: list[dict]) -> str:
    lines = ["| Granule | Class | Pages | CER | WER | Sections ref/gen | Id F1 | XSD | Judge |", "|---|---|---|---|---|---|---|---|---|"]
    for r in sorted(rows, key=lambda r: (r["era"] or "", r["granule_id"])):
        m = r["metrics"]
        judge = f"{r['judge']['overall']:.0f}" if r.get("judge") else "-"
        lines.append(
            f"| {r['granule_id']} | {r['details'].get('granule_class') or ''} | {r['details'].get('pages') or ''} | {r['cer']:.3f} | {r['wer']:.3f} | "
            f"{m['structure_reference']['section']}/{m['structure_generated']['section']} | {m['identifier_overlap']['f1']:.2f} | "
            f"{'yes' if r['details'].get('xsd_valid') else 'no'} | {judge} |"
        )
    return "\n".join(lines)


def write_report(rows: list[dict], run_id: str, spec_path: str) -> Path:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORTS_DIR / f"{date.today().isoformat()}-{run_id}.md"
    judged = [r for r in rows if r.get("judge")]
    cost = sum(r["judge"].get("cost_usd", 0) for r in judged)
    body = [
        f"# Benchmark {run_id}", "",
        f"Date: {datetime.now().isoformat(timespec='seconds')}. Spec: `{spec_path}`. Granules: {len(rows)}. Judged: {len(judged)} (${cost:.2f}).", "",
        "## By era", "", era_table(rows), "",
        "## By granule", "", granule_table(rows), "",
    ]
    if judged:
        body += ["## Judge summaries", ""]
        for r in judged:
            body.append(f"- **{r['granule_id']}** ({r['judge']['overall']:.0f}): {r['judge']['summary']}")
            for issue in r["judge"].get("issues", [])[:5]:
                body.append(f"  - {issue['severity']} {issue['type']} at {issue['location']}: {issue['description']}")
        body.append("")
    path.write_text("\n".join(body), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------- run


def run(args) -> int:
    setup_logging("evaluate", args.log_dir)
    db.init_db()
    run_id = args.run_id or datetime.now().strftime("%Y%m%d-%H%M")
    entries = load_spec(args.spec)
    if args.limit:
        entries = entries[: args.limit]
    logger.info("run %s: %d granule(s) from %s", run_id, len(entries), args.spec)

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

    units = conv.units_from_spec(args.spec, None)
    if args.limit:
        keep = {e["granule_id"] for e in entries}
        units = [u for u in units if u.unit_id in keep]
    results = {r.unit_id: r for r in conv.run_units(units, conv.workers_for_container(args.workers), args.force)}

    era_by_id = {e["granule_id"]: e.get("era") for e in entries}
    class_by_id = {e["granule_id"]: e.get("granule_class") for e in entries}
    bench_rows: list[dict] = []
    failures: dict[str, str] = {}
    for gid, row in rows.items():
        result = results.get(gid)
        if result is None or result.status == "failed" or not result.xml_path:
            failures[gid] = (result.error if result else "not converted")
            continue
        volume = int(row["package_id"].split("-")[1])
        gt_dir = splits.get(volume)
        gt = (gt_dir / f"{gid}.xml") if gt_dir else None
        if gt is None or not gt.exists():
            failures[gid] = f"no ground truth slice for {gid}"
            continue
        gen_path = Path(result.xml_path)
        gen_sha = sha256_text(gen_path)
        with db.connection() as conn:
            existing = existing_benchmark(conn, gid, run_id, gen_sha)
        if existing and not args.force:
            m = existing["metrics"]
            bench_rows.append({"id": existing["id"], "granule_id": gid, "package_id": row["package_id"], "era": existing["era"],
                               "cer": existing["cer"], "wer": existing["wer"], "metrics": m, "judge": existing["judge"],
                               "details": json.loads(existing["evaluation_details"]), "run_id": run_id,
                               "generated_xml_path": existing["generated_xml_path"],
                               "ground_truth_xml_path": existing["ground_truth_xml_path"]})
            continue
        try:
            comparison = metrics.compare(gt, gen_path)
        except Exception as exc:
            failures[gid] = f"metrics: {exc}"
            continue
        details = {
            "generated_sha256": gen_sha, "xsd_valid": result.xsd_valid, "pages": result.pages, "seconds": result.seconds,
            "granule_class": row.get("granule_class") or class_by_id.get(gid), "profile": None,
        }
        bench = {
            "granule_id": gid, "package_id": row["package_id"], "era": row.get("era") or era_by_id.get(gid),
            "ground_truth_xml_path": state.relative_to_repo(gt), "generated_xml_path": state.relative_to_repo(gen_path),
            "cer": comparison.cer, "wer": comparison.wer, "metrics": comparison.as_dict(), "details": details, "run_id": run_id,
        }
        with db.connection() as conn:
            bench["id"] = write_benchmark(conn, bench)
        logger.info("%s: CER %.3f WER %.3f, identifiers F1 %.2f, sections %d/%d", gid, comparison.cer, comparison.wer,
                    comparison.identifier_overlap["f1"], comparison.structure_reference["section"],
                    comparison.structure_generated["section"])
        bench_rows.append(bench)

    if args.judge:
        from benchmark.judge import Judge

        judge = Judge()
        todo = [b for b in bench_rows if not b.get("judge")]
        if args.judge_limit:
            todo = todo[: args.judge_limit]
        logger.info("judging %d granule(s) with %s", len(todo), judge.model)

        def run_judge(b: dict):
            row = rows[b["granule_id"]]
            identity = {"granule_id": b["granule_id"], "package_id": b["package_id"], "era": b["era"],
                        "granule_class": row.get("granule_class"), "congress": row.get("congress"),
                        "law_number": row.get("number"), "citation": row.get("citation"), "page_range": row.get("page_range")}
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
        report = write_report(bench_rows, run_id, args.spec)
        print(era_table(bench_rows))
        logger.info("report: %s", report)
    for gid, err in sorted(failures.items()):
        logger.error("FAILED %s: %s", gid, err)
    logger.info("done: %d benchmarked, %d failed", len(bench_rows), len(failures))
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
    p.add_argument("--workers", type=int, default=None)
    p.add_argument("--force", action="store_true", help="reconvert and recompute metrics")
    p.add_argument("--run-id", default=None)
    p.add_argument("--log-dir", default=str(LOG_DIR))
    return p


@exit_on_missing_env
def main(argv: Optional[list[str]] = None) -> int:
    return run(build_parser().parse_args(argv))


if __name__ == "__main__":
    sys.exit(main())
