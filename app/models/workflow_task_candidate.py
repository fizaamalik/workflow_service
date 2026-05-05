from sqlalchemy import Integer, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base, AuditMixin


class WorkflowTaskCandidate(Base, AuditMixin):
    """
    For ROLE / ALL_USERS assignment: expanded list of user_ids that are
    eligible to act on the task. Any candidate can claim → complete it.
    """
    __tablename__ = "wf_task_candidate_user"

    task_candidate_user_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    workflow_task_id: Mapped[int] = mapped_column(
        ForeignKey("wf_task.workflow_task_id"), nullable=False, index=True
    )
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    __table_args__ = (
        UniqueConstraint("workflow_task_id", "user_id", name="uq_task_candidate_user"),
    )