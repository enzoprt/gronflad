"""Gronflad web demo.

Run: streamlit run app/streamlit_app.py
"""

import warnings
from dataclasses import replace

import altair as alt
import pandas as pd
import streamlit as st

from gronflad import KNOT, Hull, Propeller, ValidityWarning, propulsion, resistance
from gronflad.ships import HM1982_HULL, HM1982_PROPELLER
from gronflad.wageningen import BSeries

PUBLISHED = {  # Holtrop and Mennen (1982), p. 170, 25 knots
    "Total resistance R_T (kN)": 1793.26,
    "Effective power P_E (kW)": 23063,
    "Wake fraction w": 0.2584,
    "Thrust deduction t": 0.1747,
    "Relative rotative efficiency η_R": 0.9931,
    "Shaft power P_S (kW)": 32621,
    "Propeller speed n (rpm)": 1.6594 * 60,
    "Open water efficiency η_O": 0.6461,
}
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]

st.set_page_config(page_title="Gronflad", page_icon="⚓", layout="wide")
st.title("Gronflad")
st.caption(
    "Voyage energy model for low carbon shipping. Calm water resistance and propulsion with the "
    "Holtrop and Mennen (1982) method and a Wageningen B-series propeller, validated against the published example."
)

with st.sidebar:
    st.header("Hull")
    h = HM1982_HULL
    L = st.number_input("Waterline length L (m)", 50.0, 400.0, h.L, 1.0)
    B = st.number_input("Breadth B (m)", 5.0, 70.0, h.B, 0.5)
    T = st.number_input("Draught T (m)", 1.0, 25.0, h.T, 0.1)
    volume = st.number_input("Displacement volume (m³)", 1000.0, 400000.0, h.volume, 500.0)
    lcb = st.number_input("LCB (% of L from midship, + forward)", -5.0, 5.0, h.lcb, 0.05)
    C_M = st.number_input("Midship coefficient C_M", 0.80, 1.0, h.C_M, 0.005)
    C_WP = st.number_input("Waterplane coefficient C_WP", 0.60, 0.95, h.C_WP, 0.005)
    C_stern = st.select_slider(
        "Afterbody shape", options=[-10.0, 0.0, 10.0], value=h.C_stern,
        format_func={-10.0: "V sections", 0.0: "Normal", 10.0: "U with Hogner stern"}.get,
    )
    with st.expander("Bulb, transom and appendages"):
        A_BT = st.number_input("Bulb transverse area A_BT (m²)", 0.0, 100.0, h.A_BT, 1.0)
        h_B = st.number_input("Bulb centroid height h_B (m)", 0.0, 15.0, h.h_B, 0.1)
        A_T = st.number_input("Immersed transom area A_T (m²)", 0.0, 100.0, h.A_T, 1.0)
        S_APP = st.number_input("Appendage wetted area (m²)", 0.0, 500.0, h.S_APP, 5.0)

    st.header("Propeller")
    D = st.number_input("Diameter D (m)", 1.0, 12.0, HM1982_PROPELLER.D, 0.1)
    Z = st.select_slider("Number of blades", options=[3, 4, 5, 6], value=HM1982_PROPELLER.Z)
    model = st.radio("Open water model", ["Wageningen B-series", "Manual η_O"], horizontal=True)
    eta_O, P_D = None, None
    if model == "Wageningen B-series":
        if not st.toggle("Optimise pitch at design speed", value=True):
            P_D = st.slider("Pitch ratio P/D", 0.5, 1.4, 1.0, 0.01)
    else:
        eta_O = st.slider("Open water efficiency η_O", 0.40, 0.80, 0.65, 0.005)

    st.header("Speed")
    v_design = st.slider("Design speed (knots)", 5.0, 30.0, 25.0, 0.5)
    v_min, v_max = st.slider("Speed range for curves (knots)", 3.0, 32.0, (10.0, 26.0), 0.5)

hull = replace(
    HM1982_HULL, name="hull", L=L, B=B, T_F=T, T_A=T, volume=volume, lcb=lcb,
    C_M=C_M, C_WP=C_WP, A_BT=A_BT, h_B=h_B, A_T=A_T, S_APP=S_APP, C_stern=C_stern,
)
prop = Propeller(D=D, Z=Z, clearance=HM1982_PROPELLER.clearance, P_D=P_D)
is_reference = hull == replace(HM1982_HULL, name="hull") and prop == HM1982_PROPELLER

