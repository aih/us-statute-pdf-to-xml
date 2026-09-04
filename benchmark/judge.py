import os
import logging
from anthropic import Anthropic

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def evaluate_conversion(ground_truth_xml, generated_xml):
    """
    Uses Anthropic Claude Opus to judge the conversion quality.
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        logger.warning("No ANTHROPIC_API_KEY found. Returning mock score.")
        return 85.5, "Mock evaluation due to missing API key."
        
    client = Anthropic(api_key=api_key)
    
    prompt = f"""
    You are an expert at evaluating OCR and PDF-to-XML conversion pipelines. 
    Compare the following GROUND TRUTH XML natively published by GovInfo with the GENERATED XML from our pipeline.
    
    Focus on:
    1. Text accuracy (no loss or distortion in text).
    2. Layout and structure preservation.
    3. Semantic tagging fidelity.
    
    GROUND TRUTH XML:
    ```xml
    {ground_truth_xml}
    ```
    
    GENERATED XML:
    ```xml
    {generated_xml}
    ```
    
    Provide an evaluation summary and a final integer score between 0 and 100 on the last line like:
    SCORE: 95
    """
    
    try:
        response = client.messages.create(
            model="claude-3-opus-20240229",
            max_tokens=1000,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        
        reply = response.content[0].text
        
        # Parse score
        score = 0
        for line in reply.split('\n'):
            if "SCORE:" in line:
                try:
                    score = int(line.split(":")[1].strip())
                except:
                    pass
                    
        return score, reply
    except Exception as e:
        logger.error(f"Error calling Anthropic API: {e}")
        return 0, str(e)
