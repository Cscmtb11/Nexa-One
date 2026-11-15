from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session
from .db import get_db
from .models import Membership, User
from .security import decode_access_token


def current_user(authorization: str | None = Header(default=None), db: Session = Depends(get_db)) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Bearer token required")
    try:
        user_id = decode_access_token(authorization[7:])
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
    user = db.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Inactive user")
    return user


def organisation_membership(
    x_org_id: int | None = Header(default=None),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> Membership:
    if not x_org_id:
        raise HTTPException(status_code=400, detail="X-Org-Id header is required")
    membership = db.query(Membership).filter_by(user_id=user.id, organisation_id=x_org_id).first()
    if not membership and not user.is_platform_admin:
        raise HTTPException(status_code=403, detail="User is not a member of this organisation")
    if membership:
        return membership
    return Membership(user_id=user.id, organisation_id=x_org_id, role="platform_admin")


def require_org_permission(permission_code: str):
    """Resolve a permission against the active organisation and the member's role."""
    def _require(
        membership: Membership = Depends(organisation_membership),
        db: Session = Depends(get_db),
    ) -> Membership:
        if membership.role == "platform_admin":
            return membership
        from .models import Permission, RolePermission
        allowed = (
            db.query(RolePermission.id)
            .join(Permission, Permission.id == RolePermission.permission_id)
            .filter(
                RolePermission.organisation_id == membership.organisation_id,
                RolePermission.role == membership.role,
                Permission.code == permission_code,
            )
            .first()
        )
        if not allowed:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Missing permission: {permission_code}")
        return membership
    return _require
