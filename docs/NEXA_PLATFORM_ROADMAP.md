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

### Phase 2 — Tenant administration (implemented in phase-2 branch)
- Legal entity registry with PAN, constitution and address details.
- GST registrations linked to legal entities and optional facilities; format, state-code and PAN-segment checks.
- Organisation-scoped financial years with overlap prevention and a single current year.
- Allow-listed organisation settings with audit events.
- User directory and expiring one-time invitations for existing NEXA accounts.
- Configurable role-permission matrix and tenant-scoped permission dependency for facility and module APIs.
- New organisation registration automatically provisions core modules and starter role permissions.
- Responsive /admin web workspace for legal entities, GST, financial years, users, permissions and settings.

Still planned for a later phase:
- Subscription plans, billing, entitlements and usage metering.
- Email delivery and self-service onboarding for invitations to new accounts.
- Granular permission checks on every business endpoint and platform-admin support-session controls.

### Phase 3 — Shared ERP engines (first engine slice implemented in phase-3 branch)
- Tenant-scoped item/service, customer/supplier and GST tax-code masters.
- Draft sales invoices and purchase bills with line-level discounts and tax calculation.
- Posting workflow with open-financial-year checks, immutable posted status and audit events.
- Double-entry journal generation with a seeded starter chart of accounts and balanced-entry assertion.
- Facility-aware stock movement ledger and stock-on-hand query; posting blocks sales when tracked stock is insufficient.
- New organisation registration provisions the ERP chart of accounts and GST tax-code catalogue.

Phase 3.1 — payments and India GST foundations (implemented in phase-3-1 branch):
- Customer receipts and supplier payments, posted as double-entry journals with financial-year validation.
- Optional allocations to posted invoices/bills; unallocated customer receipts and supplier payments post to dedicated advance ledger accounts.
- Customer receivables, supplier payables and advances are separated in the party subledger.
- Organisation-scoped bank account ledger masters and manual bank statement line import.
- Manual statement-to-payment matching validates bank account, credit/debit direction and amount; reconciliation summary shows matched/unmatched counts.
- GST tax component split at document-line level: intra-state CGST/SGST and inter-state IGST based on the organisation's primary GST registration state and place of supply.
- New bank, payment and GST component schema migration plus a finance/reconciliation workspace at /erp/finance.

Remaining before production accounting use:
- GSTIN e-invoice/IRN integration, live HSN/SAC and rate validation, GST return generation and reconciliation with portal data.
- Automated bank statement file import (CSV/OFX/API), opening balances, fees, interest, reversals and unmatched transaction workflow.
- Batch/serial and expiry tracking; purchase/sales orders, approvals, attachments, credit/debit notes and document numbering sequences. Phase 3.3 adds FIFO issue costing, COGS journals and FIFO inventory valuation; Phase 3.4 adds facility transfers and value-accounted stock adjustments.
- Purchase orders, sales orders, approval workflows, attachments, credit/debit notes and document numbering sequences.
- Financial statements, trial balance, receivables/payables ageing, advances settlement and period close controls.
- External accountant review and regulatory validation before live filing or statutory use.

Phase 3.3 — inventory costing foundation (implementation branch):
- FIFO cost layers are reconstructed from the facility/item stock ledger in movement-date order.
- Sales posting consumes oldest available purchase layers and posts COGS (debit) against inventory (credit) in the same balanced journal.
- Purchase stock receipts use net line taxable value after discounts as their FIFO unit cost.
- Inventory valuation endpoint reports FIFO quantity and value by item/facility.
- Backdated stock postings are blocked when they would rewrite an existing FIFO sequence; inconsistent legacy stock history is rejected for reconciliation.
- FIFO is not a substitute for opening-stock migration or accountant-approved valuation review. GST input tax, freight/landed cost, returns and stock adjustments require later dedicated workflows.


Phase 3.4 — facility stock operations (implementation branch):
- Transfer tracked goods between two active facilities within the same organisation, preserving FIFO cost and recording paired source/destination ledger movements.
- Post increase/decrease stock adjustments with a mandatory reason and audit event; increases require a supplied unit cost and decreases consume FIFO layers.
- Stock adjustment gains/losses create balanced journals against dedicated inventory adjustment gain/write-off accounts.
- Operations are dated, reference-numbered and restricted to open financial years where financial years are configured. Backdated operations are rejected to protect FIFO chronology.
- Transfers are internal movements and do not create income/expense journals. One item is handled per operation in this first slice.

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
