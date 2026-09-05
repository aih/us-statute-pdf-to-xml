from pathlib import Path

from lxml import etree

from benchmark import metrics

USLM = "http://schemas.gpo.gov/xml/uslm"
FIXTURES = Path(__file__).parent / "fixtures"


def doc(body: str) -> etree._Element:
    return etree.fromstring(f'<pLaw xmlns="{USLM}"><meta><title>x</title></meta><main>{body}</main></pLaw>'.encode())


def test_normalize_joins_hyphenation_and_unifies_quotes():
    assert metrics.normalize("the Secre-\n tary of “Commerce”—now") == 'the Secretary of "Commerce"-now'
    assert metrics.normalize("a ,  b .") == "a, b."
    assert metrics.normalize("soft­hyphen") == "softhyphen"


def test_body_text_excludes_meta_sidenotes_notes_pages():
    root = doc('<section><num>1.</num><heading>H</heading><content>Body <sidenote><p>margin</p></sidenote>text.'
               '<page identifier="/us/stat/64/3">64 STAT. 3</page> More.</content><note><p>fn</p></note></section>')
    assert metrics.body_text(root) == "1. H Body text. More."


def test_cer_wer():
    assert metrics.cer("abcd", "abcd") == 0.0
    assert metrics.cer("abcd", "abxd") == 0.25
    assert metrics.wer("the quick brown fox", "the quick brown fix") == 0.25
    assert metrics.cer("", "") == 0.0 and metrics.cer("", "x") == 1.0


def test_identifiers_and_overlap():
    root = doc('<section identifier="/us/pl/1/2/s1"><subsection identifier="/us/pl/1/2/s1/a"/></section>'
               '<page identifier="/us/stat/64/3"/>')
    ids, pages = metrics.identifiers(root)
    assert ids == {"/us/pl/1/2/s1", "/us/pl/1/2/s1/a"} and pages == {"/us/stat/64/3"}
    o = metrics.overlap({"a", "b", "c"}, {"a", "b", "d"})
    assert (o["precision"], o["recall"], o["matched"]) == (0.6667, 0.6667, 2)
    assert metrics.overlap(set(), set())["f1"] == 1.0


def test_compare_and_alignment():
    ref = doc('<section identifier="/us/pl/1/2/s1"><content>The Secretary shall report annually to Congress.</content></section>')
    hyp = doc('<section identifier="/us/pl/1/2/s1"><content>The Secretary shal report annually to Congress</content></section>')
    c = metrics.compare(ref, hyp)
    assert 0 < c.cer < 0.1 and 0 < c.wer < 0.5
    assert c.identifier_overlap["f1"] == 1.0
    assert c.structure_reference["section"] == 1 == c.structure_generated["section"]
    ops = {d["op"] for d in c.diffs}
    assert ops <= {"replace", "delete", "insert"} and c.diffs
    d = c.as_dict()
    assert set(d) >= {"cer", "wer", "structure_reference", "identifier_overlap", "diffs", "equal_ratio"}


def test_compare_real_plaw_against_itself():
    path = FIXTURES / "PLAW-114publ176.uslm.xml"
    c = metrics.compare(path, path)
    assert c.cer == 0.0 and c.wer == 0.0 and c.identifier_overlap["f1"] == 1.0 and c.diffs == []
    assert c.structure_reference["section"] == 1 and c.structure_reference["subsection"] == 2
