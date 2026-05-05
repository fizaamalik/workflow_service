from sqlalchemy import String, Integer, Boolean, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base, AuditMixin


class WorkflowAction(Base, AuditMixin):
    """
    Actions permitted on a node (e.g. APPROVE, REJECT, SEND_BACK, REQUEST_INFO).
    The transition table maps action_code -> next_node.
    """
    __tablename__ = "wf_node_action"

    node_action_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    node_id: Mapped[int] = mapped_column(ForeignKey("wf_node.node_id"), nullable=False, index=True)

    action_code: Mapped[str] = mapped_column(String(100), nullable=False)
    action_name: Mapped[str] = mapped_column(String(150), nullable=False)
    requires_comment: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    requires_attachment: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_positive_action: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_negative_action: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    __table_args__ = (
        UniqueConstraint("node_id", "action_code", name="uq_node_action"),
    )