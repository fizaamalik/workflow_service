from sqlalchemy import String, Integer, Boolean, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base, AuditMixin


class WorkflowTransition(Base, AuditMixin):
    """
    Directed edge: from_node --[action_code]--> to_node.

    If condition_expression is set it is a Python-safe expression evaluated
    against the instance metadata dict; highest-priority matching transition wins.
    is_default = True is the fallback when no condition matches.
    """
    __tablename__ = "wf_transition"

    transition_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    workflow_id: Mapped[int] = mapped_column(
        ForeignKey("wf_workflow_definition.workflow_id"), nullable=False, index=True
    )
    from_node_id: Mapped[int] = mapped_column(ForeignKey("wf_node.node_id"), nullable=False)
    action_code: Mapped[str] = mapped_column(String(100), nullable=False)
    to_node_id: Mapped[int] = mapped_column(ForeignKey("wf_node.node_id"), nullable=False)
    # optional CEL / simple Python expression evaluated against payload
    condition_expression: Mapped[str | None] = mapped_column(Text)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)