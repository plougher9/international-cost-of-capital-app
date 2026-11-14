from model import calculate_cost_of_capital

def test_professor_colombia_example():
    r = calculate_cost_of_capital(.80, .30, .35, .065, .04, .12, .015)
    assert abs(r["Levered beta"] - 1.0228571429) < 1e-8
    assert abs(r["USD cost of equity"] - .1064857143) < 1e-8
    assert abs(r["USD WACC"] - .085265) < 0.0001
    assert abs(r["Foreign WACC"] - .16067) < 0.001

def test_equal_yields_produce_equal_wacc():
    r = calculate_cost_of_capital(.80, .30, .35, .065, .04, .04, .015)
    assert abs(r["USD WACC"] - r["Foreign WACC"]) < 1e-10

def test_zero_debt_means_wacc_equals_equity_cost():
    r = calculate_cost_of_capital(.80, 0, .35, .065, .04, .12, .015)
    assert abs(r["USD WACC"] - r["USD cost of equity"]) < 1e-10
    assert abs(r["Foreign WACC"] - r["Foreign cost of equity"]) < 1e-10

def test_foreign_spread_override_does_not_change_usd():
    base = calculate_cost_of_capital(.80, .30, .35, .065, .04, .12, .015)
    override = calculate_cost_of_capital(.80, .30, .35, .065, .04, .12, .015, .04)
    assert base["USD WACC"] == override["USD WACC"]
    assert base["USD cost of equity"] == override["USD cost of equity"]
