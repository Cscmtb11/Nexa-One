from datetime import date
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session
from ..db import get_db
from ..dependencies import require_org_permission
from ..models import ERPAccount, ERPJournalEntry, ERPJournalLine, ERPItem, ERPStockLedger, Membership

router = APIRouter(prefix="/v1/erp/reports", tags=["ERP reports"])


def normal_side(account_type: str) -> str:
    return "debit" if account_type in {"asset", "expense"} else "credit"


def _ledger_rows(db: Session, organisation_id: int, end_date: date, start_date: date | None = None):
    query = (
        db.query(
            ERPAccount.id.label("account_id"),
            ERPAccount.account_code.label("account_code"),
            ERPAccount.name.label("account_name"),
            ERPAccount.account_type.label("account_type"),
            func.coalesce(func.sum(ERPJournalLine.debit), 0).label("debit"),
            func.coalesce(func.sum(ERPJournalLine.credit), 0).label("credit"),
        )
        .join(ERPJournalLine, ERPJournalLine.account_id == ERPAccount.id)
        .join(ERPJournalEntry, ERPJournalEntry.id == ERPJournalLine.journal_entry_id)
        .filter(
            ERPAccount.organisation_id == organisation_id,
            ERPAccount.is_active.is_(True),
            ERPJournalEntry.organisation_id == organisation_id,
            ERPJournalEntry.entry_date <= end_date,
        )
    )
    if start_date is not None:
        query = query.filter(ERPJournalEntry.entry_date >= start_date)
    rows = query.group_by(
        ERPAccount.id, ERPAccount.account_code, ERPAccount.name, ERPAccount.account_type
    ).order_by(ERPAccount.account_code).all()
    return [
        {
            "account_id": row.account_id,
            "account_code": row.account_code,
            "account_name": row.account_name,
            "account_type": row.account_type,
            "debit": Decimal(row.debit or 0),
            "credit": Decimal(row.credit or 0),
        }
        for row in rows
    ]


def _amount(value: Decimal) -> str:
    return str(value.quantize(Decimal("0.01")))


@router.get("/trial-balance")
def trial_balance(
    as_of: date = Query(default_factory=date.today),
    m: Membership = Depends(require_org_permission("erp.read")),
    db: Session = Depends(get_db),
):
    rows = _ledger_rows(db, m.organisation_id, as_of)
    result = []
    total_debit = Decimal("0")
    total_credit = Decimal("0")
    for row in rows:
        net = row["debit"] - row["credit"]
        debit_balance = max(net, Decimal("0"))
        credit_balance = max(-net, Decimal("0"))
        total_debit += debit_balance
        total_credit += credit_balance
        result.append({
            "account_code": row["account_code"],
            "account_name": row["account_name"],
            "account_type": row["account_type"],
            "debit_balance": _amount(debit_balance),
            "credit_balance": _amount(credit_balance),
        })
    return {
        "as_of": as_of.isoformat(),
        "rows": result,
        "total_debit": _amount(total_debit),
        "total_credit": _amount(total_credit),
        "is_balanced": total_debit == total_credit,
    }


@router.get("/profit-and-loss")
def profit_and_loss(
    start_date: date,
    end_date: date,
    m: Membership = Depends(require_org_permission("erp.read")),
    db: Session = Depends(get_db),
):
    if start_date > end_date:
        raise HTTPException(422, detail="Start date cannot be after end date")
    rows = _ledger_rows(db, m.organisation_id, end_date, start_date)
    income = []
    expenses = []
    total_income = Decimal("0")
    total_expenses = Decimal("0")
    for row in rows:
        if row["account_type"] == "income":
            amount = row["credit"] - row["debit"]
            income.append({"account_code": row["account_code"], "account_name": row["account_name"], "amount": _amount(amount)})
            total_income += amount
        elif row["account_type"] == "expense":
            amount = row["debit"] - row["credit"]
            expenses.append({"account_code": row["account_code"], "account_name": row["account_name"], "amount": _amount(amount)})
            total_expenses += amount
    return {
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "income": income,
        "expenses": expenses,
        "total_income": _amount(total_income),
        "total_expenses": _amount(total_expenses),
        "net_profit": _amount(total_income - total_expenses),
    }


