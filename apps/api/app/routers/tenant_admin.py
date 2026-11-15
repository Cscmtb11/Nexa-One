import hashlib
import re
import secrets
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from ..db import get_db
from ..dependencies import current_user, organisation_membership
from ..models import (
    AuditEvent, Facility, FinancialYear, GSTRegistration, LegalEntity,
    Membership, OrganisationSetting, Permission, RolePermission,
    User, UserInvitation,
)

router = APIRouter(prefix="/v1/tenant", tags=["tenant administration"])
GSTIN_RE = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$")
PAN_RE = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$")
STATE_CODE_RE = re.compile(r"^[0-9]{2}$")
ALLOWED_ROLES = {"admin", "manager", "accountant", "clinician", "technician", "member"}
SETTING_KEYS = {
    "timezone", "locale", "currency", "date_format", "financial_year_start_month",
    "invoice_prefix", "receipt_prefix", "default_gst_registration_id", "tax_mode",
    "gst_exempt", "organisation_display_name",
}


def _has_permission(db: Session, membership: Membership, code: str) -> bool:
    if membership.role == "platform_admin":
        return True
    return db.query(RolePermission.id).join(Permission, Permission.id == RolePermission.permission_id).filter(
        RolePermission.organisation_id == membership.organisation_id,
        RolePermission.role == membership.role,
        Permission.code == code,
    ).first() is not None


def _admin(membership: Membership, db: Session):
    if not _has_permission(db, membership, "org.manage"):
        raise HTTPException(status_code=403, detail="Missing permission: org.manage")


def _read(membership: Membership, db: Session, code: str = "org.read"):
    if not _has_permission(db, membership, code):
        raise HTTPException(status_code=403, detail=f"Missing permission: {code}")


def _audit(db: Session, membership: Membership, action: str, resource: str, resource_id: str, detail: str):
    db.add(AuditEvent(
        organisation_id=membership.organisation_id,
        actor_user_id=membership.user_id,
        action=action,
        resource_type=resource,
        resource_id=resource_id,
        detail=detail,
    ))


class LegalEntityCreate(BaseModel):
    code: str = Field(min_length=2, max_length=30, pattern=r"^[A-Za-z0-9_-]+$")
    legal_name: str = Field(min_length=2, max_length=200)
    trade_name: str | None = Field(default=None, max_length=200)
    pan: str | None = Field(default=None, pattern=r"^[A-Za-z]{5}[0-9]{4}[A-Za-z]$")
    constitution: str = Field(default="other", max_length=50)
    address_line1: str | None = Field(default=None, max_length=200)
    address_line2: str | None = Field(default=None, max_length=200)
    city: str | None = Field(default=None, max_length=100)
    district: str | None = Field(default=None, max_length=100)
    state_code: str | None = Field(default=None, pattern=r"^[0-9]{2}$")
    state_name: str | None = Field(default=None, max_length=100)
    pincode: str | None = Field(default=None, max_length=10)
    country: str = Field(default="IN", min_length=2, max_length=2)


class GSTRegistrationCreate(BaseModel):
    legal_entity_id: int
    facility_id: int | None = None
    gstin: str = Field(min_length=15, max_length=15)
    registration_type: str = Field(default="regular", pattern=r"^(regular|composition|casual|non_resident|sez)$")
    state_code: str = Field(pattern=r"^[0-9]{2}$")
    effective_from: date | None = None
    effective_to: date | None = None
    is_primary: bool = False


class FinancialYearCreate(BaseModel):
    name: str = Field(min_length=4, max_length=20)
    start_date: date
    end_date: date
    is_current: bool = False


class SettingUpdate(BaseModel):
    value: str = Field(max_length=2000)


class InvitationCreate(BaseModel):
    email: EmailStr
    role: str = "member"


class MembershipRoleUpdate(BaseModel):
    role: str


class InvitationAccept(BaseModel):
    token: str = Field(min_length=32, max_length=128)


