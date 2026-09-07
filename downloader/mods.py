"""Parse GovInfo MODS records for STATUTE granules."""

from __future__ import annotations

import re
from typing import Optional

from lxml import etree

MODS_NS = {"m": "http://www.loc.gov/mods/v3"}


def _int_or_none(value) -> Optional[int]:
    if value in (None, ""):
        return None
    try:
        return int(str(value).strip())
    except ValueError:
        return None


def page_label_to_int(label: str) -> Optional[int]:
    """'371' -> 371; 'B3' -> None (lettered pages in part B of a volume)."""
    return _int_or_none(label) if re.fullmatch(r"\d+", (label or "").strip()) else None


def parse_mods(xml: bytes | str) -> dict:
    """Return granule metadata from a MODS document.

    Keys: granule_id, granule_class, title, number, congress, session, volume, page_start_label,
    page_end_label, page_start, page_end, page_range, total_pages, citation, granule_date,
    is_private, is_appropriation, chapter, bill, part_number, pdf_url.
    """
    if isinstance(xml, str):
        xml = xml.encode("utf-8")
    root = etree.fromstring(xml)

    def text(xpath: str) -> str:
        return root.xpath(f"string({xpath})", namespaces=MODS_NS).strip()

    start = text("//m:part[@type='article']/m:extent[@unit='pages']/m:start")
    end = text("//m:part[@type='article']/m:extent[@unit='pages']/m:end")
    page_range = text("//m:extension/m:statuteAtLarge/m:pages/@pages") or (f"{start}-{end}" if start else "")
    law = root.xpath("//m:extension/m:law", namespaces=MODS_NS)
    bill = root.xpath("//m:extension/m:bill", namespaces=MODS_NS)
    return {
        "granule_id": text("//m:extension/m:accessId") or (root.get("ID") or "").removeprefix("id-"),
        "granule_class": text("//m:extension/m:granuleClass") or None,
        "title": text("//m:titleInfo/m:title") or None,
        "number": text("//m:extension/m:number") or None,
        "congress": _int_or_none(text("//m:extension/m:congress")),
        "session": _int_or_none(text("//m:extension/m:session")),
        "volume": _int_or_none(text("//m:extension/m:volume")),
        "page_start_label": start or None,
        "page_end_label": end or None,
        "page_start": page_label_to_int(start),
        "page_end": page_label_to_int(end),
        "page_range": page_range or None,
        "total_pages": _int_or_none(text("//m:extension/m:totalPages")),
        "citation": text("//m:identifier[@type='preferred citation']") or None,
        "granule_date": text("//m:extension/m:granuleDate") or None,
        "is_private": (law[0].get("isPrivate") == "true") if law else None,
        "is_appropriation": text("//m:extension/m:isAppropriation") == "true",
        "chapter": text("//m:extension/m:chapter") or None,
        "bill": (
            {"type": bill[0].get("type"), "number": bill[0].get("number"), "congress": bill[0].get("congress")}
            if bill else None
        ),
        "part_number": _int_or_none(text("//m:extension/m:partNumber")),
        "pdf_url": text("//m:location/m:url[@displayLabel='PDF rendition']") or None,
    }
