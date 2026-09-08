from benchmark import sample


LISTING_64 = [
    {"granuleId": "STATUTE-64-Pg3", "granuleClass": "PUBLICLAW", "title": "a"},
    {"granuleId": "STATUTE-64-Pg3-2", "granuleClass": "PUBLICLAW", "title": "b"},
    {"granuleId": "STATUTE-64-Pg10", "granuleClass": "PUBLICLAW", "title": "c"},
    {"granuleId": "STATUTE-64-Pg60", "granuleClass": "PRIVATELAW", "title": "d"},
    {"granuleId": "STATUTE-64-PgB3", "granuleClass": "TREATY", "title": "e"},
    {"granuleId": "STATUTE-64-PgB33", "granuleClass": "TREATY", "title": "f"},
    {"granuleId": "STATUTE-64-FrontMatter-1-PgIII", "granuleClass": "FRONTMATTER", "title": "g"},
]


def test_era_and_page_key():
    assert sample.era_for_volume(64) == "scanned-pre-1951"
    assert sample.era_for_volume(65) == "scanned-1951-2002"
    assert sample.era_for_volume(137) == "digital-2003+"
    assert sample.era_for_volume(138) is None
    assert sample.page_key("STATUTE-64-PgB33") == ("b", 33, 1)
    assert sample.page_key("STATUTE-64-Pg3-2") == ("", 3, 2)
    assert sample.page_key("STATUTE-64-FrontMatter-1-PgIII") is None


def test_estimate_pages():
    est = sample.estimate_pages(LISTING_64)
    assert est["STATUTE-64-Pg3"] == 1  # next granule starts on the same page
    assert est["STATUTE-64-Pg3-2"] == 7
    assert est["STATUTE-64-Pg10"] == 50
    assert est["STATUTE-64-Pg60"] == 1  # last in its part
    assert est["STATUTE-64-PgB3"] == 30 and est["STATUTE-64-PgB33"] == 1


def test_build_sample_is_seeded_and_filters_by_pages():
    s1 = sample.build_sample({64: LISTING_64}, per_cell=1, max_pages=10, seed=1)
    s2 = sample.build_sample({64: LISTING_64}, per_cell=1, max_pages=10, seed=1)
    assert s1 == s2
    ids = {r["granule_id"] for r in s1}
    assert "STATUTE-64-Pg10" not in ids and "STATUTE-64-PgB3" not in ids  # too long
    assert "STATUTE-64-FrontMatter-1-PgIII" not in ids  # class not sampled
    classes = {r["granule_class"] for r in s1}
    assert classes == {"PUBLICLAW", "PRIVATELAW", "TREATY"}
    assert all(r["era"] == "scanned-pre-1951" and r["package_id"] == "STATUTE-64" for r in s1)
    assert sample.build_sample({64: LISTING_64}, per_cell=5, max_pages=10, seed=1).__len__() == 4


def test_write_spec_roundtrip(tmp_path):
    from downloader.fetch_granules import load_spec

    rows = sample.build_sample({64: LISTING_64}, per_cell=2, max_pages=10, seed=3)
    out = tmp_path / "s.yaml"
    sample.write_spec(rows, out, {"seed": 3})
    loaded = load_spec(out)
    assert [r["granule_id"] for r in loaded] == [r["granule_id"] for r in rows]
    assert loaded[0]["era"] == "scanned-pre-1951"


LISTING_132 = [
    {"granuleId": "STATUTE-132-Pg1", "granuleClass": "PUBLICLAW", "title": "a"},
    {"granuleId": "STATUTE-132-Pg5599", "granuleClass": "PRIVATELAW", "title": "b"},
    {"granuleId": "STATUTE-132-Pg5600", "granuleClass": "HCONRES", "title": "c"},
    {"granuleId": "STATUTE-132-Pg5601", "granuleClass": "SCONRES", "title": "d"},
    {"granuleId": "STATUTE-132-Pg5703", "granuleClass": "PROCLAMATION", "title": "e"},
]


def test_f4_digital_era_samples_only_laws():
    """Reproduction of F4: resolutions and proclamations from volume 117 on have no one-to-one reference."""
    assert sample.classes_for_era("digital-2003+") == ["PUBLICLAW", "PRIVATELAW"]
    assert sample.classes_for_era("scanned-pre-1951") == sample.CLASSES
    rows = sample.build_sample({132: LISTING_132, 64: LISTING_64}, per_cell=5, max_pages=10000, seed=1)
    digital = {r["granule_class"] for r in rows if r["era"] == "digital-2003+"}
    assert digital == {"PUBLICLAW", "PRIVATELAW"}
    assert "STATUTE-132-Pg5600" not in {r["granule_id"] for r in rows}
    scanned = {r["granule_class"] for r in rows if r["era"] == "scanned-pre-1951"}
    assert "TREATY" in scanned
