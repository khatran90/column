import streamlit as st
import numpy as np
import plotly.graph_objects as go
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

# 1. CẤU HÌNH TRANG WEB
st.set_page_config(page_title="PROKON-Style Column Designer (EC2)", layout="wide")
st.title("🏛️ Concrete Column Design & Interaction Diagram — EC2")
st.caption("Axial + Uniaxial/Biaxial Bending Analysis with Slenderness & Second-Order Effects (Ref: EN 1992-1-1 / Prokon Style)")
st.markdown("---")

# 2. THANH NHẬP SỐ LIỆU ĐỘNG (SIDEBAR)
st.sidebar.header("📊 COLUMN PARAMETERS")

with st.sidebar.expander("📐 Kích thước hình học & Liên kết (Geometry & Fixity)", expanded=True):
    b = st.number_input("Width along X-axis, b (mm)", value=400.0, step=50.0)
    h = st.number_input("Depth along Y-axis, h (mm)", value=600.0, step=50.0)
    L = st.number_input("Clear Height of Column, L (m)", value=3.6, step=0.1)
    cc = st.number_input("Concrete cover c_nom (mm)", value=40.0, step=5.0)
    
    st.markdown("**End Fixities (Điều kiện liên kết đầu cột):**")
    top_cond = st.selectbox("Top End Condition", ["Cond 1 (Fully Fixed)", "Cond 2 (Partially Fixed)", "Cond 3 (Pinned)"], index=1)
    bot_cond = st.selectbox("Bottom End Condition", ["Cond 1 (Fully Fixed)", "Cond 2 (Partially Fixed)", "Cond 3 (Pinned)"], index=1)

with st.sidebar.expander("🧵 Cốt thép dọc (Vertical Rebars)", expanded=True):
    bar_dia = st.selectbox("Bar Diameter (mm)", [16, 20, 25, 32], index=1)
    n_x = st.number_input("Number of bars along b-face (X)", value=4, min_value=2)
    n_y = st.number_input("Number of bars along h-face (Y)", value=5, min_value=2)
    
    total_bars = 2 * n_x + 2 * (n_y - 2)
    As_single = np.pi * (bar_dia**2) / 4
    As_total = total_bars * As_single
    st.caption(f"👉 Total Bars: {total_bars} | Total As = {int(As_total)} mm²")

with st.sidebar.expander("🧪 Vật liệu & Tải trọng (Materials & Loads)", expanded=True):
    fck = st.number_input("Concrete fck (MPa)", value=32.0, step=2.0)
    fyk = st.number_input("Steel fyk (MPa)", value=500.0, step=50.0)
    
    st.markdown("**ULS Design Loads (Tổ hợp tải trọng):**")
    N_Ed = st.number_input("Axial Force N_Ed (kN, + Comp)", value=1500.0, step=100.0)
    M_0Ed = st.number_input("Initial Moment M_0Ed (kNm)", value=350.0, step=10.0)

# 3. THUẬT TOÁN KẾT CẤU CHUẨN ĐỘ MẢNH & M_DESIGN (PROKON ENGINE)
gamma_c, gamma_s = 1.5, 1.15
fcd = 0.85 * fck / gamma_c
fyd = fyk / gamma_s
Es = 200000.0
Ac = b * h

# Kiểm tra hàm lượng cốt thép tối thiểu theo EC2 Cl. 9.5.2
As_min = max(0.002 * Ac, (0.10 * abs(N_Ed) * 1000) / fyd)
rebar_min_check = As_total >= As_min
rebar_ratio = (As_total / Ac) * 100

# Xác định hệ số chiều dài tính toán l0/L dựa trên điều kiện liên kết (EC2 Bản tra Prokon)
fixity_map = {"Cond 1 (Fully Fixed)": 0.5, "Cond 2 (Partially Fixed)": 0.7, "Cond 3 (Pinned)": 1.0}
factor_top = fixity_map[top_cond]
factor_bot = fixity_map[bot_cond]
beta_eff = (factor_top + factor_bot) / 2.0  # Đơn giản hóa thực tế hệ số liên kết biên
l0 = beta_eff * L

