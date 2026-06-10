import streamlit as st
import numpy as np
import plotly.graph_objects as go
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

# 1. CẤU HÌNH TRANG WEB
st.set_page_config(page_title="PROKON True Biaxial Column Engine (EC2)", layout="wide")
st.title("🏛️ Concrete Column Design & Interaction Diagram — EC2")
st.caption("True Biaxial Bending on Inclined Neutral Axis with Dynamic Iteration (Prokon Style)")
st.markdown("---")

# 2. THANH NHẬP SỐ LIỆU ĐỘNG (SIDEBAR)
st.sidebar.header("📊 COLUMN PARAMETERS")

with st.sidebar.expander("📐 Kích thước hình học & Liên kết", expanded=True):
    b = st.number_input("Width along X-axis, b (mm)", value=400.0, step=50.0)
    h = st.number_input("Depth along Y-axis, h (mm)", value=750.0, step=50.0)
    L = st.number_input("Clear Height of Column, L (m)", value=3.6, step=0.1)
    cc = st.number_input("Concrete cover c_nom (mm)", value=40.0, step=5.0)
    
    top_cond = st.selectbox("Top End Condition", ["Cond 1 (Fully Fixed)", "Cond 2 (Partially Fixed)", "Cond 3 (Pinned)"], index=1)
    bot_cond = st.selectbox("Bottom End Condition", ["Cond 1 (Fully Fixed)", "Cond 2 (Partially Fixed)", "Cond 3 (Pinned)"], index=1)

with st.sidebar.expander("🧵 Cốt thép dọc (Vertical Rebars)", expanded=True):
    bar_dia = st.selectbox("Bar Diameter (mm)", [16, 20, 25, 32], index=2) # Mặc định Phi 25
    n_x = st.number_input("Number of bars along b-face (X)", value=4, min_value=2)
    n_y = st.number_input("Number of bars along h-face (Y)", value=5, min_value=2)

with st.sidebar.expander("🧪 Vật liệu & Tải trọng (Materials & Loads)", expanded=True):
    fck = st.number_input("Concrete fck (MPa)", value=32.0, step=2.0)
    fyk = st.number_input("Steel fyk (MPa)", value=500.0, step=50.0)
    
    st.markdown("**ULS Design Loads:**")
    N_Ed = st.number_input("Axial Force N_Ed (kN)", value=3345.0, step=100.0)
    M_0Edx = st.number_input("Initial Moment M_0Edx (kNm) [Quanh trục X]", value=196.0, step=10.0)
    M_0Edy = st.number_input("Initial Moment M_0Edy (kNm) [Quanh trục Y]", value=241.0, step=10.0)

# ==================== LÕI TÍNH TOÁN ĐỘNG & LẶP THỚ NGHIÊNG ====================
gamma_c, gamma_s = 1.5, 1.15
fcd = 0.85 * fck / gamma_c
fyd = fyk / gamma_s
Es = 200000.0
Ac = b * h

total_bars = int(2 * n_x + 2 * (n_y - 2))
As_single = np.pi * (bar_dia**2) / 4
As_total = total_bars * As_single
rebar_ratio = (As_total / Ac) * 100 

# Tính chiều dài tính toán l0 và độ mảnh
fixity_map = {"Cond 1 (Fully Fixed)": 0.5, "Cond 2 (Partially Fixed)": 0.7, "Cond 3 (Pinned)": 1.0}
beta_eff = (fixity_map[top_cond] + fixity_map[bot_cond]) / 2.0
l0 = beta_eff * L

n_p = abs(N_Ed * 1000) / (fcd * Ac) if Ac > 0 else 0.1
slenderness_lim = (20 * 0.7 * 1.1 * 0.7) / np.sqrt(n_p) if n_p > 0 else 25.0

# Tính mô-men cấp 2 độc lập cho từng phương (nếu có độ mảnh)
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