class RolePermissionsUpdate(BaseModel):
    permission_codes: list[str] = Field(max_length=100)


@router.get("/legal-entities")
def list_legal_entities(membership: Membership = Depends(organisation_membership), db: Session = Depends(get_db)):
    _read(membership, db)
    return db.query(LegalEntity).filter_by(organisation_id=membership.organisation_id).order_by(LegalEntity.legal_name).all()


@router.post("/legal-entities", status_code=201)
def create_legal_entity(payload: LegalEntityCreate, membership: Membership = Depends(organisation_membership), db: Session = Depends(get_db)):
    _admin(membership, db)
    data = payload.model_dump()
    data["code"] = data["code"].upper()
    if data["pan"]:
        data["pan"] = data["pan"].upper()
        if not PAN_RE.fullmatch(data["pan"]):
            raise HTTPException(status_code=422, detail="Invalid PAN format")
    entity = LegalEntity(organisation_id=membership.organisation_id, **data)
    db.add(entity)
    try:
        db.flush()
        _audit(db, membership, "legal_entity.created", "legal_entity", str(entity.id), f"Created legal entity {entity.code}")
        db.commit()
        db.refresh(entity)
    except Exception:
        db.rollback()
        raise HTTPException(status_code=409, detail="Legal entity code or details conflict")
    return entity


@router.put("/legal-entities/{entity_id}")
def update_legal_entity(entity_id: int, payload: LegalEntityCreate, membership: Membership = Depends(organisation_membership), db: Session = Depends(get_db)):
    _admin(membership, db)
    entity = db.query(LegalEntity).filter_by(id=entity_id, organisation_id=membership.organisation_id).first()
    if not entity:
        raise HTTPException(status_code=404, detail="Legal entity not found")
    data = payload.model_dump()
    data["code"] = data["code"].upper()
    if data["pan"]:
        data["pan"] = data["pan"].upper()
        if not PAN_RE.fullmatch(data["pan"]):
            raise HTTPException(status_code=422, detail="Invalid PAN format")
    for key, value in data.items():
        setattr(entity, key, value)
    _audit(db, membership, "legal_entity.updated", "legal_entity", str(entity.id), f"Updated legal entity {entity.code}")
    try:
        db.commit()
        db.refresh(entity)
    except Exception:
        db.rollback()
        raise HTTPException(status_code=409, detail="Legal entity update conflicts with existing data")
    return entity


@router.get("/gst-registrations")
def list_gst_registrations(membership: Membership = Depends(organisation_membership), db: Session = Depends(get_db)):
    _read(membership, db)
    return db.query(GSTRegistration).filter_by(organisation_id=membership.organisation_id).order_by(GSTRegistration.gstin).all()


@router.post("/gst-registrations", status_code=201)
def create_gst_registration(payload: GSTRegistrationCreate, membership: Membership = Depends(organisation_membership), db: Session = Depends(get_db)):
    _admin(membership, db)
    gstin = payload.gstin.strip().upper()
    if not GSTIN_RE.fullmatch(gstin):
        raise HTTPException(status_code=422, detail="GSTIN format is invalid")
    if gstin[:2] != payload.state_code:
        raise HTTPException(status_code=422, detail="GSTIN state code does not match the supplied state code")
    if payload.effective_from and payload.effective_to and payload.effective_to < payload.effective_from:
        raise HTTPException(status_code=422, detail="Effective-to date cannot precede effective-from date")
    entity = db.query(LegalEntity).filter_by(id=payload.legal_entity_id, organisation_id=membership.organisation_id, is_active=True).first()
    if not entity:
        raise HTTPException(status_code=404, detail="Legal entity not found in this organisation")
    if entity.pan and gstin[2:12] != entity.pan:
        raise HTTPException(status_code=422, detail="GSTIN PAN segment does not match the legal entity PAN")
    if payload.facility_id is not None:
        facility = db.query(Facility).filter_by(id=payload.facility_id, organisation_id=membership.organisation_id).first()
        if not facility:
            raise HTTPException(status_code=404, detail="Facility not found in this organisation")
    if db.query(GSTRegistration).filter_by(gstin=gstin).first():
        raise HTTPException(status_code=409, detail="GSTIN is already registered")
    if payload.is_primary:
        db.query(GSTRegistration).filter_by(organisation_id=membership.organisation_id, is_primary=True).update({"is_primary": False})
    row = GSTRegistration(organisation_id=membership.organisation_id, gstin=gstin, **payload.model_dump(exclude={"gstin"}))
    db.add(row)
    _audit(db, membership, "gst_registration.created", "gst_registration", gstin, "Added GST registration")
    db.commit()
    db.refresh(row)
    return row


