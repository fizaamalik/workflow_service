import httpx
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)


class EntityServiceClient:
    """
    Calls the Entity Service to sync workflow status back to the business entity record.
    Uses a service-to-service token in addition to the user JWT.
    """

    async def update_workflow_status(
        self,
        entity_name: str,
        entity_record_id: str,
        payload: dict,
        auth_header: str,
    ) -> dict | None:
        headers = {
            "Authorization": auth_header,
            "X-Service-Token": settings.ENTITY_SERVICE_TOKEN,
        }
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                resp = await client.patch(
                    f"{settings.ENTITY_SERVICE_URL}/api/v1/{entity_name}/{entity_record_id}/workflow-status",
                    json=payload,
                    headers=headers,
                )
                resp.raise_for_status()
                return resp.json()
        except httpx.HTTPError as e:
            # Log but do not fail the workflow – entity sync is best-effort
            logger.error(
                "EntityServiceClient.update_workflow_status failed for %s/%s: %s",
                entity_name, entity_record_id, str(e),
            )
            return None