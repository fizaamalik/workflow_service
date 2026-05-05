from datetime import datetime
from sqlalchemy import String, Integer, ForeignKey, Text, DateTime, JSON
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base, AuditMixin


class WorkflowHistory(Base, AuditMixin):
    """
    Immutable audit trail of every action taken on a workflow instance.
    Includes IP, user-agent for compliance/audit purposes.
    """
    __tablename__ = "wf_action_history"

    workflow_action_history_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    workflow_instance_id: Mapped[int] = mapped_column(
        ForeignKey("wf_instance.workflow_instance_id"), nullable=False, index=True
    )
    workflow_task_id: Mapped[int | None] = mapped_column(ForeignKey("wf_task.workflow_task_id"))

    from_node_id: Mapped[int | None] = mapped_column(Integer)
    to_node_id: Mapped[int | None] = mapped_column(Integer)
    action_code: Mapped[str] = mapped_column(String(100), nullable=False)
    action_by: Mapped[int] = mapped_column(Integer, nullable=False)
    action_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    comments: Mapped[str | None] = mapped_column(Text)
    action_payload: Mapped[dict | None] = mapped_column(JSON)
    ip_address: Mapped[str | None] = mapped_column(String(100))
    user_agent: Mapped[str | None] = mapped_column(Text)