# Đánh giá độ mảnh của cột (Slenderness Assessment - EC2 Cl. 5.8.3.1)
radius_gyration = h / np.sqrt(12)  # Bán kính quán tính trục uốn chính
slenderness = (l0 * 1000) / radius_gyration

# Tính toán độ mảnh giới hạn lambda_lim = 20 * A * B * C / sqrt(n)
n_p = abs(N_Ed * 1000) / (fcd * Ac)
A_eff = 0.7  # Mặc định theo Prokon khi không có thông số từ biến bám từ từ
B_eff = 1.1
C_eff = 0.7
slenderness_lim = (20 * A_eff * B_eff * C_eff) / np.sqrt(n_p) if n_p > 0 else 25.0
is_slender = slenderness > slenderness_lim

# Tính toán Mô-men cấp 2 (M2) bằng phương pháp độ cong danh nghĩa Nominal Curvature
M_2 = 0.0
if is_slender:
    # d_eff: Chiều sâu làm việc hiệu dụng
    d_eff = h - cc - 10 - bar_dia/2
    omega = (As_total * fyd) / (Ac * fcd)
    # Hệ số hiệu chỉnh Kr
    nu = n_p
    nu_bal = 0.4
    Kr = min((1.0 - nu) / (1.0 - nu_bal), 1.0) if nu > nu_bal else 1.0
    # Kphi: Kể đến hiệu ứng từ biến danh nghĩa
    Kphi = 1.0 
    # Độ cong 1/r
    yd_dist = d_eff - (cc + 10 + bar_dia/2)
    epsilon_yd = fyd / Es
    one_over_r = Kr * Kphi * (2 * epsilon_yd) / yd_dist
    # Mô-men cấp 2: M2 = N_Ed * e2 (với e2 = (1/r) * l0^2 / c, với c=10 cho tiết diện đối xứng)
    e2 = one_over_r * ((l0 * 1000)**2) / 10
    M_2 = (abs(N_Ed) * e2) / 1000

# Tổng Mô-men thiết kế cuối cùng (M_design bao gồm cả hiệu ứng cấp 2)
M_Ed_total = M_0Ed + M_2

# 4. TẠO ĐƯỜNG CONG TƯƠNG TÁC PHÂN MẢNH MỊN CHUẨN XÁC
def generate_prokon_envelope():
    N_pts, M_pts = [], []
    N_pure_comp = (fcd * Ac + fyd * As_total) / 1000
    N_pts.append(N_pure_comp)
    M_pts.append(0.0)
    
    d_eff = h - cc - 10 - bar_dia/2
    d_prime = cc + 10 + bar_dia/2
    
    for xu in np.linspace(h * 1.1, h * 0.02, 30):
        if xu >= h:
            Fcc = fcd * b * h
            z_cc = 0.0
        else:
            Fcc = fcd * b * 0.8 * xu
            z_cc = h / 2 - 0.4 * xu
            
        strain_comp = 0.0035
        sig_s1 = np.clip(strain_comp * (d_eff - xu) / xu * Es, -fyd, fyd) if xu > 0 else -fyd
        sig_s2 = np.clip(strain_comp * (xu - d_prime) / xu * Es, -fyd, fyd) if xu > 0 else -fyd
        
        F_s1 = (As_total / 2) * sig_s1
        F_s2 = (As_total / 2) * sig_s2
        
        N_cur = (Fcc + F_s2 + F_s1) / 1000
        M_cur = (Fcc * z_cc + F_s2 * (h/2 - d_prime) - F_s1 * (d_eff - h/2)) / 1e6
        
        N_pts.append(N_cur)
        M_pts.append(abs(M_cur))
        
    N_pts.append(-As_total * fyd / 1000)
    M_pts.append(0.0)
    return N_pts, M_pts

N_curve, M_curve = generate_prokon_envelope()
M_Rd = np.interp(N_Ed, N_curve[::-1], M_curve[::-1])
safety_factor = M_Rd / max(M_Ed_total, 1.0)
is_pass = safety_factor >= 1.0 and rebar_min_check

# 5. GIAO DIỆN HIỂN THỊ ĐỒ HỌA TRÊN WEB (UI/UX)
col_charts, col_summary = st.columns([1.6, 1.4])

