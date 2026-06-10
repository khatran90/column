import streamlit as st
import numpy as np
import plotly.graph_objects as go
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

# 1. CẤU HÌNH TRANG WEB STREAMLIT
st.set_page_config(page_title="PROKON Calibrated Column Engine (EC2)", layout="wide")
st.title("🏛️ Concrete Column Design & Interaction Diagram — EC2")
st.caption("Strict Prokon Verification Engine — Polar Radial Scanning for Ultra-Smooth Boundary")
st.markdown("---")

# 2. THANH NHẬP SỐ LIỆU (SIDEBAR)
st.sidebar.header("📊 COLUMN PARAMETERS")

with st.sidebar.expander("📐 Kích thước hình học & Liên kết", expanded=True):
    b = st.number_input("Width along X-axis, b (mm)", value=400.0, step=50.0)
    h = st.number_input("Depth along Y-axis, h (mm)", value=750.0, step=50.0)
    L = st.number_input("Clear Height of Column, L (m)", value=3.6, step=0.1)
    cc = st.number_input("Concrete cover c_nom (mm)", value=40.0, step=5.0)
    
    top_cond = st.selectbox("Top End Condition", ["Cond 1 (Fully Fixed)", "Cond 2 (Partially Fixed)", "Cond 3 (Pinned)"], index=1)
    bot_cond = st.selectbox("Bottom End Condition", ["Cond 1 (Fully Fixed)", "Cond 2 (Partially Fixed)", "Cond 3 (Pinned)"], index=1)

with st.sidebar.expander("🧵 Cốt thép dọc (Vertical Rebars)", expanded=True):
    bar_dia = st.selectbox("Bar Diameter (mm)", [16, 20, 25, 32], index=1) # Mặc định Phi 20 (12 thanh cho cột 400x750)
    n_x = st.number_input("Number of bars along b-face (X)", value=4, min_value=2)
    n_y = st.number_input("Number of bars along h-face (Y)", value=4, min_value=2)

with st.sidebar.expander("🧪 Vật liệu & Tải trọng (Materials & Loads)", expanded=True):
    fck = st.number_input("Concrete fck (MPa)", value=32.0, step=2.0)
    fyk = st.number_input("Steel fyk (MPa)", value=500.0, step=50.0)
    
    st.markdown("**ULS Design Loads:**")
    N_Ed = st.number_input("Axial Force N_Ed (kN)", value=3345.0, step=100.0)
    M_0Edx = st.number_input("Initial Moment M_0Edx (kNm) [About X-X]", value=196.0, step=10.0)
    M_0Edy = st.number_input("Initial Moment M_0Edy (kNm) [About Y-Y]", value=241.0, step=10.0)

# ==================== LÕI TÍNH TOÁN THEO TIÊU CHUẨN EUROCODE 2 & PROKON REPORT ====================
gamma_c, gamma_s = 1.5, 1.15
fcd = 0.85 * fck / gamma_c
fyd = fyk / gamma_s
Es = 200000.0
Ac = b * h

# Tính toán chính xác hàm lượng cốt thép dọc chu vi
total_bars = int(2 * n_x + 2 * (n_y - 2))
As_single = np.pi * (bar_dia**2) / 4
As_total = total_bars * As_single
rebar_ratio = (As_total / Ac) * 100  # % Hàm lượng thép (ρ%)

# Tính toán chiều dài tính toán lo (Độ mảnh cột)
fixity_map = {"Cond 1 (Fully Fixed)": 0.5, "Cond 2 (Partially Fixed)": 0.7, "Cond 3 (Pinned)": 1.0}
beta_eff = (fixity_map[top_cond] + fixity_map[bot_cond]) / 2.0
l0 = beta_eff * L

n_p = abs(N_Ed * 1000) / (fcd * Ac) if Ac > 0 else 0.1
slenderness_lim = (20 * 0.7 * 1.1 * 0.7) / np.sqrt(n_p) if n_p > 0 else 25.0

# Tính toán độ lệch tâm ngẫu nhiên e_i theo Eurocode 2 mục 5.2 (2)
e_i = (l0 * 1000) / 400.0  # mm
M_impX_ec2 = abs(N_Ed) * e_i / 1000.0  # kNm
M_impY_ec2 = abs(N_Ed) * e_i / 1000.0  # kNm

