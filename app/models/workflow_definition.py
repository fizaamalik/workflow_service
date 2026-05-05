from sqlalchemy import String, Integer, Boolean, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base, AuditMixin


class WorkflowDefinition(Base, AuditMixin):
    """
    Master workflow definition. One definition can have multiple versions.
    A workflow is linked to a specific entity (table) and triggered on a specific action.
    Only one published version per org+entity+trigger_action is active at runtime.
    """
    __tablename__ = "wf_workflow_definition"

    workflow_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    workflow_code: Mapped[str] = mapped_column(String(100), nullable=False)
    workflow_name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)

    # Entity binding – which table this workflow governs
    entity_name: Mapped[str] = mapped_column(String(150), nullable=False)
    entity_table_name: Mapped[str] = mapped_column(String(150), nullable=False)

    # What event triggers this workflow (e.g., SUBMIT, CREATE, UPDATE)
    trigger_type: Mapped[str] = mapped_column(String(50), nullable=False)   # MANUAL, AUTO
    trigger_action: Mapped[str] = mapped_column(String(100), nullable=False)  # SUBMIT, CREATE, etc.

    # Versioning – draft a new version without disrupting active instances
    version_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_published: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Workflow-level feature flags
    allow_parallel_approval: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    allow_delegation: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    allow_send_back: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    allow_reminder: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (
        UniqueConstraint("org_id", "workflow_code", "version_no", name="uq_wf_code_version"),
    )