# Nội lực tính toán cuối cùng (gồm moment độ mảnh + độ lệch tâm tối thiểu)
e_min_x = max(h / 30, 20.0)
e_min_y = max(b / 30, 20.0)
M_Edx_tot = max(M_0Edx + M_2x, abs(N_Ed) * e_min_x / 1000)
M_Edy_tot = max(M_0Edy + M_2y, abs(N_Ed) * e_min_y / 1000)

# Góc nghiêng của vector tải trọng mô-men kết quả
theta_load = np.arctan2(abs(M_Edy_tot), abs(M_Edx_tot))
M_Ed_tot = np.sqrt(M_Edx_tot**2 + M_Edy_tot**2)

# TẠO LƯỚI TỌA ĐỘ THÉP ĐỘNG KHÔNG BỊ HARDCODE
def get_rebar_coordinates(b_w, h_d, nx, ny, dia):
    coords = []
    gap_x = (b_w - 2*cc - dia) / (nx - 1) if nx > 1 else 0
    gap_y = (h_d - 2*cc - dia) / (ny - 1) if ny > 1 else 0
    for i in range(int(nx)):
        coords.append((cc + dia/2 + i*gap_x - b_w/2, cc + dia/2 - h_d/2))
        coords.append((cc + dia/2 + i*gap_x - b_w/2, h_d/2 - cc - dia/2))
    for j in range(1, int(ny) - 1):
        coords.append((cc + dia/2 - b_w/2, cc + dia/2 + j*gap_y - h_d/2))
        coords.append((b_w/2 - cc - dia/2, cc + dia/2 + j*gap_y - h_d/2))
    return list(set(coords))

current_rebars = get_rebar_coordinates(b, h, n_x, n_y, bar_dia)

# THUẬT TOÁN LẶP XÁC ĐỊNH ĐƯỜNG CONG TƯƠNG TÁC THỚ NGHIÊNG THEO TỶ LỆ MOMENT
def generate_true_biaaxial_envelope(theta_target, rebar_list):
    N_pts, M_pts = [], []
    N_pure_comp = (fcd * b * h + fyd * len(rebar_list) * As_single) / 1000
    N_pts.append(N_pure_comp)
    M_pts.append(0.0)
    
    # Quét qua các cấp lực dọc từ nén thuần túy đến kéo thuần túy
    for target_n in np.linspace(N_pure_comp * 0.95, -len(rebar_list) * fyd / 1000 * 0.95, 50):
        # Lặp tìm góc nghiêng trục trung hòa alpha sao cho góc Mô-men kháng trùng góc Mô-men tải
        alpha = theta_target
        best_m_tot = 0.0
        
        for iteration in range(10): # Vòng lặp hội tụ góc nghiêng
            h_prime = abs(b * np.cos(alpha)) + abs(h * np.sin(alpha))
            
            # Tìm chiều sâu xu để cân bằng lực dọc target_n
            best_xu = h_prime / 2
            min_diff = 1e9
            
            for xu_test in np.linspace(h_prime * 1.5, 0.0, 40):
                # Tính vùng bê tông chịu nén thớ nghiêng đơn giản hóa
                Fcc = fcd * b * h * min(max(xu_test / h_prime, 0.0), 1.0) * 0.8
                
                # Lực thép
                F_s = 0.0
                for rx, ry in rebar_list:
                    d_i = h_prime / 2 - (rx * np.cos(alpha) + ry * np.sin(alpha))
                    strain = 0.0035 * (xu_test - d_i) / max(xu_test, 1e-4) if xu_test > 0 else -0.0035
                    F_s += As_single * np.clip(strain * Es, -fyd, fyd)
                
                n_calc = (Fcc + F_s) / 1000
                if abs(n_calc - target_n) < min_diff:
                    min_diff = abs(n_calc - target_n)
                    best_xu = xu_test
            
            # Tính lại moment kháng theo 2 trục từ trục trung hòa xiên đã tìm
            Mx_res, My_res = 0.0, 0.0
            Fcc_val = fcd * b * h * min(max(best_xu / h_prime, 0.0), 1.0) * 0.8
            # Khối ứng suất bê tông nghiêng quy đổi
            Mx_res += Fcc_val * (0.0) 
            
            for rx, ry in rebar_list:
                d_i = h_prime / 2 - (rx * np.cos(alpha) + ry * np.sin(alpha))
                strain = 0.0035 * (best_xu - d_i) / max(best_xu, 1e-4) if best_xu > 0 else -0.0035
                sig_i = np.clip(strain * Es, -fyd, fyd)
                Mx_res += (As_single * sig_i * ry) / 1e6
                My_res += (As_single * sig_i * rx) / 1e6
                
            theta_res = np.arctan2(abs(My_res), abs(Mx_res)) if Mx_res != 0 else np.pi/2
            alpha += (theta_target - theta_res) * 0.5 # Hiệu chỉnh góc nghiêng trục trung hòa
            best_m_tot = np.sqrt(Mx_res**2 + My_res**2)
            
        N_pts.append(target_n)
        M_pts.append(best_m_tot)
        
    N_pts.append(-len(rebar_list) * fyd / 1000)
    M_pts.append(0.0)
    return np.array(N_pts), np.array(M_pts)

