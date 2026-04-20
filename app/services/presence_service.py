from datetime import datetime

from sqlmodel import Session, select

from app.core.config import PresenceMode
from app.models.entities import PresenceRecord


def record_presence(
    session: Session,
    user_id: str,
    context_id: str,
    mode: PresenceMode,
    source: str,
    confidence: float | None,
    camera_id: str,
):
    now = datetime.utcnow()
    today = now.date()

    latest_today = session.exec(
        select(PresenceRecord).where(
            PresenceRecord.user_id == user_id,
            PresenceRecord.context_id == context_id,
            PresenceRecord.presence_date == today,
        )
    ).all()

    latest_record = latest_today[-1] if latest_today else None

    if mode == PresenceMode.CHECKIN_ONLY:
        if latest_record:
            raise ValueError("Presence already marked for this user/context today")

        rec = PresenceRecord(
            user_id=user_id,
            context_id=context_id,
            mode=mode.value,
            presence_date=today,
            checkin_at=now,
            source=source,
            confidence=confidence,
            camera_id=camera_id,
            notes="present",
        )
        session.add(rec)
        session.commit()
        session.refresh(rec)
        return {
            "action": "present",
            "record_id": rec.id,
            "checkin_at": rec.checkin_at,
            "checkout_at": rec.checkout_at,
            "duration_seconds": rec.duration_seconds,
        }

    COOLDOWN_SECONDS = 60 

    # 1. No records today? Start the first Check-In.
    if latest_record is None:
        rec = PresenceRecord(
            user_id=user_id,
            context_id=context_id,
            mode=mode.value,
            presence_date=today,
            checkin_at=now,
            source=source,
            confidence=confidence,
            camera_id=camera_id,
            notes="checkin",
        )
        session.add(rec)
        session.commit()
        session.refresh(rec)
        return {
            "action": "checkin",
            "record_id": rec.id,
            "checkin_at": rec.checkin_at,
            "checkout_at": rec.checkout_at,
            "duration_seconds": rec.duration_seconds,
        }

    # 2. Are they currently checked in? Do a Check-Out.
    if latest_record.checkout_at is None:
        # THE FIX: Prevent impossibly short shifts!
        time_since_checkin = (now - latest_record.checkin_at).total_seconds()
        if time_since_checkin < COOLDOWN_SECONDS:
            raise ValueError(f"Scan ignored. You just checked in! Wait {int(COOLDOWN_SECONDS - time_since_checkin)}s.")

        latest_record.checkout_at = now
        latest_record.duration_seconds = int(time_since_checkin)
        latest_record.notes = "checkout"
        if confidence is not None:
            latest_record.confidence = confidence
        latest_record.camera_id = camera_id

        session.add(latest_record)
        session.commit()
        session.refresh(latest_record)

        return {
            "action": "checkout",
            "record_id": latest_record.id,
            "checkin_at": latest_record.checkin_at,
            "checkout_at": latest_record.checkout_at,
            "duration_seconds": latest_record.duration_seconds,
        }

    # 3. IF WE REACH THIS POINT: They already checked out earlier. 
    # THE FIX: Prevent them from instantly re-checking in right after checking out!
    time_since_checkout = (now - latest_record.checkout_at).total_seconds()
    if time_since_checkout < COOLDOWN_SECONDS:
         raise ValueError(f"Scan ignored. You just checked out! Wait {int(COOLDOWN_SECONDS - time_since_checkout)}s.")

    # They are coming back from lunch or a break! Start a NEW shift.
    new_rec = PresenceRecord(
        user_id=user_id,
        context_id=context_id,
        mode=mode.value,
        presence_date=today,
        checkin_at=now,
        source=source,
        confidence=confidence,
        camera_id=camera_id,
        notes="return_checkin",
    )
    session.add(new_rec)
    session.commit()
    session.refresh(new_rec)

    return {
        "action": "checkin",
        "record_id": new_rec.id,
        "checkin_at": new_rec.checkin_at,
        "checkout_at": new_rec.checkout_at,
        "duration_seconds": new_rec.duration_seconds,
    }