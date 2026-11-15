"""tenant administration foundations

Revision ID: 0004_tenant_admin
Revises: 0003_module_catalogue
"""
from alembic import op
import sqlalchemy as sa

revision = "0004_tenant_admin"
down_revision = "0003_module_catalogue"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "legal_entities",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organisation_id", sa.Integer(), sa.ForeignKey("organisations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("code", sa.String(30), nullable=False),
        sa.Column("legal_name", sa.String(200), nullable=False),
        sa.Column("trade_name", sa.String(200)),
        sa.Column("pan", sa.String(10)),
        sa.Column("constitution", sa.String(50), nullable=False, server_default="other"),
        sa.Column("address_line1", sa.String(200)),
        sa.Column("address_line2", sa.String(200)),
        sa.Column("city", sa.String(100)),
        sa.Column("district", sa.String(100)),
        sa.Column("state_code", sa.String(2)),
        sa.Column("state_name", sa.String(100)),
        sa.Column("pincode", sa.String(10)),
        sa.Column("country", sa.String(2), nullable=False, server_default="IN"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("organisation_id", "code", name="uq_legal_entity_org_code"),
        sa.CheckConstraint("length(code) >= 2", name="ck_legal_entity_code_length"),
    )
    op.create_index("ix_legal_entities_organisation_id", "legal_entities", ["organisation_id"])
    op.create_index("ix_legal_entities_pan", "legal_entities", ["pan"])

    op.create_table(
        "gst_registrations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organisation_id", sa.Integer(), sa.ForeignKey("organisations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("legal_entity_id", sa.Integer(), sa.ForeignKey("legal_entities.id", ondelete="CASCADE"), nullable=False),
        sa.Column("facility_id", sa.Integer(), sa.ForeignKey("facilities.id", ondelete="SET NULL")),
        sa.Column("gstin", sa.String(15), nullable=False),
        sa.Column("registration_type", sa.String(40), nullable=False, server_default="regular"),
        sa.Column("state_code", sa.String(2), nullable=False),
        sa.Column("effective_from", sa.Date()),
        sa.Column("effective_to", sa.Date()),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("gstin", name="uq_gst_registration_gstin"),
    )
    op.create_index("ix_gst_registrations_organisation_id", "gst_registrations", ["organisation_id"])
    op.create_index("ix_gst_registrations_legal_entity_id", "gst_registrations", ["legal_entity_id"])
    op.create_index("ix_gst_registrations_facility_id", "gst_registrations", ["facility_id"])
    op.create_index("ix_gst_registrations_gstin", "gst_registrations", ["gstin"])

    op.create_table(
        "financial_years",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organisation_id", sa.Integer(), sa.ForeignKey("organisations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(20), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_closed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("organisation_id", "name", name="uq_financial_year_org_name"),
        sa.CheckConstraint("end_date >= start_date", name="ck_financial_year_dates"),
    )
    op.create_index("ix_financial_years_organisation_id", "financial_years", ["organisation_id"])

    op.create_table(
        "organisation_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organisation_id", sa.Integer(), sa.ForeignKey("organisations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("key", sa.String(100), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("updated_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("organisation_id", "key", name="uq_org_setting_key"),
    )
    op.create_index("ix_organisation_settings_organisation_id", "organisation_settings", ["organisation_id"])

    op.create_table(
        "user_invitations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organisation_id", sa.Integer(), sa.ForeignKey("organisations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("role", sa.String(80), nullable=False, server_default="member"),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("invited_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_user_invitations_organisation_id", "user_invitations", ["organisation_id"])
    op.create_index("ix_user_invitations_email", "user_invitations", ["email"])
    op.create_index("ix_user_invitations_token_hash", "user_invitations", ["token_hash"])

    # Seed initial role permissions for every existing organisation.
    op.execute("""
      INSERT INTO role_permissions (organisation_id, role, permission_id)
      SELECT o.id, r.role, p.id
      FROM organisations o
      CROSS JOIN (VALUES ('owner'), ('admin'), ('manager'), ('member')) AS r(role)
      JOIN permissions p ON
        (r.role = 'owner')
        OR (r.role = 'admin' AND p.code <> 'org.manage')
        OR (r.role = 'manager' AND p.code IN ('org.read','facility.read','user.read','audit.read'))
        OR (r.role = 'member' AND p.code IN ('org.read','facility.read'))
    """)


def downgrade():
    op.drop_index("ix_user_invitations_token_hash", table_name="user_invitations")
    op.drop_index("ix_user_invitations_email", table_name="user_invitations")
    op.drop_index("ix_user_invitations_organisation_id", table_name="user_invitations")
    op.drop_table("user_invitations")
    op.drop_index("ix_organisation_settings_organisation_id", table_name="organisation_settings")
    op.drop_table("organisation_settings")
    op.drop_index("ix_financial_years_organisation_id", table_name="financial_years")
    op.drop_table("financial_years")
    op.drop_index("ix_gst_registrations_gstin", table_name="gst_registrations")
    op.drop_index("ix_gst_registrations_facility_id", table_name="gst_registrations")
    op.drop_index("ix_gst_registrations_legal_entity_id", table_name="gst_registrations")
    op.drop_index("ix_gst_registrations_organisation_id", table_name="gst_registrations")
    op.drop_table("gst_registrations")
    op.drop_index("ix_legal_entities_pan", table_name="legal_entities")
    op.drop_index("ix_legal_entities_organisation_id", table_name="legal_entities")
    op.drop_table("legal_entities")