@router.get("/financial-years")
def list_financial_years(membership: Membership = Depends(organisation_membership), db: Session = Depends(get_db)):
    _read(membership, db)
    return db.query(FinancialYear).filter_by(organisation_id=membership.organisation_id).order_by(FinancialYear.start_date.desc()).all()


@router.post("/financial-years", status_code=201)
def create_financial_year(payload: FinancialYearCreate, membership: Membership = Depends(organisation_membership), db: Session = Depends(get_db)):
    _admin(membership, db)
    if payload.end_date < payload.start_date:
        raise HTTPException(status_code=422, detail="End date must be on or after start date")
    overlap = db.query(FinancialYear).filter(
        FinancialYear.organisation_id == membership.organisation_id,
        FinancialYear.start_date <= payload.end_date,
        FinancialYear.end_date >= payload.start_date,
    ).first()
    if overlap:
        raise HTTPException(status_code=409, detail=f"Financial year overlaps with {overlap.name}")
    if payload.is_current:
        db.query(FinancialYear).filter_by(organisation_id=membership.organisation_id, is_current=True).update({"is_current": False})
    row = FinancialYear(organisation_id=membership.organisation_id, **payload.model_dump())
    db.add(row)
    _audit(db, membership, "financial_year.created", "financial_year", payload.name, f"Created financial year {payload.name}")
    db.commit()
    db.refresh(row)
    return row


@router.put("/financial-years/{year_id}/current")
def set_current_financial_year(year_id: int, membership: Membership = Depends(organisation_membership), db: Session = Depends(get_db)):
    _admin(membership, db)
    row = db.query(FinancialYear).filter_by(id=year_id, organisation_id=membership.organisation_id, is_closed=False).first()
    if not row:
        raise HTTPException(status_code=404, detail="Open financial year not found")
    db.query(FinancialYear).filter_by(organisation_id=membership.organisation_id).update({"is_current": False})
    row.is_current = True
    _audit(db, membership, "financial_year.current_changed", "financial_year", str(row.id), f"Set current financial year to {row.name}")
    db.commit()
    return row


@router.get("/settings")
def list_organisation_settings(membership: Membership = Depends(organisation_membership), db: Session = Depends(get_db)):
    _read(membership, db)
    rows = db.query(OrganisationSetting).filter_by(organisation_id=membership.organisation_id).all()
    return {row.key: row.value for row in rows}


@router.put("/settings/{key}")
def update_organisation_setting(key: str, payload: SettingUpdate, membership: Membership = Depends(organisation_membership), user: User = Depends(current_user), db: Session = Depends(get_db)):
    _admin(membership, db)
    if key not in SETTING_KEYS:
        raise HTTPException(status_code=400, detail="Setting key is not supported")
    if key == "financial_year_start_month" and payload.value not in {str(i) for i in range(1, 13)}:
        raise HTTPException(status_code=422, detail="Financial year start month must be between 1 and 12")
    if key == "gst_exempt" and payload.value.lower() not in {"true", "false"}:
        raise HTTPException(status_code=422, detail="gst_exempt must be true or false")
    row = db.query(OrganisationSetting).filter_by(organisation_id=membership.organisation_id, key=key).first()
    if row is None:
        row = OrganisationSetting(organisation_id=membership.organisation_id, key=key, value=payload.value, updated_by_user_id=user.id)
        db.add(row)
    else:
        row.value = payload.value
        row.updated_by_user_id = user.id
    _audit(db, membership, "organisation_setting.updated", "organisation_setting", key, f"Updated setting {key}")
    db.commit()
    return {"key": key, "value": payload.value}