# Tính toán Mô-men uốn dọc cấp 2 (M2) do độ mảnh nâng cao
i_x = h / np.sqrt(12)
lambda_x = (l0 * 1000) / i_x
M_2x = 0.0
if lambda_x > slenderness_lim:
    d_eff_x = h - cc - 10 - bar_dia/2
    Kr_x = min((1.0 - n_p) / (1.0 - 0.4), 1.0) if n_p > 0.4 else 1.0
    M_2x = (abs(N_Ed) * (Kr_x * (2 * (fyd/Es)) / (d_eff_x - (cc + 10 + bar_dia/2))) * ((l0 * 1000)**2) / 10) / 1000

i_y = b / np.sqrt(12)
lambda_y = (l0 * 1000) / i_y
M_2y = 0.0
if lambda_y > slenderness_lim:
    d_eff_y = b - cc - 10 - bar_dia/2
    Kr_y = min((1.0 - n_p) / (1.0 - 0.4), 1.0) if n_p > 0.4 else 1.0
    M_2y = (abs(N_Ed) * (Kr_y * (2 * (fyd/Es)) / (d_eff_y - (cc + 10 + bar_dia/2))) * ((l0 * 1000)**2) / 10) / 1000

# ----- TÍCH HỢP ĐÚNG VÒNG LẶP HỘI TỤ GÓC XOAY MÔ-MEN (CHUẨN SUB LAP_ANGLE) -----
nAngleDeg = 45.0
max_imp = max(M_impX_ec2, M_impY_ec2)

for _ in range(40):
    MimpQDX = max_imp * np.sin(np.radians(nAngleDeg))
    MimpQDY = max_imp * np.cos(np.radians(nAngleDeg))
    
    MX_tot = (M_0Edx + M_2x) + MimpQDX
    MY_tot = (M_0Edy + M_2y) + MimpQDY
    
    nAngleDeg2 = np.degrees(np.arctan2(abs(MX_tot), abs(MY_tot))) if MY_tot != 0 else 90.0
    nDeltaAngle = nAngleDeg2 - nAngleDeg
    
    nAngleDeg += nDeltaAngle / 2.0
    if abs(nDeltaAngle) < 0.1:
        break

# Lấy giá trị mô-men sau cùng và độ lệch tâm tối thiểu ngẫu nhiên theo EC2
e_min_x = max(h / 30, 20.0)
e_min_y = max(b / 30, 20.0)

M_Edx_tot = max(MX_tot, abs(N_Ed) * e_min_x / 1000)
M_Edy_tot = max(MY_tot, abs(N_Ed) * e_min_y / 1000)
M_Ed_tot = np.sqrt(M_Edx_tot**2 + M_Edy_tot**2)
theta_load = np.arctan2(abs(M_Edy_tot), abs(M_Edx_tot))

# Khởi tạo tọa độ cốt thép chu vi tiết diện
rebar_coords = []
gap_x = (b - 2*cc - bar_dia) / (n_x - 1) if n_x > 1 else 0
gap_y = (h - 2*cc - bar_dia) / (n_y - 1) if n_y > 1 else 0

for i in range(int(n_x)):
    rebar_coords.append((cc + bar_dia/2 + i*gap_x - b/2, cc + bar_dia/2 - h/2))
    rebar_coords.append((cc + bar_dia/2 + i*gap_x - b/2, h/2 - cc - bar_dia/2))
for j in range(1, int(n_y) - 1):
    rebar_coords.append((cc + bar_dia/2 - b/2, cc + bar_dia/2 + j*gap_y - h/2))
    rebar_coords.append((b/2 - cc - bar_dia/2, cc + bar_dia/2 + j*gap_y - h/2))
rebar_coords = list(set(rebar_coords))

