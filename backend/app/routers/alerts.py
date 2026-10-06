from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query
from sqlalchemy import func, select, update

from .. import serializers
from ..deps import DB, CurrentUser
from ..errors import not_found
from ..models import Alert, utcnow

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("")
def list_alerts(
    db: DB,
    user: CurrentUser,
    unread_only: bool = False,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> dict:
    query = select(Alert).where(Alert.recipient_user_id == user.id)
    if unread_only:
        query = query.where(Alert.is_read.is_(False))
    alerts = db.scalars(query.order_by(Alert.created_at.desc(), Alert.id.desc()).limit(limit))
    unread = db.scalar(select(func.count(Alert.id)).where(Alert.recipient_user_id == user.id, Alert.is_read.is_(False)))
    return {"items": [serializers.alert(a) for a in alerts], "unread_count": unread or 0}


@router.patch("/{alert_id}/read")
def mark_read(alert_id: int, db: DB, user: CurrentUser) -> dict:
    alert = db.get(Alert, alert_id)
    # Same response for "missing" and "not yours" so alert ids cannot be probed.
    if alert is None or alert.recipient_user_id != user.id:
        raise not_found("Alert")
    if not alert.is_read:
        alert.is_read = True
        alert.read_at = utcnow()
        db.commit()
    return {"alert": serializers.alert(alert)}


@router.post("/read-all")
def mark_all_read(db: DB, user: CurrentUser) -> dict:
    result = db.execute(
        update(Alert)
        .where(Alert.recipient_user_id == user.id, Alert.is_read.is_(False))
        .values(is_read=True, read_at=utcnow())
    )
    db.commit()
    return {"updated": result.rowcount}
