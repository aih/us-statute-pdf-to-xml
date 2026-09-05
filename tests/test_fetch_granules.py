from pathlib import Path

import pytest

from downloader import fetch_granules


def test_package_id_for():
    assert fetch_granules.package_id_for("STATUTE-64-Pg371") == "STATUTE-64"
    assert fetch_granules.package_id_for("STATUTE-64-Pg373-2") == "STATUTE-64"
    assert fetch_granules.package_id_for("STATUTE-64-PgB3") == "STATUTE-64"
    with pytest.raises(ValueError):
        fetch_granules.package_id_for("PLAW-118publ5")


def test_load_spec_dedupes_and_fills_package(tmp_path):
    spec = tmp_path / "s.yaml"
    spec.write_text(
        "granules:\n"
        "  - granule_id: STATUTE-64-Pg371\n    era: x\n"
        "  - STATUTE-64-PgB3\n"
        "  - granule_id: STATUTE-64-Pg371\n"
    )
    items = fetch_granules.load_spec(spec)
    assert [i["granule_id"] for i in items] == ["STATUTE-64-Pg371", "STATUTE-64-PgB3"]
    assert items[0]["package_id"] == "STATUTE-64" and items[0]["era"] == "x"


def test_smoke_spec_parses():
    items = fetch_granules.load_spec(Path("benchmark/sample_smoke.yaml"))
    assert len(items) >= 4


def test_granule_paths():
    pdf, mods = fetch_granules.granule_paths("STATUTE-64-Pg371", Path("/x"))
    assert pdf == Path("/x/STATUTE-64/STATUTE-64-Pg371.pdf")
    assert mods == Path("/x/STATUTE-64/STATUTE-64-Pg371.mods.xml")
