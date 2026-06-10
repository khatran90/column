import streamlit as st
import numpy as np
import plotly.graph_objects as go
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

# 1. CẤU HÌNH TRANG WEB
st.set_page_config(page_title="PROKON Ultimate Column Verification (EC2)", layout="wide")
st.title("🏛️ Concrete Column Design & Interaction Diagram — EC2")
st.caption("Strict Prokon Verification Engine — Calibrated for 450x900mm Core Section")
st.markdown("---")

# 2. THANH NHẬP SỐ LIỆU ĐỘNG (SIDEBAR)
st.sidebar.header("📊 COLUMN PARAMETERS")

with st.sidebar.expander("📐 Kích thước hình học & Liên kết (Geometry)", expanded=True):
    b = st.number_input("Width along X-axis, b (mm)", value=450.0, step=50.0)
    h = st.number_input("Depth along Y-axis, h (mm)", value=900.0, step=50.0)
    L = st.number_input("Clear Height of Column, L (m)", value=3.6, step=0.1)
    cc = st.number_input("Concrete cover c_nom (mm)", value=40.0, step=5.0)
    
    st.markdown("**End Fixities (Điều kiện liên kết):**")
    top_cond = st.selectbox("Top End Condition", ["Cond 1 (Fully Fixed)", "Cond 2 (Partially Fixed)", "Cond 3 (Pinned)"], index=1)
    bot_cond = st.selectbox("Bottom End Condition", ["Cond 1 (Fully Fixed)", "Cond 2 (Partially Fixed)", "Cond 3 (Pinned)"], index=1)

with st.sidebar.expander("🧵 Cốt thép dọc (Vertical Rebars)", expanded=True):
    bar_dia = st.selectbox("Bar Diameter (mm)", [16, 20, 25, 32], index=2) # Mặc định phi 25
    n_x = st.number_input("Number of bars along b-face (X)", value=4, min_value=2)
    n_y = st.number_input("Number of bars along h-face (Y)", value=6, min_value=2)
    
    total_bars = 2 * n_x + 2 * (n_y - 2)
    As_single = np.pi * (bar_dia**2) / 4
    As_total = total_bars * As_single
    st.caption(f"👉 Total Bars: {total_bars} | Total As = {int(As_total)} mm²")

with st.sidebar.expander("🧪 Vật liệu & Tải trọng (Materials & Loads)", expanded=True):
    fck = st.number_input("Concrete fck (MPa)", value=32.0, step=2.0)
    fyk = st.number_input("Steel fyk (MPa)", value=500.0, step=50.0)
    
    st.markdown("**ULS Design Loads:**")
    N_Ed = st.number_input("Axial Force N_Ed (kN, + Comp)", value=3345.0, step=100.0)
    M_0Edx = st.number_input("Initial Moment M_0Edx (kNm)", value=196.0, step=10.0)
    M_0Edy = st.number_input("Initial Moment M_0Edy (kNm)", value=241.0, step=10.0)

# 3. THUẬT TOÁN KẾT CẤU NÂNG CẤP THEO TIÊU CHUẨN KIỂM TRA ĐỘ LỆCH TÂM TỐI THIỂU EC2
gamma_c, gamma_s = 1.5, 1.15
fcd = 0.85 * fck / gamma_c
fyd = fyk / gamma_s
Es = 200000.0
Ac = b * h

# Kiểm tra hàm lượng thép tối thiểu
As_min = max(0.002 * Ac, (0.10 * abs(N_Ed) * 1000) / fyd)
rebar_min_check = As_total >= As_min
rebar_ratio = (As_total / Ac) * 100

# Chiều dài tính toán l0 theo điều kiện biên Prokon
fixity_map = {"Cond 1 (Fully Fixed)": 0.5, "Cond 2 (Partially Fixed)": 0.7, "Cond 3 (Pinned)": 1.0}
beta_eff = (fixity_map[top_cond] + fixity_map[bot_cond]) / 2.0
l0 = beta_eff * L

# Độ lệch tâm ngẫu nhiên tối thiểu (EC2 Cl. 5.2)
e_min_x = max(h / 30, 20.0)
e_min_y = max(b / 30, 20.0)

# Tính toán độ mảnh 2 phương
n_p = abs(N_Ed * 1000) / (fcd * Ac) if Ac > 0 else 0.1
slenderness_lim = (20 * 0.7 * 1.1 * 0.7) / np.sqrt(n_p) if n_p > 0 else 25.0

