"""Gronflad web demo.

Run: streamlit run app/streamlit_app.py
"""

import warnings
from dataclasses import replace

import altair as alt
import pandas as pd
import pydeck as pdk
import streamlit as st

from gronflad import KNOT, Hull, Propeller, ValidityWarning, propulsion, resistance
from gronflad.ships import HM1982_HULL, HM1982_PROPELLER, KCS_HULL, KCS_PROPELLER
from gronflad.fuels import FUELS, MGO, fueleu_limit, wind_reward
from gronflad.rotor import FlettnerRotor
from gronflad.route import ROUTES, load_wind, total_distance, track
from gronflad.voyage import Voyage, compare_fuels, teu_slots, voyage_energy
from gronflad.wind_assist import TWA_GRID, TWS_GRID, assisted_energy, rotor_table, route_saving, shaft_power_per_newton
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
    presets = {
        "Holtrop-Mennen 1982 example (205 m)": (HM1982_HULL, HM1982_PROPELLER, 25.0),
        "KRISO Container Ship, KCS (230 m)": (KCS_HULL, KCS_PROPELLER, 24.0),
    }
    h, preset_prop, preset_speed = presets[st.selectbox("Ship", list(presets))]
    st.header("Hull")
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
    D = st.number_input("Diameter D (m)", 1.0, 12.0, preset_prop.D, 0.1)
    Z = st.select_slider("Number of blades", options=[3, 4, 5, 6], value=preset_prop.Z)
    model = st.radio("Open water model", ["Wageningen B-series", "Manual η_O"], horizontal=True)
    eta_O, P_D = None, None
    if model == "Wageningen B-series":
        if not st.toggle("Optimise pitch at design speed", value=True):
            P_D = st.slider("Pitch ratio P/D", 0.5, 1.4, 1.0, 0.01)
    else:
        eta_O = st.slider("Open water efficiency η_O", 0.40, 0.80, 0.65, 0.005)

    st.header("Speed")
    v_design = st.slider("Design speed (knots)", 5.0, 30.0, preset_speed, 0.5)
    v_min, v_max = st.slider("Speed range for curves (knots)", 3.0, 32.0, (10.0, 26.0), 0.5)

    st.header("Voyage")
    route_options = {"Custom distance": None, **{r.name: r for r in ROUTES.values()}}
    route = route_options[st.selectbox("Route", list(route_options), index=1)]
    if route:
        reverse = st.toggle("Sail the route in reverse")
        distance = total_distance(route)
        st.caption(f"{distance:,.0f} nm along great circle legs, ERA5 wind of 2024")
    else:
        reverse = False
        distance = st.number_input("Distance (nautical miles)", 100.0, 20000.0, 5000.0, 100.0)
    sea_margin = st.slider("Sea margin over calm water (%)", 0, 40, 15, 1) / 100
    engine_eff = st.slider("Engine efficiency", 0.30, 0.60, 0.50, 0.01,
                           help="0.50 is a two-stroke diesel at about 170 g/kWh on MGO.")
    year = st.select_slider("FuelEU reporting year", options=[2025, 2030, 2035, 2040, 2045, 2050], value=2030)
    default_fuels = ["HFO", "MGO", "LNG, Otto medium speed", "LNG, Diesel slow speed",
                     "Methanol (natural gas)", "Ammonia (natural gas)", "e-Methanol", "e-Ammonia"]
    chosen = st.multiselect("Fuels to compare", list(FUELS), default=default_fuels)

    st.header("Wind assistance")
    n_rotors = st.slider("Number of Flettner rotors", 0, 6, 2, help="Needs a route with wind data.")
    rotor_D = st.number_input("Rotor diameter (m)", 2.0, 8.0, 5.0, 0.5)
    rotor_H = st.number_input("Rotor height (m)", 10.0, 40.0, 30.0, 1.0)
    rotor_base = st.number_input("Rotor foot above waterline (m)", 5.0, 50.0, 20.0, 1.0)

hull = replace(
    h, name="hull", L=L, B=B, T_F=T, T_A=T, volume=volume, lcb=lcb,
    C_M=C_M, C_WP=C_WP, A_BT=A_BT, h_B=h_B, A_T=A_T, S_APP=S_APP, C_stern=C_stern,
)
if hull != replace(h, name="hull"):
    # Measured wetted surface and entrance angle no longer apply to a modified hull
    hull = replace(hull, S=None, i_E=None)
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


