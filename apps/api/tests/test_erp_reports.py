from decimal import Decimal

from app.routers.erp_reports import _profit_loss_amount, _trial_balance_sides


def test_trial_balance_splits_net_debit_and_credit_balances():
    assert _trial_balance_sides(Decimal("150.00"), Decimal("40.00")) == (
        Decimal("110.00"), Decimal("0"))
    assert _trial_balance_sides(Decimal("40.00"), Decimal("150.00")) == (
        Decimal("0"), Decimal("110.00"))
    assert _trial_balance_sides(Decimal("75.00"), Decimal("75.00")) == (
        Decimal("0"), Decimal("0"))


def test_profit_and_loss_uses_normal_account_signs():
    assert _profit_loss_amount("income", Decimal("10"), Decimal("110")) == Decimal("100")
    assert _profit_loss_amount("expense", Decimal("90"), Decimal("5")) == Decimal("85")
    assert _profit_loss_amount("asset", Decimal("90"), Decimal("5")) == Decimal("0")
