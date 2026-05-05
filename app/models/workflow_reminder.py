from datetime import datetime
from sqlalchemy import Integer, ForeignKey, Text, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base


class WorkflowReminder(Base):
    """
    Log of every reminder sent by the workflow initiator.
    Does not extend AuditMixin – reminders are immutable logs, not editable records.
    """
    __tablename__ = "wf_reminder"

    workflow_reminder_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    workflow_instance_id: Mapped[int] = mapped_column(
        ForeignKey("wf_instance.workflow_instance_id"), nullable=False, index=True
    )
    workflow_task_id: Mapped[int] = mapped_column(
        ForeignKey("wf_task.workflow_task_id"), nullable=False
    )
    org_id: Mapped[int] = mapped_column(Integer, nullable=False)
    reminder_sent_by: Mapped[int] = mapped_column(Integer, nullable=False)
    reminder_sent_to: Mapped[int] = mapped_column(Integer, nullable=False)
    reminder_message: Mapped[str | None] = mapped_column(Text)
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # PENDING | SENT | FAILED
    notification_status: Mapped[str | None] = mapped_column(String(50))