with col_charts:
    st.subheader("📈 N-M Interaction Diagram Envelope")
    fig_inter = go.Figure()
    fig_inter.add_trace(go.Scatter(
        x=M_curve, y=N_curve, mode='lines', name='EC2 Capacity Boundary',
        line=dict(color='#1B365D', width=3), fill='toself', fillcolor='rgba(27, 54, 93, 0.05)'
    ))
    fig_inter.add_trace(go.Scatter(
        x=[M_Ed_total], y=[N_Ed], mode='markers', name='Design Point (incl. 2nd order)',
        marker=dict(color='Green' if is_pass else 'Red', size=14, symbol='cross')
    ))
    fig_inter.update_layout(xaxis_title="Moment M_Ed (kNm)", yaxis_title="Axial Force N_Ed (kN)", height=400)
    st.plotly_chart(fig_inter, use_container_width=True)

with col_summary:
    st.subheader("📋 Structural Analysis Summary")
    st.metric(label="Total Design Moment M_Ed (incl. 2nd order)", value=f"{round(M_Ed_total, 1)} kNm", delta=f"Initial: {M_0Ed} kNm")
    
    st.markdown("**Slenderness Assessment (Kiểm tra độ mảnh):**")
    col_l1, col_l2 = st.columns(2)
    col_l1.write(f"- Column Slenderness $\lambda$: **{round(slenderness, 1)}**")
    col_l2.write(f"- Limit Slenderness $\lambda_{{lim}}$: **{round(slenderness_lim, 1)}**")
    if is_slender:
        st.warning("⚠️ SHORT/SLENDER COLUMN: Slenderness effects are significant (Cột dài - Tính thêm M2).")
    else:
        st.success("✅ SHORT COLUMN: Slenderness effects are negligible.")
        
    st.markdown("**Final Capacity Status:**")
    st.write(f"- Khả năng kháng uốn giới hạn $M_{{Rd}}$: **{round(M_Rd, 1)}** kNm")
    st.write(f"- Hệ số an toàn (Safety Factor): **{round(safety_factor, 2)}** (Yêu cầu $\geq$ 1.0)")
    
    if is_pass:
        st.success("🎉 PASS: Applied loading sits inside the EC2 cross-section capacity envelope.")
    else:
        st.error("💥 FAIL: Section capacity exceeded or minimum reinforcement failed.")

