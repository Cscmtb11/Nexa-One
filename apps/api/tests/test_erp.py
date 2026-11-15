from decimal import Decimal
import pytest
from pydantic import ValidationError
from app.routers.erp import ItemIn, PartyIn, TaxCodeIn, DocumentLineIn, DocumentIn, money


def test_item_master_rejects_unknown_type_and_negative_price():
    with pytest.raises(ValidationError):
        ItemIn(item_code="SVC1", name="Service", item_type="unknown")
    with pytest.raises(ValidationError):
        ItemIn(item_code="ITEM1", name="Item", purchase_price="-1")


def test_party_types_are_limited():
    PartyIn(party_code="C001", name="Customer", party_type="customer")
    with pytest.raises(ValidationError):
        PartyIn(party_code="X001", name="Invalid", party_type="employee")


def test_tax_rate_is_bounded():
    TaxCodeIn(code="GST18", name="GST 18%", rate=Decimal("18"))
    with pytest.raises(ValidationError):
        TaxCodeIn(code="GST150", name="Invalid", rate=Decimal("150"))


def test_document_lines_require_positive_quantity_and_valid_discount():
    DocumentLineIn(item_id=1, quantity=Decimal("2"), unit_price=Decimal("100"), discount_amount=Decimal("10"))
    with pytest.raises(ValidationError):
        DocumentLineIn(item_id=1, quantity=Decimal("0"), unit_price=Decimal("100"))


def test_document_type_is_limited_to_supported_phase_three_documents():
    DocumentIn(document_type="sales_invoice", document_no="INV-1", party_id=1,
        issue_date="2026-11-15", lines=[{"item_id":1,"quantity":"1","unit_price":"100"}])
    with pytest.raises(ValidationError):
        DocumentIn(document_type="credit_note", document_no="CN-1", party_id=1,
            issue_date="2026-11-15", lines=[{"item_id":1,"quantity":"1","unit_price":"100"}])


def test_money_rounds_to_two_decimal_places():
    assert money(Decimal("12.345")) == Decimal("12.35")


from app.routers.erp import PaymentIn, BankAccountIn, BankStatementLineIn, split_gst_components


def test_gst_components_split_intra_state_evenly():
    cgst, sgst, igst = split_gst_components(Decimal("18.00"), "01", "01")
    assert (cgst, sgst, igst) == (Decimal("9.00"), Decimal("9.00"), Decimal("0.00"))


def test_gst_components_use_igst_for_inter_state_supply():
    cgst, sgst, igst = split_gst_components(Decimal("18.00"), "01", "07")
    assert (cgst, sgst, igst) == (Decimal("0.00"), Decimal("0.00"), Decimal("18.00"))


def test_gst_components_require_state_context_for_taxable_supply():
    with pytest.raises(ValueError):
        split_gst_components(Decimal("18.00"), None, "01")
    assert split_gst_components(Decimal("0.00"), None, None) == (
        Decimal("0.00"), Decimal("0.00"), Decimal("0.00"))


def test_payment_schema_requires_supported_type_and_positive_amount():
    PaymentIn(payment_no="RCPT-1", payment_type="customer_receipt", party_id=1,
        payment_date="2026-11-15", amount="100", method="cash")
    with pytest.raises(ValidationError):
        PaymentIn(payment_no="PAY-1", payment_type="refund", party_id=1,
            payment_date="2026-11-15", amount="100")


def test_bank_account_and_statement_validation():
    BankAccountIn(account_code="1010", bank_name="Example Bank", account_label="Current Account", account_last4="1234")
    BankStatementLineIn(bank_account_id=1, transaction_date="2026-11-15",
        description="Customer receipt", direction="credit", amount="100")
    with pytest.raises(ValidationError):
        BankStatementLineIn(bank_account_id=1, transaction_date="2026-11-15",
            description="Invalid", direction="transfer", amount="100")


from app.inventory_costing import replay_fifo_layers, issue_fifo_layers, fifo_layer_totals


def test_fifo_consumes_oldest_purchase_layers_first():
    layers = replay_fifo_layers([
        {"quantity_in": Decimal("5"), "quantity_out": Decimal("0"), "unit_cost": Decimal("10")},
        {"quantity_in": Decimal("3"), "quantity_out": Decimal("0"), "unit_cost": Decimal("14")},
    ])
    cost = issue_fifo_layers(layers, Decimal("6"))
    assert cost == Decimal("64.00")
    assert layers == [{"quantity": Decimal("2"), "unit_cost": Decimal("14")}]


def test_fifo_replay_applies_prior_sales_to_oldest_layers():
    layers = replay_fifo_layers([
        {"quantity_in": Decimal("4"), "quantity_out": Decimal("0"), "unit_cost": Decimal("12")},
        {"quantity_in": Decimal("0"), "quantity_out": Decimal("1"), "unit_cost": Decimal("999")},
        {"quantity_in": Decimal("2"), "quantity_out": Decimal("0"), "unit_cost": Decimal("15")},
    ])
    assert fifo_layer_totals(layers) == (Decimal("5"), Decimal("66.00"))


def test_fifo_rejects_issue_beyond_available_layers():
    layers = replay_fifo_layers([{"quantity_in": Decimal("2"), "quantity_out": Decimal("0"), "unit_cost": Decimal("8")}])
    with pytest.raises(ValueError, match="Insufficient FIFO quantity"):
        issue_fifo_layers(layers, Decimal("3"))


from app.routers.erp import StockTransferIn, StockAdjustmentIn


def test_stock_transfer_schema_rejects_non_positive_quantity():
    with pytest.raises(ValidationError):
        StockTransferIn(reference_no="TR-1",item_id=1,source_facility_id=1,destination_facility_id=2,
            quantity="0",operation_date="2026-11-15",reason="Branch replenishment")


def test_stock_adjustment_requires_supported_direction():
    StockAdjustmentIn(reference_no="ADJ-1",item_id=1,facility_id=1,direction="increase",
        quantity="2",unit_cost="15",operation_date="2026-11-15",reason="Opening count correction")
    with pytest.raises(ValidationError):
        StockAdjustmentIn(reference_no="ADJ-2",item_id=1,facility_id=1,direction="transfer",
            quantity="2",operation_date="2026-11-15",reason="Invalid direction")
