"""payments, party allocations, bank reconciliation and GST components

Revision ID: 0006_payments_gst
Revises: 0005_shared_erp
"""
from alembic import op
import sqlalchemy as sa

revision = "0006_payments_gst"
down_revision = "0005_shared_erp"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("erp_document_lines", sa.Column("cgst_amount", sa.Numeric(14,2), nullable=False, server_default="0"))
    op.add_column("erp_document_lines", sa.Column("sgst_amount", sa.Numeric(14,2), nullable=False, server_default="0"))
    op.add_column("erp_document_lines", sa.Column("igst_amount", sa.Numeric(14,2), nullable=False, server_default="0"))

    op.create_table("erp_bank_accounts",
        sa.Column("id",sa.Integer(),primary_key=True),
        sa.Column("organisation_id",sa.Integer(),sa.ForeignKey("organisations.id",ondelete="CASCADE"),nullable=False),
        sa.Column("ledger_account_id",sa.Integer(),sa.ForeignKey("erp_accounts.id"),nullable=False,unique=True),
        sa.Column("account_code",sa.String(30),nullable=False),sa.Column("bank_name",sa.String(120),nullable=False),
        sa.Column("account_label",sa.String(120),nullable=False),sa.Column("account_last4",sa.String(4)),
        sa.Column("is_active",sa.Boolean(),nullable=False,server_default=sa.true()),
        sa.UniqueConstraint("organisation_id","account_code",name="uq_erp_bank_account_org_code"))
    op.create_index("ix_erp_bank_accounts_organisation_id","erp_bank_accounts",["organisation_id"])

    op.create_table("erp_payments",
        sa.Column("id",sa.Integer(),primary_key=True),
        sa.Column("organisation_id",sa.Integer(),sa.ForeignKey("organisations.id",ondelete="CASCADE"),nullable=False),
        sa.Column("party_id",sa.Integer(),sa.ForeignKey("erp_parties.id"),nullable=False),
        sa.Column("bank_account_id",sa.Integer(),sa.ForeignKey("erp_bank_accounts.id")),
        sa.Column("journal_entry_id",sa.Integer(),sa.ForeignKey("erp_journal_entries.id"),nullable=False,unique=True),
        sa.Column("payment_no",sa.String(60),nullable=False),sa.Column("payment_type",sa.String(30),nullable=False),
        sa.Column("payment_date",sa.Date(),nullable=False),sa.Column("amount",sa.Numeric(14,2),nullable=False),
        sa.Column("method",sa.String(30),nullable=False,server_default="bank"),sa.Column("reference",sa.String(100)),
        sa.Column("created_by_user_id",sa.Integer(),sa.ForeignKey("users.id"),nullable=False),
        sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.func.now()),
        sa.UniqueConstraint("organisation_id","payment_no",name="uq_erp_payment_org_no"))
    op.create_index("ix_erp_payments_organisation_id","erp_payments",["organisation_id"])
    op.create_index("ix_erp_payments_party_id","erp_payments",["party_id"])
    op.create_index("ix_erp_payments_bank_account_id","erp_payments",["bank_account_id"])

    op.create_table("erp_payment_allocations",
        sa.Column("id",sa.Integer(),primary_key=True),
        sa.Column("payment_id",sa.Integer(),sa.ForeignKey("erp_payments.id",ondelete="CASCADE"),nullable=False),
        sa.Column("document_id",sa.Integer(),sa.ForeignKey("erp_documents.id"),nullable=False),
        sa.Column("amount",sa.Numeric(14,2),nullable=False))
    op.create_index("ix_erp_payment_allocations_payment_id","erp_payment_allocations",["payment_id"])
    op.create_index("ix_erp_payment_allocations_document_id","erp_payment_allocations",["document_id"])

    op.create_table("erp_bank_statement_lines",
        sa.Column("id",sa.Integer(),primary_key=True),
        sa.Column("organisation_id",sa.Integer(),sa.ForeignKey("organisations.id",ondelete="CASCADE"),nullable=False),
        sa.Column("bank_account_id",sa.Integer(),sa.ForeignKey("erp_bank_accounts.id"),nullable=False),
        sa.Column("transaction_date",sa.Date(),nullable=False),sa.Column("description",sa.String(250),nullable=False),
        sa.Column("reference",sa.String(100)),sa.Column("direction",sa.String(10),nullable=False),
        sa.Column("amount",sa.Numeric(14,2),nullable=False),
        sa.Column("reconciled_payment_id",sa.Integer(),sa.ForeignKey("erp_payments.id"),unique=True),
        sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.func.now()))
    op.create_index("ix_erp_bank_statement_lines_organisation_id","erp_bank_statement_lines",["organisation_id"])
    op.create_index("ix_erp_bank_statement_lines_bank_account_id","erp_bank_statement_lines",["bank_account_id"])

    op.execute("""
      INSERT INTO erp_accounts (organisation_id,account_code,name,account_type,is_system)
      SELECT o.id,a.code,a.name,a.kind,TRUE FROM organisations o CROSS JOIN (VALUES
        ('2110','Output CGST','liability'),('2120','Output SGST','liability'),('2130','Output IGST','liability'),('2200','Customer Advances','liability'),
        ('1310','Input CGST','asset'),('1320','Input SGST','asset'),('1330','Input IGST','asset'),('1400','Supplier Advances','asset')
      ) a(code,name,kind)
      ON CONFLICT (organisation_id,account_code) DO NOTHING
    """)


def downgrade():
    op.drop_index("ix_erp_bank_statement_lines_bank_account_id",table_name="erp_bank_statement_lines")
    op.drop_index("ix_erp_bank_statement_lines_organisation_id",table_name="erp_bank_statement_lines")
    op.drop_table("erp_bank_statement_lines")
    op.drop_index("ix_erp_payment_allocations_document_id",table_name="erp_payment_allocations")
    op.drop_index("ix_erp_payment_allocations_payment_id",table_name="erp_payment_allocations")
    op.drop_table("erp_payment_allocations")
    op.drop_index("ix_erp_payments_bank_account_id",table_name="erp_payments")
    op.drop_index("ix_erp_payments_party_id",table_name="erp_payments")
    op.drop_index("ix_erp_payments_organisation_id",table_name="erp_payments")
    op.drop_table("erp_payments")
    op.drop_index("ix_erp_bank_accounts_organisation_id",table_name="erp_bank_accounts")
    op.drop_table("erp_bank_accounts")
    op.drop_column("erp_document_lines","igst_amount")
    op.drop_column("erp_document_lines","sgst_amount")
    op.drop_column("erp_document_lines","cgst_amount")
