import os
import httpx
import logging
import json
from huggingface_hub import HfApi, create_repo

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from .config import govinfo_api_key

API_KEY = govinfo_api_key()  # raises MissingEnv when unset; no default
BASE_URL = "https://api.govinfo.gov"
HISTORICAL_DIR = "data/historical"

def fetch_package_summary(package_id):
    url = f"{BASE_URL}/packages/{package_id}/summary"
    params = {"api_key": API_KEY}
    response = httpx.get(url, params=params, timeout=10)
    if response.status_code == 404:
        return None
    response.raise_for_status()
    return response.json()

def download_file(url, out_path):
    if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
        logger.info(f"Skipping download, {out_path} already exists.")
        return True

    params = {"api_key": API_KEY}
    try:
        with httpx.stream("GET", url, params=params, timeout=120, follow_redirects=True) as response:
            response.raise_for_status()
            with open(out_path, "wb") as f:
                for chunk in response.iter_bytes(chunk_size=8192):
                    f.write(chunk)
        return True
    except Exception as e:
        logger.error(f"Failed to download from {url}: {e}")
        return False

def append_hf_metadata(metadata_path, pdf_file, vol):
    metadata = {
        "file_name": f"pdfs/{pdf_file}",
        "volume": vol,
        "collection": "STATUTE",
        "source": "GovInfo"
    }
    with open(metadata_path, "a") as f:
        f.write(json.dumps(metadata) + "\n")

def download_historical_statutes():
    """
    Downloads all historical bound volumes of the Statutes at Large.
    If HF_TOKEN is provided, it streams them directly to HuggingFace 
    by uploading and then immediately deleting the local file to save storage.
    """
    os.makedirs(f"{HISTORICAL_DIR}/pdfs", exist_ok=True)
    os.makedirs(f"{HISTORICAL_DIR}/xmls", exist_ok=True)
    
    hf_token = os.getenv("HF_TOKEN")
    repo_id = os.getenv("HF_REPO_ID", "your-username/us-statutes-at-large")
    metadata_path = f"{HISTORICAL_DIR}/metadata.jsonl"
    
    api = None
    if hf_token:
        logger.info(f"HF_TOKEN found. Will push directly to {repo_id} and clean up local storage.")
        api = HfApi(token=hf_token)
        create_repo(repo_id=repo_id, repo_type="dataset", exist_ok=True)
        # Ensure metadata file is initialized on Hub
        if not os.path.exists(metadata_path):
            open(metadata_path, 'w').close()
    
    vol = 1
    consecutive_404s = 0
    
    while True:
        pkg_id = f"STATUTE-{vol}"
        
        try:
            summary = fetch_package_summary(pkg_id)
        except Exception as e:
            logger.warning(f"Error fetching {pkg_id}: {e}")
            break
            
        if summary is None:
            logger.info(f"{pkg_id} not found.")
            consecutive_404s += 1
            if consecutive_404s >= 5:
                logger.info("Hit 5 consecutive 404s. Assuming end of collection.")
                break
            vol += 1
            continue
            
        consecutive_404s = 0
        
        pdf_link = summary.get("download", {}).get("pdfLink")
        xml_link = summary.get("download", {}).get("uslmLink")
        
        pdf_filename = f"{pkg_id}.pdf"
        pdf_path = f"{HISTORICAL_DIR}/pdfs/{pdf_filename}"
        
        if pdf_link:
            logger.info(f"Downloading PDF for {pkg_id}...")
            if download_file(pdf_link, pdf_path):
                # If uploading to HuggingFace, push the file and update metadata
                if api:
                    logger.info(f"Uploading {pdf_filename} to HuggingFace...")
                    try:
                        api.upload_file(
                            path_or_fileobj=pdf_path,
                            path_in_repo=f"pdfs/{pdf_filename}",
                            repo_id=repo_id,
                            repo_type="dataset"
                        )
                        append_hf_metadata(metadata_path, pdf_filename, vol)
                        
                        # Upload updated metadata.jsonl
                        api.upload_file(
                            path_or_fileobj=metadata_path,
                            path_in_repo="metadata.jsonl",
                            repo_id=repo_id,
                            repo_type="dataset"
                        )
                        
                        # Delete local PDF to save disk space
                        os.remove(pdf_path)
                        logger.info(f"Uploaded and deleted local copy of {pdf_filename}")
                    except Exception as e:
                        logger.error(f"Failed to upload {pdf_filename} to HuggingFace: {e}")
                
        if xml_link:
            xml_filename = f"{pkg_id}.xml"
            xml_path = f"{HISTORICAL_DIR}/xmls/{xml_filename}"
            logger.info(f"Downloading USLM XML for {pkg_id}...")
            if download_file(xml_link, xml_path):
                if api:
                    try:
                        api.upload_file(
                            path_or_fileobj=xml_path,
                            path_in_repo=f"xmls/{xml_filename}",
                            repo_id=repo_id,
                            repo_type="dataset"
                        )
                        os.remove(xml_path)
                    except Exception as e:
                        logger.error(f"Failed to upload XML to HuggingFace: {e}")
                        
        vol += 1

if __name__ == "__main__":
    download_historical_statutes()