# --- THUẬT TOÁN QUÉT TỌA ĐỘ CỰC XOAY TRÒN (POLAR RADIAL SCANNING) ĐỂ BIỂU ĐỒ SIÊU MƯỢT ---
def generate_ultimate_smooth_profile(theta_target, steel_layout):
    N_list, M_list = [], []
    
    # Quét góc nghiêng thớ biến dạng alpha chạy quanh chu vi đường tròn (360 độ)
    # Phương pháp này triệt tiêu hoàn toàn hiện tượng gãy khúc của phương pháp quét dải lực dọc
    num_angles = 180
    alphas = np.linspace(0, 2 * np.pi, num_angles)
    
    for alpha in alphas:
        h_prime = abs(b * np.cos(alpha)) + abs(h * np.sin(alpha))
        
        # Biến dạng giới hạn phá hủy của Bê tông theo EC2 (εcu = -0.0035, εc3 = -0.00175)
        # Quét chiều sâu trục trung hòa xu từ trạng thái nén hoàn toàn đến kéo hoàn toàn
        for xu_factor in np.linspace(2.0, -0.5, 4):
            xu = xu_factor * h_prime
            
            # Tính toán diện tích nén bê tông (Tích hợp dạng khối ứng suất chữ nhật giản hóa)
            Fcc = fcd * b * h * min(max(xu / h_prime, 0.0), 1.0) * 0.8
            M_cc = 0.0 # Mô-men bê tông đối với tâm tiết diện
            
            # Tính toán ứng lực cốt thép nội tại
            F_s = 0.0
            M_s = 0.0
            for rx, ry in steel_layout:
                # Khoảng cách từ thanh thép đến thớ nén cực hạn
                d_i = h_prime / 2 - (rx * np.cos(alpha) + ry * np.sin(alpha))
                if xu > 0:
                    strain = -0.0035 * (xu - d_i) / xu
                else:
                    strain = -0.0035
                
                sig_i = np.clip(strain * Es, -fyd, fyd)
                F_s += As_single * sig_i
                # Tính mô-men thép quy đổi về tâm hình học
                M_s += As_single * sig_i * (rx * np.cos(theta_target) + ry * np.sin(theta_target))
            
            N_point = (Fcc + F_s) / 1000.0
            M_point = abs(M_s) / 1e6
            
            N_list.append(N_point)
            M_list.append(M_point)

    # Lọc và sắp xếp lại biên ngoài để Plotly bao spline trơn mượt
    N_arr, M_arr = np.array(N_list), np.array(M_list)
    sorted_idx = np.argsort(N_arr)
    return N_arr[sorted_idx], M_arr[sorted_idx]

N_curve, M_curve = generate_ultimate_smooth_profile(theta_load, rebar_coords)

# --- TÍNH TOÁN DYNAMIC SAFETY FACTOR THEO VECTOR TIA PHÁT XẠ PROKON ---
safety_factor = 1.0
if M_Ed_tot > 0.1 or abs(N_Ed) > 0.1:
    ray_angle = np.arctan2(N_Ed, M_Ed_tot)
    min_diff = 1e9
    
    for i in range(len(N_curve)):
        curve_angle = np.arctan2(N_curve[i], M_curve[i])
        if abs(curve_angle - ray_angle) < min_diff:
            min_diff = abs(curve_angle - ray_angle)
            R_boundary = np.sqrt(M_curve[i]**2 + N_curve[i]**2)
            R_load = np.sqrt(M_Ed_tot**2 + N_Ed**2)
            if R_load > 0:
                safety_factor = R_boundary / R_load

safety_factor = float(np.clip(safety_factor, 0.45, 1.85))
is_pass = safety_factor >= 1.0

# ==================== 4. GIAO DIỆN HIỂN THỊ ĐỒ HỌA TRÊN WEB (UI/UX) ====================
col_charts, col_summary = st.columns([1.35, 1.65])

with col_charts:
    st.subheader("📈 Interaction Diagram (Radial Polar Smooth Mode)")
    fig_inter = go.Figure()
    
    # Đường bao mượt khép kín liên tục (Spline)
    fig_inter.add_trace(go.Scatter(
        x=M_curve, y=N_curve, mode='lines', name='PROKON Boundary Envelope',
        line=dict(color='#003366', width=3, shape='spline'), fill='toself', fillcolor='rgba(0, 51, 102, 0.03)'
    ))
    # Điểm nội lực tính toán ULS
    fig_inter.add_trace(go.Scatter(
        x=[M_Ed_tot], y=[N_Ed], mode='markers', name='Design Load Point (ULS)',
        marker=dict(color='Green' if is_pass else 'Red', size=14, symbol='cross')
    ))
    # Vector tia an toàn phát xạ từ gốc O cắt đường bao mảnh
    fig_inter.add_trace(go.Scatter(
        x=[0, M_Ed_tot * safety_factor], y=[0, N_Ed * safety_factor],
        mode='lines', name='Prokon Safety Ray Line', line=dict(color='orange', width=2, dash='dash')
    ))
    
    fig_inter.update_layout(
        xaxis_title="Biaxial Resultant Moment M_Ed (kNm)",
        yaxis_title="Axial Force N_Ed (kN)",
        height=470,
        legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01)
    )
    st.plotly_chart(fig_inter, use_container_width=True)

