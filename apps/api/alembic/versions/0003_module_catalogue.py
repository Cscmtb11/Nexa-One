"""industry module catalogue and tenant activation

Revision ID: 0003_module_catalogue
Revises: 0002_roles_permissions
"""
from alembic import op
import sqlalchemy as sa

revision = "0003_module_catalogue"
down_revision = "0002_roles_permissions"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "module_catalog",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("key", sa.String(100), nullable=False, unique=True),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("industry", sa.String(80), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("is_core", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_index("ix_module_catalog_key", "module_catalog", ["key"], unique=True)
    op.create_index("ix_module_catalog_industry", "module_catalog", ["industry"])

    op.create_table(
        "organisation_modules",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organisation_id", sa.Integer(), sa.ForeignKey("organisations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("module_id", sa.Integer(), sa.ForeignKey("module_catalog.id", ondelete="CASCADE"), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("organisation_id", "module_id", name="uq_org_module"),
    )
    op.create_index("ix_organisation_modules_organisation_id", "organisation_modules", ["organisation_id"])
    op.create_index("ix_organisation_modules_module_id", "organisation_modules", ["module_id"])

    modules = sa.table(
        "module_catalog",
        sa.column("key", sa.String),
        sa.column("name", sa.String),
        sa.column("industry", sa.String),
        sa.column("description", sa.String),
        sa.column("is_core", sa.Boolean),
        sa.column("is_active", sa.Boolean),
    )
    op.bulk_insert(modules, [
        {"key": "core.organisations", "name": "Organisation & Branches", "industry": "Platform", "description": "Legal entities, organisations, facilities, branches and tenant settings.", "is_core": True, "is_active": True},
        {"key": "core.access", "name": "Identity & Access", "industry": "Platform", "description": "Users, memberships, roles and permissions.", "is_core": True, "is_active": True},
        {"key": "core.audit", "name": "Audit & Compliance", "industry": "Platform", "description": "Security events, audit history and compliance evidence.", "is_core": True, "is_active": True},
        {"key": "core.reporting", "name": "Reporting & Analytics", "industry": "Platform", "description": "Cross-module reporting and operational analytics.", "is_core": True, "is_active": True},
        {"key": "finance.accounting", "name": "Finance & Accounting", "industry": "Shared Services", "description": "Ledgers, receivables, payables, journals and financial statements.", "is_core": False, "is_active": True},
        {"key": "shared.inventory", "name": "Inventory & Procurement", "industry": "Shared Services", "description": "Items, warehouses, purchase orders, stock movements and valuation.", "is_core": False, "is_active": True},
        {"key": "shared.hrms", "name": "Human Resources", "industry": "Shared Services", "description": "Employee records, attendance, leave and payroll preparation.", "is_core": False, "is_active": True},
        {"key": "shared.crm", "name": "CRM & Communications", "industry": "Shared Services", "description": "Contacts, leads, customer communications and service requests.", "is_core": False, "is_active": True},
        {"key": "healthcare.pms", "name": "Patient Management (PMS)", "industry": "Healthcare", "description": "Patient identity, registration, consent, encounters and appointments.", "is_core": False, "is_active": True},
        {"key": "healthcare.hmis", "name": "Hospital Management (HMIS)", "industry": "Healthcare", "description": "OPD, IPD, emergency, wards, beds, nursing and discharge workflows.", "is_core": False, "is_active": True},
        {"key": "healthcare.lmis", "name": "Laboratory & Logistics (LMIS)", "industry": "Healthcare", "description": "Lab orders, specimens, validation, reports and medical logistics.", "is_core": False, "is_active": True},
        {"key": "healthcare.diagnostics", "name": "Diagnostics & Electrophysiology", "industry": "Healthcare", "description": "Diagnostic workflows, test catalogues, reporting and equipment records.", "is_core": False, "is_active": True},
        {"key": "healthcare.tms", "name": "Treatment & Transactions (TMS)", "industry": "Healthcare", "description": "Treatment plans, service packages, authorisations and claims.", "is_core": False, "is_active": True},
        {"key": "pharma.retail", "name": "Retail Pharmacy", "industry": "Pharmaceutical", "description": "Pharmacy POS, prescriptions, batch sales, returns and GST invoices.", "is_core": False, "is_active": True},
        {"key": "pharma.wholesale", "name": "Wholesale Pharma Distribution", "industry": "Pharmaceutical", "description": "Distributor sales, retailer orders, schemes, credit and batch distribution.", "is_core": False, "is_active": True},
        {"key": "trade.import_export", "name": "Import & Export", "industry": "International Trade", "description": "Trade orders, shipping documents, customs records, forex and landed cost.", "is_core": False, "is_active": True},
        {"key": "ngo.management", "name": "NGO & Trust Management", "industry": "Non-profit", "description": "Donors, beneficiaries, projects, grants, volunteers and fund utilisation.", "is_core": False, "is_active": True},
        {"key": "ngo.grants", "name": "Grant & CSR Management", "industry": "Non-profit", "description": "Grant budgets, CSR projects, milestones and utilisation certificates.", "is_core": False, "is_active": True},
        {"key": "compliance.gst", "name": "GST & Tax Compliance", "industry": "Compliance", "description": "GST registrations, tax configuration, return preparation and reconciliations.", "is_core": False, "is_active": True},
        {"key": "assets.management", "name": "Fixed Assets", "industry": "Shared Services", "description": "Asset register, depreciation schedules, maintenance and allocation.", "is_core": False, "is_active": True},
    ])

    # Every existing tenant receives only the non-optional platform foundation.
    op.execute("""
        INSERT INTO organisation_modules (organisation_id, module_id, enabled)
        SELECT o.id, m.id, TRUE
        FROM organisations AS o
        CROSS JOIN module_catalog AS m
        WHERE m.is_core = TRUE
    """)


def downgrade():
    op.drop_index("ix_organisation_modules_module_id", table_name="organisation_modules")
    op.drop_index("ix_organisation_modules_organisation_id", table_name="organisation_modules")
    op.drop_table("organisation_modules")
    op.drop_index("ix_module_catalog_industry", table_name="module_catalog")
    op.drop_index("ix_module_catalog_key", table_name="module_catalog")
    op.drop_table("module_catalog")
