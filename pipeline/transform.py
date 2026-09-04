import os
import json
import logging
from pathlib import Path
import xml.etree.ElementTree as ET

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def doclang_to_uslm(doclang_path, out_xml_path):
    logger.info(f"Transforming {doclang_path} to USLM XML...")
    with open(doclang_path, 'r') as f:
        data = json.load(f)
        
    # Create root element based on USLM
    root = ET.Element("law", xmlns="http://xml.house.gov/schemas/uslm/1.0")
    main = ET.SubElement(root, "main")
    
    # Extract text from DocLang items
    # docling stores text items in 'texts' array or 'body'
    texts = data.get('texts', [])
    for text_obj in texts:
        text_content = text_obj.get('text', '')
        # Simple paragraph wrapper
        p = ET.SubElement(main, "p")
        p.text = text_content
        
    tree = ET.ElementTree(root)
    tree.write(out_xml_path, encoding="utf-8", xml_declaration=True)
    logger.info(f"Saved USLM XML to {out_xml_path}")

if __name__ == "__main__":
    # Test transform
    os.makedirs("data/generated_xmls", exist_ok=True)
    jsons = list(Path("data/doclang").glob("*.json"))
    if jsons:
        test_json = jsons[0]
        out_path = f"data/generated_xmls/{test_json.stem}.xml"
        doclang_to_uslm(test_json, out_path)