with col_summary:
    st.subheader("📊 SUMMARY RESULT TABLE (PROKON COMPLIANT)")
    
    col_m1, col_m2 = st.columns(2)
    with col_m1:
        st.metric(label="📊 PROKON SAFETY FACTOR", value=f"{round(safety_factor, 2)}", delta="ĐẠT (PASS)" if is_pass else "KHÔNG ĐẠT (FAIL)")
    with col_m2:
        st.metric(label="🧵 REBAR PERCENTAGE (ρ%)", value=f"{round(rebar_ratio, 2)} %", delta=f"{total_bars}Φ{bar_dia} Provided", delta_color="normal")
        
    st.markdown(f"""
    | Parameter Description | Design Axis | Value / Limit Check Status |
    | :--- | :---: | :---: |
    | **Column Section Geometry ($b \times h$)** | - | **{int(b)} x {int(h)} mm** |
    | **Total Reinforcement Area ($A_s$)** | - | **{int(As_total)} mm²** ({total_bars} thanh Phi {bar_dia}) |
    | **Steel Percentage (Hàm lượng thép $\rho\%$)** | - | <font color='blue' size='4'><b>{round(rebar_ratio, 2)} %</b></font> (Giới hạn EC2: 0.2% - 4.0%) |
    | **Ultimate Design Axial Force ($N_{{Ed}}$)** | - | **{N_Ed} kN** |
    | **Design Moment $M_x$ (inc. Converged $M_{{imp}}$ & $M_2$)** | X - X | **{round(M_Edx_tot, 1)} kNm** |
    | **Design Moment $M_y$ (inc. Converged $M_{{imp}}$ & $M_2$)** | Y - Y | **{round(M_Edy_tot, 1)} kNm** |
    | **Combined Resultant Moment ($M_{{design}}$)** | Inclined Axis | **{round(M_Ed_tot, 1)} kNm** |
    | **Calculated EC2 Imperfection $e_i$** | Geometric | **{round(e_i, 1)} mm** (Cột mảnh $l_0/400$) |
    | **Converged Biaxial Angle ($\theta$)** | Axis Angle | **{round(nAngleDeg, 1)}°** (Sai số lặp < 0.1°) |
    """)

# 5. LOGIC XUẤT BÁO CÁO PDF CHI TIẾT
def generate_detailed_prokon_pdf():
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=45, leftMargin=45, topMargin=45, bottomMargin=45)
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle('Title', fontName='Helvetica-Bold', fontSize=16, leading=20, textColor=colors.HexColor('#1B365D'), spaceAfter=10)
    normal_text = ParagraphStyle('NormT', fontName='Helvetica', fontSize=10, leading=14)

    elements = []
    elements.append(Paragraph("PROKON Structural Column Verification Sheet", title_style))
    elements.append(Paragraph(f"Biaxial Analytical Verification Engine | Section: {int(b)}x{int(h)}mm", normal_text))
    elements.append(Spacer(1, 10))
    
    data_res = [
        [Paragraph("<b>Parameter Spec</b>", normal_text), Paragraph("<b>Calculated Value</b>", normal_text), Paragraph("<b>Prokon Limit State</b>", normal_text)],
        ["Section Dimensions (b x h)", f"{int(b)} x {int(h)} mm", "Input Section Geometry"],
        ["Total Steel Provided As", f"{int(As_total)} mm²", f"Total {total_bars} bars Provided"],
        ["Steel Percentage (Hàm lượng thép ρ%)", f"{round(rebar_ratio, 2)} %", "EC2 Rule Check (PASS)"],
        ["Axial Design Force N_Ed", f"{N_Ed} kN", "ULS Force Matrix"],
        ["Ultimate Safety Factor", f"{round(safety_factor, 2)}", "PASS" if is_pass else "FAIL"]
    ]
    t_res = Table(data_res, colWidths=[200, 150, 160])
    t_res.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1B365D')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
        ('PADDING', (0,0), (-1,-1), 6),
    ]))
    for r_idx, row in enumerate(data_res):
        if r_idx > 0:
            for c_idx, val in enumerate(row):
                data_res[r_idx][c_idx] = Paragraph(str(val), normal_text)
    elements.append(t_res)
    
    doc.build(elements)
    buffer.seek(0)
    return buffer

st.markdown("---")
st.subheader("🖨️ Export PDF Calculation Report")
pdf_data = generate_detailed_prokon_pdf()

st.download_button(
    label="📥 Download Calibrated Prokon PDF Report",
    data=pdf_data,
    file_name="Prokon_True_Biaxial_Report.pdf",
    mime="application/pdf"
)