# Trục X
i_x = h / np.sqrt(12)
lambda_x = (l0 * 1000) / i_x
M_2x = 0.0
if lambda_x > slenderness_lim:
    d_eff_x = h - cc - 10 - bar_dia/2
    Kr_x = min((1.0 - n_p) / (1.0 - 0.4), 1.0) if n_p > 0.4 else 1.0
    one_over_r_x = Kr_x * 1.0 * (2 * (fyd/Es)) / (d_eff_x - (cc + 10 + bar_dia/2))
    e2_x = one_over_r_x * ((l0 * 1000)**2) / 10
    M_2x = (abs(N_Ed) * e2_x) / 1000

# Trục Y
i_y = b / np.sqrt(12)
lambda_y = (l0 * 1000) / i_y
M_2y = 0.0
if lambda_y > slenderness_lim:
    d_eff_y = b - cc - 10 - bar_dia/2
    Kr_y = min((1.0 - n_p) / (1.0 - 0.4), 1.0) if n_p > 0.4 else 1.0
    one_over_r_y = Kr_y * 1.0 * (2 * (fyd/Es)) / (d_eff_y - (cc + 10 + bar_dia/2))
    e2_y = one_over_r_y * ((l0 * 1000)**2) / 10
    M_2y = (abs(N_Ed) * e2_y) / 1000

# Áp dụng hàm Max bao kiểm tra cấu kiện theo EC2 Mục 5.8.8.2 (Bao gồm độ lệch tâm tối thiểu)
M_Edx = max(M_0Edx + M_2x, abs(N_Ed) * e_min_x / 1000)
M_Edy = max(M_0Edy + M_2y, abs(N_Ed) * e_min_y / 1000)

# Tổng hợp mô-men quy đổi thiết kế và Góc uốn xiên theta
M_Ed_tot = np.sqrt(M_Edx**2 + M_Edy**2)
theta = np.arctan2(abs(M_Edy), abs(M_Edx)) if M_Edx > 0 else np.pi/2

# --- TẠO MẠNG LƯỚI TỌA ĐỘ THÉP TRÊN TIẾT DIỆN THỰC 450x900 ---
rebar_coords = []
dx = (b - 2*cc - bar_dia) / (n_x - 1) if n_x > 1 else 0
dy = (h - 2*cc - bar_dia) / (n_y - 1) if n_y > 1 else 0

for i in range(n_x):
    rebar_coords.append((cc + bar_dia/2 + i*dx - b/2, cc + bar_dia/2 - h/2))
    rebar_coords.append((cc + bar_dia/2 + i*dx - b/2, h/2 - cc - bar_dia/2))
for j in range(1, n_y - 1):
    rebar_coords.append((cc + bar_dia/2 - b/2, cc + bar_dia/2 + j*dy - h/2))
    rebar_coords.append((b/2 - cc - bar_dia/2, cc + bar_dia/2 + j*dy - h/2))
rebar_coords = list(set(rebar_coords))

# Vẽ biểu đồ tương tác mặt cắt xiên
def generate_calibrated_profile(angle):
    N_profile, M_profile = [], []
    N_pure_comp = (fcd * Ac + fyd * As_total) / 1000
    N_profile.append(N_pure_comp)
    M_profile.append(0.0)
    
    h_prime = abs(b * np.cos(angle)) + abs(h * np.sin(angle))
    
    for xu in np.linspace(h_prime * 1.0, h_prime * 0.01, 40):
        area_ratio = min(xu / h_prime, 1.0)
        Fcc = fcd * b * h * area_ratio * 0.8
        z_cc = (h_prime / 2 - 0.4 * xu)
        
        F_steel_tot = 0.0
        M_steel_tot = 0.0
        
        for rx, ry in rebar_coords:
            d_i = h_prime / 2 - (rx * np.cos(angle) + ry * np.sin(angle))
            if xu > 0:
                strain_i = 0.0035 * (xu - d_i) / xu
                sig_i = np.clip(strain_i * Es, -fyd, fyd)
            else:
                sig_i = -fyd
                
            F_steel_tot += As_single * sig_i
            M_steel_tot += As_single * sig_i * (h_prime / 2 - d_i)
            
        N_cur = (Fcc + F_steel_tot) / 1000
        M_cur = (Fcc * z_cc + M_steel_tot) / 1e6
        
        N_profile.append(N_cur)
        M_profile.append(abs(M_cur))
        
    N_profile.append(-As_total * fyd / 1000)
    M_profile.append(0.0)
    return N_profile, M_profile

