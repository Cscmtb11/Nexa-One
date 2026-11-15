"""facility stock transfers and value-accounted adjustments

Revision ID: 0007_stock_operations
Revises: 0006_payments_gst
"""
from alembic import op
import sqlalchemy as sa

revision = "0007_stock_operations"
down_revision = "0006_payments_gst"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column("erp_stock_ledger", "document_id", existing_type=sa.Integer(), nullable=True)
    op.add_column("erp_stock_ledger", sa.Column("stock_operation_id", sa.Integer(),
        sa.ForeignKey("erp_stock_operations.id"), nullable=True))
    op.create_index("ix_erp_stock_ledger_stock_operation_id", "erp_stock_ledger", ["stock_operation_id"])

    op.create_table("erp_stock_operations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organisation_id", sa.Integer(), sa.ForeignKey("organisations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("reference_no", sa.String(60), nullable=False),
        sa.Column("operation_type", sa.String(20), nullable=False),
        sa.Column("item_id", sa.Integer(), sa.ForeignKey("erp_items.id"), nullable=False),
        sa.Column("source_facility_id", sa.Integer(), sa.ForeignKey("facilities.id")),
        sa.Column("destination_facility_id", sa.Integer(), sa.ForeignKey("facilities.id")),
        sa.Column("adjustment_direction", sa.String(10)),
        sa.Column("quantity", sa.Numeric(14, 3), nullable=False),
        sa.Column("unit_cost", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("total_cost", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("operation_date", sa.Date(), nullable=False),
        sa.Column("reason", sa.String(250), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("journal_entry_id", sa.Integer(), sa.ForeignKey("erp_journal_entries.id"), unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("organisation_id", "reference_no", name="uq_erp_stock_operation_org_ref"))
    for column in ["organisation_id", "item_id", "source_facility_id", "destination_facility_id"]:
        op.create_index(f"ix_erp_stock_operations_{column}", "erp_stock_operations", [column])

    op.execute("""
      INSERT INTO erp_accounts (organisation_id,account_code,name,account_type,is_system)
      SELECT o.id,a.code,a.name,a.kind,TRUE FROM organisations o CROSS JOIN (VALUES
        ('4100','Inventory Adjustment Gain','income'),
        ('5100','Inventory Write-off / Adjustment Loss','expense')
      ) a(code,name,kind)
      ON CONFLICT (organisation_id,account_code) DO NOTHING
    """)


def downgrade():
    op.execute("DELETE FROM erp_accounts WHERE account_code IN ('4100','5100') AND is_system=TRUE")
    for column in ["destination_facility_id", "source_facility_id", "item_id", "organisation_id"]:
        op.drop_index(f"ix_erp_stock_operations_{column}", table_name="erp_stock_operations")
    op.drop_table("erp_stock_operations")
    op.drop_index("ix_erp_stock_ledger_stock_operation_id", table_name="erp_stock_ledger")
    op.drop_column("erp_stock_ledger", "stock_operation_id")
    op.alter_column("erp_stock_ledger", "document_id", existing_type=sa.Integer(), nullable=False)
