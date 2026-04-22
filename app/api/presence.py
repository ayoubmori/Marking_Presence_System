import csv
from datetime import date, datetime
from io import StringIO

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from sqlmodel import Session, select

from app.core.config import PresenceMode, get_settings
from app.core.database import get_session
from app.models.entities import PresencePolicy, PresenceRecord, User, VerificationChallenge
from app.schemas.presence import PolicyUpsert, TestQrRequest, UserCreate
from app.services.email_service import email_delivery_mode, send_qr_email
from app.services.real_face_provider import RealFaceProvider
from app.services.presence_service import record_presence
from app.services.qr_challenge_service import (
    build_qr_token,
    render_qr_png,
    token_hash_of,
    verify_qr_token,
)


router = APIRouter(prefix="/presence", tags=["presence"])
settings = get_settings()
face_provider = RealFaceProvider()


def resolve_mode(session: Session, context_id: str) -> PresenceMode:
    policy = session.exec(
        select(PresencePolicy).where(
            PresencePolicy.context_id == context_id,
            PresencePolicy.active == True,  # noqa: E712
        )
    ).first()

    if policy:
        return PresenceMode(policy.mode)

    return settings.default_presence_mode


def issue_qr_challenge(
    *,
    session: Session,
    background_tasks: BackgroundTasks,
    user: User,
    context_id: str,
):
    pending = session.exec(
        select(VerificationChallenge).where(
            VerificationChallenge.user_id == user.id,
            VerificationChallenge.context_id == context_id,
            VerificationChallenge.status == "pending",
        )
    ).all()

    for item in pending:
        item.status = "cancelled"
        session.add(item)

    token, hashed_token, expires_at, jti = build_qr_token(user.id, context_id)

    challenge = VerificationChallenge(
        jti=jti,
        user_id=user.id,
        context_id=context_id,
        token_hash=hashed_token,
        status="pending",
        expires_at=expires_at,
    )
    session.add(challenge)
    session.commit()
    session.refresh(challenge)

    qr_png = render_qr_png(token)

    background_tasks.add_task(
        send_qr_email,
        user.email,
        user.full_name,
        qr_png,
        context_id,
        expires_at.isoformat(),
    )

    return {
        "expires_at": expires_at.isoformat(),
        "delivery_mode": email_delivery_mode(),
    }


@router.get("/health")
def health():
    return {"ok": True, "service": settings.app_name}


@router.post("/users")
def create_user(payload: UserCreate, session: Session = Depends(get_session)):
    existing = session.get(User, payload.id)
    if existing:
        raise HTTPException(status_code=400, detail="User ID already exists")

    user = User(**payload.model_dump())
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


@router.put("/policies")
def upsert_policy(payload: PolicyUpsert, session: Session = Depends(get_session)):
    existing = session.exec(
        select(PresencePolicy).where(PresencePolicy.context_id == payload.context_id)
    ).first()

    if existing:
        existing.mode = payload.mode.value
        existing.active = payload.active
        session.add(existing)
        session.commit()
        session.refresh(existing)
        return existing

    policy = PresencePolicy(
        context_id=payload.context_id,
        mode=payload.mode.value,
        active=payload.active,
    )
    session.add(policy)
    session.commit()
    session.refresh(policy)
    return policy


@router.get("/records")
def list_records(
    session: Session = Depends(get_session),
    user_id: str | None = None,
    context_id: str | None = None,
):
    statement = select(PresenceRecord)

    if user_id:
        statement = statement.where(PresenceRecord.user_id == user_id)
    if context_id:
        statement = statement.where(PresenceRecord.context_id == context_id)

    return session.exec(statement).all()


