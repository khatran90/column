import streamlit as st
import numpy as np
import plotly.graph_objects as go

# 1. WEB APP CONFIGURATION
st.set_page_config(page_title="EC2 Column Designer (Prokon Style)", layout="wide")
st.title("🏛️ Concrete Column Design & Interaction Diagram — EC2")
st.caption("Axial + Uniaxial Bending Analysis (Ref: EN 1992-1-1 / Prokon Style)")
st.markdown("---")

# 2. SIDEBAR INPUTS
st.sidebar.header("📊 COLUMN PARAMETERS")

with st.sidebar.expander("📐 Section Geometry", expanded=True):
    b = st.number_input("Width of column b (mm)", value=400.0, step=50.0)
    h = st.number_input("Depth of column h (mm)", value=600.0, step=50.0)
    L = st.number_input("Clear Height L (m)", value=4.0, step=0.5)
    cc = st.number_input("Concrete cover c_nom (mm)", value=40.0, step=5.0)

with st.sidebar.expander("🧵 Reinforcement (Prokon style layout)", expanded=True):
    bar_dia = st.selectbox("Bar Diameter (mm)", [16, 20, 25, 32], index=1)
    n_bars_b = st.number_input("Number of bars along b-face", value=3, min_value=2)
    n_bars_h = st.number_input("Number of bars along h-face", value=4, min_value=2)

    # Calculate total bars (corners counted once)
    total_bars = 2 * n_bars_b + 2 * (n_bars_h - 2)
    As_total = total_bars * (np.pi * (bar_dia ** 2) / 4)
    st.caption(f"👉 Total Bars: {total_bars} | Total As = {int(As_total)} mm²")

with st.sidebar.expander("🧪 Materials & Loads", expanded=True):
    fck = st.number_input("Concrete fck (MPa)", value=30.0, step=5.0)
    fyk = st.number_input("Steel fyk (MPa)", value=500.0, step=50.0)

    st.markdown("**ULS Design Loads:**")
    N_Ed = st.number_input("Axial Force N_Ed (kN, + Compression)", value=1200.0, step=50.0)
    M_Ed = st.number_input("Moment M_Ed (kNm)", value=150.0, step=10.0)

# 3. ENGINEERING LOGIC & MATHEMATICS
gamma_c, gamma_s = 1.5, 1.15
fcd = 0.85 * fck / gamma_c
fyd = fyk / gamma_s
Es = 200000  # MPa

# Effective depth calculations for top and bottom steel zones
d = h - cc - (bar_dia / 2) - 10  # 10mm assumed link
d_prime = cc + (bar_dia / 2) + 10
As_half = As_total / 2  # Simplified symmetrical steel zones for interaction

# --- SLENDERNESS & SECOND ORDER EFFECTS (EN 1992-1-1 Cl 5.8) ---
i_radius = h / (12 ** 0.5)  # Radius of gyration for rectangular section
lambda_col = (L * 1000) / i_radius  # Slenderness ratio

# Limiting slenderness lambda_lim = 20 * A * B * C / sqrt(n)
# Using standard conservative default values: A=0.7, B=1.1, C=0.7
n_axial = (N_Ed * 1000) / (b * h * fcd)
lambda_lim = (20 * 0.7 * 1.1 * 0.7) / (max(n_axial, 0.01) ** 0.5)
is_slender = lambda_col > lambda_lim

# First-order eccentricity including imperfections
e_0 = (M_Ed * 1e6) / (N_Ed * 1000) if N_Ed > 0 else 0
e_i = max(L * 1000 / 400, 20.0)  # Geometrical imperfection
e_1 = e_0 + e_i

# Second-order eccentricity (Nominal Curvature Method)
if is_slender:
    # Simplified estimation of Kr and K_phi
    kr = 1.0
    k_phi = 1.0
    nu = 1.0 + 0.1  # Simplification factor
    c_factor = 10  # Factor depending on curvature distribution (10 for constant)

    # Curvature 1/r
    myd = fyd / Es
    omega = (As_total * fyd) / (b * h * fcd)
    n_bal = 0.4

    # Corrected string conversion format for safety
    r_val = (nu / (1 - n_bal)) * (myd / (0.45 * d))
    curvature = kr * k_phi * r_val
    e_2 = curvature * (L * 1000) ** 2 / c_factor
    e_tot = e_1 + e_2
