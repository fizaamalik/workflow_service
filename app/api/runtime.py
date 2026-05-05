from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.config import settings
from app.core.security import get_current_user
from app.schemas.workflow_runtime import (
    StartWorkflowRequest,
    StartWorkflowResponse,
    WorkflowActionRequest,
    ReminderRequest,
    ReminderResponse,
    ClaimTaskResponse,
)
from app.services.workflow_runtime_service import WorkflowRuntimeService

router = APIRouter(prefix="/api/v1/workflow-runtime", tags=["workflow-runtime"])
_svc = WorkflowRuntimeService()


def _meta(request: Request) -> dict:
    """Extract IP + UA for audit trail."""
    return {
        "ip_address": request.client.host if request.client else None,
        "user_agent": request.headers.get("user-agent"),
    }


# ── Start ─────────────────────────────────────────────────────────────────────

@router.post(
    "/start",
    response_model=StartWorkflowResponse,
    status_code=201,
    summary="Start a workflow for an entity record",
)
async def start_workflow(
    req: StartWorkflowRequest,
    http_request: Request,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
    authorization: str | None = Header(None),
):
    if not authorization and settings.APP_ENV.lower() in {"dev", "local"}:
        authorization = "Bearer dev"
    return await _svc.start_workflow(db, req, current_user, authorization or "", _meta(http_request))


# ── Pending tasks ─────────────────────────────────────────────────────────────

@router.get(
    "/tasks/pending",
    summary="List all pending/claimed tasks assigned to the current user",
)
async def get_pending_tasks(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return await _svc.get_pending_tasks(db, current_user)


# ── Task detail ───────────────────────────────────────────────────────────────

@router.get(
    "/tasks/{task_id}",
    summary="Get full task detail including allowed actions",
)
async def get_task_detail(
    task_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return await _svc.get_task_detail(db, task_id, current_user)


# ── Perform action ────────────────────────────────────────────────────────────

@router.post(
    "/tasks/{task_id}/action",
    summary="Perform an action on a task (approve, reject, send-back, etc.)",
)
async def perform_action(
    task_id: int,
    req: WorkflowActionRequest,
    http_request: Request,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
    authorization: str | None = Header(None),
):
    if not authorization and settings.APP_ENV.lower() in {"dev", "local"}:
        authorization = "Bearer dev"
    return await _svc.perform_action(
        db, task_id, req, current_user, authorization or "", _meta(http_request)
    )


# ── Claim task ────────────────────────────────────────────────────────────────

@router.post(
    "/tasks/{task_id}/claim",
    response_model=ClaimTaskResponse,
    summary="Claim a task from a shared role/pool assignment",
)
async def claim_task(
    task_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return await _svc.claim_task(db, task_id, current_user)


# ── Reminder ──────────────────────────────────────────────────────────────────

@router.post(
    "/tasks/{task_id}/reminder",
    response_model=ReminderResponse,
    summary="Send a reminder to task assignees (initiator only)",
)
async def send_reminder(
    task_id: int,
    req: ReminderRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return await _svc.send_reminder(db, task_id, req.reminder_message, current_user)


# ── Instance detail ───────────────────────────────────────────────────────────

@router.get(
    "/instances/{instance_id}",
    summary="Get full workflow instance detail with action history",
)
async def get_instance_detail(
    instance_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return await _svc.get_instance_detail(db, instance_id, current_user)
