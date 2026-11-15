from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import get_db
from ..dependencies import current_user, require_org_permission
from ..models import AuditEvent, ModuleCatalog, OrganisationModule, Membership, User

router = APIRouter(prefix="/v1/modules", tags=["modules"])


def _module_payload(module: ModuleCatalog) -> dict:
    return {
        "key": module.key,
        "name": module.name,
        "industry": module.industry,
        "description": module.description,
        "is_core": module.is_core,
    }


@router.get("/catalog")
def list_module_catalog(
    _user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Return the platform module catalogue. Activation is tenant-specific."""
    modules = db.query(ModuleCatalog).filter(ModuleCatalog.is_active.is_(True)).order_by(
        ModuleCatalog.industry, ModuleCatalog.name
    ).all()
    return [_module_payload(module) for module in modules]


@router.get("/enabled")
def list_enabled_modules(
    membership: Membership = Depends(require_org_permission("org.read")),
    db: Session = Depends(get_db),
):
    """Return modules enabled for the organisation selected by X-Org-Id."""
    rows = (
        db.query(ModuleCatalog, OrganisationModule)
        .join(OrganisationModule, OrganisationModule.module_id == ModuleCatalog.id)
        .filter(
            OrganisationModule.organisation_id == membership.organisation_id,
            OrganisationModule.enabled.is_(True),
            ModuleCatalog.is_active.is_(True),
        )
        .order_by(ModuleCatalog.industry, ModuleCatalog.name)
        .all()
    )
    return [{**_module_payload(module), "enabled": activation.enabled} for module, activation in rows]


@router.put("/{module_key}/enable")
def enable_module(
    module_key: str,
    membership: Membership = Depends(require_org_permission("org.manage")),
    db: Session = Depends(get_db),
):
    module = db.query(ModuleCatalog).filter_by(key=module_key, is_active=True).first()
    if not module:
        raise HTTPException(status_code=404, detail="Module not found")

    activation = db.query(OrganisationModule).filter_by(
        organisation_id=membership.organisation_id, module_id=module.id
    ).first()
    if activation is None:
        activation = OrganisationModule(
            organisation_id=membership.organisation_id,
            module_id=module.id,
            enabled=True,
        )
        db.add(activation)
    else:
        activation.enabled = True

    db.add(AuditEvent(
        organisation_id=membership.organisation_id,
        actor_user_id=membership.user_id,
        action="module.enabled",
        resource_type="module",
        resource_id=module.key,
        detail=f"Enabled module {module.key}",
    ))
    db.commit()
    return {**_module_payload(module), "enabled": True}


@router.put("/{module_key}/disable")
def disable_module(
    module_key: str,
    membership: Membership = Depends(require_org_permission("org.manage")),
    db: Session = Depends(get_db),
):
    if membership.role not in {"owner", "admin", "platform_admin"}:
        raise HTTPException(status_code=403, detail="Organisation admin role required")

    module = db.query(ModuleCatalog).filter_by(key=module_key, is_active=True).first()
    if not module:
        raise HTTPException(status_code=404, detail="Module not found")
    if module.is_core:
        raise HTTPException(status_code=409, detail="Core platform modules cannot be disabled")

    activation = db.query(OrganisationModule).filter_by(
        organisation_id=membership.organisation_id, module_id=module.id
    ).first()
    if activation is not None:
        activation.enabled = False

    db.add(AuditEvent(
        organisation_id=membership.organisation_id,
        actor_user_id=membership.user_id,
        action="module.disabled",
        resource_type="module",
        resource_id=module.key,
        detail=f"Disabled module {module.key}",
    ))
    db.commit()
    return {**_module_payload(module), "enabled": False}
