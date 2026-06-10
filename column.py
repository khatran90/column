import streamlit as st
import numpy as np
import plotly.graph_objects as go

# 1. CẤU HÌNH TRANG WEB
st.set_page_config(page_title="EC2 Biaxial Column Designer", layout="wide")
st.title("🏛️ Concrete Column Design — Biaxial Bending (EC2)")
st.caption("Axial + Biaxial Bending Analysis ($M_x, M_y$) with Section Visualization")
st.markdown("---")

# 2. THANH NHẬP SỐ LIỆU ĐỘNG (SIDEBAR)
st.sidebar.header("📊 COLUMN PARAMETERS")

with st.sidebar.expander("📐 Kích thước hình học (Geometry)", expanded=True):
    b = st.number_input("Width along X-axis, b (mm)", value=400.0, step=50.0)
    h = st.number_input("Depth along Y-axis, h (mm)", value=600.0, step=50.0)
    cc = st.number_input("Concrete cover c_nom (mm)", value=40.0, step=5.0)

with st.sidebar.expander("🧵 Bố trí cốt thép (Rebar Layout)", expanded=True):
    bar_dia = st.selectbox("Bar Diameter (mm)", [16, 20, 25, 32], index=1)
    n_x = st.number_input("Number of bars along b-face (X)", value=4, min_value=2)
    n_y = st.number_input("Number of bars along h-face (Y)", value=5, min_value=2)

    # Tính tổng số thanh (trừ các góc trùng nhau)
    total_bars = 2 * n_x + 2 * (n_y - 2)
    As_single = np.pi * (bar_dia ** 2) / 4
    As_total = total_bars * As_single
    st.caption(f"👉 Total Bars: {total_bars} | Total As = {int(As_total)} mm²")

with st.sidebar.expander("🧪 Vật liệu & Tải trọng (Materials & Loads)", expanded=True):
    fck = st.number_input("Concrete fck (MPa)", value=30.0, step=5.0)
    fyk = st.number_input("Steel fyk (MPa)", value=500.0, step=50.0)

    st.markdown("**ULS Design Loads:**")
    N_Ed = st.number_input("Axial Force N_Ed (kN, + Comp)", value=1500.0, step=100.0)
    M_Edx = st.number_input("Moment M_Edx (kNm) [Uốn quanh trục X]", value=180.0, step=10.0)
    M_Edy = st.number_input("Moment M_Edy (kNm) [Uốn quanh trục Y]", value=90.0, step=10.0)

# 3. THUẬT TOÁN LOGIC TOÁN HỌC & KIỂM TRA KẾT CẤU (EC2)
gamma_c, gamma_s = 1.5, 1.15
fcd = 0.85 * fck / gamma_c
fyd = fyk / gamma_s
Es = 200000.0

# Tính toán tọa độ phân bổ các thanh thép trong mặt cắt phục vụ vẽ hình & tính Moment
rebar_coords = []
dx = (b - 2 * cc - bar_dia) / (n_x - 1) if n_x > 1 else 0
dy = (h - 2 * cc - bar_dia) / (n_y - 1) if n_y > 1 else 0

# Hàng thép biên dưới và biên trên
for i in range(n_x):
    rebar_coords.append((cc + bar_dia / 2 + i * dx - b / 2, cc + bar_dia / 2 - h / 2))
    rebar_coords.append((cc + bar_dia / 2 + i * dx - b / 2, h / 2 - cc - bar_dia / 2))
# Các hàng thép ở giữa dọc theo hai bên hông
for j in range(1, n_y - 1):
    rebar_coords.append((cc + bar_dia / 2 - b / 2, cc + bar_dia / 2 + j * dy - h / 2))
    rebar_coords.append((b / 2 - cc - bar_dia / 2, cc + bar_dia / 2 + j * dy - h / 2))


