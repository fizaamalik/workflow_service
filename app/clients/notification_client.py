import httpx
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)


class NotificationClient:
    """
    Fires-and-forgets notification payloads to the notification service.
    Failures are logged but never bubble up to the caller.
    """

    async def send(self, payload: dict) -> dict | None:
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                resp = await client.post(
                    f"{settings.NOTIFICATION_SERVICE_URL}/api/v1/notify",
                    json=payload,
                )
                resp.raise_for_status()
                return resp.json()
        except httpx.HTTPError as e:
            logger.error("NotificationClient.send failed: %s", str(e))
            return None