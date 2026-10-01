from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import Membership, Organisation, User
from ..schemas import LoginRequest, RegisterRequest, TokenResponse
from ..security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/v1/auth", tags=["auth"])

@router.post("/register", response_model=TokenResponse, status_code=201)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    if db.query(User).filter_by(email=payload.email).first():
        raise HTTPException(status_code=409, detail="Email already registered")
    if db.query(Organisation).filter_by(slug=payload.organisation_slug).first():
        raise HTTPException(status_code=409, detail="Organisation slug already exists")
    org = Organisation(name=payload.organisation_name, slug=payload.organisation_slug)
    user = User(email=payload.email, full_name=payload.full_name, password_hash=hash_password(payload.password))
    db.add_all([org, user])
    db.flush()
    db.add(Membership(user_id=user.id, organisation_id=org.id, role="owner"))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Registration conflict")
    return TokenResponse(access_token=create_access_token(user.id))

@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter_by(email=payload.email).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="User is inactive")
    return TokenResponse(access_token=create_access_token(user.id))
