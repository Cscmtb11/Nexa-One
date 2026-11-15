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
