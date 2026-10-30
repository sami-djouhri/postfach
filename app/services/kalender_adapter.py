import logging
from dataclasses import dataclass

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


@dataclass
class KalenderPushResult:
    ok: bool
    status: str
    message: str | None = None


class KalenderAdapter:
    """HTTP client for the Kalender service. Pushes deadlines as calendar events.

    Graceful degradation: errors are logged but never block the caller.
    """

    def __init__(self):
        self.base_url = settings.KALENDER_BASE_URL
        self.feed_token = settings.KALENDER_FEED_TOKEN or settings.FEED_TOKEN
        self.password = settings.KALENDER_PASSWORD

    def is_configured(self) -> bool:
        return bool(self.base_url)

    async def push_deadline(
        self,
        typ: str,
        datum: str,
        beschreibung: str,
        letter_id: int,
    ) -> KalenderPushResult:
        """Push a deadline to the Kalender service as a calendar event.

        Returns a small status object. Errors are logged and never raised.
        """
        if not self.is_configured():
            logger.debug("Kalender not configured: skipping deadline push")
            return KalenderPushResult(
                ok=False,
                status="skipped",
                message="Kalender nicht konfiguriert",
            )

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                headers = await self._auth_headers(client)
                resp = await client.post(
                    f"{self.base_url}/api/integrations/postfach/deadlines",
                    json={
                        "letter_id": letter_id,
                        "typ": typ,
                        "datum": datum,
                        "beschreibung": beschreibung,
                    },
                    params={"feed_token": self.feed_token} if self.feed_token else {},
                    headers=headers,
                )
                if resp.status_code < 300:
                    payload = resp.json()
                    logger.info(
                        "Pushed deadline to Kalender: %s on %s (letter #%d)",
                        beschreibung, datum, letter_id,
                    )
                    return KalenderPushResult(
                        ok=True,
                        status=payload.get("status", "created"),
                        message=str(payload.get("event_id")),
                    )
                logger.warning(
                    "Kalender returned %d for deadline push: %s",
                    resp.status_code, resp.text[:200],
                )
                return KalenderPushResult(
                    ok=False,
                    status="failed",
                    message=f"Kalender HTTP {resp.status_code}",
                )
        except Exception as e:
            logger.warning("Could not push deadline to Kalender: %s", e)
            return KalenderPushResult(ok=False, status="failed", message=str(e))

    async def _auth_headers(self, client: httpx.AsyncClient) -> dict[str, str]:
        if self.feed_token:
            return {"X-Feed-Token": self.feed_token}
        if not self.password:
            return {}

        resp = await client.post(
            f"{self.base_url}/api/auth/login",
            json={"password": self.password},
        )
        if resp.status_code >= 300:
            logger.warning(
                "Kalender login failed with HTTP %d: %s",
                resp.status_code,
                resp.text[:200],
            )
            return {}
        token = resp.json().get("access_token")
        return {"Authorization": f"Bearer {token}"} if token else {}