# TẠO ĐƯỜNG CONG TƯƠNG TÁC MƯỢT MÀ VỚI 11 ĐIỂM (N - M)
def generate_interaction_curve(dim_b, dim_h, axis='X'):
    N_pts, M_pts = [], []
    d_eff = dim_h - cc - 10 - bar_dia / 2
    d_prime = cc + 10 + bar_dia / 2

    # 11 điểm quét tương ứng với các trạng thái giới hạn của trục trung hòa xu
    xu_steps = [0.01, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 1.0, 2.0]

    # Điểm 1: Nén thuần túy
    N_pure_comp = (fcd * dim_b * dim_h + fyd * As_total) / 1000
    N_pts.append(N_pure_comp)
    M_pts.append(0.0)

    for xu_ratio in xu_steps:
        xu = xu_ratio * d_eff
        if xu <= dim_h:
            Fcc = fcd * dim_b * 0.8 * xu
            z_cc = dim_h / 2 - 0.4 * xu
        else:
            Fcc = fcd * dim_b * dim_h
            z_cc = 0.0

        # Tính toán lực trong cốt thép đơn giản hóa chia làm 2 lớp biên
        strain_comp = 0.0035
        strain_tens = strain_comp * (d_eff - xu) / xu if xu > 0 else 1.0

        sig_s1 = min(max(-fyd, strain_tens * Es), fyd)  # Lớp thép chịu kéo/nén ít
        sig_s2 = fyd if xu > d_prime else fyd * (xu - d_prime) / xu

        F_s1 = (As_total / 2) * sig_s1
        F_s2 = (As_total / 2) * sig_s2

        N_cur = (Fcc + F_s2 + F_s1) / 1000
        M_cur = (Fcc * z_cc + F_s2 * (dim_h / 2 - d_prime) - F_s1 * (d_eff - dim_h / 2)) / 1e6

        N_pts.append(N_cur)
        M_pts.append(abs(M_cur))

    # Điểm cuối: Kéo thuần túy
    N_pts.append(-As_total * fyd / 1000)
    M_pts.append(0.0)

    return N_pts, M_pts


# Tính toán đường bao công suất cho cả 2 trục X và Y
N_curve_x, M_curve_x = generate_interaction_curve(b, h, 'X')
N_curve_y, M_curve_y = generate_interaction_curve(h, b, 'Y')

# Lấy khả năng chịu mômen lớn nhất ứng với lực dọc N_Ed hiện tại bằng nội suy tuyến tính
MRdx = np.interp(N_Ed, N_curve_x[::-1], M_curve_x[::-1])
MRdy = np.interp(N_Ed, N_curve_y[::-1], M_curve_y[::-1])

# KIỂM TRA ĐIỀU KIỆN UỐN XIÊN THEO BIAXIAL BENDING CỦA EUROCODE 2 (Mục 5.8.9)
N_Rd = (fcd * b * h + fyd * As_total) / 1000
N_ratio = N_Ed / N_Rd

if N_ratio <= 0.1:
    a_exp = 1.0
elif N_ratio >= 0.7:
    a_exp = 2.0
else:
    a_exp = 1.0 + (N_ratio - 0.1) * (2.0 - 1.0) / (0.7 - 0.1)  # Nội suy mũ α

# Công thức kiểm tra uốn xiên tổng quát
biaxial_check = (M_Edx / max(MRdx, 1.0)) ** a_exp + (M_Edy / max(MRdy, 1.0)) ** a_exp
is_pass = biaxial_check <= 1.0

# 4. GIAO DIỆN HIỂN THỊ TRỰC QUAN TRÊN WEB (UI/UX)
col_sec, col_charts, col_summary = st.columns([0.8, 1.4, 0.8])