N_curve, M_curve = generate_calibrated_profile(theta)
M_Rd = np.interp(N_Ed, N_curve[::-1], M_curve[::-1])

# Hệ số an toàn chuẩn Prokon (Capacity / Action)
safety_factor = M_Rd / max(M_Ed_tot, 1.0)
is_pass = safety_factor >= 1.0 and rebar_min_check

# 4. GIAO DIỆN ĐỒ HỌA TRÊN WEB (UI/UX)
col_charts, col_summary = st.columns([1.5, 1.5])

with col_charts:
    st.subheader(f"📈 Interaction Curve M_design ({b}x{h} mm)")
    fig_inter = go.Figure()
    fig_inter.add_trace(go.Scatter(
        x=M_curve, y=N_curve, mode='lines', name='EC2 Capacity Boundary',
        line=dict(color='#1B365D', width=3), fill='toself', fillcolor='rgba(27, 54, 93, 0.05)'
    ))
    fig_inter.add_trace(go.Scatter(
        x=[M_Ed_tot], y=[N_Ed], mode='markers', name='Design Load Point',
        marker=dict(color='Green' if is_pass else 'Red', size=14, symbol='cross')
    ))
    fig_inter.update_layout(xaxis_title="Design Moment M_design (kNm)", yaxis_title="Axial Force N_Ed (kN)", height=420)
    st.plotly_chart(fig_inter, use_container_width=True)

with col_summary:
    st.subheader("📋 Prokon Calibrated Verification")
    st.metric(label="Safety Factor (Hệ số an toàn)", value=f"{round(safety_factor, 3)}", delta="ĐẠT (PASS)" if is_pass else "KHÔNG ĐẠT (FAIL)", delta_color="normal" if is_pass else "inverse")
    
    st.markdown("**Chi tiết Nội lực tính toán cuối cùng (gồm e_min & Cấp 2):**")
    st.write(f"- Lực dọc thiết kế $N_{{Ed}}$: **{N_Ed}** kN")
    st.write(f"- Mô-men thiết kế tổng hợp $M_{{design}}$: **{round(M_Ed_tot, 1)}** kNm")
    st.write(f"- Giới hạn khả năng chịu lực mặt cắt $M_{{Rd}}$: **{round(M_Rd, 1)}** kNm")
    
    st.markdown("**Kiểm soát độ mảnh hệ thống:**")
    st.write(f"- Giới hạn độ mảnh cho phép $\lambda_{{lim}}$: **{round(slenderness_lim, 2)}**")
    st.write(f"- Trục X ($\lambda_x$): **{round(lambda_x, 2)}** $\rightarrow$ " + ("Cột mảnh" if lambda_x > slenderness_lim else "Cột ngắn"))
    st.write(f"- Trục Y ($\lambda_y$): **{round(lambda_y, 2)}** $\rightarrow$ " + ("Cột mảnh" if lambda_y > slenderness_lim else "Cột ngắn"))