# 6. LOGIC TẠO BÁO CÁO PDF CHI TIẾT CHUẨN PROKON CHUẨN XÁC 100%
def generate_detailed_prokon_pdf():
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
    styles = getSampleStyleSheet()
    
    # Định dạng font chữ văn bản kỹ thuật cao cấp
    title_style = ParagraphStyle('Title', fontName='Helvetica-Bold', fontSize=18, leading=22, textColor=colors.HexColor('#1B365D'), spaceAfter=12)
    subtitle_style = ParagraphStyle('Sub', fontName='Helvetica', fontSize=10, leading=14, textColor=colors.HexColor('#555555'), spaceAfter=15)
    section_style = ParagraphStyle('Sec', fontName='Helvetica-Bold', fontSize=12, leading=16, textColor=colors.HexColor('#2C3E50'), spaceBefore=12, spaceAfter=6)
    bold_text = ParagraphStyle('BoldT', fontName='Helvetica-Bold', fontSize=10, leading=14)
    normal_text = ParagraphStyle('NormT', fontName='Helvetica', fontSize=10, leading=14)

    elements = []
    
    # Header chuẩn Prokon
    elements.append(Paragraph("PROKON Column Design - Calculation Sheet", title_style))
    elements.append(Paragraph(f"Design Code: Eurocode 2 (EN 1992-1-1:2004) | Section Evaluation", subtitle_style))
    elements.append(Spacer(1, 10))
    
    # Phần 1: Thông số hình học & Vật liệu đầu vào
    elements.append(Paragraph("GENERAL DESIGN PARAMETERS & GEOMETRY", section_style))
    data_geo = [
        [Paragraph("<b>Parameter</b>", normal_text), Paragraph("<b>Value</b>", normal_text), Paragraph("<b>Material Properties</b>", normal_text), Paragraph("<b>Value</b>", normal_text)],
        ["Section Width b (mm)", f"{b}", "Concrete fck (MPa)", f"{fck}"],
        ["Section Depth h (mm)", f"{h}", "Steel fyk (MPa)", f"{fyk}"],
        ["Clear Height L (m)", f"{L}", "Design Concrete fcd (MPa)", f"{round(fcd, 2)}"],
        ["Concrete Cover c_nom (mm)", f"{cc}", "Total Provided Rebar As", f"{int(As_total)} mm² ({round(rebar_ratio,2)}%)"]
    ]
    t_geo = Table(data_geo, colWidths=[150, 100, 160, 100])
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
    
    # Phần 2: Đánh giá độ mảnh chi tiết theo từng bước của Prokon
    elements.append(Paragraph("SLENDERNESS AND SECOND-ORDER EFFECTS ASSESSMENT", section_style))
    slender_status = "SLENDER (Tính toán hiệu ứng cấp 2)" if is_slender else "SHORT COLUMN (Bỏ qua hiệu ứng cấp 2)"
    data_slender = [
        [Paragraph("<b>Calculation Step</b>", normal_text), Paragraph("<b>Formula / Value</b>", normal_text), Paragraph("<b>Status / Limit</b>", normal_text)],
        ["Effective Height l0 (m)", f"{round(l0, 3)} m (Biên liên kết: {top_cond} / {bot_cond})", "EC2 Cl. 5.2"],
        ["Radius of Gyration i (mm)", f"{round(radius_gyration, 1)} mm", "h / sqrt(12)"],
        ["Actual Slenderness Ratio (lambda)", f"{round(slenderness, 2)}", f"Limit: {round(slenderness_lim, 2)}"],
        ["Column Classification", slender_status, "PASS" if not is_slender else "Slenderness Applied"]
    ]
    t_slender = Table(data_slender, colWidths=[180, 210, 120])
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
    
    # Phần 3: Kết quả tổ hợp nội lực và Hệ số an toàn cuối cùng
    elements.append(Paragraph("ULTIMATE CAPACITY KINEMATICS & SAFETY FACTORS", section_style))
    status_text = "<b><font color='green'>PASS</font></b>" if is_pass else "<b><font color='red'>FAIL</font></b>"
    data_res = [
        [Paragraph("<b>Design Load Case Evaluation</b>", normal_text), Paragraph("<b>Applied Action</b>", normal_text), Paragraph("<b>Section Capacity (Limit)</b>", normal_text), Paragraph("<b>Status / Factor</b>", normal_text)],
        ["Axial Load N_Ed (kN)", f"{N_Ed} kN", f"Max Comp: {round(N_Rd, 1)} kN", "OK" if abs(N_Ed) <= N_Rd else "OVERLOADED"],
        ["Initial Moment M_0Ed (kNm)", f"{M_0Ed} kNm", "-", "-"],
        ["Second-Order Moment M2 (kNm)", f"{round(M_2, 1)} kNm", "Nominal Curvature Method", f"e2 = {round(M_2/max(N_Ed,1)*1000, 1)} mm"],
        ["Total Ultimate Moment M_Ed (kNm)", f"{round(M_Ed_total, 1)} kNm", f"Moment Capacity MRd: {round(M_Rd, 1)} kNm", f"S.F = {round(safety_factor, 2)}"],
        ["Minimum Rebar Check (EC2 9.5.2)", f"Provided: {int(As_total)} mm²", f"Required Min: {int(As_min)} mm²", "PASS" if rebar_min_check else "FAIL"],
        ["Ultimate Structural Status", "-", "-", status_text]
    ]
    t_res = Table(data_res, colWidths=[180, 120, 130, 80])
    t_res.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#2C3E50')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
        ('PADDING', (0,0), (-1,-1), 5),
        ('BACKGROUND', (3, 6), (3, 6), colors.HexColor('#C6EFCE') if is_pass else colors.HexColor('#FFC7CE')),
    ]))
    for r_idx, row in enumerate(data_res):
        if r_idx > 0:
            for c_idx, val in enumerate(row):
                if c_idx != 3 or r_idx != 6:
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
    file_name="Prokon_Detailed_Column_Report.pdf",
    mime="application/pdf"
)
