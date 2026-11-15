from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import Membership, ModuleCatalog, Organisation, OrganisationModule, Permission, RolePermission, User
from ..schemas import LoginRequest, RegisterRequest, TokenResponse
from ..security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/v1/auth", tags=["auth"])


def _seed_organisation_defaults(db: Session, organisation_id: int):
    """Apply mandatory platform modules and least-surprise starter role grants."""
    core_modules = db.query(ModuleCatalog).filter_by(is_core=True, is_active=True).all()
    for module in core_modules:
        db.add(OrganisationModule(organisation_id=organisation_id, module_id=module.id, enabled=True))

    permission_rows = db.query(Permission).all()
    by_code = {permission.code: permission for permission in permission_rows}
    role_grants = {
        "owner": set(by_code),
        "admin": set(by_code) - {"org.manage"},
        "manager": {"org.read", "facility.read", "user.read", "audit.read"},
        "accountant": {"org.read", "facility.read"},
        "clinician": {"org.read", "facility.read"},
        "technician": {"org.read", "facility.read"},
        "member": {"org.read", "facility.read"},
    }
    for role, codes in role_grants.items():
        for code in codes:
            permission = by_code.get(code)
            if permission:
                db.add(RolePermission(organisation_id=organisation_id, role=role, permission_id=permission.id))


@router.post("/register", response_model=TokenResponse, status_code=201)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    email = str(payload.email).lower()
    if db.query(User).filter_by(email=email).first():
        raise HTTPException(status_code=409, detail="Email already registered")
    if db.query(Organisation).filter_by(slug=payload.organisation_slug).first():
        raise HTTPException(status_code=409, detail="Organisation slug already exists")
    org = Organisation(name=payload.organisation_name, slug=payload.organisation_slug)
    user = User(email=email, full_name=payload.full_name, password_hash=hash_password(payload.password))
    db.add_all([org, user])
    db.flush()
    db.add(Membership(user_id=user.id, organisation_id=org.id, role="owner"))
    _seed_organisation_defaults(db, org.id)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Registration conflict")
    return TokenResponse(access_token=create_access_token(user.id))


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter_by(email=str(payload.email).lower()).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="User is inactive")
    return TokenResponse(access_token=create_access_token(user.id))
