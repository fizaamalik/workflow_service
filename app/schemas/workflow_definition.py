from pydantic import BaseModel, field_validator, model_validator
from typing import Any


# ── Workflow Definition ──────────────────────────────────────────────────────

class WorkflowCreateRequest(BaseModel):
    workflow_code: str
    workflow_name: str
    description: str | None = None
    entity_name: str
    entity_table_name: str
    trigger_type: str        # MANUAL | AUTO
    trigger_action: str      # SUBMIT | CREATE | UPDATE
    version_no: int = 1

    @field_validator("trigger_type")
    @classmethod
    def validate_trigger_type(cls, v: str) -> str:
        allowed = {"MANUAL", "AUTO"}
        if v.upper() not in allowed:
            raise ValueError(f"trigger_type must be one of {allowed}")
        return v.upper()

    @field_validator("workflow_code", "entity_name", "entity_table_name", "trigger_action")
    @classmethod
    def no_whitespace(cls, v: str) -> str:
        if " " in v.strip():
            raise ValueError("Value must not contain spaces")
        return v.strip()


class WorkflowUpdateRequest(BaseModel):
    workflow_name: str | None = None
    description: str | None = None
    allow_parallel_approval: bool | None = None
    allow_delegation: bool | None = None
    allow_send_back: bool | None = None
    allow_reminder: bool | None = None


class WorkflowResponse(BaseModel):
    workflow_id: int
    workflow_code: str
    workflow_name: str
    description: str | None
    entity_name: str
    entity_table_name: str
    trigger_type: str
    trigger_action: str
    version_no: int
    is_published: bool
    allow_parallel_approval: bool
    allow_delegation: bool
    allow_send_back: bool
    allow_reminder: bool

    model_config = {"from_attributes": True}


# ── Node ─────────────────────────────────────────────────────────────────────

class NodeCreateRequest(BaseModel):
    node_code: str
    node_name: str
    # START | APPROVAL | REVIEW | END_APPROVED | END_REJECTED | END_CANCELLED
    node_type: str
    sequence_no: int | None = None
    is_start_node: bool = False
    is_end_node: bool = False

    # Assignment
    assignment_type: str | None = None    # USER | ROLE | DYNAMIC_USER
    assigned_user_id: int | None = None
    assigned_role_id: int | None = None
    dynamic_assignment_field: str | None = None
    # FIRST_AVAILABLE | ALL_USERS | ROUND_ROBIN
    assignment_strategy: str = "FIRST_AVAILABLE"

    maker_checker_required: bool = True
    allow_self_approval: bool = False
    sla_hours: int | None = None
    escalation_enabled: bool = False
    escalation_after_hours: int | None = None
    escalation_to_role_id: int | None = None

    @field_validator("node_type")
    @classmethod
    def validate_node_type(cls, v: str) -> str:
        allowed = {"START", "APPROVAL", "REVIEW", "END_APPROVED", "END_REJECTED", "END_CANCELLED"}
        if v.upper() not in allowed:
            raise ValueError(f"node_type must be one of {allowed}")
        return v.upper()

    @field_validator("assignment_type")
    @classmethod
    def validate_assignment_type(cls, v: str | None) -> str | None:
        if v is None:
            return v
        allowed = {"USER", "ROLE", "DYNAMIC_USER"}
        if v.upper() not in allowed:
            raise ValueError(f"assignment_type must be one of {allowed}")
        return v.upper()

    @model_validator(mode="after")
    def validate_assignment_fields(self) -> "NodeCreateRequest":
        if self.is_end_node or self.node_type == "START":
            return self
        if self.assignment_type == "USER" and not self.assigned_user_id:
            raise ValueError("assigned_user_id is required when assignment_type=USER")
        if self.assignment_type == "ROLE" and not self.assigned_role_id:
            raise ValueError("assigned_role_id is required when assignment_type=ROLE")
        if self.assignment_type == "DYNAMIC_USER" and not self.dynamic_assignment_field:
            raise ValueError(
                "dynamic_assignment_field is required when assignment_type=DYNAMIC_USER"
            )
        return self


class NodeResponse(BaseModel):
    node_id: int
    workflow_id: int
    node_code: str
    node_name: str
    node_type: str
    sequence_no: int | None
    is_start_node: bool
    is_end_node: bool
    assignment_type: str | None
    assigned_user_id: int | None
    assigned_role_id: int | None
    dynamic_assignment_field: str | None
    assignment_strategy: str
    maker_checker_required: bool
    allow_self_approval: bool
    sla_hours: int | None

    model_config = {"from_attributes": True}


# ── Action ───────────────────────────────────────────────────────────────────

class ActionCreateRequest(BaseModel):
    action_code: str
    action_name: str
    requires_comment: bool = False
    requires_attachment: bool = False
    is_positive_action: bool = False
    is_negative_action: bool = False
    display_order: int = 1

    @model_validator(mode="after")
    def validate_action_polarity(self) -> "ActionCreateRequest":
        if self.is_positive_action and self.is_negative_action:
            raise ValueError("An action cannot be both positive and negative")
        return self


class ActionResponse(BaseModel):
    node_action_id: int
    node_id: int
    action_code: str
    action_name: str
    requires_comment: bool
    requires_attachment: bool
    is_positive_action: bool
    is_negative_action: bool
    display_order: int

    model_config = {"from_attributes": True}


# ── Transition ───────────────────────────────────────────────────────────────

class TransitionCreateRequest(BaseModel):
    from_node_id: int
    action_code: str
    to_node_id: int
    condition_expression: str | None = None
    priority: int = 1
    is_default: bool = False

    @model_validator(mode="after")
    def validate_no_self_loop(self) -> "TransitionCreateRequest":
        if self.from_node_id == self.to_node_id:
            raise ValueError("Transition cannot loop back to the same node")
        return self


class TransitionResponse(BaseModel):
    transition_id: int
    workflow_id: int
    from_node_id: int
    action_code: str
    to_node_id: int
    condition_expression: str | None
    priority: int
    is_default: bool

    model_config = {"from_attributes": True}


# ── Generic responses ────────────────────────────────────────────────────────

class CreatedResponse(BaseModel):
    id: int
    message: str = "Created successfully"


class MessageResponse(BaseModel):
    message: str