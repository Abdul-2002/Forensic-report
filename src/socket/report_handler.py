"""
Socket.io event handlers for reports.
"""
import asyncio
import uuid
import time
from typing import Dict, Any, Optional
from src.socket.socket_manager import sio, start_background_task, send_progress_update, send_heartbeat
from src.core.logging_config import get_logger

logger = get_logger(__name__)

@sio.event
async def generate_report(sid, data, auth=None):
    """
    Generate a report for a case.

    Args:
        sid: Session ID
        data: Data containing case_id and section
        auth: Authentication data (optional)
    """
    case_id = data.get('case_id')
    section = data.get('section')
    case_type = data.get('case_type')

    if not case_id:
        await sio.emit('error', {'message': 'Missing case_id'}, room=sid)
        return

    if not section:
        await sio.emit('error', {'message': 'Missing section'}, room=sid)
        return

    # Generate a unique task ID
    task_id = f"report_{case_id}_{section}_{uuid.uuid4().hex[:8]}"

    try:
        # Import the prediction service
        from src.api.endpoints.predictions import query_case
        from fastapi import Request
        from src.api.schemas.prediction import QueryRequest as CaseQuery

        # Create a mock request object
        mock_request = {
            "case_id": case_id,
            "section": section,
            "case_type": case_type
        }

        # Create a task to generate the report
        result = await start_background_task(
            sid,
            task_id,
            _generate_report_task,
            mock_request,
            sid,
            task_id
        )

        # Return the result to the client
        await sio.emit('report_generated', {
            'task_id': task_id,
            'case_id': case_id,
            'section': section,
            'result': result
        }, room=sid)

    except Exception as e:
        logger.error(f"Error generating report: {str(e)}")
        await sio.emit('error', {
            'task_id': task_id,
            'message': f"Error generating report: {str(e)}"
        }, room=sid)


async def _generate_report_task(request_data: Dict[str, Any], sid: str, task_id: str):
    """
    Task to generate a report.

    Args:
        request_data: Request data
        sid: Session ID
        task_id: Task ID

    Returns:
        The generated report
    """
    try:
        # Import the prediction service and dependencies
        from src.api.endpoints.predictions import query_case
        from src.api.schemas.prediction import QueryRequest as CaseQuery
        from src.api.dependencies import get_case_repository, get_prediction_repository
        from src.db.repositories.case_repository import CaseRepository
        from src.db.repositories.prediction_repository import PredictionRepository

        # Create a CaseQuery object
        case_query = CaseQuery(**request_data)

        # Send progress updates
        await send_progress_update(sid, task_id, 10, "Starting report generation...")

        # Set up heartbeat task
        heartbeat_task = None

        try:
            # Create a heartbeat task that runs every 5 seconds
            async def heartbeat_coro():
                current_progress = 10
                while True:
                    # Send a heartbeat update
                    await send_heartbeat(sid, task_id, 
                                        f"Processing report... (heartbeat at {time.strftime('%H:%M:%S')})")
                    logger.debug(f"Sent heartbeat for report task {task_id} at progress {current_progress}")

                    # Wait for 5 seconds
                    await asyncio.sleep(5)

                    # Increment progress slightly to show activity (max 85%)
                    if current_progress < 85:
                        current_progress += 1

            # Start the heartbeat task
            heartbeat_task = asyncio.create_task(heartbeat_coro())

            # Simulate initial progress updates
            for i in range(2, 5):
                await asyncio.sleep(1)  # Simulate work
                await send_progress_update(sid, task_id, i * 10, "Processing report...")

            # Manually create the dependencies
            case_repo = get_case_repository()
            prediction_repo = get_prediction_repository()

            # Call the query_case function with manually created dependencies
            result = await query_case(case_query, case_repo, prediction_repo)

        finally:
            # Cancel the heartbeat task if it exists
            if heartbeat_task and not heartbeat_task.done():
                heartbeat_task.cancel()
                try:
                    await heartbeat_task
                except asyncio.CancelledError:
                    pass

        # Send final progress update
        await send_progress_update(sid, task_id, 90, "Finalizing report...")
        await send_progress_update(sid, task_id, 100, "Report generation complete")

        return result
    except Exception as e:
        logger.error(f"Error in report generation task: {str(e)}")
        raise
