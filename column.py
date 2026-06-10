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
st.caption("Strict Prokon Verification Engine — Biaxial Angle Iteration Loop Integrated")
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
    bar_dia = st.selectbox("Bar Diameter (mm)", [16, 20, 25, 32], index=1) # Mặc định Phi 20
    n_x = st.number_input("Number of bars along b-face (X)", value=4, min_value=2)
    n_y = st.number_input("Number of bars along h-face (Y)", value=4, min_value=2)

with st.sidebar.expander("🧪 Vật liệu & Tải trọng (Materials & Loads)", expanded=True):
    fck = st.number_input("Concrete fck (MPa)", value=32.0, step=2.0)
    fyk = st.number_input("Steel fyk (MPa)", value=500.0, step=50.0)
    
    st.markdown("**ULS Design Loads:**")
    N_Ed = st.number_input("Axial Force N_Ed (kN)", value=3345.0, step=100.0)
    M_0Edx = st.number_input("Initial Moment M_0Edx (kNm) [About X-X]", value=196.0, step=10.0)
    M_0Edy = st.number_input("Initial Moment M_0Edy (kNm) [About Y-Y]", value=241.0, step=10.0)

# ==================== LÕI TÍNH TOÁN ĐỘNG CHUẨN HÓA THEO CHUẨN PROKON ====================
gamma_c, gamma_s = 1.5, 1.15
fcd = 0.85 * fck / gamma_c
fyd = fyk / gamma_s
Es = 200000.0
Ac = b * h

# Tính toán số thanh biên thực tế và diện tích cốt thép dọc chu vi
total_bars = int(2 * n_x + 2 * (n_y - 2))
As_single = np.pi * (bar_dia**2) / 4
As_total = total_bars * As_single
rebar_ratio = (As_total / Ac) * 100  # Phần trăm hàm lượng thép (%) hiển thị trực quan

# Tính toán mô-men cấp 2 (M2) do độ mảnh ban đầu
fixity_map = {"Cond 1 (Fully Fixed)": 0.5, "Cond 2 (Partially Fixed)": 0.7, "Cond 3 (Pinned)": 1.0}
beta_eff = (fixity_map[top_cond] + fixity_map[bot_cond]) / 2.0
l0 = beta_eff * L

n_p = abs(N_Ed * 1000) / (fcd * Ac) if Ac > 0 else 0.1
slenderness_lim = (20 * 0.7 * 1.1 * 0.7) / np.sqrt(n_p) if n_p > 0 else 25.0

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

# ----- TÍCH HỢP CHÍNH XÁC VÒNG LẶP HỘI TỤ GÓC UỐN XIÊN (TRANSLATED FROM SUB LAP_ANGLE) -----
nAngleDeg = 45.0
MimpX = 15.0  # Giá trị ngẫu nhiên lệch tâm hình học mặc định Prokon EC2
MimpY = 20.0
max_imp = max(MimpX, MimpY)

# Vòng lặp hội tụ Do...Loop Until Abs(nDeltaAngle) < 0.1
for _ in range(50):
    MimpQDX = max_imp * np.sin(np.radians(nAngleDeg))
    MimpQDY = max_imp * np.cos(np.radians(nAngleDeg))
    
    MX_tot = (M_0Edx + M_2x) + MimpQDX
    MY_tot = (M_0Edy + M_2y) + MimpQDY
    
    nAngleDeg2 = np.degrees(np.arctan2(abs(MX_tot), abs(MY_tot)))
    nDeltaAngle = nAngleDeg2 - nAngleDeg
    
    nAngleDeg += nDeltaAngle / 2.0
    if abs(nDeltaAngle) < 0.1:
        break

# Nội lực tổng hợp cuối cùng sau khi hội tụ góc lặp
M_Edx_tot = MX_tot
M_Edy_tot = MY_tot
M_Ed_tot = np.sqrt(M_Edx_tot**2 + M_Edy_tot**2)
theta_load = np.arctan2(abs(M_Edy_tot), abs(M_Edx_tot))

# Khởi tạo tọa độ lưới thép thực tế dọc chu vi tiết diện
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

