"""
Socket.io manager for the application.
"""
import socketio
import asyncio
import time
from typing import Dict, Any, Optional, List, Callable, Set
from src.core.logging_config import get_logger

logger = get_logger(__name__)

# Create a Socket.IO server with improved configuration
sio = socketio.AsyncServer(
    async_mode='asgi',
    # Specify allowed origins explicitly for better security
    # In production, this should be set to your frontend domain
    # For now, we'll keep it as '*' but this should be changed in production
    cors_allowed_origins='*',
    # Enable logging for debugging
    logger=True,
    engineio_logger=True,
    # Increase timeouts for long-running operations
    ping_timeout=12000,  # 2 minutes
    ping_interval=25,  # 25 seconds
    # Maximum HTTP request size
    max_http_buffer_size=1000000,  # 1MB
    # Allow upgrades from polling to WebSocket
    allow_upgrades=True,
    # Enable WebSocket compression
    compression=True,
    # Don't use cookie for session ID
    cookie=False,
    # Don't use binary packets (can cause issues with some proxies)
    binary=False,
    # Increase the number of concurrent connections
    max_queue=100
)

# Create an ASGI application
socket_app = socketio.ASGIApp(
    sio,
    socketio_path='socket.io',
    other_asgi_app=None
)

# Store active connections
active_connections: Dict[str, Dict[str, Any]] = {}

# Store long-running tasks
tasks: Dict[str, Dict[str, Any]] = {}


@sio.event
async def connect(sid, environ, auth):
    """
    Handle client connection.

    Args:
        sid: Session ID
        environ: WSGI environment
        auth: Authentication data
    """
    logger.info(f"Client connected: {sid}")
    active_connections[sid] = {
        'user_id': auth.get('user_id') if auth else None,
        'connected_at': asyncio.get_event_loop().time(),
    }
    await sio.emit('welcome', {'message': 'Connected to Forensic API'}, room=sid)


@sio.event
async def disconnect(sid):
    """
    Handle client disconnection.

    Args:
        sid: Session ID
    """
    logger.info(f"Client disconnected: {sid}")
    if sid in active_connections:
        del active_connections[sid]

    # Cancel any tasks associated with this session
    if sid in tasks:
        for task_id, task_info in list(tasks[sid].items()):
            if 'task' in task_info and not task_info['task'].done():
                logger.info(f"Cancelling task {task_id} for session {sid}")
                task_info['task'].cancel()
        del tasks[sid]


@sio.event
async def register_for_updates(sid, data):
    """
    Register a client for updates on a specific case.

    Args:
        sid: Session ID
        data: Data containing case_id
    """
    case_id = data.get('case_id')
    if not case_id:
        await sio.emit('error', {'message': 'Missing case_id'}, room=sid)
        return

    if sid in active_connections:
        active_connections[sid]['case_id'] = case_id
        logger.info(f"Client {sid} registered for updates on case {case_id}")
        await sio.emit('registered', {'case_id': case_id}, room=sid)


async def start_background_task(sid: str, task_id: str, func: Callable, *args, **kwargs):
    """
    Start a background task and track its progress.

    Args:
        sid: Session ID
        task_id: Task ID
        func: Function to run
        *args: Arguments for the function
        **kwargs: Keyword arguments for the function

    Returns:
        The task result
    """
    if sid not in tasks:
        tasks[sid] = {}

    # Create a new task
    task = asyncio.create_task(func(*args, **kwargs))

    # Store the task
    tasks[sid][task_id] = {
        'task': task,
        'started_at': asyncio.get_event_loop().time(),
        'status': 'running',
    }

    # Notify the client that the task has started
    await sio.emit('task_started', {
        'task_id': task_id,
        'message': f'Task {task_id} started',
    }, room=sid)

    try:
        # Wait for the task to complete
        result = await task

        # Update the task status
        tasks[sid][task_id]['status'] = 'completed'
        tasks[sid][task_id]['completed_at'] = asyncio.get_event_loop().time()

        # Notify the client that the task has completed
        await sio.emit('task_completed', {
            'task_id': task_id,
            'message': f'Task {task_id} completed',
        }, room=sid)

        return result
    except asyncio.CancelledError:
        # Update the task status
        tasks[sid][task_id]['status'] = 'cancelled'
        tasks[sid][task_id]['cancelled_at'] = asyncio.get_event_loop().time()

        # Notify the client that the task has been cancelled
        await sio.emit('task_cancelled', {
            'task_id': task_id,
            'message': f'Task {task_id} cancelled',
        }, room=sid)

        raise
    except Exception as e:
        # Update the task status
        tasks[sid][task_id]['status'] = 'failed'
        tasks[sid][task_id]['failed_at'] = asyncio.get_event_loop().time()
        tasks[sid][task_id]['error'] = str(e)

        # Notify the client that the task has failed
        await sio.emit('task_failed', {
            'task_id': task_id,
            'message': f'Task {task_id} failed: {str(e)}',
        }, room=sid)

        raise


