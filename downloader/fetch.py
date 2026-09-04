import os
import httpx
import logging
from pathlib import Path
from pypdf import PdfReader, PdfWriter
from .db import insert_statute

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

API_KEY = os.getenv("GOVINFO_API_KEY", "861dPygDW6DkZBGEWA10SbjRcHdbQxgBxyJ7ikHt")
BASE_URL = "https://api.govinfo.gov"

def fetch_packages(collection="STATUTE", offset=0, page_size=100):
    url = f"{BASE_URL}/packages"
    params = {
        "collection": collection,
        "offset": offset,
        "pageSize": page_size,
        "api_key": API_KEY
    }
    response = httpx.get(url, params=params, timeout=30)
    response.raise_for_status()
    return response.json()

def fetch_granules(package_id, offset=0, page_size=100):
    url = f"{BASE_URL}/packages/{package_id}/granules"
    params = {
        "offset": offset,
        "pageSize": page_size,
        "api_key": API_KEY
    }
    response = httpx.get(url, params=params, timeout=30)
    response.raise_for_status()
    return response.json()

def fetch_granule_summary(package_id, granule_id):
    url = f"{BASE_URL}/packages/{package_id}/granules/{granule_id}/summary"
    params = {"api_key": API_KEY}
    response = httpx.get(url, params=params, timeout=30)
    response.raise_for_status()
    return response.json()

def download_file(url, out_path):
    params = {"api_key": API_KEY}
    response = httpx.get(url, params=params, timeout=60, follow_redirects=True)
    response.raise_for_status()
    with open(out_path, "wb") as f:
        f.write(response.content)

def process_recent_statutes(limit=10):
    """Fetch recent post-2012 statutes for benchmark testing."""
    os.makedirs("data/pdfs", exist_ok=True)
    os.makedirs("data/xmls", exist_ok=True)
    
    # Let's fetch packages starting from 2013 (which is STATUTE-127 and onwards)
    # Since we can't easily filter by date in the list packages, we will fetch and filter
    packages_data = fetch_packages(page_size=100)
    packages = packages_data.get("packages", [])
    
    processed = 0
    for pkg in packages:
        pkg_id = pkg["packageId"]
        # STATUTE-127 is 2013. Post 2012 means we can look at STATUTE-127, STATUTE-128 etc.
        try:
            vol = int(pkg_id.replace("STATUTE-", ""))
            if vol < 127:
                continue
        except:
            continue
            
        logger.info(f"Processing package {pkg_id}")
        granules_data = fetch_granules(pkg_id)
        granules = granules_data.get("granules", [])
        
        for gran in granules:
            if processed >= limit:
                return
                
            gran_id = gran["granuleId"]
            summary = fetch_granule_summary(pkg_id, gran_id)
            
            # We want Public Laws
            title = summary.get("title", "")
            if "Public Law" not in title:
                continue
                
            pl_number = None
            law_number = None
            congress = None
            
            # Extract PL number from title or metadata
            # usually title is "Public Law 113-1 - ..."
            try:
                parts = title.split(" ")
                pl_number = parts[2]
                congress, law_number = map(int, pl_number.split("-"))
            except:
                pl_number = gran_id # fallback
            
            date_enacted = summary.get("dateIssued")
            start_page = None # Can extract from pg metadata if needed
            end_page = None
            
            pdf_link = summary.get("download", {}).get("pdfLink")
            xml_link = summary.get("download", {}).get("xmlLink")
            
            if not pdf_link or not xml_link:
                continue # Skip if no XML for ground truth
                
            pdf_path = f"data/pdfs/{gran_id}.pdf"
            xml_path = f"data/xmls/{gran_id}.xml"
            
            logger.info(f"Downloading {gran_id}")
            download_file(pdf_link, pdf_path)
            download_file(xml_link, xml_path)
            
            insert_statute(
                pl_number=pl_number,
                congress=congress,
                law_number=law_number,
                title=title,
                date_enacted=date_enacted,
                volume=vol,
                start_page=start_page,
                end_page=end_page,
                pdf_path=pdf_path
            )
            processed += 1

if __name__ == "__main__":
    process_recent_statutes(5)
