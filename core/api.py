# MIT License - Copyright (c) 2024 Wrench AI
# For full license information, see the LICENSE file in the repo root.

import os
import logging
from typing import Dict, List, Any, Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, BackgroundTasks, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import asyncio
import json
import time
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from datetime import datetime, timedelta
import uuid

from core.agent_system import AgentManager
from core.bayesian_engine import BayesianEngine
from core.tool_system import ToolRegistry
from core.config_loader import load_config, load_configs
from core.agents.super_agent import SuperAgent, TaskRequest
from core.agents.inspector_agent import InspectorAgent
from core.agents.journey_agent import JourneyAgent, JourneyStep
from core.tools.secrets_manager import secrets

# Import standardized response and request schemas
from core.schemas.responses import (
    APIResponse, 
    PaginatedResponse, 
    create_response, 
    error_response, 
    paginated_response
)
from core.schemas.requests import (
    PlaybookExecuteRequest,
    TaskCreateRequest,
    AgentCreateRequest,
    ToolExecuteRequest,
    ToolCategory,
    AgentType
)

# Import standardized API routers
from core.api_routes import agents_router, playbooks_router, tools_router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="WrenchAI API",
    description="Multi-Agent Framework API",
    version="1.0.0"
)

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add validation middleware and exception handlers
from core.middleware.validation import add_validation_middleware
from core.middleware.exception_handlers import add_exception_handlers

add_validation_middleware(app)
add_exception_handlers(app)

# Include standardized routers
app.include_router(agents_router)
app.include_router(playbooks_router)
app.include_router(tools_router)

# Initialize systems
CONFIG_DIR = os.getenv("CONFIG_DIR", "core/configs")
system_config = None
agent_manager = None
tool_registry = None
bayesian_engine = None

# Initialize agents
super_agent = SuperAgent()
inspector_agent = InspectorAgent()
journey_agent = JourneyAgent()

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, client_id: str):
        await websocket.accept()
        if client_id not in self.active_connections:
            self.active_connections[client_id] = []
        self.active_connections[client_id].append(websocket)

    async def disconnect(self, websocket: WebSocket, client_id: str):
        self.active_connections[client_id].remove(websocket)
        if not self.active_connections[client_id]:
            del self.active_connections[client_id]

    async def broadcast(self, message: Dict[str, Any], client_id: str):
        if client_id in self.active_connections:
            for connection in self.active_connections[client_id]:
                await connection.send_json(message)

manager = ConnectionManager()

# OAuth2 configuration
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

def get_agent_id(agent):
    """Get a string identifier for an agent"""
    return str(id(agent))

@app.on_event("startup")
async def startup_event():
    """Initialize the system on startup"""
    global system_config, agent_manager, tool_registry, bayesian_engine
    
    try:
        # Load configurations
        system_config = load_configs(CONFIG_DIR)
        logging.info("Loaded system configuration")
        
        # Initialize components
        bayesian_engine = BayesianEngine()
        logging.info("Initialized Bayesian engine")
        
        tool_registry = ToolRegistry(os.path.join(CONFIG_DIR, "tools.yaml"))
        logging.info("Initialized tool registry")
        
        agent_manager = AgentManager(CONFIG_DIR)
        agent_manager.set_tool_registry(tool_registry)
        agent_manager.set_bayesian_engine(bayesian_engine)
        logging.info("Initialized agent manager")
        
        # Register bayesian_tools with the bayesian engine
        from core.tools import bayesian_tools
        bayesian_tools.set_bayesian_engine(bayesian_engine)
        logging.info("Registered Bayesian engine with tools")
        
    except Exception as e:
        logging.error(f"Error initializing system: {e}")
        raise

@app.get("/health", tags=["System"], response_model=Dict[str, Any])
async def health_check() -> JSONResponse:
    """Check system health status."""
    try:
        # Implement health checks
        checks = {
            "database": True,  # Replace with actual DB check
            "cache": True,     # Replace with actual cache check
            "agents": {
                "super_agent": isinstance(super_agent, SuperAgent),
                "inspector_agent": isinstance(inspector_agent, InspectorAgent),
                "journey_agent": isinstance(journey_agent, JourneyAgent)
            }
        }
        
        # Determine overall health status
        is_healthy = all(checks.values()) and all(checks["agents"].values())
        
        return JSONResponse(
            content=create_response(
                success=is_healthy,
                message="System health status",
                data={
                    "status": "healthy" if is_healthy else "unhealthy",
                    "checks": checks,
                    "timestamp": datetime.utcnow().isoformat()
                }
            )
        )
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=error_response(
                message="Health check failed",
                code="HEALTH_CHECK_ERROR",
                details={"error": str(e)}
            )
        )

