import os
import json
import logging
from pathlib import Path
from docling.document_converter import DocumentConverter

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def convert_pdf_to_doclang(pdf_path, out_json_path):
    logger.info(f"Converting {pdf_path} to DocLang...")
    converter = DocumentConverter()
    result = converter.convert(pdf_path)
    
    # Export DoclingDocument (DocLang) to dict
    doc_dict = result.document.export_to_dict()
    
    with open(out_json_path, 'w', encoding='utf-8') as f:
        json.dump(doc_dict, f, indent=2)
        
    logger.info(f"Saved DocLang to {out_json_path}")
    return result.document

if __name__ == "__main__":
    # Test convert
    os.makedirs("data/doclang", exist_ok=True)
    pdfs = list(Path("data/pdfs").glob("*.pdf"))
    if pdfs:
        test_pdf = pdfs[0]
        out_path = f"data/doclang/{test_pdf.stem}.json"
        convert_pdf_to_doclang(test_pdf, out_path)
