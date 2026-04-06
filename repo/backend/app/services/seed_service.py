from __future__ import annotations
import uuid
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User
from app.models.property import Property, Unit
from app.models.resident import Resident, Address
from app.services.auth_service import hash_password

SEED_ADMIN = {"username": "admin", "password": "Admin@Harbor2026", "role": "admin"}
SEED_MANAGER = {"username": "manager", "password": "Manager@Hbr2026", "role": "property_manager"}
SEED_CLERK = {"username": "clerk", "password": "Clerk@@Harbor2026", "role": "accounting_clerk"}
SEED_MAINT = {"username": "maintenance", "password": "Maint@@Harbor2026", "role": "maintenance_dispatcher"}
SEED_RESIDENT = {"username": "resident1", "password": "Resident@Hbr2026", "role": "resident"}

async def seed_default_admin(db: AsyncSession) -> None:
    count_result = await db.execute(select(func.count()).select_from(User))
    if count_result.scalar_one() > 0:
        return

    # Seed users for each role
    users = {}
    for seed in [SEED_ADMIN, SEED_MANAGER, SEED_CLERK, SEED_MAINT, SEED_RESIDENT]:
        user = User(
            username=seed["username"],
            password_hash=hash_password(seed["password"]),
            role=seed["role"],
            is_active=True,
        )
        db.add(user)
        await db.flush()
        users[seed["role"]] = user

    # Seed a property
    prop = Property(
        name="HarborView Residences",
        address="100 Harbor Drive, Seaside, CA 93955",
        billing_day=1,
        late_fee_days=10,
    )
    db.add(prop)
    await db.flush()

    # Seed units
    unit_101 = Unit(property_id=prop.id, unit_number="101", status="active")
    unit_102 = Unit(property_id=prop.id, unit_number="102", status="active")
    db.add_all([unit_101, unit_102])
    await db.flush()

    # Seed a resident linked to the resident user and unit
    resident = Resident(
        user_id=users["resident"].id,
        unit_id=unit_101.id,
        first_name="Jane",
        last_name="Doe",
    )
    db.add(resident)
    await db.flush()

    # Seed an address for the resident
    address = Address(
        resident_id=resident.id,
        address_type="mailing",
        line1="100 Harbor Drive, Unit 101",
        city="Seaside",
        state="CA",
        zip_code="93955",
        is_primary=True,
    )
    db.add(address)
    await db.flush()
