"""
Dashboard service for the admin panel.
"""
import os
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List

import psutil

from src.core.logging_config import get_logger
from src.db.repositories.case_repository import CaseRepository
from src.db.repositories.prediction_repository import PredictionRepository

logger = get_logger(__name__)

async def get_system_stats() -> Dict[str, Any]:
    """
    Get system statistics.
    
    Returns:
        A dictionary with system statistics.
    """
    try:
        # CPU usage
        cpu_percent = psutil.cpu_percent(interval=0.5)
        
        # Memory usage
        memory = psutil.virtual_memory()
        memory_percent = memory.percent
        memory_used = memory.used
        memory_total = memory.total
        
        # Disk usage
        disk = psutil.disk_usage("/")
        disk_percent = disk.percent
        disk_used = disk.used
        disk_total = disk.total
        
        # Process info
        process = psutil.Process(os.getpid())
        process_memory = process.memory_info().rss
        process_cpu = process.cpu_percent(interval=0.5)
        process_threads = process.num_threads()
        process_create_time = datetime.fromtimestamp(process.create_time()).isoformat()
        
        # Uptime
        uptime = time.time() - process.create_time()
        uptime_formatted = str(timedelta(seconds=int(uptime)))
        
        return {
            "cpu": {
                "percent": cpu_percent
            },
            "memory": {
                "percent": memory_percent,
                "used": memory_used,
                "total": memory_total
            },
            "disk": {
                "percent": disk_percent,
                "used": disk_used,
                "total": disk_total
            },
            "process": {
                "memory": process_memory,
                "cpu": process_cpu,
                "threads": process_threads,
                "create_time": process_create_time,
                "uptime": uptime_formatted
            }
        }
    except Exception as e:
        logger.error(f"Error getting system stats: {str(e)}")
        return {
            "error": str(e)
        }

async def get_case_stats(case_repo: CaseRepository) -> Dict[str, Any]:
    """
    Get case statistics.
    
    Args:
        case_repo: The case repository.
        
    Returns:
        A dictionary with case statistics.
    """
    try:
        # Get all cases
        cases = case_repo.get_all_cases()
        
        # Count cases
        total_cases = len(cases)
        
        # Count cases by type
        cases_by_type = {}
        for case in cases:
            case_type = case.get("case_type", "Unknown")
            if case_type not in cases_by_type:
                cases_by_type[case_type] = 0
            cases_by_type[case_type] += 1
        
        # Count images and PDFs
        total_images = 0
        total_pdfs = 0
        for case in cases:
            total_images += len(case.get("images", []))
            total_pdfs += len(case.get("pdf", []))
            
            # Count exhibits
            if "exhibits" in case and case["exhibits"]:
                total_images += len(case["exhibits"].get("images", []))
                total_pdfs += len(case["exhibits"].get("pdfs", []))
        
        # Get recent cases
        recent_cases = sorted(
            cases,
            key=lambda x: x.get("created_at", ""),
            reverse=True
        )[:5]
        
        # Format recent cases
        recent_cases_formatted = []
        for case in recent_cases:
            recent_cases_formatted.append({
                "case_id": case.get("case_id", ""),
                "case_name": case.get("case_name", ""),
                "case_type": case.get("case_type", ""),
                "created_at": case.get("created_at", "")
            })
        
        return {
            "total_cases": total_cases,
            "cases_by_type": cases_by_type,
            "total_images": total_images,
            "total_pdfs": total_pdfs,
            "recent_cases": recent_cases_formatted
        }
    except Exception as e:
        logger.error(f"Error getting case stats: {str(e)}")
        return {
            "error": str(e)
        }

async def get_prediction_stats(prediction_repo: PredictionRepository) -> Dict[str, Any]:
    """
    Get prediction statistics.
    
    Args:
        prediction_repo: The prediction repository.
        
    Returns:
        A dictionary with prediction statistics.
    """
    try:
        # Get all predictions
        successful_predictions = prediction_repo.get_successful_predictions()
        failed_predictions = prediction_repo.get_failed_predictions()
        
        # Count predictions
        total_predictions = len(successful_predictions) + len(failed_predictions)
        success_rate = 0
        if total_predictions > 0:
            success_rate = (len(successful_predictions) / total_predictions) * 100
        
        # Count predictions by section
        predictions_by_section = {}
        for prediction in successful_predictions + failed_predictions:
            section = prediction.get("section", "Unknown")
            if section not in predictions_by_section:
                predictions_by_section[section] = {
                    "total": 0,
                    "success": 0,
                    "failure": 0
                }
            
            predictions_by_section[section]["total"] += 1
            
            if prediction.get("status", "") == "success":
                predictions_by_section[section]["success"] += 1
            else:
                predictions_by_section[section]["failure"] += 1
        
        # Calculate average processing time
        total_processing_time = 0
        for prediction in successful_predictions:
            total_processing_time += prediction.get("processing_time", 0)
        
        average_processing_time = 0
        if successful_predictions:
            average_processing_time = total_processing_time / len(successful_predictions)
        
        # Get recent predictions
        all_predictions = successful_predictions + failed_predictions
        recent_predictions = sorted(
            all_predictions,
            key=lambda x: x.get("created_at", ""),
            reverse=True
        )[:5]
        
        # Format recent predictions
        recent_predictions_formatted = []
        for prediction in recent_predictions:
            recent_predictions_formatted.append({
                "case_id": prediction.get("case_id", ""),
                "section": prediction.get("section", ""),
                "status": prediction.get("status", ""),
                "processing_time": prediction.get("processing_time", 0),
                "created_at": prediction.get("created_at", "")
            })
        
        return {
            "total_predictions": total_predictions,
            "successful_predictions": len(successful_predictions),
            "failed_predictions": len(failed_predictions),
            "success_rate": success_rate,
            "predictions_by_section": predictions_by_section,
            "average_processing_time": average_processing_time,
            "recent_predictions": recent_predictions_formatted
        }
    except Exception as e:
        logger.error(f"Error getting prediction stats: {str(e)}")
        return {
            "error": str(e)
        }
