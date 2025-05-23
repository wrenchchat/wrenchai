"""WebSocket endpoints for real-time task updates."""

from typing import Annotated
from uuid import UUID
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.core.websocket import manager
from app.core.security import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.models.task import Task

logger = get_logger(__name__)
router = APIRouter()

@router.websocket("/ws/tasks/{task_id}")
async def websocket_task_endpoint(
    websocket: WebSocket,
    task_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """
    Handles a WebSocket connection to provide real-time updates for a specific task.
    
    Establishes a WebSocket connection for the given task ID, sends the current task state to the client, and maintains the connection for live updates. Responds to client "ping" messages with "pong" and manages client disconnection and error handling.
    """
    try:
        # Connect client
        await manager.connect(websocket, str(task_id))
        
        # Send initial task state
        task = await db.get(Task, task_id)
        if task:
            await manager.broadcast_task_update(
                str(task_id),
                task.status,
                task.progress,
                task.message,
                task.result,
                task.error,
                # Include detailed step information if available
                step_details=task.input_data.get("step_details") if task.input_data else None
            )
        
        # Start heartbeat in background task
        heartbeat_task = asyncio.create_task(manager.start_heartbeat(str(task_id), 30.0))
        
        try:
            while True:
                # Keep connection alive and handle incoming messages
                data = await websocket.receive_json()
                
                # Handle client messages if needed
                if data.get("type") == "ping":
                    await websocket.send_json({"type": "pong", "timestamp": datetime.utcnow().isoformat()})
                    
        except WebSocketDisconnect:
            # Cancel heartbeat and clean up
            heartbeat_task.cancel()
            await manager.disconnect(websocket, str(task_id))
            
    except Exception as e:
        logger.error(f"WebSocket error for task {task_id}: {str(e)}")
        await manager.send_error(websocket, str(e))
        await manager.disconnect(websocket, str(task_id))

@router.websocket("/ws/agents/{agent_id}/tasks")
async def websocket_agent_tasks_endpoint(
    websocket: WebSocket,
    agent_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """
    Handles a WebSocket connection to stream real-time updates for all tasks associated with a specific agent.
    
    Upon connection, sends the current state of each task belonging to the agent and continues to broadcast updates. Responds to client "ping" messages to maintain the connection and manages client disconnects and error handling gracefully.
    """
    try:
        # Connect client
        await manager.connect(websocket, str(agent_id))
        
        # Send initial tasks state
        tasks = await db.execute(
            select(Task)
            .where(Task.agent_id == agent_id)
            .order_by(Task.created_at.desc())
        )
        tasks = tasks.scalars().all()
        
        for task in tasks:
            await manager.broadcast_task_update(
                str(task.id),
                task.status,
                task.progress,
                task.message,
                task.result,
                task.error,
                # Include detailed step information if available
                step_details=task.input_data.get("step_details") if task.input_data else None
            )
        
        # Start heartbeat in background task
        heartbeat_task = asyncio.create_task(manager.start_heartbeat(str(agent_id), 30.0))
        
        try:
            while True:
                # Keep connection alive and handle incoming messages
                data = await websocket.receive_json()
                
                # Handle client messages if needed
                if data.get("type") == "ping":
                    await websocket.send_json({"type": "pong", "timestamp": datetime.utcnow().isoformat()})
                    
        except WebSocketDisconnect:
            # Cancel heartbeat and clean up
            heartbeat_task.cancel()
            await manager.disconnect(websocket, str(agent_id))
            
    except Exception as e:
        logger.error(f"WebSocket error for agent {agent_id}: {str(e)}")
        await manager.send_error(websocket, str(e))
        await manager.disconnect(websocket, str(agent_id)) 