# Keep backward compatibility with existing API endpoints
# These can be gradually migrated to the new standardized routers

@app.post("/api/agents/{agent_id}/process")
async def process_with_agent(agent_id: str, data: Dict[str, Any]):
    """Process input with a specific agent"""
    try:
        if agent_id not in agent_manager.agents:
            raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")
            
        agent = agent_manager.agents[agent_id]
        result = await agent.process(data)
        
        return {"status": "success", "result": result}
    except Exception as e:
        logging.error(f"Error processing with agent: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/playbooks/run")
async def run_playbook(data: Dict[str, Any], background_tasks: BackgroundTasks):
    """
    Runs a specified playbook asynchronously with provided input data.
    
    Validates the existence of the requested playbook and starts its execution in the background. Returns a unique run ID for tracking the playbook run status.
    
    Args:
        data: Dictionary containing the 'playbook' name and 'input' data.
        background_tasks: FastAPI background task manager for asynchronous execution.
    
    Returns:
        A dictionary with the status and unique run ID.
    
    Raises:
        HTTPException: If required fields are missing, the playbook does not exist, or an error occurs during processing.
    """
    try:
        if 'playbook' not in data:
            raise HTTPException(status_code=400, detail="Missing 'playbook' field")
        if 'input' not in data:
            raise HTTPException(status_code=400, detail="Missing 'input' field")
            
        # Validate input data against expected schema
        from core.playbook_schema import Playbook
        
        try:
            # The playbook name is used to locate the actual playbook file
            playbook_name = data['playbook']
            playbook_path = os.path.join(CONFIG_DIR, "playbooks", f"{playbook_name}.yaml")
            
            # Validate that the playbook exists
            if not os.path.exists(playbook_path):
                raise HTTPException(status_code=404, detail=f"Playbook not found: {playbook_name}")
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid playbook request: {str(e)}")
            
        # Generate a unique run ID
        run_id = f"run_{int(time.time())}"
        
        # Start workflow in background
        background_tasks.add_task(
            execute_workflow_and_log, 
            run_id=run_id,
            playbook_name=data['playbook'], 
            input_data=data['input']
        )
        
        return {"status": "started", "run_id": run_id}
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error running playbook: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/playbooks/status/{run_id}")
async def get_playbook_status(run_id: str):
    """Get the status of a playbook run"""
    # In a real implementation, this would check a database or cache
    # For now, we'll return a placeholder
    return {"status": "running", "run_id": run_id}

@app.post("/api/reasoning/models/create")
async def create_belief_model(data: Dict[str, Any]):
    """Create a new belief model in the Bayesian engine"""
    try:
        if 'model_name' not in data:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content=error_response(
                    message="Missing 'model_name' field",
                    code="MISSING_FIELD"
                )
            )
        if 'variables' not in data or not isinstance(data['variables'], dict):
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content=error_response(
                    message="Missing or invalid 'variables' field",
                    code="INVALID_FIELD"
                )
            )
            
        bayesian_engine.create_model(data['model_name'], data['variables'])
        
        return JSONResponse(
            content=create_response(
                success=True,
                message="Belief model created successfully",
                data={"model": data['model_name']}
            )
        )
    except Exception as e:
        logging.error(f"Error creating belief model: {e}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=error_response(
                message="Failed to create belief model",
                code="MODEL_CREATION_ERROR",
                details={"error": str(e)}
            )
        )

