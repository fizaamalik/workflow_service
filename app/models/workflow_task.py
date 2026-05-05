from datetime import datetime
from sqlalchemy import String, Integer, ForeignKey, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base, AuditMixin


class WorkflowTask(Base, AuditMixin):
    """
    A single pending work item for an approver at a specific node.
    One task per node per instance. For ROLE/ALL_USERS assignment,
    the actual candidate list is stored in wf_task_candidate_user.

    task_status: PENDING | CLAIMED | COMPLETED | SKIPPED | EXPIRED
    """
    __tablename__ = "wf_task"

    workflow_task_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    workflow_instance_id: Mapped[int] = mapped_column(
        ForeignKey("wf_instance.workflow_instance_id"), nullable=False, index=True
    )
    workflow_id: Mapped[int] = mapped_column(
        ForeignKey("wf_workflow_definition.workflow_id"), nullable=False
    )
    node_id: Mapped[int] = mapped_column(ForeignKey("wf_node.node_id"), nullable=False)

    # PENDING | CLAIMED | COMPLETED | SKIPPED | EXPIRED
    task_status: Mapped[str] = mapped_column(String(50), nullable=False, default="PENDING")

    # Direct assignment (USER / DYNAMIC_USER)
    assigned_to_user_id: Mapped[int | None] = mapped_column(Integer, index=True)
    # Role-level assignment (used alongside candidate table for ROLE assignment)
    assigned_to_role_id: Mapped[int | None] = mapped_column(Integer)
    assignment_type: Mapped[str | None] = mapped_column(String(50))
    assignment_strategy: Mapped[str | None] = mapped_column(String(50))

    # Claim tracking (for ROLE/ALL_USERS where anyone in the pool can claim)
    claimed_by: Mapped[int | None] = mapped_column(Integer)
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Action result
    action_taken: Mapped[str | None] = mapped_column(String(100))
    action_taken_by: Mapped[int | None] = mapped_column(Integer)
    action_taken_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    comments: Mapped[str | None] = mapped_column(Text)

    # SLA
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reminder_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_reminder_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))