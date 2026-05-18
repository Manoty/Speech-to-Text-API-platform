"""
app/domains/webhooks/tasks.py

Celery task that delivers webhook payloads with HMAC signing
and exponential backoff retry.

WHY HMAC signing?
Receivers can verify the payload came from us by checking
the X-Signature header against their secret.
"""

import hashlib
import hmac
import json
import uuid

import httpx

from app.core.logging import get_logger
from app.workers.celery_app import celery_app

logger = get_logger(__name__)

MAX_RESPONSE_BODY = 1000  # chars to store from response


def _sign_payload(secret: str, payload: str) -> str:
    return hmac.new(
        secret.encode(), payload.encode(), hashlib.sha256
    ).hexdigest()


@celery_app.task(
    bind=True,
    max_retries=5,
    name="webhooks.deliver",
)
def deliver_webhook(
    self,
    endpoint_id: str,
    endpoint_url: str,
    secret: str | None,
    job_id: str,
    payload: dict,
) -> None:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.core.config import settings
    from app.domains.webhooks.models import DeliveryStatus, WebhookDelivery

    engine = create_engine(settings.database_url_sync)
    Session = sessionmaker(bind=engine)
    db = Session()

    payload_str = json.dumps(payload)
    headers = {"Content-Type": "application/json", "X-STT-Event": "transcription.completed"}

    if secret:
        headers["X-STT-Signature"] = f"sha256={_sign_payload(secret, payload_str)}"

    attempt = self.request.retries + 1

    try:
        with httpx.Client(timeout=10) as client:
            response = client.post(endpoint_url, content=payload_str, headers=headers)

        success = 200 <= response.status_code < 300
        delivery = WebhookDelivery(
            endpoint_id=uuid.UUID(endpoint_id),
            job_id=uuid.UUID(job_id),
            status=DeliveryStatus.SUCCESS if success else DeliveryStatus.FAILED,
            http_status_code=response.status_code,
            response_body=response.text[:MAX_RESPONSE_BODY],
            attempt_number=attempt,
        )
        db.add(delivery)
        db.commit()

        if not success:
            raise Exception(f"Webhook returned HTTP {response.status_code}")

        logger.info("webhook_delivered", endpoint_id=endpoint_id, job_id=job_id)

    except Exception as exc:
        logger.warning(
            "webhook_delivery_failed",
            endpoint_id=endpoint_id,
            job_id=job_id,
            attempt=attempt,
            error=str(exc),
        )
        delivery = WebhookDelivery(
            endpoint_id=uuid.UUID(endpoint_id),
            job_id=uuid.UUID(job_id),
            status=DeliveryStatus.FAILED,
            attempt_number=attempt,
            error_message=str(exc),
        )
        db.add(delivery)
        db.commit()

        # Exponential backoff: 60s, 120s, 240s, 480s, 960s
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))
    finally:
        db.close()