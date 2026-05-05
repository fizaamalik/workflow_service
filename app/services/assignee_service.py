import logging
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.workflow_node import WorkflowNode
from app.clients.core_service_client import CoreServiceClient
from app.core.exceptions import BusinessException

logger = logging.getLogger(__name__)


class AssigneeService:
    """
    Resolves the concrete list of user IDs that should be assigned a task
    for a given node + payload combination.

    Rules:
      USER         → returns [assigned_user_id]
      DYNAMIC_USER → reads the field named dynamic_assignment_field from payload
      ROLE         → fetches all users of assigned_role_id from core-service,
                     then applies assignment_strategy:
                       FIRST_AVAILABLE – returns first user only
                       ALL_USERS       – returns every user in the role
                       ROUND_ROBIN     – (future) returns single user by rotation
    """

    async def resolve_assignees(
        self,
        db: AsyncSession,  # kept for future ROUND_ROBIN state tracking
        node: WorkflowNode,
        payload: dict,
        auth_header: str,
    ) -> list[int]:
        assignment_type = (node.assignment_type or "").upper()

        if assignment_type == "USER":
            if not node.assigned_user_id:
                raise BusinessException(
                    "assigned_user_id is required for USER assignment",
                    code="ASSIGNMENT_CONFIG_ERROR",
                )
            return [node.assigned_user_id]

        if assignment_type == "DYNAMIC_USER":
            if not node.dynamic_assignment_field:
                raise BusinessException(
                    "dynamic_assignment_field is required for DYNAMIC_USER assignment",
                    code="ASSIGNMENT_CONFIG_ERROR",
                )
            value = payload.get(node.dynamic_assignment_field)
            if value is None:
                raise BusinessException(
                    f"Field '{node.dynamic_assignment_field}' missing in payload; "
                    "required for dynamic user assignment",
                    code="DYNAMIC_ASSIGNMENT_FIELD_MISSING",
                )
            try:
                return [int(value)]
            except (ValueError, TypeError):
                raise BusinessException(
                    f"Field '{node.dynamic_assignment_field}' must be a valid integer user_id",
                    code="DYNAMIC_ASSIGNMENT_FIELD_INVALID",
                )

        if assignment_type == "ROLE":
            if not node.assigned_role_id:
                raise BusinessException(
                    "assigned_role_id is required for ROLE assignment",
                    code="ASSIGNMENT_CONFIG_ERROR",
                )
            users = await CoreServiceClient().get_users_by_role(
                node.assigned_role_id, auth_header
            )
            if not users:
                raise BusinessException(
                    f"No active users found for role_id={node.assigned_role_id}. "
                    "Cannot create task.",
                    code="NO_ROLE_USERS",
                )

            strategy = (node.assignment_strategy or "FIRST_AVAILABLE").upper()
            if strategy == "ALL_USERS":
                return [int(u["user_id"]) for u in users]
            # FIRST_AVAILABLE and ROUND_ROBIN (fallback) → first user
            return [int(users[0]["user_id"])]

        raise BusinessException(
            f"Unsupported or missing assignment_type '{node.assignment_type}' "
            f"on node '{node.node_code}'",
            code="UNSUPPORTED_ASSIGNMENT_TYPE",
        )