"""HF Jobs runner for the GPU VLM profiles (candidate C4).

    python -m benchmark.jobs submit --run-id wp9b-vlm --variant deepseek_ocr [--variant ...] [--spec benchmark/sample.yaml]
                                    [--classes PUBLICLAW,PRIVATELAW] [--max-pages 3] [--limit N] [--tier-a]
                                    [--flavor l4x1] [--timeout 45m] [--namespace dreamproit] [--dry-run]
    python -m benchmark.jobs status --run-id wp9b-vlm
    python -m benchmark.jobs logs --run-id wp9b-vlm --variant deepseek_ocr [--tail 200]
    python -m benchmark.jobs cancel --run-id wp9b-vlm
    python -m benchmark.jobs fetch --run-id wp9b-vlm [--variant ...]

Inputs: the selected granule PDFs (pipeline.vlm.select_units) are staged under the output stem and uploaded once
per run to `benchmark-runs/<run-id>/inputs/` in the dataset repo HF_REPO_ID, with the job script
`benchmark-runs/<run-id>/job_vlm.py` and `manifest.json`. One job per variant:

    inline engines (transformers)   image python:3.12; installs docling[vlm]==2.126.0
    deepseek_ocr (api_ollama)       image ollama/ollama; installs python and docling==2.126.0, starts `ollama serve`,
                                    pulls deepseek-ocr:3b

The job downloads the inputs, converts every PDF with the variant's Docling preset and engine, and uploads
`benchmark-runs/<run-id>/doclang/vlm-<variant>/` (DoclingDocument JSON and `.timing.json` sidecars with the same
keys pipeline.vlm writes). The ledger data/benchmark-runs/<run-id>/jobs.json records job ids, flavor, timeout,
submission and completion times, and the estimated cost from the flavor's hourly price.

`fetch` downloads the outputs into data/doclang/vlm-<variant>/ and normalizes each document with
pipeline.vlm.finalize_document, so the container can score them with
`benchmark.evaluate --profiles vlm:<variant> --rebuild`.

Requirements: HF_TOKEN with write access to HF_REPO_ID and the Jobs permission on the billing namespace. Jobs are
billed per minute of the flavor (`hf jobs hardware`); `--timeout` bounds the cost of one job.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import shlex
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from downloader.config import DATA_DIR, LOG_DIR, setup_logging
from pipeline import vlm

logger = logging.getLogger("jobs")

DOCLING_VERSION = "2.126.0"
DEFAULT_NAMESPACE = "dreamproit"
DEFAULT_TIMEOUT = "45m"
PYTHON_IMAGE = "python:3.12"
OLLAMA_IMAGE = "ollama/ollama"
OLLAMA_MODEL = "deepseek-ocr:3b"
RUNS_PREFIX = "benchmark-runs"
# $/hour from `hf jobs hardware` on 2026-09-08, for the ledger's cost estimate.
FLAVOR_USD_PER_HOUR = {"cpu-basic": 0.01, "cpu-upgrade": 0.03, "t4-small": 0.40, "t4-medium": 0.60, "a10g-small": 1.00,
                       "a10g-large": 1.50, "l4x1": 0.80, "l40sx1": 1.80, "a100-large": 2.50}

# Runs on the job. Reads VLM_RUN_ID, VLM_VARIANT, VLM_PRESET, VLM_ENGINE, HF_REPO_ID, HF_TOKEN; writes the outputs
# back to the dataset repo. Kept dependency-free beyond docling and huggingface_hub.
JOB_SCRIPT = r'''
import json, os, platform, sys, time, traceback
from datetime import datetime
from pathlib import Path

from huggingface_hub import HfApi, snapshot_download

RUN, VARIANT, PRESET, ENGINE, REPO = (os.environ[k] for k in ("VLM_RUN_ID", "VLM_VARIANT", "VLM_PRESET", "VLM_ENGINE", "HF_REPO_ID"))
OLLAMA_URL = os.environ.get("VLM_OLLAMA_URL") or "http://localhost:11434/v1/chat/completions"
WORK = Path(os.environ.get("VLM_WORK", "/work"))
INPUTS = WORK / "benchmark-runs" / RUN / "inputs"
OUT = WORK / "out"
REMOTE_OUT = f"benchmark-runs/{RUN}/doclang/vlm-{VARIANT}"


def log(msg):
    print(f"{datetime.utcnow().isoformat(timespec='seconds')}Z {msg}", flush=True)


def engine_options():
    from docling.datamodel.vlm_engine_options import ApiVlmEngineOptions, TransformersVlmEngineOptions
    from docling.models.inference_engines.vlm.base import VlmEngineType

    if ENGINE == "transformers":
        return TransformersVlmEngineOptions(load_in_8bit=False)
    if ENGINE == "api_ollama":
        return ApiVlmEngineOptions(engine_type=VlmEngineType.API_OLLAMA, url=OLLAMA_URL, timeout=900.0)
    raise SystemExit(f"unsupported engine {ENGINE}")


def make_converter():
    from docling.datamodel.accelerator_options import AcceleratorOptions
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import VlmConvertOptions, VlmPipelineOptions
    from docling.datamodel.settings import settings
    from docling.document_converter import DocumentConverter, PdfFormatOption
    from docling.pipeline.vlm_pipeline import VlmPipeline

    settings.debug.profile_pipeline_timings = True
    vc = VlmConvertOptions.from_preset(PRESET, engine_options=engine_options())
    opts = VlmPipelineOptions(vlm_options=vc)
    opts.generate_page_images = False
    opts.generate_picture_images = False
    opts.enable_remote_services = ENGINE.startswith("api")
    opts.accelerator_options = AcceleratorOptions(num_threads=4)
    et = vc.engine_options.engine_type
    spec = {"variant": VARIANT, "preset": PRESET, "engine": et.value, "repo_id": vc.model_spec.get_repo_id(et),
            "revision": vc.model_spec.get_revision(et), "response_format": vc.model_spec.response_format.value,
            "scale": vc.scale, "max_size": vc.max_size, "max_new_tokens": vc.model_spec.max_new_tokens,
            "prompt": vc.model_spec.prompt, "api_params": vc.model_spec.get_api_params(et) if et.value.startswith("api") else None}
    return DocumentConverter(format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=opts, pipeline_cls=VlmPipeline)}), spec


def versions():
    import importlib.metadata as md

    out = {}
    for name in ("docling", "docling-core", "transformers", "torch"):
        try:
            out[name] = md.version(name)
        except md.PackageNotFoundError:
            pass
    return out


def gpu_name():
    try:
        import torch

        return torch.cuda.get_device_name(0) if torch.cuda.is_available() else None
    except Exception:
        return None


def convert_all(manifest):
    converter, spec = make_converter()
    OUT.mkdir(parents=True, exist_ok=True)
    host = {"node": platform.node(), "system": platform.system(), "machine": platform.machine(),
            "python": platform.python_version(), "gpu": gpu_name(), "flavor": os.environ.get("VLM_FLAVOR")}
    for entry in manifest["units"]:
        stem = entry["stem"]
        pdf = INPUTS / f"{stem}.pdf"
        timing = {"stem": stem, "variant": VARIANT, "engine": ENGINE, "status": "success", "pages": 0, "seconds": 0.0,
                  "model_seconds": 0.0, "tokens": 0, "page_times": [], "errors": [], "stats": {"granule_class": entry.get("granule_class"),
                  "era": entry.get("era"), "tier": entry.get("tier", "B")}, "spec": spec, "granule_id": entry.get("granule_id"),
                  "input": str(pdf), "input_sha256": entry.get("sha256"), "started": datetime.now().isoformat(timespec="seconds"),
                  "host": host, "versions": versions(), "profile": f"vlm:{VARIANT}", "job_id": os.environ.get("JOB_ID")}
        t0 = time.monotonic()
        try:
            res = converter.convert(str(pdf), raises_on_error=False)
            timing["seconds"] = time.monotonic() - t0
            timing["errors"] = [f"page {e.page_no}: {e.error_message}" if e.page_no else e.error_message for e in res.errors]
            status = res.status.value
            doc = res.document
            if doc is None or status == "failure":
                timing["status"] = "failed"
            else:
                timing["status"] = "success" if status == "success" else "partial"
                for page in res.pages:
                    r = page.predictions.vlm_response
                    if r is None:
                        timing["page_times"].append({"page": page.page_no, "seconds": None, "tokens": None, "stop_reason": "none"})
                        continue
                    gen = float(r.generation_time) if r.generation_time and r.generation_time > 0 else 0.0
                    timing["model_seconds"] += gen
                    timing["tokens"] += int(r.num_tokens or 0)
                    timing["page_times"].append({"page": page.page_no, "seconds": round(gen, 2), "tokens": r.num_tokens,
                                                 "stop_reason": getattr(r.stop_reason, "value", str(r.stop_reason))})
                for page in doc.pages.values():
                    page.image = None
                timing["pages"] = len(doc.pages)
                timing["stats"].update({"items": len(doc.texts) + len(doc.tables), "text_chars": sum(len(t.text or "") for t in doc.texts)})
                (OUT / f"{stem}.json").write_text(json.dumps(doc.export_to_dict(), separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
        except Exception as exc:
            timing["seconds"] = time.monotonic() - t0
            timing["status"] = "failed"
            timing["errors"].append(f"{type(exc).__name__}: {exc}")
            traceback.print_exc()
        timing["seconds_per_page"] = timing["seconds"] / timing["pages"] if timing["pages"] else None
        (OUT / f"{stem}.timing.json").write_text(json.dumps(timing, indent=1, ensure_ascii=False), encoding="utf-8")
        log(f"{stem}: {timing['status']} {timing['pages']} page(s) in {timing['seconds']:.0f}s")


def main():
    log(f"run {RUN} variant {VARIANT} preset {PRESET} engine {ENGINE} repo {REPO}")
    snapshot_download(REPO, repo_type="dataset", allow_patterns=[f"benchmark-runs/{RUN}/inputs/*"], local_dir=str(WORK))
    manifest = json.loads((INPUTS / "manifest.json").read_text(encoding="utf-8"))
    log(f"{len(manifest['units'])} input(s)")
    try:
        convert_all(manifest)
    finally:
        if OUT.exists() and any(OUT.iterdir()):
            HfApi().upload_folder(repo_id=REPO, repo_type="dataset", folder_path=str(OUT), path_in_repo=REMOTE_OUT,
                                  commit_message=f"benchmark-runs/{RUN}: vlm-{VARIANT} outputs")
            log(f"uploaded {len(list(OUT.iterdir()))} file(s) to {REMOTE_OUT}")
    log("done")


if __name__ == "__main__":
    main()
'''


# ---------------------------------------------------------------------------- staging and ledger


def repo_id() -> str:
    value = os.getenv("HF_REPO_ID", "").strip()
    if not value:
        raise SystemExit("HF_REPO_ID is not set (the dataset repo that holds benchmark-runs/)")
    return value


def runs_dir(run_id: str, data_dir: Path = DATA_DIR) -> Path:
    return Path(data_dir) / RUNS_PREFIX / run_id


def ledger_path(run_id: str, data_dir: Path = DATA_DIR) -> Path:
    return runs_dir(run_id, data_dir) / "jobs.json"


def load_ledger(run_id: str, data_dir: Path = DATA_DIR) -> dict:
    p = ledger_path(run_id, data_dir)
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return {"run_id": run_id, "repo_id": None, "inputs": None, "jobs": []}


def save_ledger(ledger: dict, data_dir: Path = DATA_DIR) -> Path:
    p = ledger_path(ledger["run_id"], data_dir)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(ledger, indent=1), encoding="utf-8")
    return p


def stage_inputs(units: list[vlm.VlmUnit], run_id: str, data_dir: Path = DATA_DIR) -> Path:
    """Copy the unit PDFs to data/benchmark-runs/<run-id>/inputs/{stem}.pdf and write manifest.json."""
    inputs = runs_dir(run_id, data_dir) / "inputs"
    inputs.mkdir(parents=True, exist_ok=True)
    manifest = {"run_id": run_id, "created": datetime.now(timezone.utc).isoformat(timespec="seconds"), "units": []}
    for u in units:
        dest = inputs / f"{u.stem}.pdf"
        shutil.copyfile(u.pdf, dest)
        manifest["units"].append({"stem": u.stem, "granule_id": u.granule_id, "granule_class": u.granule_class, "era": u.era,
                                  "tier": u.tier, "pages": u.pages, "source": str(u.pdf), "sha256": vlm.sha256_file(dest)})
    (inputs / "manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    (runs_dir(run_id, data_dir) / "job_vlm.py").write_text(JOB_SCRIPT.lstrip("\n"), encoding="utf-8")
    return inputs


def remote_prefix(run_id: str) -> str:
    return f"{RUNS_PREFIX}/{run_id}"


def upload_inputs(run_id: str, data_dir: Path = DATA_DIR) -> str:
    """Upload inputs/ and job_vlm.py to benchmark-runs/<run-id>/ in the dataset repo; returns the commit url."""
    from huggingface_hub import HfApi

    api = HfApi(token=os.getenv("HF_TOKEN") or None)
    folder = runs_dir(run_id, data_dir)
    info = api.upload_folder(repo_id=repo_id(), repo_type="dataset", folder_path=str(folder), path_in_repo=remote_prefix(run_id),
                             allow_patterns=["inputs/*", "job_vlm.py"], commit_message=f"{remote_prefix(run_id)}: inputs")
    return str(getattr(info, "commit_url", info))


# ---------------------------------------------------------------------------- job command


def job_image(variant: vlm.VlmVariant) -> str:
    return OLLAMA_IMAGE if variant.engines[0] == "api_ollama" else PYTHON_IMAGE


def job_engine(variant: vlm.VlmVariant) -> str:
    return variant.engines[0]


def job_shell(run_id: str, variant: vlm.VlmVariant) -> str:
    """Shell command run in the job image: install Docling, download the job script, run it."""
    script = f"{remote_prefix(run_id)}/job_vlm.py"
    fetch = ("python -c \"from huggingface_hub import hf_hub_download; import os; "
             f"hf_hub_download(os.environ['HF_REPO_ID'], '{script}', repo_type='dataset', local_dir='/work')\"")
    run = f"python /work/{script}"
    if job_engine(variant) == "api_ollama":
        return " && ".join([
            "apt-get update -qq", "apt-get install -y -qq python3 python3-pip python3-venv libgl1 libglib2.0-0 >/dev/null",
            "python3 -m venv /venv", f"/venv/bin/pip install -q docling=={DOCLING_VERSION}",
            "(ollama serve >/tmp/ollama.log 2>&1 &)", "sleep 8", f"ollama pull {OLLAMA_MODEL}",
            fetch.replace("python ", "/venv/bin/python ", 1), run.replace("python ", "/venv/bin/python ", 1),
        ])
    return " && ".join([
        "apt-get update -qq", "apt-get install -y -qq libgl1 libglib2.0-0 >/dev/null",
        f"pip install -q \"docling[vlm]=={DOCLING_VERSION}\"", fetch, run,
    ])


def job_env(run_id: str, variant: vlm.VlmVariant, flavor: str) -> dict[str, str]:
    return {"VLM_RUN_ID": run_id, "VLM_VARIANT": variant.name, "VLM_PRESET": variant.preset, "VLM_ENGINE": job_engine(variant),
            "VLM_FLAVOR": flavor, "HF_REPO_ID": repo_id(), "HF_HUB_DISABLE_PROGRESS_BARS": "1"}


def job_command(run_id: str, variant: vlm.VlmVariant, flavor: Optional[str] = None, timeout: str = DEFAULT_TIMEOUT,
                namespace: str = DEFAULT_NAMESPACE) -> dict:
    """Everything one job needs: image, shell command, env, flavor; `argv` is the equivalent `hf jobs run` line."""
    flavor = flavor or variant.flavor
    env = job_env(run_id, variant, flavor)
    shell = job_shell(run_id, variant)
    name = f"{run_id}-vlm-{variant.name}".replace("_", "-")
    argv = ["hf", "jobs", "run", "--flavor", flavor, "--timeout", timeout, "--namespace", namespace, "--name", name,
            "--secrets", "HF_TOKEN", "--detach"]
    for k, v in env.items():
        argv += ["--env", f"{k}={v}"]
    argv += [job_image(variant), "sh", "-c", shell]
    return {"variant": variant.name, "engine": job_engine(variant), "image": job_image(variant), "flavor": flavor, "timeout": timeout,
            "namespace": namespace, "name": name, "env": env, "command": ["sh", "-c", shell], "argv": argv}


def estimate_cost(flavor: str, seconds: float) -> Optional[float]:
    rate = FLAVOR_USD_PER_HOUR.get(flavor)
    return round(rate * seconds / 3600, 4) if rate is not None else None


def submit_job(spec: dict) -> str:
    """Run the job through the Hub API (same request as `hf jobs run`); returns the job id."""
    from huggingface_hub import HfApi

    api = HfApi(token=os.getenv("HF_TOKEN") or None)
    info = api.run_job(image=spec["image"], command=spec["command"], env=spec["env"], secrets={"HF_TOKEN": os.environ["HF_TOKEN"]},
                       flavor=spec["flavor"], timeout=spec["timeout"], name=spec["name"], namespace=spec["namespace"])
    return info.id


# ---------------------------------------------------------------------------- fetch


def normalize_outputs(source: Path, variant: str, data_dir: Path = DATA_DIR) -> list[Path]:
    """Copy JSON and sidecars from `source` into data/doclang/vlm-<variant>/, applying finalize_document."""
    from docling_core.types.doc import DoclingDocument

    written = []
    for sidecar in sorted(Path(source).glob("*.timing.json")):
        stem = sidecar.name[: -len(".timing.json")]
        out = vlm.output_path(variant, stem, data_dir)
        out.parent.mkdir(parents=True, exist_ok=True)
        timing = json.loads(sidecar.read_text(encoding="utf-8"))
        src_json = Path(source) / f"{stem}.json"
        if src_json.exists():
            doc = DoclingDocument.load_from_json(src_json)
            timing.setdefault("stats", {}).update(vlm.finalize_document(doc))
            out.write_text(json.dumps(doc.export_to_dict(), separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
            written.append(out)
        timing["fetched"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        vlm.timing_sidecar(out).write_text(json.dumps(timing, indent=1, ensure_ascii=False), encoding="utf-8")
    return written


def download_outputs(run_id: str, variant: str, data_dir: Path = DATA_DIR) -> Path:
    from huggingface_hub import snapshot_download

    local = runs_dir(run_id, data_dir) / "download"
    snapshot_download(repo_id(), repo_type="dataset", allow_patterns=[f"{remote_prefix(run_id)}/doclang/vlm-{variant}/*"],
                      local_dir=str(local), token=os.getenv("HF_TOKEN") or None)
    return local / remote_prefix(run_id) / "doclang" / f"vlm-{variant}"


# ---------------------------------------------------------------------------- CLI


def cmd_submit(args) -> int:
    data_dir = Path(args.data_dir)
    variants = [vlm.get_variant(v) for v in (args.variant or ["deepseek_ocr"])]
    classes = [c.strip() for c in args.classes.split(",")] if args.classes else None
    entries = vlm.load_spec_entries(args.spec)
    units = vlm.select_units(entries, data_dir, classes=classes, max_pages=args.max_pages, limit=args.limit)
    if args.tier_a:
        units += vlm.select_units(entries, data_dir, classes=classes, max_pages=args.max_pages, limit=args.limit, tier_a=True)
    if not units:
        logger.error("no units selected")
        return 2
    ledger = load_ledger(args.run_id, data_dir)
    ledger["repo_id"] = repo_id()
    inputs = stage_inputs(units, args.run_id, data_dir)
    logger.info("staged %d input(s), %d page(s) -> %s", len(units), sum(u.pages or 0 for u in units), inputs)
    specs = [job_command(args.run_id, v, args.flavor, args.timeout, args.namespace) for v in variants]
    for s in specs:
        print(" ".join(shlex.quote(a) for a in s["argv"]))
    if args.dry_run:
        save_ledger(ledger, data_dir)
        return 0
    if not ledger.get("inputs"):
        ledger["inputs"] = {"remote": f"{remote_prefix(args.run_id)}/inputs", "commit": upload_inputs(args.run_id, data_dir),
                            "units": [u.stem for u in units]}
        logger.info("uploaded inputs: %s", ledger["inputs"]["commit"])
    for s in specs:
        try:
            job_id = submit_job(s)
        except Exception as exc:
            logger.error("%s: submit failed: %s", s["variant"], exc)
            ledger["jobs"].append({**{k: s[k] for k in ("variant", "engine", "image", "flavor", "timeout", "namespace", "name")},
                                   "job_id": None, "error": str(exc), "submitted": datetime.now(timezone.utc).isoformat(timespec="seconds")})
            continue
        logger.info("%s: job %s (%s, %s)", s["variant"], job_id, s["flavor"], s["timeout"])
        ledger["jobs"].append({**{k: s[k] for k in ("variant", "engine", "image", "flavor", "timeout", "namespace", "name")},
                               "job_id": job_id, "submitted": datetime.now(timezone.utc).isoformat(timespec="seconds")})
    save_ledger(ledger, data_dir)
    return 0 if all(j.get("job_id") for j in ledger["jobs"]) else 1


def _api():
    from huggingface_hub import HfApi

    return HfApi(token=os.getenv("HF_TOKEN") or None)


def cmd_status(args) -> int:
    ledger = load_ledger(args.run_id, Path(args.data_dir))
    api = _api()
    print("| Variant | Job | Flavor | Stage | Submitted | Started | Finished | Wall | Est. cost |")
    print("|---|---|---|---|---|---|---|---|---|")
    for j in ledger["jobs"]:
        if not j.get("job_id"):
            print(f"| {j['variant']} | - | {j['flavor']} | not submitted: {j.get('error', '')[:80]} | {j['submitted']} | | | | |")
            continue
        info = api.inspect_job(job_id=j["job_id"], namespace=j.get("namespace"))
        stage = getattr(info.status, "stage", None) or str(info.status)
        started, finished = getattr(info, "started_at", None), getattr(info, "finished_at", None)
        wall = (finished - started).total_seconds() if started and finished else None
        j.update({"stage": stage, "started": started.isoformat() if started else None, "finished": finished.isoformat() if finished else None,
                  "wall_seconds": wall, "estimated_cost_usd": estimate_cost(j["flavor"], wall) if wall else None})
        print(f"| {j['variant']} | {j['job_id']} | {j['flavor']} | {stage} | {j['submitted']} | {j['started'] or ''} | {j['finished'] or ''} | "
              f"{f'{wall:.0f}s' if wall else ''} | {j['estimated_cost_usd'] if wall else ''} |")
    save_ledger(ledger, Path(args.data_dir))
    return 0


def cmd_logs(args) -> int:
    ledger = load_ledger(args.run_id, Path(args.data_dir))
    api = _api()
    for j in ledger["jobs"]:
        if j.get("job_id") and (not args.variant or j["variant"] in args.variant):
            print(f"=== {j['variant']} {j['job_id']}")
            for line in api.fetch_job_logs(job_id=j["job_id"], namespace=j.get("namespace"), tail=args.tail):
                print(line)
    return 0


def cmd_cancel(args) -> int:
    ledger = load_ledger(args.run_id, Path(args.data_dir))
    api = _api()
    for j in ledger["jobs"]:
        if j.get("job_id") and (not args.variant or j["variant"] in args.variant):
            api.cancel_job(job_id=j["job_id"], namespace=j.get("namespace"))
            j["cancelled"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
            logger.info("%s: cancelled %s", j["variant"], j["job_id"])
    save_ledger(ledger, Path(args.data_dir))
    return 0


def cmd_fetch(args) -> int:
    data_dir = Path(args.data_dir)
    ledger = load_ledger(args.run_id, data_dir)
    variants = args.variant or [j["variant"] for j in ledger["jobs"] if j.get("job_id")]
    total = 0
    for name in variants:
        source = download_outputs(args.run_id, name, data_dir)
        if not source.exists():
            logger.warning("%s: no outputs under %s", name, source)
            continue
        written = normalize_outputs(source, name, data_dir)
        logger.info("%s: %d document(s) -> %s", name, len(written), vlm.output_path(name, "x", data_dir).parent)
        total += len(written)
    return 0 if total else 1


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m benchmark.jobs", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--data-dir", default=str(DATA_DIR))
    p.add_argument("--log-dir", default=str(LOG_DIR))
    sub = p.add_subparsers(dest="command", required=True)
    s = sub.add_parser("submit")
    s.add_argument("--run-id", required=True)
    s.add_argument("--variant", action="append", default=[], choices=sorted(vlm.VARIANTS))
    s.add_argument("--spec", default="benchmark/sample.yaml")
    s.add_argument("--classes", default=None)
    s.add_argument("--max-pages", type=int, default=None)
    s.add_argument("--limit", type=int, default=None)
    s.add_argument("--tier-a", action="store_true", help="also stage the clean rasters of the born-digital granules")
    s.add_argument("--flavor", default=None, help="override the variant's flavor (see `hf jobs hardware`)")
    s.add_argument("--timeout", default=DEFAULT_TIMEOUT)
    s.add_argument("--namespace", default=DEFAULT_NAMESPACE)
    s.add_argument("--dry-run", action="store_true", help="stage inputs and print the commands; upload and submit nothing")
    for name in ("status", "logs", "cancel", "fetch"):
        q = sub.add_parser(name)
        q.add_argument("--run-id", required=True)
        q.add_argument("--variant", action="append", default=[])
        if name == "logs":
            q.add_argument("--tail", type=int, default=200)
    return p


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    setup_logging("jobs", args.log_dir)
    return {"submit": cmd_submit, "status": cmd_status, "logs": cmd_logs, "cancel": cmd_cancel, "fetch": cmd_fetch}[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