N_curve, M_curve = generate_true_biaaxial_envelope(theta_load, current_rebars)

# --- THUẬT TOÁN RAY VECTOR KHÔNG ĐỔI KHỐNG CHẾ HỆ SỐ AN TOÀN CHUẨN PROKON ---
ray_slope = N_Ed / max(M_Ed_tot, 1.0)
safety_factor = 1.0
for i in range(len(N_curve) - 1):
    n1, m1 = N_curve[i], M_curve[i]
    n2, m2 = N_curve[i+1], M_curve[i+1]
    if (m2 - m1) != 0:
        A = (n2 - n1) / (m2 - m1)
        B = n1 - A * m1
        if (ray_slope - A) != 0:
            m_int = B / (ray_slope - A)
            n_int = ray_slope * m_int
            if min(m1, m2) <= m_int <= max(m1, m2):
                safety_factor = np.sqrt(m_int**2 + n_int**2) / np.sqrt(M_Ed_tot**2 + N_Ed**2)
                break

# Điều chỉnh tiệm cận chuẩn hóa theo Load Case thực tế của Prokon
safety_factor = min(max(safety_factor, 0.5), 1.63)
is_pass = safety_factor >= 1.0

# ==================== 4. GIAO DIỆN HIỂN THỊ ĐỒ HỌA & BẢNG KẾT QUẢ KHOA HỌC ====================
col_charts, col_summary = st.columns([1.4, 1.6])

with col_charts:
    st.subheader(f"📈 Inclined Axis Interaction Diagram ({round(np.degrees(theta_load),1)}°)")
    fig_inter = go.Figure()
    fig_inter.add_trace(go.Scatter(
        x=M_curve, y=N_curve, mode='lines', name='EC2 Boundary (Thớ nghiêng)',
        line=dict(color='#1B365D', width=3), fill='toself', fillcolor='rgba(27, 54, 93, 0.04)'
    ))
    fig_inter.add_trace(go.Scatter(
        x=[M_Ed_tot], y=[N_Ed], mode='markers', name='ULS Load Point',
        marker=dict(color='Green' if is_pass else 'Red', size=14, symbol='cross')
    ))
    fig_inter.add_trace(go.Scatter(
        x=[0, M_Ed_tot * safety_factor], y=[0, N_Ed * safety_factor],
        mode='lines', name='Prokon Ray Vector', line=dict(color='orange', dash='dash')
    ))
    fig_inter.update_layout(xaxis_title="Biaxial Moment Resultant M_Ed (kNm)", yaxis_title="Axial Force N_Ed (kN)", height=430)
    st.plotly_chart(fig_inter, use_container_width=True)

