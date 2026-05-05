from app.core.exceptions import BusinessException


class MakerCheckerService:
    """
    Enforces the 4-eyes / maker-checker principle:
      – The person who initiated (made) a workflow instance cannot also approve (check) it,
        unless allow_self_approval=True is explicitly configured on the node.
    """

    @staticmethod
    def validate_start(
        initiated_by: int,
        assignees: list[int],
        allow_self_approval: bool,
    ) -> None:
        """
        Called when creating the first task after workflow start.
        If the initiator is in the assignee pool and self-approval is off → reject.
        """
        if not allow_self_approval and initiated_by in assignees:
            raise BusinessException(
                "The workflow initiator cannot be the approver for this step. "
                "Maker-checker rule violated.",
                code="MAKER_CHECKER_VIOLATION",
                status_code=422,
            )

    @staticmethod
    def validate_action(
        actor_user_id: int,
        initiated_by: int,
        assignees: list[int],
        allow_self_approval: bool,
    ) -> None:
        """
        Called when an action (approve/reject/etc.) is submitted on a task.
        Validates both maker-checker and assignment eligibility.
        """
        # 1. Maker ≠ checker
        if not allow_self_approval and actor_user_id == initiated_by:
            raise BusinessException(
                "The workflow initiator cannot act on their own workflow instance. "
                "Maker-checker rule violated.",
                code="MAKER_CHECKER_VIOLATION",
                status_code=422,
            )

        # 2. Must be an eligible assignee or candidate
        if actor_user_id not in assignees:
            raise BusinessException(
                f"User {actor_user_id} is not assigned to this task and cannot act on it.",
                code="NOT_TASK_ASSIGNEE",
                status_code=403,
            )