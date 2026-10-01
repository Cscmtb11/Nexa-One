from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from ..db import get_db
from ..dependencies import current_user
from ..models import Membership, Organisation, User
from ..schemas import OrganisationResponse

router = APIRouter(prefix="/v1/organisations", tags=["organisations"])

@router.get("", response_model=list[OrganisationResponse])
def list_organisations(user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.query(Membership, Organisation).join(Organisation, Membership.organisation_id == Organisation.id).filter(Membership.user_id == user.id, Organisation.is_active == True).all()
    return [OrganisationResponse(id=o.id, name=o.name, slug=o.slug, role=m.role) for m, o in rows]
