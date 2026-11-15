from app.routers.erp_reports import normal_side


def test_account_normal_balance_side():
    assert normal_side("asset") == "debit"
    assert normal_side("expense") == "debit"
    assert normal_side("liability") == "credit"
    assert normal_side("equity") == "credit"
    assert normal_side("income") == "credit"