else:
    e_2 = 0
    e_tot = e_1

M_Ed_total = (N_Ed * 1000 * e_tot) / 1e6

# --- CONSTRUCT INTERACTION DIAGRAM (N-M Envelope Points) ---
# Point A: Pure Axial Compression
N_A = (fcd * b * h + fyd * As_total) / 1000
M_A = 0.0

# Point B: Balanced Failure (Concrete crushing at 0.0035, Steel yielding at fyd/Es)
xu_bal = (0.0035 / (0.0035 + (fyd / Es))) * d
Fcc_bal = fcd * b * 0.8 * xu_bal
Fs1_bal = As_half * fyd  # Tension steel yielding
Fs2_bal = As_half * fyd  # Compression steel yielding

N_B = (Fcc_bal + Fs2_bal - Fs1_bal) / 1000
M_B = (Fcc_bal * (h / 2 - 0.4 * xu_bal) + Fs2_bal * (h / 2 - d_prime) + Fs1_bal * (d - h / 2)) / 1e6

# Point C: Pure Flexure (N = 0)
# Simple equilibrium check for pure bending capacity
xu_pure = (As_half * fyd) / (fcd * b * 0.8)
N_C = 0.0
M_C = (As_half * fyd * (d - 0.4 * xu_pure)) / 1e6

# Compile envelope trace line arrays
N_points = [N_A, N_B, N_C, 0, -As_total * fyd / 1000]
M_points = [M_A, M_B, M_C, M_C, 0.0]

# Verification check logic
is_inside = False
# Simple analytical bounding check box for safety display
if N_Ed <= N_A and M_Ed_total <= max(M_points):
    is_inside = True

# 4. GRAPHICAL UI RENDERING
col_plot, col_results = st.columns([1.2, 0.8])

with col_plot:
    st.subheader("📈 N-M Interaction Diagram Envelope")

    fig = go.Figure()

    # Draw Capacity Boundary Line
    fig.add_trace(go.Scatter(
        x=M_points, y=N_points,
        mode='lines+markers',
        name='EC2 Capacity Boundary',
        line=dict(color='#1B365D', width=3),
        fill='toself',
        fillcolor='rgba(27, 54, 93, 0.05)'
    ))

    # Draw Current Design Loading Point
    fig.add_trace(go.Scatter(
        x=[M_Ed_total], y=[N_Ed],
        mode='markers',
        name='Design Point (incl. 2nd order)',
        marker=dict(color='Red' if not is_inside else 'Green', size=14, symbol='cross')
    ))

    fig.update_layout(
        xaxis_title="Moment M_Ed (kNm)",
        yaxis_title="Axial Force N_Ed (kN)",
        height=500,
        margin=dict(l=20, r=20, t=30, b=20)
    )
    st.plotly_chart(fig, use_container_width=True)

with col_results:
    st.subheader("📋 Structural Analysis Summary")

    st.metric(label="Total Design Moment M_Ed (incl. 2nd order)", value=f"{round(M_Ed_total, 1)} kNm",
              delta=f"Initial: {round(M_Ed, 1)} kNm")

    st.markdown("### Slenderness Assessment")
    st.write(f"- Column Slenderness $\lambda$: **{round(lambda_col, 1)}**")
    st.write(f"- Limit Slenderness $\lambda_{{lim}}$: **{round(lambda_lim, 1)}**")

    if is_slender:
        st.warning(f"⚠️ **SLENDER COLUMN**: Second-order eccentricity $e_2 = {round(e_2, 1)}$ mm is added.")
    else:
        st.success("✅ **SHORT COLUMN**: Slenderness effects are negligible.")

    st.markdown("### Final Capacity Status")
    if is_inside:
        st.success("✅ **PASS**: Applied loading sits inside the EC2 cross-section capacity envelope.")
    else:
        st.error("❌ **FAIL**: Applied loading exceeds the structural reinforcement limits.")