# Global Cost of Capital

A Streamlit app that estimates project WACC in USD and a selected foreign currency using the class-slide framework.

## Run locally

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
streamlit run app.py
```

## Deploy

1. Create a public GitHub repository and upload `app.py`, `requirements.txt`, and `README.md`.
2. Go to https://share.streamlit.io/ and sign in with GitHub.
3. Select the repository, branch `main`, and main file path `app.py`.
4. Deploy. The public app URL can be copied from Streamlit Community Cloud.

## Model equations

- Relevering: `beta_E = beta_U * (1 + (1 - tax) * debt_weight / (1 - debt_weight))`
- USD equity cost: `R_E = R_f + beta_E * ERP`
- USD debt cost: `R_D = R_f + spread`
- Foreign equity cost: `(1 + R_E_foreign) = (1 + R_E_USD) * (1 + R_f_foreign) / (1 + R_f_USD)`
- Foreign spread: `spread_foreign = spread_USD * (1 + R_f_foreign) / (1 + R_f_USD)` unless overridden
- WACC: `(1 - debt_weight) * cost_of_equity + debt_weight * cost_of_debt * (1 - tax)`

All input rates in the UI are percentages; the calculation function uses decimals.

## Data sources

- Damodaran industry betas: https://pages.stern.nyu.edu/~adamodar/pc/datasets/betas.xls
- Damodaran ratings / default spreads: https://pages.stern.nyu.edu/adamodar/New_Home_Page/datafile/ratings.html
- OECD Corporate Tax Statistics 2024: https://www.oecd.org/en/publications/corporate-tax-statistics-2024_9c27d6e8-en/full-report/statutory-corporate-income-tax-rates_440f9286.html
- Trading Economics 10-year government bond yields: https://tradingeconomics.com/country-list/government-bond-10y

Source parsers are cached for 24 hours. If a provider changes its HTML or blocks requests, the app exposes the source status and provides manual overrides. Check fallback values against the linked sources before using the model in a submitted analysis.

## Run calculation tests

```bash
pytest -q
```

## Verification

The professor's slide example (unlevered beta 0.80, debt share 30%, tax 35%, ERP 6.5%, U.S. yield 4%, Colombia yield 12%, U.S. BBB spread 1.5%) should produce approximately:
- Levered beta: 1.0229
- USD cost of equity: 10.6486%
- USD WACC: 8.5265%
- COP cost of equity: 19.16%
- COP WACC: 16.07%

Additional checks:
1. Equal U.S. and foreign government yields with no foreign spread override should give equal USD and foreign WACC.
2. With debt share set to zero, WACC equals cost of equity.
3. Changing only the foreign BBB override must not change USD outputs.