@router.post("/identify")
async def identify_face(
    background_tasks: BackgroundTasks,
    context_id: str = Form(...),
    camera_id: str = Form(default="usb-cam-1"),
    image: UploadFile = File(...),
    session: Session = Depends(get_session),
):
    image_bytes = await image.read()
    decision = face_provider.identify(image_bytes)
    mode = resolve_mode(session, context_id)

    if decision.candidate_user_id is None:
        raise HTTPException(status_code=401, detail="Face not recognized")

    # First try finding by ID
    user = session.get(User, decision.candidate_user_id)

    # If that fails, search by their Full Name (which matches your folder name)
    if not user:
        user = session.exec(select(User).where(User.full_name == decision.candidate_user_id)).first()

    if not user or not user.active:
        raise HTTPException(status_code=404, detail=f"User '{decision.candidate_user_id}' not found in database")

    if decision.confidence >= settings.face_auto_accept_threshold:
        try:
            result = record_presence(
                session=session,
                user_id=user.id,
                context_id=context_id,
                mode=mode,
                source="face",
                confidence=decision.confidence,
                camera_id=camera_id,
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

        return {
            "ok": True,
            "verification": "face_accepted",
            "user_id": user.id,
            "full_name": user.full_name,
            "confidence": decision.confidence,
            "reason": decision.reason,
            **result,
        }

    if decision.confidence >= settings.face_qr_fallback_threshold:
        # We NO LONGER send the email here! We just ask for confirmation.
        return {
            "ok": True,
            "verification": "needs_confirmation",  # <-- New State!
            "user_id": user.id,
            "full_name": user.full_name,
            "confidence": decision.confidence,
            "reason": "Needs manual confirmation before sending email",
        }

    raise HTTPException(status_code=401, detail="Face confidence too low")


@router.get("/export")
def export_records_csv(
    session: Session = Depends(get_session),
    user_id: str | None = None,
    context_id: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
):
    statement = (
        select(PresenceRecord, User)
        .join(User, User.id == PresenceRecord.user_id)
        .order_by(PresenceRecord.presence_date.desc(), PresenceRecord.checkin_at.desc())
    )

    if user_id:
        statement = statement.where(PresenceRecord.user_id == user_id)

    if context_id:
        statement = statement.where(PresenceRecord.context_id == context_id)

    if date_from:
        statement = statement.where(PresenceRecord.presence_date >= date_from)

    if date_to:
        statement = statement.where(PresenceRecord.presence_date <= date_to)

    rows = session.exec(statement).all()

    buffer = StringIO()
    writer = csv.writer(buffer)

    writer.writerow([
        "record_id",
        "user_id",
        "full_name",
        "email",
        "user_type",
        "department_or_filiere",
        "context_id",
        "mode",
        "presence_date",
        "checkin_at",
        "checkout_at",
        "duration_seconds",
        "duration_hours",
        "source",
        "confidence",
        "camera_id",
        "notes",
    ])

    for record, user in rows:
        writer.writerow([
            record.id,
            user.id,
            user.full_name,
            user.email,
            user.user_type,
            user.department_or_filiere or "",
            record.context_id,
            record.mode,
            record.presence_date.isoformat() if record.presence_date else "",
            record.checkin_at.isoformat() if record.checkin_at else "",
            record.checkout_at.isoformat() if record.checkout_at else "",
            record.duration_seconds if record.duration_seconds is not None else "",
            round(record.duration_seconds / 3600, 2) if record.duration_seconds is not None else "",
            record.source,
            record.confidence if record.confidence is not None else "",
            record.camera_id or "",
            record.notes or "",
        ])

    filename = f'presence_export_{datetime.utcnow().strftime("%Y%m%d_%H%M%S")}.csv'

    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/send-fallback-email")
def trigger_fallback_email(
    background_tasks: BackgroundTasks,
    user_id: str = Form(...),
    context_id: str = Form(...),
    session: Session = Depends(get_session)
):
    user = session.get(User, user_id)
    if not user or not user.active:
        raise HTTPException(status_code=404, detail="User not found")

    # Now we actually generate the token and send the email!
    qr_info = issue_qr_challenge(
        session=session,
        background_tasks=background_tasks,
        user=user,
        context_id=context_id,
    )
    
    return {
        "ok": True,
        "verification": "qr_sent",
        "user_id": user.id,
        "full_name": user.full_name,
        **qr_info,
    }

@router.post("/verify-qr")
def verify_qr(
    qr_raw: str = Form(...),
    camera_id: str = Form(default="usb-cam-1"),
    session: Session = Depends(get_session),
):
    import jwt  # Import here just in case

    # Clean up the raw string in case the camera added weird spaces
    clean_qr = qr_raw.strip()
    
    try:
        payload = verify_qr_token(clean_qr)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=400, detail="EXPIRED! You scanned an old email.")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"INVALID! The camera misread the QR: {e}")

    hashed_token = token_hash_of(clean_qr)

    challenge = session.exec(
        select(VerificationChallenge).where(
            VerificationChallenge.token_hash == hashed_token,
            VerificationChallenge.status == "pending",
        )
    ).first()

    if not challenge:
        raise HTTPException(status_code=400, detail="Challenge not found or already used")

    if challenge.expires_at < datetime.utcnow():
        challenge.status = "expired"
        session.add(challenge)
        session.commit()
        raise HTTPException(status_code=400, detail="QR challenge expired in database")

    if payload.get("sub") != challenge.user_id or payload.get("context_id") != challenge.context_id:
        raise HTTPException(status_code=400, detail="QR token does not match challenge")

    challenge.status = "used"
    challenge.used_at = datetime.utcnow()
    session.add(challenge)
    session.commit()

    mode = resolve_mode(session, challenge.context_id)
    user = session.get(User, challenge.user_id)

    try:
        result = record_presence(
            session=session,
            user_id=challenge.user_id,
            context_id=challenge.context_id,
            mode=mode,
            source="qr_email_fallback",
            confidence=None,
            camera_id=camera_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {
        "ok": True,
        "verification": "qr_accepted",
        "user_id": user.id,
        "full_name": user.full_name,
        **result,
    }


@router.post("/test/request-qr")
def request_test_qr(
    payload: TestQrRequest,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
):
    if not settings.enable_test_endpoints:
        raise HTTPException(status_code=404, detail="Test endpoints are disabled")

    user = session.get(User, payload.user_id)
    if not user or not user.active:
        raise HTTPException(status_code=404, detail="User not found or inactive")

    qr_info = issue_qr_challenge(
        session=session,
        background_tasks=background_tasks,
        user=user,
        context_id=payload.context_id,
    )

    return {
        "ok": True,
        "message": "Test QR generated",
        "user_id": user.id,
        "full_name": user.full_name,
        **qr_info,
    }
