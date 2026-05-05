from datetime import datetime
from sqlalchemy import String, Integer, ForeignKey, DateTime, JSON, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base, AuditMixin


class WorkflowInstance(Base, AuditMixin):
    """
    A running execution of a workflow for a specific entity record.
    Unique per (workflow_id, entity_name, entity_record_id) – one active instance at a time.

    workflow_status values:
      IN_PROGRESS | APPROVED | REJECTED | CANCELLED
    """
    __tablename__ = "wf_instance"

    workflow_instance_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    workflow_id: Mapped[int] = mapped_column(
        ForeignKey("wf_workflow_definition.workflow_id"), nullable=False, index=True
    )

    entity_name: Mapped[str] = mapped_column(String(150), nullable=False)
    entity_table_name: Mapped[str] = mapped_column(String(150), nullable=False)
    entity_record_id: Mapped[str] = mapped_column(String(100), nullable=False)

    current_node_id: Mapped[int | None] = mapped_column(ForeignKey("wf_node.node_id"), index=True)
    # IN_PROGRESS | APPROVED | REJECTED | CANCELLED
    workflow_status: Mapped[str] = mapped_column(String(50), nullable=False, default="IN_PROGRESS")

    initiated_by: Mapped[int] = mapped_column(Integer, nullable=False)
    initiated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_by: Mapped[int | None] = mapped_column(Integer)

    last_action_code: Mapped[str | None] = mapped_column(String(100))
    last_action_by: Mapped[int | None] = mapped_column(Integer)
    last_action_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Snapshot of the payload at initiation; also used for DYNAMIC_USER resolution
    metadata_json: Mapped[dict | None] = mapped_column("metadata", JSON)

    __table_args__ = (
        # Prevent duplicate active instances for the same entity record
        UniqueConstraint(
            "workflow_id", "entity_name", "entity_record_id",
            name="uq_workflow_entity_record"
        ),
    )