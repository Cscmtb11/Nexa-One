"""role permission foundation

Revision ID: 0002_roles_permissions
Revises: 0001_initial
"""
from alembic import op
import sqlalchemy as sa

revision = "0002_roles_permissions"
down_revision = "0001_initial"
branch_labels = None
depends_on = None

def upgrade():
    op.create_unique_constraint("uq_facility_org_code", "facilities", ["organisation_id", "code"])
    op.create_table("permissions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(120), nullable=False, unique=True),
        sa.Column("description", sa.String(255), nullable=False))
    op.create_table("role_permissions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organisation_id", sa.Integer(), sa.ForeignKey("organisations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(80), nullable=False),
        sa.Column("permission_id", sa.Integer(), sa.ForeignKey("permissions.id", ondelete="CASCADE"), nullable=False),
        sa.UniqueConstraint("organisation_id", "role", "permission_id", name="uq_role_permission"))
    permissions = sa.table("permissions", sa.column("code", sa.String), sa.column("description", sa.String))
    op.bulk_insert(permissions, [
        {"code":"org.read","description":"View organisation settings"},
        {"code":"org.manage","description":"Manage organisation settings"},
        {"code":"facility.read","description":"View facilities"},
        {"code":"facility.manage","description":"Create and manage facilities"},
        {"code":"user.read","description":"View organisation users"},
        {"code":"user.manage","description":"Manage organisation users"},
        {"code":"audit.read","description":"View audit events"},
    ])

def downgrade():
    op.drop_table("role_permissions")
    op.drop_table("permissions")
    op.drop_constraint("uq_facility_org_code", "facilities", type_="unique")
