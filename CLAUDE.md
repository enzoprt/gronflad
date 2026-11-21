# Gronflad

Voyage energy model for low carbon shipping (Python library, `src/gronflad`).

## Rules
- All code, docs and commit messages in English.
- Written text for the author (README, docs, posts): no em-dashes and no semicolons.
- Validation first: every physical model must reproduce a published reference case in `tests/` before it is used elsewhere. Cite the source and page in the module docstring.
- Formulas follow the paper notation (L, B, T_F, C_P, ...) on purpose, so a naval architect can check them line by line against the source.
- Statistical methods must warn (`ValidityWarning`) outside their regression envelope, never extrapolate silently.

## Commands
- Setup: `python3 -m venv .venv && .venv/bin/pip install -e '.[dev]'`
- Tests: `.venv/bin/pytest`
- Web app: `.venv/bin/streamlit run app/streamlit_app.py`
- README figure: `.venv/bin/python examples/resistance_breakdown.py`

## Status
- Done: Holtrop-Mennen 1982 resistance and propulsion factors, validated on the paper's 25 kn example.
- Next: Wageningen B-series (eta_O is still an input), KCS validation, fuels, route + ERA5 wind, Flettner rotor, online deployment of the app.