@st.cache_data(show_spinner="Running a year of ERA5 wind along the route...")
def cached_route_saving(hull, prop, rotor, slug, speed_kn, reverse, eta_O):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", ValidityWarning)
        return route_saving(hull, prop, rotor, load_wind(ROUTES[slug]), speed_kn, reverse=reverse, eta_O=eta_O)


@st.cache_data
def cached_rotor_table(hull, prop, rotor, speed_kn, eta_O):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", ValidityWarning)
        return rotor_table(rotor, speed_kn * KNOT, shaft_power_per_newton(hull, prop, speed_kn, eta_O), hull)


def leg_map(route, assist):
    """Route track and legs coloured by their mean net saving."""
    top = max(max(assist.leg_net_fraction), 1e-9)
    rows = []
    for leg, frac, tws in zip(assist.legs, assist.leg_net_fraction, assist.leg_mean_wind):
        f = max(frac, 0.0) / top
        # Light to dark blue, from #b4d2f5 to #0f3c8a
        color = [round(180 + (15 - 180) * f), round(210 + (60 - 210) * f), round(245 + (138 - 245) * f)]
        rows.append({"lat": leg.lat, "lon": leg.lon, "color": color,
                     "saving": f"{frac:.1%}", "wind": f"{tws:.1f}"})
    path = [{"path": [[lon, lat] for lat, lon in track(route)]}]
    view = pdk.data_utils.compute_view([[r["lon"], r["lat"]] for r in rows])
    view.zoom = max(view.zoom - 0.6, 0.5)
    return pdk.Deck(
        layers=[
            pdk.Layer("PathLayer", path, get_path="path", get_color=[120, 120, 120], width_min_pixels=1),
            pdk.Layer("ScatterplotLayer", pd.DataFrame(rows), get_position=["lon", "lat"], get_fill_color="color",
                      get_line_color=[60, 60, 60], stroked=True, line_width_min_pixels=0.5,
                      radius_min_pixels=5, radius_max_pixels=9, get_radius=40000, pickable=True),
        ],
        initial_view_state=view,
        tooltip={"text": "Net saving {saving}\nMean wind {wind} m/s"},
        map_style="light",
    )


rotor = FlettnerRotor(D=rotor_D, H=rotor_H, base_height=rotor_base, count=n_rotors)
assist = cached_route_saving(hull, curve_prop, rotor, route.slug, v_design, reverse, eta_O) if route and n_rotors else None

c = st.columns(3) + st.columns(3)
c[0].metric("Total resistance", f"{res.R_T / 1e3:,.0f} kN")
c[1].metric("Effective power", f"{res.P_E / 1e6:,.2f} MW")
c[2].metric("Shaft power", f"{p.P_S / 1e6:,.2f} MW")
c[3].metric("Propulsive efficiency η_D", f"{p.eta_D:.3f}")
c[4].metric("Propeller speed", f"{p.n * 60:.1f} rpm" if p.n else "n/a")
c[5].metric("Froude number", f"{res.Fn:.3f}")