@router.get("/users")
def list_organisation_users(membership: Membership = Depends(organisation_membership), db: Session = Depends(get_db)):
    _read(membership, db, "user.read")
    rows = db.query(Membership, User).join(User, User.id == Membership.user_id).filter(Membership.organisation_id == membership.organisation_id).order_by(User.full_name).all()
    return [{"user_id": user.id, "email": user.email, "full_name": user.full_name, "role": item.role, "is_active": user.is_active} for item, user in rows]


@router.post("/invitations", status_code=201)
def create_user_invitation(payload: InvitationCreate, membership: Membership = Depends(organisation_membership), db: Session = Depends(get_db)):
    if not _has_permission(db, membership, "user.manage"):
        raise HTTPException(status_code=403, detail="Missing permission: user.manage")
    role = payload.role.strip().lower()
    if role not in ALLOWED_ROLES:
        raise HTTPException(status_code=422, detail="Role is not assignable through invitations")
    if role == "admin" and membership.role != "owner":
        raise HTTPException(status_code=403, detail="Only the organisation owner can invite an admin")
    email = str(payload.email).lower()
    user = db.query(User).filter_by(email=email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User must create a NEXA account before receiving an organisation invitation")
    if db.query(Membership).filter_by(user_id=user.id, organisation_id=membership.organisation_id).first():
        raise HTTPException(status_code=409, detail="User already belongs to this organisation")
    pending = db.query(UserInvitation).filter_by(organisation_id=membership.organisation_id, email=email, accepted_at=None).filter(UserInvitation.expires_at > datetime.now(timezone.utc)).first()
    if pending:
        raise HTTPException(status_code=409, detail="A pending invitation already exists")
    token = secrets.token_urlsafe(36)
    invitation = UserInvitation(
        organisation_id=membership.organisation_id,
        email=email,
        role=role,
        token_hash=hashlib.sha256(token.encode()).hexdigest(),
        invited_by_user_id=membership.user_id,
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )
    db.add(invitation)
    _audit(db, membership, "user.invited", "user_invitation", email, f"Invited {email} as {role}")
    db.commit()
    return {"invitation_id": invitation.id, "email": email, "role": role, "expires_at": invitation.expires_at, "invitation_token": token, "delivery": "manual_share_required"}


@router.post("/invitations/accept")
def accept_user_invitation(payload: InvitationAccept, user: User = Depends(current_user), db: Session = Depends(get_db)):
    token_hash = hashlib.sha256(payload.token.encode()).hexdigest()
    invitation = db.query(UserInvitation).filter_by(token_hash=token_hash, email=user.email.lower(), accepted_at=None).first()
    now = datetime.now(timezone.utc)
    if not invitation or invitation.expires_at.replace(tzinfo=timezone.utc) < now:
        raise HTTPException(status_code=400, detail="Invitation is invalid, expired or belongs to another account")
    if db.query(Membership).filter_by(user_id=user.id, organisation_id=invitation.organisation_id).first():
        raise HTTPException(status_code=409, detail="User already belongs to this organisation")
    db.add(Membership(user_id=user.id, organisation_id=invitation.organisation_id, role=invitation.role))
    invitation.accepted_at = now
    db.add(AuditEvent(organisation_id=invitation.organisation_id, actor_user_id=user.id, action="user.invitation_accepted", resource_type="user_invitation", resource_id=str(invitation.id), detail=f"Accepted invitation for {user.email}"))
    db.commit()
    return {"accepted": True, "organisation_id": invitation.organisation_id, "role": invitation.role}


@router.put("/users/{user_id}/role")
def update_user_role(user_id: int, payload: MembershipRoleUpdate, membership: Membership = Depends(organisation_membership), db: Session = Depends(get_db)):
    if not _has_permission(db, membership, "user.manage"):
        raise HTTPException(status_code=403, detail="Missing permission: user.manage")
    role = payload.role.strip().lower()
    if role not in ALLOWED_ROLES:
        raise HTTPException(status_code=422, detail="Role is not assignable")
    if role == "admin" and membership.role != "owner":
        raise HTTPException(status_code=403, detail="Only the organisation owner can assign admin")
    target = db.query(Membership).filter_by(user_id=user_id, organisation_id=membership.organisation_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="Organisation membership not found")
    if target.role == "owner":
        raise HTTPException(status_code=409, detail="The organisation owner role cannot be changed here")
    old_role = target.role
    target.role = role
    _audit(db, membership, "user.role_updated", "membership", str(target.id), f"Changed user {user_id} role from {old_role} to {role}")
    db.commit()
    return {"user_id": user_id, "role": role}


@router.delete("/users/{user_id}", status_code=204)
def remove_organisation_user(user_id: int, membership: Membership = Depends(organisation_membership), db: Session = Depends(get_db)):
    if not _has_permission(db, membership, "user.manage"):
        raise HTTPException(status_code=403, detail="Missing permission: user.manage")
    target = db.query(Membership).filter_by(user_id=user_id, organisation_id=membership.organisation_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="Organisation membership not found")
    if target.role == "owner":
        raise HTTPException(status_code=409, detail="The organisation owner cannot be removed")
    if target.user_id == membership.user_id and membership.role == "owner":
        raise HTTPException(status_code=409, detail="The organisation owner cannot remove their own membership")
    _audit(db, membership, "user.removed", "membership", str(target.id), f"Removed user {user_id} from organisation")
    db.delete(target)
    db.commit()


@router.get("/permissions")
def list_permissions(membership: Membership = Depends(organisation_membership), db: Session = Depends(get_db)):
    _read(membership, db, "user.read")
    permissions = db.query(Permission).order_by(Permission.code).all()
    assigned = db.query(RolePermission, Permission).join(Permission, Permission.id == RolePermission.permission_id).filter(RolePermission.organisation_id == membership.organisation_id).all()
    mapping: dict[str, list[str]] = {}
    for rp, permission in assigned:
        mapping.setdefault(rp.role, []).append(permission.code)
    return {"catalog": [{"code": p.code, "description": p.description} for p in permissions], "roles": mapping}


@router.put("/permissions/{role}")
def update_role_permissions(role: str, payload: RolePermissionsUpdate, membership: Membership = Depends(organisation_membership), db: Session = Depends(get_db)):
    if membership.role != "owner":
        raise HTTPException(status_code=403, detail="Only the organisation owner can configure role permissions")
    if role not in {"admin", "manager", "accountant", "clinician", "technician", "member"}:
        raise HTTPException(status_code=400, detail="Role cannot be configured")
    requested = set(payload.permission_codes)
    permission_rows = db.query(Permission).filter(Permission.code.in_(requested)).all() if requested else []
    found = {p.code for p in permission_rows}
    if found != requested:
        raise HTTPException(status_code=422, detail="One or more permission codes are unknown")
    if role == "admin" and "org.manage" in requested:
        raise HTTPException(status_code=422, detail="Organisation-wide ownership permission cannot be delegated to admin")
    db.query(RolePermission).filter_by(organisation_id=membership.organisation_id, role=role).delete()
    for permission in permission_rows:
        db.add(RolePermission(organisation_id=membership.organisation_id, role=role, permission_id=permission.id))
    _audit(db, membership, "role.permissions_updated", "role", role, f"Updated permissions for role {role}")
    db.commit()
    return {"role": role, "permission_codes": sorted(found)}