@router.get("/balance-sheet")
def balance_sheet(
    as_of: date = Query(default_factory=date.today),
    m: Membership = Depends(require_org_permission("erp.read")),
    db: Session = Depends(get_db),
):
    rows = _ledger_rows(db, m.organisation_id, as_of)
    assets = []
    liabilities = []
    equity = []
    total_assets = Decimal("0")
    total_liabilities = Decimal("0")
    total_equity = Decimal("0")
    current_earnings = Decimal("0")
    for row in rows:
        if row["account_type"] == "asset":
            amount = row["debit"] - row["credit"]
            assets.append({"account_code": row["account_code"], "account_name": row["account_name"], "amount": _amount(amount)})
            total_assets += amount
        elif row["account_type"] == "liability":
            amount = row["credit"] - row["debit"]
            liabilities.append({"account_code": row["account_code"], "account_name": row["account_name"], "amount": _amount(amount)})
            total_liabilities += amount
        elif row["account_type"] == "equity":
            amount = row["credit"] - row["debit"]
            equity.append({"account_code": row["account_code"], "account_name": row["account_name"], "amount": _amount(amount)})
            total_equity += amount
        elif row["account_type"] == "income":
            current_earnings += row["credit"] - row["debit"]
        elif row["account_type"] == "expense":
            current_earnings -= row["debit"] - row["credit"]
    total_equity += current_earnings
    return {
        "as_of": as_of.isoformat(),
        "assets": assets,
        "liabilities": liabilities,
        "equity": equity,
        "current_earnings": _amount(current_earnings),
        "total_assets": _amount(total_assets),
        "total_liabilities": _amount(total_liabilities),
        "total_equity_and_earnings": _amount(total_equity),
        "liabilities_plus_equity": _amount(total_liabilities + total_equity),
        "is_balanced": total_assets == total_liabilities + total_equity,
    }


@router.get("/stock-movements")
def stock_movements(
    start_date: date | None = None,
    end_date: date | None = None,
    facility_id: int | None = None,
    m: Membership = Depends(require_org_permission("erp.read")),
    db: Session = Depends(get_db),
):
    if start_date and end_date and start_date > end_date:
        raise HTTPException(422, detail="Start date cannot be after end date")
    query = (
        db.query(
            ERPItem.id.label("item_id"),
            ERPItem.item_code,
            ERPItem.name,
            ERPItem.unit,
            ERPStockLedger.facility_id,
            func.coalesce(func.sum(ERPStockLedger.quantity_in), 0).label("quantity_in"),
            func.coalesce(func.sum(ERPStockLedger.quantity_out), 0).label("quantity_out"),
            func.coalesce(func.sum(ERPStockLedger.quantity_in * ERPStockLedger.unit_cost), 0).label("receipt_cost"),
            func.coalesce(func.sum(ERPStockLedger.quantity_out * ERPStockLedger.unit_cost), 0).label("issue_value_at_recorded_rate"),
        )
        .join(ERPStockLedger, ERPStockLedger.item_id == ERPItem.id)
        .filter(ERPItem.organisation_id == m.organisation_id, ERPStockLedger.organisation_id == m.organisation_id)
    )
    if start_date:
        query = query.filter(ERPStockLedger.movement_date >= start_date)
    if end_date:
        query = query.filter(ERPStockLedger.movement_date <= end_date)
    if facility_id is not None:
        query = query.filter(ERPStockLedger.facility_id == facility_id)
    rows = query.group_by(ERPItem.id, ERPItem.item_code, ERPItem.name, ERPItem.unit, ERPStockLedger.facility_id).order_by(ERPItem.item_code).all()
    return [
        {
            "item_id": row.item_id,
            "item_code": row.item_code,
            "name": row.name,
            "unit": row.unit,
            "facility_id": row.facility_id,
            "quantity_in": str(row.quantity_in),
            "quantity_out": str(row.quantity_out),
            "net_quantity": str(Decimal(row.quantity_in or 0) - Decimal(row.quantity_out or 0)),
            "receipt_cost": _amount(Decimal(row.receipt_cost or 0)),
            "issue_cost_at_recorded_rate": _amount(Decimal(row.issue_cost_at_recorded_rate or 0)),
        }
        for row in rows
    ]
