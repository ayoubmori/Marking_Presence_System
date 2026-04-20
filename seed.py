from sqlmodel import Session, select

from app.core.database import create_db_and_tables, engine
from app.models.entities import PresencePolicy, User

def upsert_user(session: Session, user: User):
    existing = session.get(User, user.id)
    if existing:
        existing.full_name = user.full_name
        existing.email = user.email
        existing.user_type = user.user_type
        existing.department_or_filiere = user.department_or_filiere
        existing.active = user.active
        session.add(existing)
    else:
        session.add(user)

def upsert_policy(session: Session, context_id: str, mode: str):
    existing = session.exec(
        select(PresencePolicy).where(PresencePolicy.context_id == context_id)
    ).first()

    if existing:
        existing.mode = mode
        existing.active = True
        session.add(existing)
    else:
        session.add(PresencePolicy(context_id=context_id, mode=mode, active=True))

def main():
    # 1. Create the database tables if they don't exist
    create_db_and_tables()

    with Session(engine) as session:
        # 2. Add your real team members! 
        # (Make sure 'full_name' matches your folder names exactly)
        upsert_user(
            session,
            User(
                id="USR001",
                full_name="ayoub",
                email="ayoubmori33@gmail.com",  # Replace with real emails later
                user_type="student",
                department_or_filiere="GI",
                active=True,
            ),
        )

        upsert_user(
            session,
            User(
                id="USR002",
                full_name="saida",
                email="saida@example.com",
                user_type="student",
                department_or_filiere="GI",
                active=True,
            ),
        )

        upsert_user(
            session,
            User(
                id="USR003",
                full_name="hasna",
                email="hasna@example.com",
                user_type="student",
                department_or_filiere="GI",
                active=True,
            ),
        )

        upsert_user(
            session,
            User(
                id="USR004",
                full_name="salma",
                email="salma@example.com",
                user_type="student",
                department_or_filiere="GI",
                active=True,
            ),
        )

        # 3. Setup the rules for the scanning context
        upsert_policy(session, "WORK-HQ", "checkin_checkout")

        session.commit()

    print("✅ Database Seed Completed Successfully!")
    print("Registered Users: ayoub, saida, hasna, salma")
    print("Active Contexts: WORK-HQ -> checkin_checkout")

if __name__ == "__main__":
    main()