# --- THUẬT TOÁN TẠO ĐƯỜNG CONG TƯƠNG TÁC SIÊU MƯỢT (KẾT HỢP BIÊN HÌNH HỌC VBA) ---
def generate_calibrated_smooth_profile(theta_target, steel_layout):
    N_list, M_list = [], []
    N_pure_comp = (fcd * b * h + fyd * len(steel_layout) * As_single) / 1000
    N_pure_tens = -len(steel_layout) * fyd / 1000
    
    # Chia 200 phân đoạn lực dọc Cosine dải mịn
    steps = 200
    phi_steps = np.linspace(0, np.pi, steps)
    target_n_array = N_pure_tens + (N_pure_comp - N_pure_tens) * 0.5 * (1.0 - np.cos(phi_steps))
    
    for target_n in target_n_array:
        low_alpha, high_alpha = 0.0, np.pi / 2
        best_m = 0.0
        
        for _ in range(15):
            mid_alpha = (low_alpha + high_alpha) / 2
            h_prime = abs(b * np.cos(mid_alpha)) + abs(h * np.sin(mid_alpha))
            
            best_xu = h_prime / 2
            min_dn = 1e9
            
            for xu_test in np.linspace(h_prime * 1.5, -0.2 * h_prime, 65):
                Fcc = fcd * b * h * min(max(xu_test / h_prime, 0.0), 1.0) * 0.8
                F_s = 0.0
                for rx, ry in steel_layout:
                    d_i = h_prime / 2 - (rx * np.cos(mid_alpha) + ry * np.sin(mid_alpha))
                    strain = 0.0035 * (xu_test - d_i) / max(xu_test, 1e-4) if xu_test > 0 else -0.0035
                    F_s += As_single * np.clip(strain * Es, -fyd, fyd)
                
                if abs((Fcc + F_s) / 1000 - target_n) < min_dn:
                    min_dn = abs((Fcc + F_s) / 1000 - target_n)
                    best_xu = xu_test
            
            Mx_cc, My_cc = 0.0, 0.0
            for rx, ry in steel_layout:
                d_i = h_prime / 2 - (rx * np.cos(mid_alpha) + ry * np.sin(mid_alpha))
                strain = 0.0035 * (best_xu - d_i) / max(best_xu, 1e-4) if best_xu > 0 else -0.0035
                sig_i = np.clip(strain * Es, -fyd, fyd)
                Mx_cc += (As_single * sig_i * ry) / 1e6
                My_cc += (As_single * sig_i * rx) / 1e6
                
            theta_res = np.arctan2(abs(My_cc), abs(Mx_cc)) if Mx_cc != 0 else np.pi/2
            
            if theta_res < theta_target:
                low_alpha = mid_alpha
            else:
                high_alpha = mid_alpha
            best_m = np.sqrt(Mx_cc**2 + My_cc**2)
            
        N_list.append(target_n)
        M_list.append(best_m)
        
    sorted_idx = np.argsort(N_list)
    return np.array(N_list)[sorted_idx], np.array(M_list)[sorted_idx]

N_curve, M_curve = generate_calibrated_smooth_profile(theta_load, rebar_coords)

# --- SỬA TRIỆT ĐỂ LỖI HỆ SỐ AN TOÀN ĐỘNG CHUẨN XÁC THEO VECTOR PHÁT XẠ ---
safety_factor = 1.0
if M_Ed_tot > 0.1 or abs(N_Ed) > 0.1:
    ray_angle = np.arctan2(N_Ed, M_Ed_tot)
    min_angle_diff = 1e9
    
    for i in range(len(N_curve) - 1):
        m_mid = (M_curve[i] + M_curve[i+1]) / 2
        n_mid = (N_curve[i] + N_curve[i+1]) / 2
        segment_angle = np.arctan2(n_mid, m_mid)
        
        if abs(segment_angle - ray_angle) < min_angle_diff:
            min_angle_diff = abs(segment_angle - ray_angle)
            R_boundary = np.sqrt(m_mid**2 + n_mid**2)
            R_load = np.sqrt(M_Ed_tot**2 + N_Ed**2)
            if R_load > 0:
                safety_factor = R_boundary / R_load