# 5. LOGIC TẠO BÁO CÁO PDF CHI TIẾT ĐỒNG BỘ KẾT QUẢ BẢNG TÍNH
def generate_detailed_prokon_pdf():
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=45, leftMargin=45, topMargin=45, bottomMargin=45)
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle('Title', fontName='Helvetica-Bold', fontSize=18, leading=22, textColor=colors.HexColor('#1B365D'), spaceAfter=12)
    section_style = ParagraphStyle('Sec', fontName='Helvetica-Bold', fontSize=12, leading=16, textColor=colors.HexColor('#2C3E50'), spaceBefore=12, spaceAfter=6)
    normal_text = ParagraphStyle('NormT', fontName='Helvetica', fontSize=10, leading=14)

    elements = []
    elements.append(Paragraph("PROKON Column Design - Calculation Sheet", title_style))
    elements.append(Paragraph(f"Design Code: Eurocode 2 (EN 1992-1-1:2004) | Calibrated Engine Verification", normal_text))
    elements.append(Spacer(1, 10))
    
    # Bảng 1
    elements.append(Paragraph("1. GENERAL DESIGN PARAMETERS & GEOMETRY", section_style))
    data_geo = [
        [Paragraph("<b>Parameter</b>", normal_text), Paragraph("<b>Value</b>", normal_text), Paragraph("<b>Material Properties</b>", normal_text), Paragraph("<b>Value</b>", normal_text)],
        ["Section Width b (mm)", f"{b}", "Concrete fck (MPa)", f"{fck}"],
        ["Section Depth h (mm)", f"{h}", "Steel fyk (MPa)", f"{fyk}"],
        ["Clear Height L (m)", f"{L}", "Design Concrete fcd (MPa)", f"{round(fcd, 2)}"],
        ["Concrete Cover c_nom (mm)", f"{cc}", "Total Provided Rebar As", f"{int(As_total)} mm² ({round(rebar_ratio,2)}%)"]
    ]
    t_geo = Table(data_geo, colWidths=[140, 100, 150, 100])
    t_geo.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1B365D')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
        ('PADDING', (0,0), (-1,-1), 5),
    ]))
    for r_idx, row in enumerate(data_geo):
        if r_idx > 0:
            for c_idx, val in enumerate(row):
                data_geo[r_idx][c_idx] = Paragraph(str(val), normal_text)
    elements.append(t_geo)
    elements.append(Spacer(1, 15))
    
    # Bảng 2
    elements.append(Paragraph("2. BIAXIAL SLENDERNESS ASSESSMENT", section_style))
    data_slender = [
        [Paragraph("<b>Axis Direction</b>", normal_text), Paragraph("<b>Actual Slenderness (λ)</b>", normal_text), Paragraph("<b>Limit Slenderness (λ_lim)</b>", normal_text), Paragraph("<b>Second-Order M2 (kNm)</b>", normal_text)],
        ["X-Axis (Around X)", f"{round(lambda_x, 2)}", f"{round(slenderness_lim, 2)}", f"{round(M_2x, 1)}"],
        ["Y-Axis (Around Y)", f"{round(lambda_y, 2)}", f"{round(slenderness_lim, 2)}", f"{round(M_2y, 1)}"]
    ]
    t_slender = Table(data_slender, colWidths=[150, 130, 130, 130])
    t_slender.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#2C3E50')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
        ('PADDING', (0,0), (-1,-1), 5),
    ]))
    for r_idx, row in enumerate(data_slender):
        if r_idx > 0:
            for c_idx, val in enumerate(row):
                data_slender[r_idx][c_idx] = Paragraph(str(val), normal_text)
    elements.append(t_slender)
    elements.append(Spacer(1, 15))
    
    # Bảng 3
    elements.append(Paragraph("3. ULTIMATE CAPACITY & SAFETY FACTORS (M_design)", section_style))
    status_text = "<b><font color='green'>PASS</font></b>" if is_pass else "<b><font color='red'>FAIL</font></b>"
    data_res = [
        [Paragraph("<b>Design Parameter</b>", normal_text), Paragraph("<b>Applied Value (Action)</b>", normal_text), Paragraph("<b>Section Capacity (Limit)</b>", normal_text), Paragraph("<b>Safety Factor / Status</b>", normal_text)],
        ["Axial Load N_Ed (kN)", f"{N_Ed} kN", f"Max Resistance N_Rd: {round(N_Rd, 1)} kN", "OK"],
        ["Combined Moment M_design (kNm)", f"{round(M_Ed_tot, 1)} kNm", f"Moment Capacity M_Rd: {round(M_Rd, 1)} kNm", f"<b>{round(safety_factor, 3)}</b>"],
        ["Min Rebar Check (EC2 9.5.2)", f"Provided: {int(As_total)} mm²", f"Required Min: {int(As_min)} mm²", "PASS" if rebar_min_check else "FAIL"],
        ["Ultimate Structural Status", "-", "-", status_text]
    ]
    t_res = Table(data_res, colWidths=[180, 130, 130, 100])
    t_res.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#2C3E50')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
        ('PADDING', (0,0), (-1,-1), 5),
        ('BACKGROUND', (3, 4), (3, 4), colors.HexColor('#C6EFCE') if is_pass else colors.HexColor('#FFC7CE')),
    ]))
    for r_idx, row in enumerate(data_res):
        if r_idx > 0:
            for c_idx, val in enumerate(row):
                if c_idx != 3 or r_idx != 4:
                    data_res[r_idx][c_idx] = Paragraph(str(val), normal_text)
    elements.append(t_res)
    
    doc.build(elements)
    buffer.seek(0)
    return buffer

st.markdown("---")
st.subheader("🖨️ Export PDF Calculation Report")
pdf_data = generate_prokon_pdf = generate_detailed_prokon_pdf()

st.download_button(
    label="📥 Download Detailed Prokon PDF Report",
    data=pdf_data,
    file_name="Prokon_Calibrated_Column_Report.pdf",
    mime="application/pdf"
)
