import os
import httpx
import logging
from pathlib import Path
from .db import insert_statute

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

API_KEY = os.getenv("GOVINFO_API_KEY", "861dPygDW6DkZBGEWA10SbjRcHdbQxgBxyJ7ikHt")
BASE_URL = "https://api.govinfo.gov"

def fetch_package_summary(package_id):
    url = f"{BASE_URL}/packages/{package_id}/summary"
    params = {"api_key": API_KEY}
    response = httpx.get(url, params=params, timeout=10)
    if response.status_code == 404:
        return None
    response.raise_for_status()
    return response.json()

def download_file(url, out_path):
    # Idempotent: don't download if it already exists and is non-empty
    if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
        logger.info(f"Skipping download, {out_path} already exists.")
        return

    params = {"api_key": API_KEY}
    response = httpx.get(url, params=params, timeout=60, follow_redirects=True)
    response.raise_for_status()
    with open(out_path, "wb") as f:
        f.write(response.content)

def process_recent_statutes(limit=10):
    """Fetch recent post-2012 statutes for benchmark testing."""
    os.makedirs("data/pdfs", exist_ok=True)
    os.makedirs("data/xmls", exist_ok=True)
    
    # We iterate over Congress numbers starting from 113 (which is 2013, post-2012).
    # For each Congress, we iterate through Public Law numbers starting from 1.
    
    processed = 0
    congress = 113
    
    while processed < limit:
        law_number = 1
        consecutive_404s = 0
        
        while processed < limit:
            pkg_id = f"PLAW-{congress}publ{law_number}"
            
            try:
                summary = fetch_package_summary(pkg_id)
            except Exception as e:
                logger.warning(f"Error fetching {pkg_id}: {e}")
                break
                
            if summary is None:
                consecutive_404s += 1
                if consecutive_404s >= 3:
                    # If we hit 3 consecutive 404s, assume we've reached the end of this Congress
                    break
                law_number += 1
                continue
            
            consecutive_404s = 0
            title = summary.get("title", "")
            
            pdf_link = summary.get("download", {}).get("pdfLink")
            # USLM is the native XML format on GovInfo
            xml_link = summary.get("download", {}).get("uslmLink")
            
            if not pdf_link or not xml_link:
                logger.info(f"Skipping {pkg_id} because it lacks PDF or USLM XML.")
                law_number += 1
                continue
                
            pl_number = f"{congress}-{law_number}"
            date_enacted = summary.get("dateIssued")
            
            # The API doesn't always provide volume or pages easily at the package level for PLAW
            vol = None
            start_page = None
            end_page = None
            
            pdf_path = f"data/pdfs/{pkg_id}.pdf"
            xml_path = f"data/xmls/{pkg_id}.xml"
            
            logger.info(f"Downloading files for {pkg_id}...")
            try:
                download_file(pdf_link, pdf_path)
                download_file(xml_link, xml_path)
            except Exception as e:
                logger.error(f"Failed to download files for {pkg_id}: {e}")
                law_number += 1
                continue
                
            # insert_statute is idempotent (ON CONFLICT DO NOTHING)
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
            law_number += 1
            
        congress += 1

if __name__ == "__main__":
    process_recent_statutes(5)
