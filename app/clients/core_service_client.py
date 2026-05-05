import httpx
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)


class CoreServiceClient:
    """
    Calls the Core Service for user/role data.
    All calls forward the caller's JWT so the core service can enforce its own authz.
    """

    async def get_users_by_role(self, role_id: int, auth_header: str) -> list[dict]:
        """Return list of {user_id, username, email} for the given role."""
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                resp = await client.get(
                    f"{settings.CORE_SERVICE_URL}/api/v1/roles/{role_id}/users",
                    headers={"Authorization": auth_header},
                )
                resp.raise_for_status()
                data = resp.json()
                return data.get("data", [])
        except httpx.HTTPError as e:
            logger.error("CoreServiceClient.get_users_by_role failed: %s", str(e))
            return []

    async def get_user_by_id(self, user_id: int, auth_header: str) -> dict | None:
        """Return user detail or None if not found."""
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                resp = await client.get(
                    f"{settings.CORE_SERVICE_URL}/api/v1/users/{user_id}",
                    headers={"Authorization": auth_header},
                )
                if resp.status_code == 404:
                    return None
                resp.raise_for_status()
                return resp.json().get("data")
        except httpx.HTTPError as e:
            logger.error("CoreServiceClient.get_user_by_id failed: %s", str(e))
            return None