with col_sec:
    st.subheader("🖼️ Column Cross-Section")
    fig_sec = go.Figure()
    # Vẽ tiết diện Bê tông
    fig_sec.add_shape(type="rect", x0=-b / 2, y0=-h / 2, x1=b / 2, y1=h / 2,
                      line=dict(color="#2C3E50", width=4), fillcolor="rgba(189, 195, 199, 0.4)")
    # Vẽ cốt đai (Stirrup) giả định cách cốt dọc lớp bảo vệ
    fig_sec.add_shape(type="rect", x0=-b / 2 + cc, y0=-h / 2 + cc, x1=b / 2 - cc, y1=h / 2 - cc,
                      line=dict(color="#7F8C8D", width=2, dash="dash"))
    # Vẽ các thanh cốt thép dọc dạng tròn
    xs, ys = zip(*rebar_coords)
    fig_sec.add_trace(go.Scatter(x=xs, y=ys, mode='markers',
                                 marker=dict(size=bar_dia * 0.8, color='#E74C3C', line=dict(width=1, color='black')),
                                 name=f'{total_bars}-T{bar_dia}'))

    fig_sec.update_layout(xaxis_range=[-b * 0.7, b * 0.7], yaxis_range=[-h * 0.7, h * 0.7],
                          width=280, height=380, showlegend=False,
                          xaxis=dict(visible=False), yaxis=dict(visible=False), margin=dict(l=10, r=10, t=10, b=10))
    st.plotly_chart(fig_sec, use_container_width=True)

with col_charts:
    st.subheader("📈 Smooth Interaction Diagram (11+ Points)")
    tab1, tab2 = st.tabs(["Trục X (Mx)", "Trục Y (My)"])

    with tab1:
        fig_x = go.Figure()
        fig_x.add_trace(go.Scatter(x=M_curve_x, y=N_curve_x, mode='lines+markers', name='Capacity Mx',
                                   line=dict(color='#1B365D', width=3)))
        fig_x.add_trace(go.Scatter(x=[M_Edx], y=[N_Ed], mode='markers', name='Design Point',
                                   marker=dict(color='Red' if not is_pass else 'Green', size=12, symbol='cross')))
        fig_x.update_layout(xaxis_title="Moment M_Edx (kNm)", yaxis_title="Axial Force N_Ed (kN)", height=350,
                            margin=dict(l=10, r=10, t=10, b=10))
        st.plotly_chart(fig_x, use_container_width=True)

    with tab2:
        fig_y = go.Figure()
        fig_y.add_trace(go.Scatter(x=M_curve_y, y=N_curve_y, mode='lines+markers', name='Capacity My',
                                   line=dict(color='#008080', width=3)))
        fig_y.add_trace(go.Scatter(x=[M_Edy], y=[N_Ed], mode='markers', name='Design Point',
                                   marker=dict(color='Red' if not is_pass else 'Green', size=12, symbol='cross')))
        fig_y.update_layout(xaxis_title="Moment M_Edy (kNm)", yaxis_title="Axial Force N_Ed (kN)", height=350,
                            margin=dict(l=10, r=10, t=10, b=10))
        st.plotly_chart(fig_y, use_container_width=True)

with col_summary:
    st.subheader("📋 Biaxial Analysis Summary")
    st.metric(label="Lực dọc thiết kế N_Ed", value=f"{int(N_Ed)} kN")
    st.write(f"- Khả năng kháng uốn tối đa $M_{{Rdx}}$: **{round(MRdx, 1)}** kNm")
    st.write(f"- Khả năng kháng uốn tối đa $M_{{Rdy}}$: **{round(MRdy, 1)}** kNm")
    st.write(f"- Hệ số mũ EC2 $\\alpha$: **{round(a_exp, 2)}**")

    st.markdown("---")
    st.markdown(f"**Biaxial Utilization Ratio:**")
    st.info(
        f"👉 $(\\frac{{M_{{dx}}}}{{M_{{rdx}}}})^\\alpha + (\\frac{{M_{{dy}}}}{{M_{{rdy}}}})^\\alpha$ = **{round(biaxial_check, 2)}**")

    if is_pass:
        st.success("✅ **PASS**: Tiết diện cột đủ khả năng chịu uốn xiên đồng thời.")
    else:
        st.error("❌ **FAIL**: Cột bị quá tải! Hãy tăng tiết diện bê tông hoặc thêm lượng thép dọc.")