with warnings.catch_warnings(record=True) as caught:
    warnings.simplefilter("always", ValidityWarning)
    res = resistance(hull, v_design * KNOT)
    p = propulsion(hull, prop, res, eta_O=eta_O)
for issue in sorted({str(w.message).removeprefix("hull: ") for w in caught}):
    st.warning(f"Outside the validity range of the method: {issue}. Results are extrapolated.")

# Off design points keep the design pitch, as for a real fixed pitch propeller
curve_prop = replace(prop, P_D=p.P_D) if p.P_D is not None else prop

c = st.columns(6)
c[0].metric("Total resistance", f"{res.R_T / 1e3:,.0f} kN")
c[1].metric("Effective power", f"{res.P_E / 1e6:,.2f} MW")
c[2].metric("Shaft power", f"{p.P_S / 1e6:,.2f} MW")
c[3].metric("Propulsive efficiency η_D", f"{p.eta_D:.3f}")
c[4].metric("Propeller speed", f"{p.n * 60:.1f} rpm" if p.n else "n/a")
c[5].metric("Froude number", f"{res.Fn:.3f}")

tab_curves, tab_propeller, tab_details, tab_validation = st.tabs(
    ["Speed curves", "Propeller", "Breakdown at design speed", "Validation"]
)

with tab_curves:
    speeds = [v_min + i * (v_max - v_min) / 80 for i in range(81)]
    rows, power = [], []
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", ValidityWarning)
        for v in speeds:
            r = resistance(hull, v * KNOT)
            parts = {
                "Viscous (friction x form factor)": r.form_factor * r.R_F,
                "Wave making": r.R_W,
                "Correlation allowance": r.R_A,
                "Appendages, bulb, transom": r.R_APP + r.R_B + r.R_TR,
            }
            rows += [{"Speed (kn)": v, "Component": k, "Resistance (kN)": x / 1e3} for k, x in parts.items()]
            power.append({"Speed (kn)": v, "Shaft power (MW)": propulsion(hull, curve_prop, r, eta_O).P_S / 1e6})

    order = list(parts)
    area = (
        alt.Chart(pd.DataFrame(rows))
        .mark_area(stroke="white", strokeWidth=1)
        .encode(
            x=alt.X("Speed (kn):Q", scale=alt.Scale(domain=[v_min, v_max])),
            y=alt.Y("Resistance (kN):Q", stack=True),
            color=alt.Color("Component:N", sort=order, scale=alt.Scale(domain=order, range=SERIES),
                            legend=alt.Legend(orient="top", title=None, labelLimit=0)),
            order=alt.Order("order:Q"),
            tooltip=["Component", alt.Tooltip("Speed (kn):Q", format=".1f"),
                     alt.Tooltip("Resistance (kN):Q", format=",.0f")],
        )
        .transform_calculate(order=f"indexof({order}, datum.Component)")
        .properties(title="Calm water resistance breakdown", height=380)
    )
    st.altair_chart(area, width="stretch")

    line = (
        alt.Chart(pd.DataFrame(power))
        .mark_line(strokeWidth=2, color=SERIES[0])
        .encode(
            x=alt.X("Speed (kn):Q", scale=alt.Scale(domain=[v_min, v_max])),
            y="Shaft power (MW):Q",
            tooltip=[alt.Tooltip("Speed (kn):Q", format=".1f"), alt.Tooltip("Shaft power (MW):Q", format=".2f")],
        )
        .properties(title="Required shaft power", height=300)
    )
    st.altair_chart(line, width="stretch")
    st.caption("Power grows roughly with the cube of speed. Slow steaming is the cheapest decarbonisation lever.")

