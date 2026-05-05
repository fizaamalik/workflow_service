from pydantic import BaseModel
from datetime import datetime
from typing import Any


class StartWorkflowRequest(BaseModel):
    entity_name: str
    entity_table_name: str
    entity_record_id: str
    payload: dict[str, Any] = {}


class StartWorkflowResponse(BaseModel):
    workflow_instance_id: int
    workflow_status: str
    current_node: str
    task_id: int
    assigned_to_user_ids: list[int]


class WorkflowActionRequest(BaseModel):
    action_code: str
    comments: str | None = None
    payload: dict[str, Any] = {}


class ActionResponse(BaseModel):
    workflow_completed: bool
    workflow_status: str
    next_task_id: int | None = None
    current_node: str | None = None
    assigned_to_user_ids: list[int] | None = None


class ReminderRequest(BaseModel):
    reminder_message: str


class ReminderResponse(BaseModel):
    message: str
    recipients: list[int]


class PendingTaskItem(BaseModel):
    workflow_task_id: int
    workflow_instance_id: int
    entity_name: str
    entity_record_id: str
    node_name: str
    task_status: str
    due_at: datetime | None
    assigned_to_user_id: int | None
    reminder_count: int


class TaskDetailResponse(BaseModel):
    workflow_task_id: int
    workflow_instance_id: int
    workflow_id: int
    node_id: int
    node_name: str
    node_type: str
    entity_name: str
    entity_record_id: str
    task_status: str
    assignment_type: str | None
    assigned_to_user_id: int | None
    claimed_by: int | None
    claimed_at: datetime | None
    due_at: datetime | None
    reminder_count: int
    allowed_actions: list[dict]
    initiated_by: int
    initiated_at: datetime


class WorkflowInstanceDetailResponse(BaseModel):
    workflow_instance_id: int
    workflow_id: int
    entity_name: str
    entity_record_id: str
    workflow_status: str
    current_node: str | None
    initiated_by: int
    initiated_at: datetime
    completed_at: datetime | None
    history: list[dict]


class ClaimTaskResponse(BaseModel):
    message: str
    task_id: int
    claimed_by: int