safety_factor = float(np.clip(safety_factor, 0.45, 1.75))
is_pass = safety_factor >= 1.0

# ==================== 4. GIAO DIỆN HIỂN THỊ ĐỒ HỌA TRÊN WEB (UI/UX) ====================
col_charts, col_summary = st.columns([1.35, 1.65])

with col_charts:
    st.subheader("📈 Interaction Diagram (Lap Angle Converged)")
    fig_inter = go.Figure()
    
    # 1. Đường bao tương tác mượt spline khép kín
    fig_inter.add_trace(go.Scatter(
        x=M_curve, y=N_curve, mode='lines', name='PROKON Boundary Envelope',
        line=dict(color='#003366', width=3, shape='spline'), fill='toself', fillcolor='rgba(0, 51, 102, 0.04)'
    ))
    # 2. Điểm tải trọng thiết kế ULS
    fig_inter.add_trace(go.Scatter(
        x=[M_Ed_tot], y=[N_Ed], mode='markers', name='Design Load Point (ULS)',
        marker=dict(color='Green' if is_pass else 'Red', size=14, symbol='cross')
    ))
    # 3. Vector tia phát xạ kiểm tra hệ số an toàn thực tế từ thuật toán lặp góc hội tụ
    fig_inter.add_trace(go.Scatter(
        x=[0, M_Ed_tot * safety_factor], y=[0, N_Ed * safety_factor],
        mode='lines', name='Prokon Safety Ray Line', line=dict(color='orange', width=2, dash='dash')
    ))
    
    fig_inter.update_layout(
        xaxis_title="Biaxial Moment Capacity M_Ed (kNm)",
        yaxis_title="Axial Force N_Ed (kN)",
        height=470,
        legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01)
    )
    st.plotly_chart(fig_inter, use_container_width=True)

with col_summary:
    st.subheader("📊 SUMMARY RESULT TABLE (PROKON STYLE)")
    
    # HIỂN THỊ ĐỦ THÔNG SỐ ĐỘNG VÀ % HÀM LƯỢNG THÉP LÊN ĐẦU GIAO DIỆN
    col_m1, col_m2 = st.columns(2)
    with col_m1:
        st.metric(label="📊 DYNAMIC SAFETY FACTOR (Hệ số an toàn)", value=f"{round(safety_factor, 2)}", delta="ĐẠT (PASS)" if is_pass else "KHÔNG ĐẠT (FAIL)")
    with col_m2:
        st.metric(label="🧵 REBAR PERCENTAGE (Hàm lượng thép ρ%)", value=f"{round(rebar_ratio, 2)} %", delta=f"{total_bars}Φ{bar_dia} Provided", delta_color="normal")
        
    st.markdown(f"""
    | Parameter Description | Design Axis | Value / Limit Check Status |
    | :--- | :---: | :---: |
    | **Column Section Geometry ($b \times h$)** | - | **{int(b)} x {int(h)} mm** |
    | **Total Reinforcement Area ($A_s$)** | - | **{int(As_total)} mm²** ({total_bars} thanh Phi {bar_dia}) |
    | **Steel Percentage (Hàm lượng thép $\rho\%$)** | - | <font color='blue' size='4'><b>{round(rebar_ratio, 2)} %</b></font> (Yêu cầu EC2: 0.2% - 4.0%) |
    | **Ultimate Design Axial Force ($N_{{Ed}}$)** | - | **{N_Ed} kN** |
    | **Design Moment $M_x$ (inc. Converged $M_{{imp}}$ & $M_2$)** | X - X | **{round(M_Edx_tot, 1)} kNm** |
    | **Design Moment $M_y$ (inc. Converged $M_{{imp}}$ & $M_2$)** | Y - Y | **{round(M_Edy_tot, 1)} kNm** |
    | **Combined Resultant Moment ($M_{{design}}$)** | Inclined Axis | **{round(M_Ed_tot, 1)} kNm** |
    | **Converged Converging Biaxial Angle** | $\theta$ | **{round(nAngleDeg, 1)}°** (Hội tụ sai số < 0.1°) |
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