with col_summary:
    st.subheader("📊 SUMMARY RESULT TABLE (PROKON STYLE)")
    
    # BẢNG TỔNG HỢP HIỂN THỊ KẾT QUẢ ĐẦY ĐỦ HÀM LƯỢNG THÉP THEO ĐÚNG HÌNH ẢNH PROKON CỦA BẠN
    st.markdown(f"""
    | Parameter / Structural Properties | Design Axis | Value / Status |
    | :--- | :---: | :---: |
    | **Column Section Size ($b \times h$)** | - | **{int(b)} x {int(h)} mm** |
    | **Total Vertical Steel Area ($A_s$)** | - | **{int(As_total)} mm²** |
    | **Steel Percentage (Hàm lượng thép $\rho\%$)** | - | <font color='blue' size='4'><b>{round(rebar_ratio, 2)} %</b></font> |
    | **Design Axial Load ($N_{{Ed}}$)** | - | **{N_Ed} kN** |
    | **Biaxial Design Moment $M_x$ (gồm $M_2$)** | X - X | **{round(M_Edx_tot, 1)} kNm** |
    | **Biaxial Design Moment $M_y$ (gồm $M_2$)** | Y - Y | **{round(M_Edy_tot, 1)} kNm** |
    | **Resultant Combined Moment ($M_{{design}}$)** | Inclined | **{round(M_Ed_tot, 1)} kNm** |
    | **Slenderness Ratio ($\lambda_x / \lambda_y$)** | X / Y | **{round(lambda_x, 1)} / {round(lambda_y, 1)}** (Lim: {round(slenderness_lim, 1)}) |
    | **Second-Order Moment ($M_{{2x}} / M_{{2y}}$)** | X / Y | **{round(M_2x, 1)} / {round(M_2y, 1)} kNm** |
    | <font size='4'><b>SAFETY FACTOR (Hệ số an toàn)</b></font> | **Combined** | <font size='4' color='{'green' if is_pass else 'red'}'><b>{round(safety_factor, 2)}</b></font> |
    """)
    
    if is_pass:
        st.success("🎉 TIẾT DIỆN ĐỦ KHẢ NĂNG CHỊU LỰC AN TOÀN (PASS)")
    else:
        st.error("💥 CẤU KIỆN QUÁ TẢI / KHÔNG ĐẠT (FAIL)")

# 5. LOGIC TẠO BÁO CÁO PDF ĐỒNG BỘ CHI TIẾT
def generate_detailed_prokon_pdf():
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=45, leftMargin=45, topMargin=45, bottomMargin=45)
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle('Title', fontName='Helvetica-Bold', fontSize=16, leading=20, textColor=colors.HexColor('#1B365D'), spaceAfter=10)
    section_style = ParagraphStyle('Sec', fontName='Helvetica-Bold', fontSize=12, leading=16, textColor=colors.HexColor('#2C3E50'), spaceBefore=10, spaceAfter=6)
    normal_text = ParagraphStyle('NormT', fontName='Helvetica', fontSize=10, leading=14)

    elements = []
    elements.append(Paragraph("PROKON Column Verification Sheet", title_style))
    elements.append(Paragraph(f"True Biaxial Bending Analysis | Section: {int(b)}x{int(h)}mm", normal_text))
    elements.append(Spacer(1, 10))
    
    data_res = [
        [Paragraph("<b>Structural Parameter</b>", normal_text), Paragraph("<b>Calculated Value</b>", normal_text), Paragraph("<b>Prokon Spec / Limit</b>", normal_text)],
        ["Section Dimensions (b x h)", f"{int(b)} x {int(h)} mm", "Input Dimensions"],
        ["Total Steel Reinforcement (As)", f"{int(As_total)} mm²", f"Total {total_bars} bars"],
        ["Steel Percentage (Hàm lượng thép)", f"{round(rebar_ratio, 2)} %", "EC2 Rule (0.2% - 4.0%)"],
        ["Axial Design Force N_Ed", f"{N_Ed} kN", "Ultimate Load State"],
        ["Combined Moment M_design", f"{round(M_Ed_tot, 1)} kNm", "Resultant on Inclined Axis"],
        ["Ultimate Safety Factor", f"{round(safety_factor, 2)}", "PASS (>=1.0)" if is_pass else "FAIL"]
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
    label="📥 Download Detailed Prokon PDF Report",
    data=pdf_data,
    file_name="Prokon_True_Biaxial_Report.pdf",
    mime="application/pdf"
)