async def send_progress_update(sid: str, task_id: str, progress: float, message: str = None):
    """
    Send a progress update to a client.

    Args:
        sid: Session ID
        task_id: Task ID
        progress: Progress (0-100)
        message: Optional message
    """
    await sio.emit('task_progress', {
        'task_id': task_id,
        'progress': progress,
        'message': message,
    }, room=sid)


async def broadcast_to_case(case_id: str, event: str, data: Dict[str, Any]):
    """
    Broadcast an event to all clients registered for a specific case.

    Args:
        case_id: Case ID
        event: Event name
        data: Event data
    """
    for sid, connection in active_connections.items():
        if connection.get('case_id') == case_id:
            await sio.emit(event, data, room=sid)


@sio.event
async def heartbeat(sid, data):
    """
    Handle heartbeat from client to keep connection alive.

    Args:
        sid: Session ID
        data: Heartbeat data
    """
    logger.debug(f"Received heartbeat from client {sid}")
    # Respond with current server time
    await sio.emit('heartbeat_response', {
        'server_time': time.time(),
        'received_client_time': data.get('timestamp') if data else None,
    }, room=sid)


@sio.event
async def keep_alive(sid, data):
    """
    Handle keep-alive request from client during long-running operations.

    Args:
        sid: Session ID
        data: Keep-alive data including task_id
    """
    task_id = data.get('task_id')
    if not task_id:
        return

    logger.debug(f"Received keep-alive for task {task_id} from client {sid}")

    # Check if the task exists and is still running
    if sid in tasks and task_id in tasks[sid]:
        task_info = tasks[sid][task_id]
        if task_info['status'] == 'running':
            # Send a progress update to keep the connection alive
            await sio.emit('task_progress', {
                'task_id': task_id,
                'progress': data.get('progress', 0),
                'message': f"Processing... (heartbeat at {time.strftime('%H:%M:%S')})",
                'is_heartbeat': True
            }, room=sid)


@sio.event
async def get_task_status(sid, data):
    """
    Handle request for task status.

    Args:
        sid: Session ID
        data: Data containing task_id
    """
    task_id = data.get('task_id')
    if not task_id:
        await sio.emit('error', {'message': 'Missing task_id'}, room=sid)
        return

    logger.info(f"Received task status request for task {task_id} from client {sid}")

    # Check if the task exists
    if sid in tasks and task_id in tasks[sid]:
        task_info = tasks[sid][task_id]
        status = task_info['status']

        # Send the task status
        await sio.emit('task_status', {
            'task_id': task_id,
            'status': status,
            'started_at': task_info.get('started_at'),
            'elapsed_seconds': time.time() - task_info.get('started_at', time.time()) if 'started_at' in task_info else 0,
        }, room=sid)

        # If the task is still running, send a heartbeat
        if status == 'running':
            await send_heartbeat(sid, task_id, 50, f"Task {task_id} is still running")
    else:
        await sio.emit('task_status', {
            'task_id': task_id,
            'status': 'not_found',
            'message': f"Task {task_id} not found"
        }, room=sid)


@sio.event
async def operation_keep_alive(sid, data):
    """
    Handle operation-specific keep-alive request from client.

    Args:
        sid: Session ID
        data: Keep-alive data including task_id and progress
    """
    task_id = data.get('task_id')
    if not task_id:
        return

    progress = data.get('progress', 0)
    elapsed_seconds = data.get('elapsed_seconds', 0)

    logger.debug(f"Received operation keep-alive for task {task_id} from client {sid}")

    # Check if the task exists and is still running
    if sid in tasks and task_id in tasks[sid]:
        task_info = tasks[sid][task_id]
        if task_info['status'] == 'running':
            # Send a heartbeat with the current progress
            await send_heartbeat(
                sid,
                task_id,
                progress,
                f"Processing... (running for {elapsed_seconds}s)"
            )

            # Acknowledge the keep-alive
            await sio.emit('operation_keep_alive_ack', {
                'task_id': task_id,
                'server_time': time.time(),
                'received_progress': progress
            }, room=sid)


@sio.event
async def task_heartbeat(sid, data):
    """
    Handle task heartbeat request from client.

    Args:
        sid: Session ID
        data: Heartbeat data including task_id and progress
    """
    task_id = data.get('task_id')
    if not task_id:
        return

    progress = data.get('progress', 0)

    logger.debug(f"Received task heartbeat for task {task_id} from client {sid}")

    # Check if the task exists and is still running
    if sid in tasks and task_id in tasks[sid]:
        task_info = tasks[sid][task_id]
        if task_info['status'] == 'running':
            # Send a heartbeat with the current progress
            await send_heartbeat(
                sid,
                task_id,
                progress,
                f"Processing... (heartbeat at {time.strftime('%H:%M:%S')})"
            )


async def send_heartbeat(sid: str, task_id: str, progress: float, message: str = None):
    """
    Send a heartbeat update to a client to keep the connection alive during long-running tasks.

    Args:
        sid: Session ID
        task_id: Task ID
        progress: Current progress (0-100)
        message: Optional message
    """
    await sio.emit('task_progress', {
        'task_id': task_id,
        'progress': progress,
        'message': message or f"Processing... (heartbeat at {time.strftime('%H:%M:%S')})",
        'is_heartbeat': True
    }, room=sid)
