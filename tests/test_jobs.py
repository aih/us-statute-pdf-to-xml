import json
from pathlib import Path

import pytest

from benchmark import jobs
from pipeline import vlm


@pytest.fixture
def repo_env(monkeypatch):
    monkeypatch.setenv("HF_REPO_ID", "org/dataset")
    monkeypatch.setenv("HF_TOKEN", "hf_test")


def test_job_command_inline_and_ollama(repo_env):
    spec = jobs.job_command("wp9b-vlm", vlm.get_variant("glm_ocr"))
    assert spec["image"] == "python:3.12" and spec["flavor"] == "l4x1" and spec["engine"] == "transformers"
    assert spec["env"]["VLM_PRESET"] == "glm_ocr" and spec["env"]["HF_REPO_ID"] == "org/dataset"
    shell = spec["command"][2]
    assert 'docling[vlm]==2.126.0' in shell and "benchmark-runs/wp9b-vlm/job_vlm.py" in shell and "ollama" not in shell
    argv = spec["argv"]
    assert argv[:3] == ["hf", "jobs", "run"] and "--secrets" in argv and argv[argv.index("--secrets") + 1] == "HF_TOKEN"
    assert argv[argv.index("--flavor") + 1] == "l4x1" and argv[argv.index("--namespace") + 1] == "dreamproit"
    assert argv[-4:-1] == ["python:3.12", "sh", "-c"] and argv[-1] == shell
    assert "HF_TOKEN" not in " ".join(a for a in argv if a.startswith(("VLM_", "HF_REPO"))) and "hf_test" not in " ".join(argv)

    ds = jobs.job_command("wp9b-vlm", vlm.get_variant("deepseek_ocr"), flavor="a10g-small", timeout="30m", namespace="me")
    assert ds["image"] == "ollama/ollama" and ds["engine"] == "api_ollama" and ds["flavor"] == "a10g-small"
    shell = ds["command"][2]
    assert "ollama serve" in shell and "ollama pull deepseek-ocr:3b" in shell and "/venv/bin/python /work/benchmark-runs/wp9b-vlm/job_vlm.py" in shell
    assert "docling==2.126.0" in shell and "docling[vlm]" not in shell
    assert ds["argv"][ds["argv"].index("--timeout") + 1] == "30m" and ds["name"] == "wp9b-vlm-vlm-deepseek-ocr"


def test_job_script_compiles_and_reads_env():
    compile(jobs.JOB_SCRIPT, "job_vlm.py", "exec")
    for key in ("VLM_RUN_ID", "VLM_VARIANT", "VLM_PRESET", "VLM_ENGINE", "HF_REPO_ID"):
        assert key in jobs.JOB_SCRIPT
    assert "upload_folder" in jobs.JOB_SCRIPT and ".timing.json" in jobs.JOB_SCRIPT


def test_estimate_cost():
    assert jobs.estimate_cost("l4x1", 1800) == 0.4
    assert jobs.estimate_cost("t4-small", 3600) == 0.4
    assert jobs.estimate_cost("unknown", 60) is None


def test_stage_inputs_and_ledger(tmp_path, repo_env):
    pdf = tmp_path / "STATUTE-9-Pg1.pdf"
    pdf.write_bytes(b"%PDF-1.4 test")
    units = [vlm.VlmUnit(stem="STATUTE-9-Pg1", pdf=pdf, granule_id="STATUTE-9-Pg1", granule_class="PUBLICLAW", era="scanned-pre-1951", pages=1),
             vlm.VlmUnit(stem="STATUTE-9-Pg1_A-clean", pdf=pdf, granule_id="STATUTE-9-Pg1", granule_class="PUBLICLAW", era="digital-2003+", pages=1, tier="A")]
    inputs = jobs.stage_inputs(units, "run1", tmp_path)
    assert inputs == tmp_path / "benchmark-runs" / "run1" / "inputs"
    assert sorted(p.name for p in inputs.iterdir()) == ["STATUTE-9-Pg1.pdf", "STATUTE-9-Pg1_A-clean.pdf", "manifest.json"]
    manifest = json.loads((inputs / "manifest.json").read_text())
    assert [u["stem"] for u in manifest["units"]] == ["STATUTE-9-Pg1", "STATUTE-9-Pg1_A-clean"] and manifest["units"][1]["tier"] == "A"
    assert manifest["units"][0]["sha256"] == vlm.sha256_file(pdf)
    assert (tmp_path / "benchmark-runs" / "run1" / "job_vlm.py").read_text().startswith("import json")
    ledger = jobs.load_ledger("run1", tmp_path)
    assert ledger == {"run_id": "run1", "repo_id": None, "inputs": None, "jobs": []}
    ledger["jobs"].append({"variant": "glm_ocr", "job_id": "abc", "flavor": "l4x1"})
    assert jobs.save_ledger(ledger, tmp_path) == tmp_path / "benchmark-runs" / "run1" / "jobs.json"
    assert jobs.load_ledger("run1", tmp_path)["jobs"][0]["job_id"] == "abc"