@app.post("/api/reasoning/update", response_model=Dict[str, Any])
async def update_beliefs(data: Dict[str, Any]) -> JSONResponse:
    """Update beliefs in the Bayesian model"""
    try:
        if 'model' not in data:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content=error_response(
                    message="Missing 'model' field",
                    code="MISSING_FIELD"
                )
            )
        if 'evidence' not in data or not isinstance(data['evidence'], dict):
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content=error_response(
                    message="Missing or invalid 'evidence' field",
                    code="INVALID_FIELD"
                )
            )
            
        # Optional sampling parameters
        sample_kwargs = data.get('sample_kwargs', {})
        
        updated_beliefs = bayesian_engine.update_beliefs(
            data['model'], data['evidence'], sample_kwargs
        )
        
        return JSONResponse(
            content=create_response(
                success=True,
                message="Beliefs updated successfully",
                data={"beliefs": updated_beliefs}
            )
        )
    except Exception as e:
        logging.error(f"Error updating beliefs: {e}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=error_response(
                message="Failed to update beliefs",
                code="BELIEF_UPDATE_ERROR",
                details={"error": str(e)}
            )
        )

@app.post("/api/reasoning/decide", response_model=Dict[str, Any])
async def make_decision(data: Dict[str, Any]) -> JSONResponse:
    """Make a decision based on current beliefs"""
    try:
        if 'model' not in data:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content=error_response(
                    message="Missing 'model' field",
                    code="MISSING_FIELD"
                )
            )
        if 'options' not in data or not isinstance(data['options'], list):
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content=error_response(
                    message="Missing or invalid 'options' field",
                    code="INVALID_FIELD"
                )
            )
        if 'utility_function' not in data:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content=error_response(
                    message="Missing 'utility_function' field",
                    code="MISSING_FIELD"
                )
            )
            
        # Convert utility function from string to callable
        # WARNING: This is unsafe in production - use a safer approach
        utility_function = eval(data['utility_function'])
        
        best_option, utility = bayesian_engine.make_decision(
            data['model'], data['options'], utility_function
        )
        
        return JSONResponse(
            content=create_response(
                success=True,
                message="Decision made successfully",
                data={
                    "decision": best_option,
                    "expected_utility": utility
                }
            )
        )
    except Exception as e:
        logging.error(f"Error making decision: {e}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=error_response(
                message="Failed to make decision",
                code="DECISION_ERROR",
                details={"error": str(e)}
            )
        )

@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    await manager.connect(websocket, client_id)
    try:
        while True:
            data = await websocket.receive_json()
            await manager.broadcast({
                "client_id": client_id,
                "message": data,
                "timestamp": datetime.utcnow().isoformat()
            }, client_id)
    except Exception as e:
        logger.error(f"WebSocket error: {str(e)}")
    finally:
        await manager.disconnect(websocket, client_id)

async def execute_workflow_and_log(run_id: str, playbook_name: str, input_data: Dict[str, Any]):
    """Execute a workflow and log the results"""
    try:
        # Execute the workflow
        result = await agent_manager.run_workflow(playbook_name, input_data)
        
        # In a real implementation, store the result in a database
        logging.info(f"Workflow {run_id} ({playbook_name}) completed successfully")
        
        # For now, just log the result
        logging.info(f"Workflow result: {json.dumps(result)[:1000]}...")
        
        return result
    except Exception as e:
        logging.error(f"Error executing workflow {run_id}: {e}")
        # In a real implementation, update status in database
        raise

# Task endpoints
@app.post("/tasks", tags=["Tasks"], response_model=Dict[str, Any])
async def create_task(task: TaskCreateRequest) -> JSONResponse:
    """Create and start a new task."""
    try:
        # Convert TaskCreateRequest to TaskRequest for backward compatibility
        task_request = TaskRequest(
            title=task.title,
            description=task.description,
            priority=task.priority,
            due_date=task.due_date,
            assignee=task.assignee
        )
        
        result = await super_agent.orchestrate_task(task_request)
        
        return JSONResponse(
            status_code=status.HTTP_201_CREATED,
            content=create_response(
                success=True,
                message="Task created successfully",
                data=result
            )
        )
    except Exception as e:
        logger.error(f"Task creation failed: {str(e)}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=error_response(
                message="Task creation failed",
                code="TASK_CREATION_ERROR",
                details={"error": str(e)}
            )
        )

