#!/usr/bin/env python
"""
Script for running batch inference on multiple cases.
"""
import argparse
import asyncio
import json
import os
import sys
import time
from typing import List, Dict, Any

# Add the parent directory to the path so we can import the src module
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.logging_config import get_logger
from src.db.repositories.case_repository import CaseRepository
from src.inference.pipeline import InferencePipeline

logger = get_logger(__name__)

async def process_case(case_id: str, sections: List[str], case_type: str = None) -> Dict[str, Any]:
    """
    Process a single case with multiple sections.
    
    Args:
        case_id: The case ID.
        sections: The sections to process.
        case_type: The case type.
        
    Returns:
        A dictionary with the results.
    """
    logger.info(f"Processing case {case_id} with sections {sections}")
    
    # Get case type if not provided
    if not case_type:
        case_repo = CaseRepository()
        case = case_repo.get_by_case_id(case_id)
        if not case:
            logger.error(f"Case {case_id} not found")
            return {"case_id": case_id, "error": "Case not found"}
        
        case_type = case.get("case_type", "case_type_1")
    
    # Create inference pipeline
    pipeline = InferencePipeline(case_id, case_type)
    
    # Process each section
    results = {}
    for section in sections:
        try:
            logger.info(f"Processing section {section} for case {case_id}")
            start_time = time.time()
            
            result = await pipeline.process(section)
            
            processing_time = time.time() - start_time
            logger.info(f"Processed section {section} for case {case_id} in {processing_time:.2f} seconds")
            
            results[section] = {
                "status": "success" if "error" not in result else "error",
                "processing_time": processing_time,
                "error": result.get("error")
            }
        except Exception as e:
            logger.error(f"Error processing section {section} for case {case_id}: {str(e)}")
            results[section] = {
                "status": "error",
                "error": str(e)
            }
    
    return {"case_id": case_id, "results": results}

async def process_cases(cases: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Process multiple cases.
    
    Args:
        cases: A list of cases to process.
        
    Returns:
        A list of results.
    """
    tasks = []
    for case in cases:
        case_id = case["case_id"]
        sections = case["sections"]
        case_type = case.get("case_type")
        
        task = asyncio.create_task(process_case(case_id, sections, case_type))
        tasks.append(task)
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Handle exceptions
    processed_results = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            logger.error(f"Error processing case {cases[i]['case_id']}: {str(result)}")
            processed_results.append({
                "case_id": cases[i]["case_id"],
                "error": str(result)
            })
        else:
            processed_results.append(result)
    
    return processed_results

def main():
    """
    Main function.
    """
    parser = argparse.ArgumentParser(description="Run batch inference on multiple cases")
    parser.add_argument("--input", "-i", required=True, help="Input JSON file with cases to process")
    parser.add_argument("--output", "-o", required=True, help="Output JSON file for results")
    
    args = parser.parse_args()
    
    # Load input file
    try:
        with open(args.input, "r") as f:
            cases = json.load(f)
    except Exception as e:
        logger.error(f"Error loading input file: {str(e)}")
        sys.exit(1)
    
    # Process cases
    try:
        results = asyncio.run(process_cases(cases))
    except Exception as e:
        logger.error(f"Error processing cases: {str(e)}")
        sys.exit(1)
    
    # Save results
    try:
        with open(args.output, "w") as f:
            json.dump(results, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving results: {str(e)}")
        sys.exit(1)
    
    logger.info(f"Processed {len(cases)} cases. Results saved to {args.output}")

if __name__ == "__main__":
    main()
