from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from ..db import get_db
from ..dependencies import require_org_permission
from ..models import Facility, Membership

router = APIRouter(prefix="/v1/facilities", tags=["facilities"])

class FacilityCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    code: str = Field(min_length=1, max_length=50)

class FacilityResponse(FacilityCreate):
    id: int
    organisation_id: int
    is_active: bool

@router.get("", response_model=list[FacilityResponse])
def list_facilities(membership: Membership = Depends(require_org_permission("facility.read")), db: Session = Depends(get_db)):
    return db.query(Facility).filter(Facility.organisation_id == membership.organisation_id, Facility.is_active.is_(True)).all()

@router.post("", response_model=FacilityResponse, status_code=201)
def create_facility(payload: FacilityCreate, membership: Membership = Depends(require_org_permission("facility.manage")), db: Session = Depends(get_db)):
    exists = db.query(Facility).filter(Facility.organisation_id == membership.organisation_id, Facility.code == payload.code).first()
    if exists:
        raise HTTPException(status_code=409, detail="Facility code already exists")
    facility = Facility(organisation_id=membership.organisation_id, name=payload.name, code=payload.code)
    db.add(facility)
    db.commit()
    db.refresh(facility)
    return facility
