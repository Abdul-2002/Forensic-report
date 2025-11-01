"""
Report endpoints for the API.
This module provides compatibility for frontend requests to /app/v1/Reports/* endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Response
from typing import List, Dict, Any, Optional

from src.core.logging_config import get_logger
from src.db.repositories.case_repository import CaseRepository
from src.api.dependencies import get_case_repository
from src.routers.report_routes import (
    save_report as original_save_report,
    get_reports as original_get_reports,
    upload_final_report as original_upload_final_report,
    get_case_reports as original_get_case_reports,
    delete_report as original_delete_report,
    download_report as original_download_report,
    download_final_report as original_download_final_report
)

logger = get_logger(__name__)

router = APIRouter(prefix="/Reports", tags=["reports"])

@router.post("/save-report", status_code=status.HTTP_201_CREATED)
async def save_report_compat(
    case_id: str = Form(...),
    case_name: str = Form(...),
    report_content: str = Form(...),
    report_file: UploadFile = File(...)
):
    """
    Save generated report to Azure.
    This is a compatibility endpoint for frontend requests to /app/v1/Reports/save-report.
    """
    logger.info("Handling request to compatibility endpoint /app/v1/Reports/save-report")
    return await original_save_report(
        case_id=case_id,
        case_name=case_name,
        report_content=report_content,
        report_file=report_file
    )

@router.get("/reports")
async def get_reports_compat():
    """
    Get all reports.
    This is a compatibility endpoint for frontend requests to /app/v1/Reports/reports.
    """
    logger.info("Handling request to compatibility endpoint /app/v1/Reports/reports")
    return await original_get_reports()

@router.post("/upload-final-report/{report_id}", status_code=status.HTTP_200_OK)
async def upload_final_report_compat(
    report_id: str,
    final_report: UploadFile = File(...)
):
    """
    Upload final report to Azure.
    This is a compatibility endpoint for frontend requests to /app/v1/Reports/upload-final-report/{report_id}.
    """
    logger.info(f"Handling request to compatibility endpoint /app/v1/Reports/upload-final-report/{report_id}")
    return await original_upload_final_report(
        report_id=report_id,
        final_report=final_report
    )

@router.get("/reports/{case_id}")
async def get_case_reports_compat(case_id: str):
    """
    Get reports for a specific case.
    This is a compatibility endpoint for frontend requests to /app/v1/Reports/reports/{case_id}.
    """
    logger.info(f"Handling request to compatibility endpoint /app/v1/Reports/reports/{case_id}")
    return await original_get_case_reports(case_id=case_id)

@router.delete("/reports/{report_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_report_compat(report_id: str):
    """
    Delete a report.
    This is a compatibility endpoint for frontend requests to /app/v1/Reports/reports/{report_id}.
    """
    logger.info(f"Handling request to compatibility endpoint /app/v1/Reports/reports/{report_id}")
    return await original_delete_report(report_id=report_id)

@router.get("/download-report/{case_id}")
async def download_report_compat(case_id: str):
    """
    Download a report.
    This is a compatibility endpoint for frontend requests to /app/v1/Reports/download-report/{case_id}.
    """
    logger.info(f"Handling request to compatibility endpoint /app/v1/Reports/download-report/{case_id}")
    return await original_download_report(case_id=case_id)

@router.get("/download-final-report/{case_id}")
async def download_final_report_compat(case_id: str):
    """
    Download a final report.
    This is a compatibility endpoint for frontend requests to /app/v1/Reports/download-final-report/{case_id}.
    """
    logger.info(f"Handling request to compatibility endpoint /app/v1/Reports/download-final-report/{case_id}")
    return await original_download_final_report(case_id=case_id)
