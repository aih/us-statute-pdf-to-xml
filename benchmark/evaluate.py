import os
import logging
from pathlib import Path
from pipeline.convert import convert_pdf_to_doclang
from pipeline.transform import doclang_to_uslm
from benchmark.judge import evaluate_conversion

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_benchmark():
    pdfs = list(Path("data/pdfs").glob("*.pdf"))
    logger.info(f"Starting benchmark on {len(pdfs)} PDFs.")
    
    os.makedirs("data/doclang", exist_ok=True)
    os.makedirs("data/generated_xmls", exist_ok=True)
    
    total_score = 0
    evaluated = 0
    
    for pdf_path in pdfs:
        gran_id = pdf_path.stem
        ground_truth_path = Path(f"data/xmls/{gran_id}.xml")
        
        if not ground_truth_path.exists():
            logger.warning(f"No ground truth XML for {gran_id}, skipping.")
            continue
            
        doclang_path = f"data/doclang/{gran_id}.json"
        generated_xml_path = f"data/generated_xmls/{gran_id}.xml"
        
        try:
            # 1. Convert PDF to DocLang
            convert_pdf_to_doclang(str(pdf_path), doclang_path)
            
            # 2. Transform DocLang to USLM XML
            doclang_to_uslm(doclang_path, generated_xml_path)
            
            # 3. Evaluate
            with open(ground_truth_path, 'r', encoding='utf-8') as f:
                gt_xml = f.read()
            with open(generated_xml_path, 'r', encoding='utf-8') as f:
                gen_xml = f.read()
                
            score, details = evaluate_conversion(gt_xml, gen_xml)
            logger.info(f"Score for {gran_id}: {score}")
            
            # TODO: Store results in DB benchmark table
            
            total_score += score
            evaluated += 1
            
        except Exception as e:
            logger.error(f"Error benchmarking {gran_id}: {e}")
            
    if evaluated > 0:
        avg_score = total_score / evaluated
        logger.info(f"--- Benchmark Complete ---")
        logger.info(f"Total evaluated: {evaluated}")
        logger.info(f"Average Score: {avg_score:.2f}")
    else:
        logger.info("No documents evaluated.")

if __name__ == "__main__":
    run_benchmark()