tab_curves, tab_propeller, tab_fuels, tab_wind, tab_details, tab_validation = st.tabs(
    ["Speed curves", "Propeller", "Voyage & fuels", "Wind assistance", "Breakdown at design speed", "Validation"]
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

with tab_fuels:
    voyage = Voyage(distance_nm=distance, speed_kn=v_design, sea_margin=sea_margin, engine_efficiency=engine_eff)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", ValidityWarning)
        energy_no_wind = voyage_energy(hull, prop, voyage, eta_O=eta_O)
    energy = assisted_energy(energy_no_wind, assist) if assist else energy_no_wind
    f_wind = wind_reward(assist.wind_power_ratio) if assist else 1.0
    uses = compare_fuels(energy, [FUELS[name] for name in chosen], f_wind)
    mgo_storage = compare_fuels(energy, [MGO])[0].storage_volume
    limit = fueleu_limit(year)

    c = st.columns(4)
    c[0].metric("Voyage duration", f"{voyage.duration_h / 24:.1f} days")
    c[1].metric("Service shaft power", f"{energy.P_service / 1e6:.1f} MW")
    c[2].metric(
        "Fuel energy", f"{energy.fuel_energy / 1e6:,.1f} TJ",
        delta=f"{energy.fuel_energy / energy_no_wind.fuel_energy - 1:.1%} with rotors" if assist else None,
        delta_color="inverse",
    )
    c[3].metric(f"FuelEU limit {year}", f"{limit:.1f} g/MJ")

    if not uses:
        st.info("Pick at least one fuel in the sidebar.")
    else:
        table = pd.DataFrame(
            {
                "Fuel": [u.fuel.name for u in uses],
                "Mass (t)": [u.mass for u in uses],
                "Storage volume (m³)": [u.storage_volume for u in uses],
                "Extra TEU slots vs MGO": [teu_slots(u.storage_volume - mgo_storage) for u in uses],
                "WtW intensity (gCO2eq/MJ)": [u.intensity for u in uses],
                "WtW GHG (t CO2eq)": [u.ghg for u in uses],
                f"FuelEU {year}": ["compliant" if u.complies(year) else "deficit" for u in uses],
                f"Penalty {year} (k EUR)": [u.fueleu_penalty(year) / 1e3 for u in uses],
            }
        )
        bars = (
            alt.Chart(table)
            .mark_bar(color=SERIES[0], cornerRadiusEnd=4, height={"band": 0.6})
            .encode(
                x=alt.X("WtW intensity (gCO2eq/MJ):Q", title="Well-to-wake GHG intensity (gCO2eq/MJ)"),
                y=alt.Y("Fuel:N", sort="-x", title=None, axis=alt.Axis(labelLimit=0)),
                tooltip=["Fuel", alt.Tooltip("WtW intensity (gCO2eq/MJ):Q", format=".1f"),
                         alt.Tooltip("WtW GHG (t CO2eq):Q", format=",.0f")],
            )
        )
        rule = alt.Chart(pd.DataFrame({"x": [limit]})).mark_rule(color="#52514e", strokeDash=[4, 4]).encode(x="x:Q")
        label = (
            alt.Chart(pd.DataFrame({"x": [limit], "t": [f"FuelEU {year} limit"]}))
            .mark_text(align="left", dx=4, dy=-6, color="#52514e")
            .encode(x="x:Q", y=alt.value(0), text="t:N")
        )
        st.altair_chart((bars + rule + label).properties(title="GHG intensity per fuel", height=34 * len(uses) + 40),
                        width="stretch")

        storage = (
            alt.Chart(table.assign(ratio=table["Storage volume (m³)"] / mgo_storage))
            .mark_bar(color=SERIES[0], cornerRadiusEnd=4, height={"band": 0.6})
            .encode(
                x=alt.X("ratio:Q", title="Storage volume relative to MGO tanks"),
                y=alt.Y("Fuel:N", sort="-x", title=None, axis=alt.Axis(labelLimit=0)),
                tooltip=["Fuel", alt.Tooltip("Storage volume (m³):Q", format=",.0f"),
                         alt.Tooltip("Extra TEU slots vs MGO:Q", format=",.0f")],
            )
            .properties(title="Bunker storage volume for this voyage", height=34 * len(uses) + 40)
        )
        st.altair_chart(storage, width="stretch")

        st.dataframe(
            table.style.format(
                {"Mass (t)": "{:,.0f}", "Storage volume (m³)": "{:,.0f}", "Extra TEU slots vs MGO": "{:,.0f}",
                 "WtW intensity (gCO2eq/MJ)": "{:.1f}", "WtW GHG (t CO2eq)": "{:,.0f}",
                 f"Penalty {year} (k EUR)": "{:,.0f}"}
            ),
            hide_index=True, width="stretch",
        )
        st.caption(
            "Emission factors: FuelEU Maritime, Annex II. Grey ammonia, hydrogen and methanol are made from "
            "natural gas. e-fuels are set at the minimum saving that qualifies as RFNBO (28.2 gCO2eq/MJ). "
            "Storage volumes include tank systems and are indicative (DNV GL, 2020). The penalty assumes "
            "the whole voyage is in FuelEU scope, without the RFNBO multiplier or pilot fuel."
        )

with tab_wind:
    if not route:
        st.info("Pick a route in the sidebar to use a year of real wind.")
    elif not n_rotors:
        st.info("Add at least one Flettner rotor in the sidebar.")
    else:
        c = st.columns(4)
        c[0].metric("Net saving in propulsion power", f"{assist.net_fraction:.1%}")
        c[1].metric("Mean net rotor thrust", f"{assist.mean_thrust / 1e3:,.0f} kN",
                    help="Rotor thrust minus the hull drift resistance caused by the side force.")
        c[2].metric("Mean rotor motor power", f"{assist.rotor_power / 1e3:,.0f} kW")
        c[3].metric("FuelEU wind reward f_wind", f"{wind_reward(assist.wind_power_ratio):.2f}")

        left, right = st.columns([3, 2])
        with left:
            table = cached_rotor_table(hull, curve_prop, rotor, v_design, eta_O)
            rows = [
                {"True wind angle (deg)": twa, "Wind": f"{tws:g} m/s", "Thrust (kN)": table.thrust[int(tws)][j] / 1e3}
                for tws in (5.0, 10.0, 15.0)
                for j, twa in enumerate(TWA_GRID)
            ]
            winds = ["5 m/s", "10 m/s", "15 m/s"]
            polar = (
                alt.Chart(pd.DataFrame(rows))
                .mark_line(strokeWidth=2)
                .encode(
                    x=alt.X("True wind angle (deg):Q", scale=alt.Scale(domain=[0, 180]),
                            axis=alt.Axis(values=list(range(0, 181, 30)))),
                    y="Thrust (kN):Q",
                    color=alt.Color("Wind:N", sort=winds, scale=alt.Scale(domain=winds, range=SERIES[:3]),
                                    legend=alt.Legend(orient="top", title="True wind at 10 m")),
                    tooltip=["Wind", "True wind angle (deg):Q", alt.Tooltip("Thrust (kN):Q", format=",.0f")],
                )
                .properties(title=f"Net thrust of {n_rotors} rotor(s) at {v_design:g} kn, optimal spin", height=320)
            )
            st.altair_chart(polar, width="stretch")
            st.caption("0 deg is a head wind, 180 deg a following wind. Beam to broad reach winds work best.")
        with right:
            st.pydeck_chart(leg_map(route, assist), height=360)
            st.caption("Each dot is a 200 nm leg, darker where the rotors save more. Hover for values.")

        start = 0.0
        leg_rows = []
        for leg, frac, tws in zip(assist.legs, assist.leg_net_fraction, assist.leg_mean_wind):
            leg_rows.append({"From (nm)": start, "To (nm)": start + leg.length_nm, "Net saving": frac,
                             "Mean wind (m/s)": tws})
            start += leg.length_nm
        along = (
            alt.Chart(pd.DataFrame(leg_rows))
            .mark_rect(color=SERIES[0], stroke="white", strokeWidth=1)
            .encode(
                x=alt.X("From (nm):Q", title="Distance from departure (nm)", scale=alt.Scale(domain=[0, start], nice=False)),
                x2="To (nm):Q",
                y=alt.Y("Net saving:Q", axis=alt.Axis(format="%")),
                y2=alt.datum(0),
                tooltip=[alt.Tooltip("From (nm):Q", format=",.0f"), alt.Tooltip("To (nm):Q", format=",.0f"),
                         alt.Tooltip("Net saving:Q", format=".1%"),
                         alt.Tooltip("Mean wind (m/s):Q", format=".1f")],
            )
            .properties(title="Net saving in propulsion power along the route, mean of 2024", height=240)
        )
        st.altair_chart(along, width="stretch")

        months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        monthly = (
            alt.Chart(pd.DataFrame({"Month": months, "Net saving": assist.monthly_net_fraction}))
            .mark_bar(color=SERIES[0], cornerRadiusEnd=4)
            .encode(
                x=alt.X("Month:N", sort=months, title=None),
                y=alt.Y("Net saving:Q", axis=alt.Axis(format="%")),
                tooltip=["Month", alt.Tooltip("Net saving:Q", format=".1%")],
            )
            .properties(title="Net saving in propulsion power per month, ERA5 2024", height=260)
        )
        st.altair_chart(monthly, width="stretch")
        st.caption(
            "Rotor coefficients from Tillig and Ringsberg (2020), fitted to full-scale measurements. "
            "Every 6 hour ERA5 sample on every 200 nm leg is used, with the rotor speed optimised each time. "
            "The hull drift resistance from the side force is deducted (Tillig and Ringsberg, 2020). "
            "Rotor interaction and rudder resistance are not modelled, so these savings remain an upper bound."
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
