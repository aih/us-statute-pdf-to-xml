import os
import json
import logging
from huggingface_hub import HfApi, create_repo

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

HISTORICAL_DIR = "data/historical"

def package_for_huggingface(repo_id="us-statutes-at-large-pdfs"):
    """
    Packages the downloaded historical PDFs into a HuggingFace dataset.
    This generates a metadata.jsonl file so the HuggingFace Hub can index the PDFs.
    If HF_TOKEN is present in the environment, it will push the dataset to the Hub.
    """
    pdfs_dir = os.path.join(HISTORICAL_DIR, "pdfs")
    
    if not os.path.exists(pdfs_dir):
        logger.error("No historical PDFs found. Run fetch_historical.py first.")
        return
        
    pdf_files = sorted([f for f in os.listdir(pdfs_dir) if f.endswith(".pdf")])
    
    if not pdf_files:
        logger.error("No PDF files found in the directory.")
        return
        
    metadata_path = os.path.join(HISTORICAL_DIR, "metadata.jsonl")
    
    logger.info(f"Generating {metadata_path} for {len(pdf_files)} volumes...")
    
    with open(metadata_path, "w") as f:
        for pdf_file in pdf_files:
            # Extract volume number from filename (e.g., STATUTE-1.pdf -> 1)
            vol_str = pdf_file.replace("STATUTE-", "").replace(".pdf", "")
            try:
                volume = int(vol_str)
            except ValueError:
                volume = None
                
            metadata = {
                "file_name": f"pdfs/{pdf_file}",
                "volume": volume,
                "collection": "STATUTE",
                "source": "GovInfo"
            }
            f.write(json.dumps(metadata) + "\n")
            
    logger.info("Local packaging complete. The dataset is structured in data/historical/")
    
    hf_token = os.getenv("HF_TOKEN")
    if hf_token:
        logger.info(f"HF_TOKEN found. Pushing dataset to HuggingFace Hub: {repo_id}...")
        api = HfApi(token=hf_token)
        try:
            create_repo(repo_id=repo_id, repo_type="dataset", exist_ok=True)
            api.upload_folder(
                folder_path=HISTORICAL_DIR,
                repo_id=repo_id,
                repo_type="dataset",
            )
            logger.info("Successfully pushed dataset to HuggingFace Hub!")
        except Exception as e:
            logger.error(f"Failed to push to HuggingFace Hub: {e}")
    else:
        logger.info("No HF_TOKEN found in environment. Skipping upload to HuggingFace Hub.")
        logger.info("To upload manually, install huggingface_hub and run: huggingface-cli upload [repo_id] data/historical --repo-type dataset")

if __name__ == "__main__":
    # You can customize the repo_id by changing the parameter below
    # Make sure to include your username if pushing to your personal account: 'username/repo_name'
    hf_repo_name = os.getenv("HF_REPO_ID", "your-username/us-statutes-at-large")
    package_for_huggingface(hf_repo_name)
