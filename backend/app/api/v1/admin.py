import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_password_hash
from app.models.user import User, UserRole
from app.schemas.auth import CreateStaffRequest, UpdateStaffRequest, UserResponse
from app.api.v1.deps import require_admin
from app.services.audit import record_audit_event

router = APIRouter()


@router.get("/staff", response_model=List[UserResponse], tags=["Admin"])
async def list_staff_members(
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """
    List all staff and admin accounts for the organization.
    Strictly restricted to Admin role.
    """
    query = (
        select(User)
        .where(User.role.in_([UserRole.ADMIN, UserRole.STAFF]))
        .order_by(User.created_at.desc())
    )
    result = await db.execute(query)
    users = result.scalars().all()
    return [UserResponse.model_validate(u) for u in users]


@router.post("/staff", response_model=UserResponse, status_code=status.HTTP_201_CREATED, tags=["Admin"])
async def create_staff_member(
    payload: CreateStaffRequest,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    """
    Create a new operational staff or admin member.
    Enforces email uniqueness, password complexity policy, and logs an audit record.
    Strictly restricted to Admin role.
    """
    normalized_email = payload.email.lower().strip()

    # Check for duplicate normalized email
    query = select(User).where(User.email == normalized_email)
    existing_user = (await db.execute(query)).scalar_one_or_none()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user account with this email address already exists.",
        )

    new_user = User(
        email=normalized_email,
        hashed_password=get_password_hash(payload.password),
        full_name=payload.full_name,
        role=payload.role,
        is_active=payload.is_active,
    )
    db.add(new_user)
    await db.flush()

    # Record immutable audit event
    await record_audit_event(
        db,
        entity_type="user",
        entity_id=new_user.id,
        action="CREATE_STAFF",
        actor_user_id=current_admin.id,
        changes={
            "email": new_user.email,
            "role": new_user.role.value,
            "full_name": new_user.full_name,
            "is_active": new_user.is_active,
        },
    )

    await db.commit()
    await db.refresh(new_user)
    return UserResponse.model_validate(new_user)


@router.patch("/staff/{user_id}", response_model=UserResponse, tags=["Admin"])
async def update_staff_member(
    user_id: uuid.UUID,
    payload: UpdateStaffRequest,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    """
    Update a staff member's role or active status.
    Prevents self-deactivation and preserves at least one active administrator.
    """
    query = select(User).where(User.id == user_id)
    target_user = (await db.execute(query)).scalar_one_or_none()
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User account not found.",
        )

    # Disallow managing customer users via staff admin API
    if target_user.role == UserRole.CUSTOMER:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Customer accounts cannot be administered through the staff endpoint.",
        )

    # Prevent an admin from deactivating themselves
    if target_user.id == current_admin.id and payload.is_active is False:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Administrators cannot deactivate their own account.",
        )

    # Prevent removing the last active admin
    if payload.role == UserRole.STAFF and target_user.role == UserRole.ADMIN:
        admin_count_query = select(func.count(User.id)).where(
            User.role == UserRole.ADMIN,
            User.is_active == True,  # noqa: E712
            User.id != target_user.id,
        )
        remaining_admins = (await db.execute(admin_count_query)).scalar_one()
        if remaining_admins == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot demote the sole active administrator.",
            )

    changes = {}
    if payload.full_name is not None and payload.full_name != target_user.full_name:
        changes["full_name"] = {"from": target_user.full_name, "to": payload.full_name}
        target_user.full_name = payload.full_name

    if payload.role is not None and payload.role != target_user.role:
        changes["role"] = {"from": target_user.role.value, "to": payload.role.value}
        target_user.role = payload.role

    if payload.is_active is not None and payload.is_active != target_user.is_active:
        changes["is_active"] = {"from": target_user.is_active, "to": payload.is_active}
        target_user.is_active = payload.is_active

    if changes:
        await record_audit_event(
            db,
            entity_type="user",
            entity_id=target_user.id,
            action="UPDATE_STAFF",
            actor_user_id=current_admin.id,
            changes=changes,
        )
        await db.commit()
        await db.refresh(target_user)

    return UserResponse.model_validate(target_user)