with tab_propeller:
    if p.P_D is None:
        st.info("Select the Wageningen B-series model in the sidebar to see the propeller curves.")
    else:
        bs = BSeries(D=prop.D, Z=prop.Z, AE_A0=p.AE_A0, P_D=p.P_D)
        J_max = next(j / 100 for j in range(5, 200) if bs.kt(j / 100) <= 0)
        curves = []
        for i in range(101):
            J = 0.01 + i * (J_max - 0.02) / 100
            kt, kq = bs.kt(J), bs.kq(J)
            curves += [
                {"J": J, "Curve": "K_T", "Value": kt},
                {"J": J, "Curve": "10 K_Q", "Value": 10 * kq},
                {"J": J, "Curve": "η_O", "Value": J * kt / (2 * 3.141592653589793 * kq)},
            ]
        names = ["K_T", "10 K_Q", "η_O"]
        lines = (
            alt.Chart(pd.DataFrame(curves))
            .mark_line(strokeWidth=2)
            .encode(
                x=alt.X("J:Q", title="Advance coefficient J"),
                y=alt.Y("Value:Q", title=None, scale=alt.Scale(domain=[0, max(0.9, 10 * bs.kq(0.01))])),
                color=alt.Color("Curve:N", sort=names, scale=alt.Scale(domain=names, range=SERIES[:3]),
                                legend=alt.Legend(orient="top", title=None)),
                tooltip=["Curve", alt.Tooltip("J:Q", format=".3f"), alt.Tooltip("Value:Q", format=".4f")],
            )
        )
        rule = alt.Chart(pd.DataFrame({"J": [p.J]})).mark_rule(strokeDash=[4, 4], color="#52514e").encode(x="J:Q")
        st.altair_chart(
            (lines + rule).properties(
                title=f"Open water diagram, B{prop.Z}-{round(p.AE_A0 * 100)} at P/D = {p.P_D:.3f}", height=380
            ),
            width="stretch",
        )
        st.caption(
            f"Dashed line: operating point at {v_design:g} kn (J = {p.J:.3f}, η_O = {p.eta_O:.3f}). "
            "Full scale K_T with the Holtrop and Mennen (1982) drag correction."
        )

with tab_details:
    left, right = st.columns(2)
    left.subheader("Resistance")
    left.dataframe(
        pd.DataFrame(
            {
                "Component": ["Friction R_F", "Form factor 1+k₁", "Appendages R_APP", "Wave R_W",
                              "Bulb R_B", "Transom R_TR", "Correlation R_A", "Total R_T"],
                "Value": [f"{res.R_F / 1e3:,.1f} kN", f"{res.form_factor:.3f}", f"{res.R_APP / 1e3:,.1f} kN",
                          f"{res.R_W / 1e3:,.1f} kN", f"{res.R_B / 1e3:,.2f} kN", f"{res.R_TR / 1e3:,.1f} kN",
                          f"{res.R_A / 1e3:,.1f} kN", f"{res.R_T / 1e3:,.1f} kN"],
            }
        ),
        hide_index=True, width="stretch",
    )
    right.subheader("Propulsion")
    right.dataframe(
        pd.DataFrame(
            {
                "Factor": ["Wake fraction w", "Thrust deduction t", "Hull efficiency η_H",
                           "Relative rotative η_R", "Open water η_O", "Blade area ratio A_E/A_0 (Keller)",
                           "Pitch ratio P/D", "Advance coefficient J", "Thrust", "Shaft power P_S"],
                "Value": [f"{p.w:.4f}", f"{p.t:.4f}", f"{p.eta_H:.4f}", f"{p.eta_R:.4f}", f"{p.eta_O:.4f}",
                          f"{p.AE_A0:.4f}", f"{p.P_D:.3f}" if p.P_D else "n/a", f"{p.J:.4f}" if p.J else "n/a",
                          f"{p.thrust / 1e3:,.0f} kN", f"{p.P_S / 1e3:,.0f} kW"],
            }
        ),
        hide_index=True, width="stretch",
    )
    st.caption(f"Hull: C_B = {hull.C_B:.4f}, C_P = {hull.C_P:.4f}, wetted surface S = {hull.wetted_surface:,.1f} m²")

with tab_validation:
    st.markdown(
        "The default inputs are the numerical example of Holtrop and Mennen (1982), a 205 m single "
        "screw ship at 25 knots. Starting from the hull alone, with a B-series propeller at optimum "
        "pitch, Gronflad reproduces the published values:"
    )
    ref = HM1982_HULL
    r25 = resistance(ref, 25 * KNOT)
    p25 = propulsion(ref, HM1982_PROPELLER, r25)
    ours = [r25.R_T / 1e3, r25.P_E / 1e3, p25.w, p25.t, p25.eta_R, p25.P_S / 1e3, p25.n * 60, p25.eta_O]
    st.dataframe(
        pd.DataFrame(
            {
                "Quantity": list(PUBLISHED),
                "Published": list(PUBLISHED.values()),
                "Gronflad": ours,
                "Deviation (%)": [abs(o - p) / p * 100 for o, p in zip(ours, PUBLISHED.values())],
            }
        ).style.format(lambda x: f"{x:,.4f}" if x < 10 else f"{x:,.0f}", subset=["Published", "Gronflad"])
        .format("{:.2f}", subset=["Deviation (%)"]),
        hide_index=True, width="stretch",
    )
    if not is_reference:
        st.info("You changed the inputs. The table above always shows the reference case.")
