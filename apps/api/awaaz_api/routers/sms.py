"""SMS fallback dispatch endpoint (operator-triggered)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, status
from pydantic import BaseModel
from sqlalchemy import text

from awaaz_api.deps import DbDep
from awaaz_api.observability import get_logger

router = APIRouter(prefix="/v1/orgs/{org_id}/stores/{store_id}/sms", tags=["sms"])
_log = get_logger("awaaz.sms")


class SmsRequest(BaseModel):
    order_id: UUID
    body: str
    template: str | None = None


@router.post("", status_code=status.HTTP_202_ACCEPTED)
async def send_sms(
    org_id: UUID,
    store_id: UUID,
    payload: SmsRequest,
    db: DbDep,
) -> dict[str, str]:
    """Push a fallback SMS request onto the queue.  Worker delivers via SendPK."""

    qid = (
        await db.execute(
            text(
                """
                INSERT INTO retry_queues (org_id, store_id, order_id, channel, attempt,
                                          scheduled_for, payload)
                VALUES (:org, :sid, :oid, 'sms', 1, now(), :payload::jsonb)
                RETURNING id
                """
            ),
            {
                "org": org_id,
                "sid": store_id,
                "oid": payload.order_id,
                "payload": {"body": payload.body, "template": payload.template},
            },
        )
    ).scalar_one()
    return {"queue_id": str(qid)}
