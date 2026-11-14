"""Pure calculation functions for the Global Cost of Capital app."""

def calculate_cost_of_capital(unlevered_beta, debt_weight, tax_rate, erp,
                              us_rf, foreign_rf, us_spread,
                              foreign_spread_override=None):
    """All rates are decimals. Debt weight is D/(D+E)."""
    if not 0 <= debt_weight < 1:
        raise ValueError("Debt weight must be at least 0% and below 100%.")
    if not 0 <= tax_rate < 1:
        raise ValueError("Tax rate must be between 0% and 100%.")
    if unlevered_beta <= 0:
        raise ValueError("Unlevered beta must be positive.")
    de = debt_weight / (1 - debt_weight) if debt_weight else 0.0
    levered_beta = unlevered_beta * (1 + (1 - tax_rate) * de)

    usd_cost_equity = us_rf + levered_beta * erp
    usd_cost_debt = us_rf + us_spread
    usd_after_tax_debt = usd_cost_debt * (1 - tax_rate)
    usd_wacc = (1 - debt_weight) * usd_cost_equity + debt_weight * usd_after_tax_debt

    fx_factor = (1 + foreign_rf) / (1 + us_rf)
    foreign_cost_equity = (1 + usd_cost_equity) * fx_factor - 1
    foreign_spread = (foreign_spread_override if foreign_spread_override is not None
                      else us_spread * fx_factor)
    foreign_cost_debt = foreign_rf + foreign_spread
    foreign_after_tax_debt = foreign_cost_debt * (1 - tax_rate)
    foreign_wacc = ((1 - debt_weight) * foreign_cost_equity
                    + debt_weight * foreign_after_tax_debt)

    return {
        "D/E": de, "Levered beta": levered_beta, "FX conversion factor": fx_factor,
        "USD cost of equity": usd_cost_equity, "USD pretax cost of debt": usd_cost_debt,
        "USD after-tax cost of debt": usd_after_tax_debt, "USD WACC": usd_wacc,
        "Foreign BBB spread": foreign_spread, "Foreign cost of equity": foreign_cost_equity,
        "Foreign pretax cost of debt": foreign_cost_debt,
        "Foreign after-tax cost of debt": foreign_after_tax_debt,
        "Foreign WACC": foreign_wacc,
    }