@app.get("/tasks/{task_id}", tags=["Tasks"], response_model=Dict[str, Any])
async def get_task_status(task_id: str) -> JSONResponse:
    """Get status of a specific task."""
    try:
        # Implement task status retrieval
        # This is a mock implementation - in a real system, fetch from a database
        task_data = {
            "task_id": task_id,
            "status": "running",  # Replace with actual status
            "timestamp": datetime.utcnow().isoformat()
        }
        
        return JSONResponse(
            content=create_response(
                success=True,
                message="Task status retrieved successfully",
                data=task_data
            )
        )
    except Exception as e:
        logger.error(f"Failed to get task status: {str(e)}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=error_response(
                message="Failed to get task status",
                code="TASK_STATUS_ERROR",
                details={"error": str(e)}
            )
        )

# Journey endpoints
@app.post("/journeys", tags=["Journeys"], response_model=Dict[str, Any])
async def create_journey(
    steps: List[JourneyStep],
    context: Dict[str, Any]
) -> JSONResponse:
    """Create and execute a new journey."""
    try:
        result = await journey_agent.execute_journey(steps, context)
        
        return JSONResponse(
            status_code=status.HTTP_201_CREATED,
            content=create_response(
                success=True,
                message="Journey created and executed successfully",
                data=result
            )
        )
    except Exception as e:
        logger.error(f"Journey creation failed: {str(e)}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=error_response(
                message="Journey creation failed",
                code="JOURNEY_CREATION_ERROR",
                details={"error": str(e)}
            )
        )

@app.get("/journeys/{journey_id}", tags=["Journeys"], response_model=Dict[str, Any])
async def get_journey_status(journey_id: str) -> JSONResponse:
    """Get status of a specific journey."""
    try:
        if journey_id not in journey_agent.active_journeys:
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content=error_response(
                    message="Journey not found",
                    code="JOURNEY_NOT_FOUND"
                )
            )
            
        journey_data = journey_agent.active_journeys[journey_id]
        
        return JSONResponse(
            content=create_response(
                success=True,
                message="Journey status retrieved successfully",
                data=journey_data
            )
        )
    except Exception as e:
        logger.error(f"Failed to get journey status: {str(e)}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=error_response(
                message="Failed to get journey status",
                code="JOURNEY_STATUS_ERROR",
                details={"error": str(e)}
            )
        )

# Monitoring endpoints
@app.get("/monitor/{task_id}", tags=["Monitoring"], response_model=Dict[str, Any])
async def monitor_task(task_id: str) -> JSONResponse:
    """Monitor a specific task."""
    try:
        execution_data = {
            "task_id": task_id,
            "metrics": {
                "success_rate": "95%",
                "duration": "00:05:23"
            },
            "timestamp": datetime.utcnow().isoformat()
        }
        
        result = await inspector_agent.monitor_execution(task_id, execution_data)
        
        return JSONResponse(
            content=create_response(
                success=True,
                message="Task monitoring completed successfully",
                data=result
            )
        )
    except Exception as e:
        logger.error(f"Task monitoring failed: {str(e)}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=error_response(
                message="Task monitoring failed",
                code="MONITORING_ERROR",
                details={"error": str(e)}
            )
        )

# Authentication endpoint
@app.post("/token", tags=["Auth"], response_model=Dict[str, Any])
async def login(form_data: OAuth2PasswordRequestForm = Depends()) -> JSONResponse:
    """Authenticate user and generate access token."""
    try:
        # Implement actual authentication logic
        if form_data.username == "test" and form_data.password == "test":
            token_data = {
                "access_token": "dummy_token",
                "token_type": "bearer",
                "expires_in": 3600  # 1 hour in seconds
            }
            
            return JSONResponse(
                content=create_response(
                    success=True,
                    message="Authentication successful",
                    data=token_data
                )
            )
            
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content=error_response(
                message="Invalid credentials",
                code="INVALID_CREDENTIALS"
            )
        )
    except Exception as e:
        logger.error(f"Authentication failed: {str(e)}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=error_response(
                message="Authentication failed",
                code="AUTH_ERROR",
                details={"error": str(e)}
            )
        )

# Shutdown event
@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup resources on shutdown."""
    try:
        logger.info("Cleaning up API resources...")
        # Cleanup any resources here
    except Exception as e:
        logger.error(f"Shutdown cleanup failed: {str(e)}")
        raise
