from sqlalchemy import String, Integer, Boolean, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base, AuditMixin


class WorkflowNode(Base, AuditMixin):
    """
    A step (node) in the workflow graph.

    Node types:
      START         – virtual entry point (no approver needed)
      APPROVAL      – requires an approver action
      REVIEW        – informational review step (can reject/approve)
      END_APPROVED  – terminal node resulting in APPROVED status
      END_REJECTED  – terminal node resulting in REJECTED status
      END_CANCELLED – terminal node resulting in CANCELLED status

    Assignment types:
      USER          – assigned_user_id is used directly
      ROLE          – all users of assigned_role_id are fetched from core-service;
                      assignment_strategy decides who gets the task
      DYNAMIC_USER  – user_id is read from the entity payload field specified in
                      dynamic_assignment_field (e.g., "supervisor_id")
    """
    __tablename__ = "wf_node"

    node_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    workflow_id: Mapped[int] = mapped_column(
        ForeignKey("wf_workflow_definition.workflow_id"), nullable=False, index=True
    )

    node_code: Mapped[str] = mapped_column(String(100), nullable=False)
    node_name: Mapped[str] = mapped_column(String(255), nullable=False)
    # START | APPROVAL | REVIEW | END_APPROVED | END_REJECTED | END_CANCELLED
    node_type: Mapped[str] = mapped_column(String(50), nullable=False)

    sequence_no: Mapped[int | None] = mapped_column(Integer)
    is_start_node: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_end_node: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # --- Assignment ---
    # USER | ROLE | DYNAMIC_USER
    assignment_type: Mapped[str | None] = mapped_column(String(50))
    assigned_user_id: Mapped[int | None] = mapped_column(Integer)
    assigned_role_id: Mapped[int | None] = mapped_column(Integer)
    # For DYNAMIC_USER: name of the field in the entity payload that holds the user_id
    dynamic_assignment_field: Mapped[str | None] = mapped_column(String(150))
    # FIRST_AVAILABLE | ALL_USERS | ROUND_ROBIN
    assignment_strategy: Mapped[str] = mapped_column(String(50), nullable=False, default="FIRST_AVAILABLE")

    # --- Checker/approval rules ---
    maker_checker_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    allow_self_approval: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # --- SLA & escalation ---
    sla_hours: Mapped[int | None] = mapped_column(Integer)
    escalation_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    escalation_after_hours: Mapped[int | None] = mapped_column(Integer)
    escalation_to_role_id: Mapped[int | None] = mapped_column(Integer)

    __table_args__ = (
        UniqueConstraint("workflow_id", "node_code", name="uq_wf_node_code"),
    )