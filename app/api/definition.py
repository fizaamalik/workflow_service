from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.schemas.workflow_definition import (
    WorkflowCreateRequest,
    WorkflowUpdateRequest,
    WorkflowResponse,
    NodeCreateRequest,
    NodeResponse,
    ActionCreateRequest,
    ActionResponse,
    TransitionCreateRequest,
    TransitionResponse,
)
from app.services.workflow_definition_service import WorkflowDefinitionService

router = APIRouter(prefix="/api/v1/workflows", tags=["workflow-definition"])
_svc = WorkflowDefinitionService()


# ── Workflow ──────────────────────────────────────────────────────────────────

@router.post("", status_code=201, summary="Create a new workflow definition")
async def create_workflow(
    request: WorkflowCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return await _svc.create_workflow(db, request, current_user)


@router.get("", response_model=list[WorkflowResponse], summary="List all workflows for the org")
async def list_workflows(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    rows = await _svc.list_workflows(db, current_user)
    return rows


@router.get("/{workflow_id}", response_model=WorkflowResponse, summary="Get workflow details")
async def get_workflow(
    workflow_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return await _svc.get_workflow(db, workflow_id, current_user)


@router.patch("/{workflow_id}", summary="Update workflow (draft only)")
async def update_workflow(
    workflow_id: int,
    request: WorkflowUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return await _svc.update_workflow(db, workflow_id, request, current_user)


@router.post("/{workflow_id}/publish", summary="Publish a workflow (validates structure)")
async def publish_workflow(
    workflow_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return await _svc.publish_workflow(db, workflow_id, current_user)


# ── Nodes ─────────────────────────────────────────────────────────────────────

@router.post("/{workflow_id}/nodes", status_code=201, summary="Add a node to a workflow")
async def add_node(
    workflow_id: int,
    request: NodeCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return await _svc.add_node(db, workflow_id, request, current_user)


@router.get("/{workflow_id}/nodes", response_model=list[NodeResponse], summary="List workflow nodes")
async def list_nodes(
    workflow_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return await _svc.list_nodes(db, workflow_id, current_user)


@router.delete(
    "/nodes/{node_id}",
    summary="Soft-delete a node (draft workflow only)",
)
async def delete_node(
    node_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return await _svc.delete_node(db, node_id, current_user)


# ── Actions ───────────────────────────────────────────────────────────────────

@router.post(
    "/nodes/{node_id}/actions",
    status_code=201,
    summary="Add an allowed action to a node",
)
async def add_action(
    node_id: int,
    request: ActionCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return await _svc.add_action(db, node_id, request, current_user)


@router.get(
    "/nodes/{node_id}/actions",
    response_model=list[ActionResponse],
    summary="List actions for a node",
)
async def list_actions(
    node_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return await _svc.list_actions(db, node_id, current_user)


# ── Transitions ───────────────────────────────────────────────────────────────

@router.post(
    "/{workflow_id}/transitions",
    status_code=201,
    summary="Add a transition between nodes",
)
async def add_transition(
    workflow_id: int,
    request: TransitionCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return await _svc.add_transition(db, workflow_id, request, current_user)


@router.get(
    "/{workflow_id}/transitions",
    response_model=list[TransitionResponse],
    summary="List all transitions for a workflow",
)
async def list_transitions(
    workflow_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return await _svc.list_transitions(db, workflow_id, current_user)