# Gronflad

Voyage energy model for low carbon shipping (Python library, `src/gronflad`).

## Rules
- Pure software project: no experiments, only data already published in the literature.
- All code, docs and commit messages in English.
- Written text for the author (README, docs, posts): no em-dashes and no semicolons.
- Validation first: every physical model must reproduce a published reference case in `tests/` before it is used elsewhere. Cite the source and page in the module docstring.
- Formulas follow the paper notation (L, B, T_F, C_P, ...) on purpose, so a naval architect can check them line by line against the source.
- Statistical methods must warn (`ValidityWarning`) outside their regression envelope, never extrapolate silently.

## Deployment
- Live app: https://gronflad.streamlit.app (Streamlit Community Cloud, redeploys on every push to main, entry point `app/streamlit_app.py`, deps in `requirements.txt`).

## Commands
- Setup: `python3 -m venv .venv && .venv/bin/pip install -e '.[dev]'`
- Tests: `.venv/bin/pytest`
- Web app: `.venv/bin/streamlit run app/streamlit_app.py`
- README figures: `.venv/bin/python examples/resistance_breakdown.py` `examples/fuel_comparison.py` and `examples/rotor_savings.py`

## Status
- Done: Holtrop-Mennen 1982 resistance and propulsion factors, Wageningen B-series (K_Q scale correction off by default, as in the paper example), all validated on the paper's 25 kn example. Fuels (FuelEU Annex II factors) and voyage energy. Flettner rotor (Tillig and Ringsberg 2020) with Norsepower limits, routes with ERA5 2024 wind cached in `src/gronflad/data/wind` (refresh with `scripts/fetch_wind.py`).
- Hull drift resistance from rotor side force (`drift.py`, Tillig and Ringsberg eq. 33 and 37).
- KCS comparison (`tests/test_kcs.py`): hull inputs computed from the SIMMAN IGES (`iges.py`, `hydrostatics.py`, `scripts/kcs_hydrostatics.py`), Holtrop about 10 % above the extrapolated model test.
- Per-leg savings (`WindAssistResult.legs`, `leg_net_fraction`, `leg_mean_wind`) shown as a map and an along-route chart in the app.
- Rotor strips with a local spin ratio above 4 (following wind near ship speed) keep the coefficients of spin ratio 4, power grows with omega cubed (`rotor.strip_coefficients`).
- Next: rudder resistance and yaw balance, more routes.
