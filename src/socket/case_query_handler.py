"""
Socket.io event handlers for case queries.
"""
import asyncio
import uuid
import time
from typing import Dict, Any, Optional

from src.socket.socket_manager import sio, start_background_task, send_progress_update, send_heartbeat
from src.core.logging_config import get_logger
from src.api.schemas.prediction import QueryRequest

logger = get_logger(__name__)

@sio.event
async def query_case(sid, data, auth=None):
    """
    Query a case using WebSocket for long-running operations.

    Args:
        sid: Session ID
        data: Data containing case_id and section
        auth: Authentication data (optional)
    """
    case_id = data.get('case_id')
    section = data.get('section')
    case_type = data.get('case_type')
    model = data.get('model')

    if not case_id:
        await sio.emit('error', {'message': 'Missing case_id'}, room=sid)
        return

    if not section:
        await sio.emit('error', {'message': 'Missing section'}, room=sid)
        return

    # Generate a unique task ID
    task_id = f"query_{case_id}_{section}_{uuid.uuid4().hex[:8]}"

    try:
        # Create a request object
        request_data = {
            "case_id": case_id,
            "section": section,
            "case_type": case_type,
            "model": model
        }

        # Create a task to query the case
        result = await start_background_task(
            sid,
            task_id,
            _query_case_task,
            request_data,
            sid,
            task_id
        )

        # Return the result to the client
        await sio.emit('case_query_completed', {
            'task_id': task_id,
            'case_id': case_id,
            'section': section,
            'result': result
        }, room=sid)

    except Exception as e:
        logger.error(f"Error querying case: {str(e)}")
        await sio.emit('error', {
            'task_id': task_id,
            'message': f"Error querying case: {str(e)}"
        }, room=sid)

async def _query_case_task(request_data: Dict[str, Any], sid: str, task_id: str):
    """
    Task to query a case.

    Args:
        request_data: Request data
        sid: Session ID
        task_id: Task ID

    Returns:
        The query result
    """
    try:
        # Import the prediction service and dependencies
        from src.api.endpoints.predictions import query_case
        from src.api.schemas.prediction import QueryRequest
        from src.api.dependencies import get_case_repository, get_prediction_repository

        # Create a QueryRequest object
        case_query = QueryRequest(**request_data)

        # Send progress updates
        await send_progress_update(sid, task_id, 10, "Starting case query...")

        # Get the dependencies
        case_repo = get_case_repository()
        prediction_repo = get_prediction_repository()

        # Send progress update
        await send_progress_update(sid, task_id, 20, "Processing documents...")

        # Set up heartbeat task
        heartbeat_task = None

        try:
            # Create a heartbeat task that runs every 5 seconds
            async def heartbeat_coro():
                current_progress = 20
                while True:
                    # Send a heartbeat update
                    await send_heartbeat(sid, task_id, current_progress,
                                        f"Processing... (heartbeat at {time.strftime('%H:%M:%S')})")
                    logger.debug(f"Sent heartbeat for task {task_id} at progress {current_progress}")

                    # Wait for 5 seconds
                    await asyncio.sleep(5)

                    # Increment progress slightly to show activity (max 85%)
                    if current_progress < 85:
                        current_progress += 1

            # Start the heartbeat task
            heartbeat_task = asyncio.create_task(heartbeat_coro())

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

        # Send progress updates at key points
        await send_progress_update(sid, task_id, 90, "Finalizing results...")
        await send_progress_update(sid, task_id, 100, "Query complete")

        return result
    except Exception as e:
        logger.error(f"Error in case query task: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        raise