def test_submit_dry_run_prints_commands(tmp_path, repo_env, capsys, monkeypatch):
    pytest.importorskip("pypdfium2")
    img2pdf = pytest.importorskip("img2pdf")
    Image = pytest.importorskip("PIL.Image")
    gdir = tmp_path / "granules" / "STATUTE-9"
    gdir.mkdir(parents=True)
    png = tmp_path / "p.png"
    Image.new("RGB", (100, 100), "white").save(png)
    (gdir / "STATUTE-9-Pg1.pdf").write_bytes(img2pdf.convert([str(png)], dpi=72))
    spec = tmp_path / "spec.yaml"
    spec.write_text("granules:\n- granule_id: STATUTE-9-Pg1\n  package_id: STATUTE-9\n  volume: 9\n  era: scanned-pre-1951\n  granule_class: PUBLICLAW\n")
    monkeypatch.setattr(jobs, "upload_inputs", lambda *a, **k: pytest.fail("dry run must not upload"))
    monkeypatch.setattr(jobs, "submit_job", lambda *a, **k: pytest.fail("dry run must not submit"))
    rc = jobs.main(["--data-dir", str(tmp_path), "--log-dir", str(tmp_path / "logs"), "submit", "--run-id", "r", "--spec", str(spec),
                    "--variant", "deepseek_ocr", "--variant", "granite_docling", "--dry-run"])
    assert rc == 0
    out = capsys.readouterr().out
    assert out.count("hf jobs run") == 2 and "--flavor l4x1" in out and "--flavor t4-small" in out
    assert (tmp_path / "benchmark-runs" / "r" / "inputs" / "STATUTE-9-Pg1.pdf").exists()
    assert jobs.load_ledger("r", tmp_path)["repo_id"] == "org/dataset"


def test_normalize_outputs_applies_geometry(tmp_path):
    pytest.importorskip("docling_core")
    from docling_core.types.doc import BoundingBox, DocItemLabel, DoclingDocument, ProvenanceItem, Size

    doc = DoclingDocument(name="remote")
    doc.add_page(page_no=1, size=Size(width=400, height=800))
    doc.add_text(label=DocItemLabel.TEXT, text="AN ACT", prov=ProvenanceItem(page_no=1, bbox=BoundingBox(l=0, t=0, r=0, b=0), charspan=(0, 0)))
    source = tmp_path / "remote"
    source.mkdir()
    (source / "STATUTE-9-Pg1.json").write_text(json.dumps(doc.export_to_dict()))
    (source / "STATUTE-9-Pg1.timing.json").write_text(json.dumps({"stem": "STATUTE-9-Pg1", "variant": "deepseek_ocr", "engine": "api_ollama",
                                                                    "status": "success", "pages": 1, "seconds": 3.0, "model_seconds": 2.0, "tokens": 10}))
    (source / "STATUTE-9-Pg2.timing.json").write_text(json.dumps({"stem": "STATUTE-9-Pg2", "variant": "deepseek_ocr", "engine": "api_ollama",
                                                                    "status": "failed", "pages": 0, "seconds": 1.0, "model_seconds": 0, "tokens": 0, "errors": ["x"]}))
    written = jobs.normalize_outputs(source, "deepseek_ocr", tmp_path)
    assert written == [tmp_path / "doclang" / "vlm-deepseek_ocr" / "STATUTE-9-Pg1.json"]
    data = json.loads(written[0].read_text())
    box = data["texts"][0]["prov"][0]["bbox"]
    assert box["coord_origin"] == "BOTTOMLEFT" and box["t"] == 760 and box["l"] == 40
    side = json.loads((tmp_path / "doclang" / "vlm-deepseek_ocr" / "STATUTE-9-Pg1.timing.json").read_text())
    assert side["stats"]["synthesized_geometry"] == 1 and side["fetched"]
    assert (tmp_path / "doclang" / "vlm-deepseek_ocr" / "STATUTE-9-Pg2.timing.json").exists()
    assert not (tmp_path / "doclang" / "vlm-deepseek_ocr" / "STATUTE-9-Pg2.json").exists()
