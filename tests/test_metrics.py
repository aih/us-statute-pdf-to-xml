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


REF_TEXT = ("Be it enacted by the Senate and House of Representatives of the United States of America in Congress "
            "assembled, That the Secretary of the Interior is authorized to acquire the lands described in section 2 "
            "and to hold them in trust for the Grand Portage Band of Chippewa Indians. Approved September 2, 1958.")
PREVIOUS = "of this Act. Approved September 1, 1958. Public Law 85-909 AN ACT To amend the Rural Electrification Act."
NEXT = "Public Law 85-911 AN ACT To provide for the disposition of certain lands. Be it enacted by the Senate that"


def test_f3_clip_scores_only_the_granule_span():
    """Reproduction of F3: the generated text carries the neighbouring laws; unclipped CER is inflated."""
    hyp = f"{PREVIOUS} {REF_TEXT.replace('authorized', 'authorised')} {NEXT}"
    assert metrics.cer(REF_TEXT, hyp) > 0.5
    clip = metrics.clip_to_reference(REF_TEXT, hyp)
    assert clip.found == "both" and clip.head_score >= 70 and clip.tail_score >= 70
    assert clip.text.startswith("Be it enacted") and clip.text.endswith("Approved September 2, 1958.")
    assert metrics.cer(REF_TEXT, clip.text) < 0.01
    ref = doc(f"<section><content>{REF_TEXT}</content></section>")
    gen = doc(f"<p>{PREVIOUS}</p><section><content>{REF_TEXT}</content></section><p>{NEXT}</p>")
    c = metrics.compare(ref, gen)
    assert c.cer == 0.0 and c.cer_unclipped > 0.5 and c.hyp_chars < c.hyp_chars_unclipped
    assert c.as_dict()["clip_found"] == "both"
    assert metrics.compare(ref, gen, clip=False).cer > 0.5


def test_clip_records_missing_anchors_and_scores_unclipped():
    hyp = f"{PREVIOUS} {REF_TEXT[:120]} completely different ending words here and there."
    clip = metrics.clip_to_reference(REF_TEXT, hyp)
    assert clip.found == "head" and clip.end == len(hyp)
    assert clip.text.startswith("Be it enacted")
    none = metrics.clip_to_reference(REF_TEXT, "nothing in common at all")
    assert none.found == "none" and none.text == "nothing in common at all"
    assert metrics.clip_to_reference("", "x").found == "none"
    short = metrics.clip_to_reference("one two", "zero one two three")
    assert short.text.startswith("one")


def test_section_match_and_sidenote_recall():
    ref = doc('<section><num value="1">SEC. 1.</num><content>The Secretary shall report annually to Congress.</content></section>'
              '<section><num value="2">SEC. 2.</num><content>This Act takes effect on enactment.</content></section>'
              '<sidenote><p>Report to Congress.</p></sidenote><sidenote><p>Effective date.</p></sidenote>')
    gen = doc('<section><num value="1">SEC. 1.</num><content>The Secretary shal report anually to Congress.</content></section>'
              '<section><num value="3">SEC. 3.</num><content>Something else entirely.</content></section>'
              '<sidenote><p>Report to Congres.</p></sidenote>')
    m = metrics.section_match(ref, gen)
    assert (m["matched"], m["reference"], m["hypothesis"]) == (1, 2, 2) and m["recall"] == 0.5 and m["precision"] == 0.5
    r = metrics.sidenote_recall(ref, gen)
    assert (r["matched"], r["reference"]) == (1, 2) and r["recall"] == 0.5
    assert metrics.section_match(doc(""), doc(""))["recall"] == 1.0
    c = metrics.compare(ref, gen)
    assert c.as_dict()["section_match"]["recall"] == 0.5 and c.as_dict()["sidenote_recall"]["recall"] == 0.5


def test_clip_prefers_the_nearest_repeated_ending():
    """Four private laws on one page all end with the same approval line; the span stops at the first."""
    law = "An Act for the Relief of {name}. Be it enacted by the Senate, That the Secretary shall pay {name} the sum due. Approved, March 3, 1853."
    ref = law.format(name="Robert Gibson")
    hyp = " ".join(law.format(name=n) for n in ("Asa Leach", "Robert Gibson", "Thomas Parsons", "John Smith"))
    clip = metrics.clip_to_reference(ref, hyp)
    assert clip.found == "both" and clip.text == ref
    assert metrics.cer(ref, clip.text) == 0.0
