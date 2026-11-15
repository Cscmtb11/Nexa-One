# NEXA ERP — Platform Roadmap

## Product direction

NEXA is a modular, multi-organisation SaaS ERP for healthcare providers, diagnostic centres, pharmacies, pharmaceutical distributors, import/export businesses and non-profit organisations.

The existing Next.js 15 + React 19 frontend and FastAPI + SQLAlchemy + PostgreSQL backend remain the foundation. AI stays disabled by default and is not a dependency for core business workflows.

## Platform principles

1. **Tenant isolation first:** every tenant-owned record carries an organisation scope; API queries must derive that scope from the authenticated user's membership, never trust a tenant ID supplied only in a request body.
2. **Facility-aware operations:** operational records are scoped to both organisation and facility wherever the workflow requires it.
3. **Module entitlements:** an organisation can only access modules enabled for that tenant and included in its plan.
4. **Auditable actions:** privileged configuration and business events create audit records.
5. **India-ready configuration:** multiple legal entities, GST registrations, financial years, tax settings and branch-level controls are supported by the domain model.
6. **Safe clinical workflows:** clinical documentation, diagnostic results and medication workflows require appropriate user permissions and human verification.
7. **AI optional:** core workflows remain available with AI disabled.

## Module catalogue

| Domain | Module keys |
|---|---|
| Platform | `core.organisations`, `core.access`, `core.audit`, `core.reporting` |
| Shared services | `finance.accounting`, `shared.inventory`, `shared.hrms`, `shared.crm`, `assets.management` |
| Healthcare | `healthcare.pms`, `healthcare.hmis`, `healthcare.lmis`, `healthcare.diagnostics`, `healthcare.tms` |
| Pharmaceutical | `pharma.retail`, `pharma.wholesale` |
| International trade | `trade.import_export` |
| Non-profit | `ngo.management`, `ngo.grants` |
| Compliance | `compliance.gst` |

The catalogue is seeded by Alembic migration. Each tenant receives the mandatory platform modules. Optional modules are enabled by an organisation owner/admin.

## Delivery phases

### Phase 1 — Platform foundation (current branch)
- Preserve existing registration, login, organisation, facility and RBAC foundations.
- Add a seeded industry module catalogue.
- Add tenant-specific module activation/deactivation API.
- Audit module entitlement changes.
- Add Oracle production Compose deployment template and migration-capable API image.

### Phase 2 — Tenant administration
- Legal entities and organisation profiles.
- GST registrations and branch/facility hierarchy.
- User invitations, memberships and role-permission enforcement.
- Tenant settings, financial years and numbering sequences.
- Subscription plans, entitlements and usage metering.

### Phase 3 — Shared ERP engines
- Item/service master, units, tax codes and price lists.
- Purchase, sales, stock ledger, batch/serial and expiry controls.
- Double-entry accounting, receivables, payables and bank reconciliation.
- Document numbering, attachments and approval workflows.

### Phase 4 — Healthcare
- Patient master index, registration, consent and appointments.
- OPD/IPD, wards, beds, nursing, discharge and billing.
- Laboratory orders, specimens, worklists, validation and report release.
- Diagnostic centre workflows, equipment and clinician sign-off.

### Phase 5 — Pharmaceutical
- Retail pharmacy POS, prescription capture and returns.
- Wholesale order management, schemes, credit and retailer portal.
- Batch/expiry traceability, recalls and regulated sale controls.

### Phase 6 — Import/export
- Trade contracts, proforma/commercial invoices and packing lists.
- Shipment, container and milestone tracking.
- Customs documentation register, currency conversion and landed cost.

### Phase 7 — NGO and grants
- Donor, beneficiary, volunteer and project registries.
- Donations, restricted funds, grant budgets and utilisation reporting.
- CSR/FCRA evidence registers and configurable compliance checklists.

### Phase 8 — Production hardening
- MFA, session revocation, rate limiting and security review.
- Encrypted off-host backups and tested restore procedures.
- Monitoring, alerting, disaster recovery and release rollback.
- External integration certification and regulatory review.

## Phase 1 API

All routes are versioned under `/v1`.

- `GET /v1/modules/catalog` — authenticated module catalogue.
- `GET /v1/modules/enabled` — modules enabled for the selected `X-Org-Id`.
- `PUT /v1/modules/{module_key}/enable` — owner/admin enables a module.
- `PUT /v1/modules/{module_key}/disable` — owner/admin disables an optional module; core modules cannot be disabled.

All tenant-scoped endpoints require a valid bearer token and an organisation membership context. The current platform-admin bypass is retained from the existing foundation and should be further restricted through explicit platform-admin audit and support-session controls before public SaaS launch.

## Deployment notes

- Local development remains `docker compose up --build`.
- Oracle production uses `infra/oracle/docker-compose.production.yml`.
- Production database migrations run on API container startup before Uvicorn starts.
- Keep `.env.production` out of Git; use a secrets manager or protected VM file permissions.
- The Compose stack binds web/API ports to loopback. Publish them through Cloudflare Tunnel or a hardened reverse proxy; do not expose PostgreSQL publicly.
- Free-tier capacity and quotas are provider-controlled and are not a guaranteed zero-cost SLA.
