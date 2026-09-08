"""Stratified benchmark sample: granules per era per document class, seeded.

    python -m benchmark.sample --per-cell 10 --volumes-per-era 3 --max-pages 30 --seed 20260905 \
        --out benchmark/sample.yaml

Eras: scanned-pre-1951 (volumes 1-64), scanned-1951-2002 (65-116), digital-2003+ (117-137). For each
era the script picks `--volumes-per-era` volumes at random, fetches their granule listings
(cached at data/granules/STATUTE-{n}/granules.json), estimates each granule's length from the gap
to the next granule's start page, drops granules longer than `--max-pages`, and samples
`--per-cell` granules per (era, class). Classes: PUBLICLAW, PRIVATELAW, PROCLAMATION, TREATY,
HCONRES, SCONRES; a class absent from an era's volumes yields no rows for that cell.

The digital era is restricted to PUBLICLAW and PRIVATELAW (`ERA_CLASSES`): from volume 117 on GovInfo
groups concurrent resolutions and proclamations differently from the volume USLM, so the splitter has
no one-to-one reference for the other classes (defect F4 of the 2026-09-07 plan).
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Iterable, Optional

import yaml

from downloader.config import DATA_DIR, exit_on_missing_env, govinfo_api_key

ERAS = [
    {"name": "scanned-pre-1951", "volumes": [1, 64]},
    {"name": "scanned-1951-2002", "volumes": [65, 116]},
    {"name": "digital-2003+", "volumes": [117, 137]},
]
CLASSES = ["PUBLICLAW", "PRIVATELAW", "PROCLAMATION", "TREATY", "HCONRES", "SCONRES"]
# Classes with a one-to-one ground-truth slice per era; eras absent here allow every class in CLASSES.
ERA_CLASSES = {"digital-2003+": ["PUBLICLAW", "PRIVATELAW"]}


def classes_for_era(era: str, classes: Iterable[str] = CLASSES) -> list[str]:
    allowed = ERA_CLASSES.get(era)
    return [c for c in classes if allowed is None or c in allowed]


GRANULE_ID = re.compile(r"^STATUTE-(\d+)-Pg([A-Za-z]*)(\d+)(?:-(\d+))?$")


def era_for_volume(volume: int) -> Optional[str]:
    for era in ERAS:
        lo, hi = era["volumes"]
        if lo <= volume <= hi:
            return era["name"]
    return None


def page_key(granule_id: str) -> Optional[tuple[str, int, int]]:
    m = GRANULE_ID.match(granule_id)
    if not m:
        return None
    return m.group(2).lower(), int(m.group(3)), int(m.group(4) or 1)


def estimate_pages(granules: list[dict]) -> dict[str, int]:
    """Pages per granule from the distance to the next granule's start page within the same part."""
    keyed = [(page_key(g["granuleId"]), g["granuleId"]) for g in granules]
    keyed = [(k, gid) for k, gid in keyed if k]
    keyed.sort()
    est: dict[str, int] = {}
    for (k, gid), nxt in zip(keyed, keyed[1:] + [(None, None)]):
        if nxt[0] is None or nxt[0][0] != k[0]:
            est[gid] = 1
        else:
            est[gid] = max(1, nxt[0][1] - k[1]) if nxt[0][1] > k[1] else 1
    return est


def listing_path(volume: int) -> Path:
    return DATA_DIR / "granules" / f"STATUTE-{volume}" / "granules.json"


def load_listing(volume: int, client=None) -> list[dict]:
    path = listing_path(volume)
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    if client is None:
        raise FileNotFoundError(path)
    granules = list(client.iter_granules(f"STATUTE-{volume}"))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(granules), encoding="utf-8")
    return granules


def choose_volumes(rng: random.Random, per_era: int, only: Optional[Iterable[int]] = None) -> dict[str, list[int]]:
    chosen: dict[str, list[int]] = {}
    allowed = set(only) if only else None
    for era in ERAS:
        lo, hi = era["volumes"]
        pool = [v for v in range(lo, hi + 1) if allowed is None or v in allowed]
        rng.shuffle(pool)
        chosen[era["name"]] = sorted(pool[:per_era])
    return chosen


def build_sample(listings: dict[int, list[dict]], per_cell: int, max_pages: int, seed: int,
                 classes: Iterable[str] = CLASSES) -> list[dict]:
    """Pure: from {volume: granule listing} pick per_cell granules for each (era, class)."""
    rng = random.Random(seed)
    cells: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for volume, granules in sorted(listings.items()):
        era = era_for_volume(volume)
        est = estimate_pages(granules)
        for g in granules:
            cls = g.get("granuleClass")
            if era is None or cls not in classes_for_era(era, classes):
                continue
            pages = est.get(g["granuleId"])
            if pages is None or pages > max_pages:
                continue
            cells[(era, cls)].append({
                "granule_id": g["granuleId"], "package_id": f"STATUTE-{volume}", "volume": volume, "era": era,
                "granule_class": cls, "title": (g.get("title") or "")[:200], "est_pages": pages,
                "date_issued": g.get("dateIssued"),
            })
    sample = []
    for era in [e["name"] for e in ERAS]:
        for cls in classes_for_era(era, classes):
            pool = cells.get((era, cls), [])
            pool.sort(key=lambda r: r["granule_id"])
            rng.shuffle(pool)
            sample.extend(sorted(pool[:per_cell], key=lambda r: (r["volume"], page_key(r["granule_id"]) or ())))
    return sample


def write_spec(sample: list[dict], path: Path, meta: dict) -> None:
    spec = {**meta, "eras": ERAS, "classes": CLASSES, "era_classes": ERA_CLASSES, "granules": sample}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(spec, sort_keys=False, allow_unicode=True, width=120), encoding="utf-8")


@exit_on_missing_env
def main(argv: Optional[list[str]] = None) -> int:
    p = argparse.ArgumentParser(prog="python -m benchmark.sample", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--per-cell", type=int, default=10)
    p.add_argument("--volumes-per-era", type=int, default=3)
    p.add_argument("--max-pages", type=int, default=30)
    p.add_argument("--seed", type=int, default=20260905)
    p.add_argument("--volumes", default=None, help="restrict candidate volumes, e.g. 32,64,119")
    p.add_argument("--out", default="benchmark/sample.yaml")
    args = p.parse_args(argv)

    from downloader.govinfo import GovInfoClient, parse_volume_spec

    rng = random.Random(args.seed)
    only = parse_volume_spec(args.volumes) if args.volumes else None
    chosen = choose_volumes(rng, args.volumes_per_era, only)
    listings: dict[int, list[dict]] = {}
    with GovInfoClient(govinfo_api_key()) as client:
        for era, volumes in chosen.items():
            for v in volumes:
                listings[v] = load_listing(v, client)
                print(f"{era}: STATUTE-{v} has {len(listings[v])} granules")
    sample = build_sample(listings, args.per_cell, args.max_pages, args.seed)
    write_spec(sample, Path(args.out), {"seed": args.seed, "per_cell": args.per_cell, "max_pages": args.max_pages,
                                        "volumes": {k: v for k, v in chosen.items()}})
    by_cell = defaultdict(int)
    for r in sample:
        by_cell[(r["era"], r["granule_class"])] += 1
    for (era, cls), n in sorted(by_cell.items()):
        print(f"{era:20s} {cls:12s} {n}")
    print(f"{len(sample)} granules, about {sum(r['est_pages'] for r in sample)} pages -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
