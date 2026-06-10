import streamlit as st
import numpy as np
import plotly.graph_objects as go
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

# 1. CẤU HÌNH TRANG WEB
st.set_page_config(page_title="EC2 Biaxial Column Designer", layout="wide")
st.title("🏛️ Concrete Column Design — Biaxial Bending (EC2) by KHA")
st.caption("Advanced Axial + Biaxial Bending Analysis ($M_x, M_y$) with PDF Reporting")
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
    
    total_bars = 2 * n_x + 2 * (n_y - 2)
    As_single = np.pi * (bar_dia**2) / 4
    As_total = total_bars * As_single
    st.caption(f"👉 Total Bars: {total_bars} | Total As = {int(As_total)} mm²")

with st.sidebar.expander("🧪 Vật liệu & Tải trọng (Materials & Loads)", expanded=True):
    fck = st.number_input("Concrete fck (MPa)", value=30.0, step=5.0)
    fyk = st.number_input("Steel fyk (MPa)", value=500.0, step=50.0)
    
    st.markdown("**ULS Design Loads:**")
    N_Ed = st.number_input("Axial Force N_Ed (kN, + Comp)", value=1500.0, step=100.0)
    M_Edx = st.number_input("Moment M_Edx (kNm) [Around X-Axis]", value=180.0, step=10.0)
    M_Edy = st.number_input("Moment M_Edy (kNm) [Around Y-Axis]", value=90.0, step=10.0)

# 3. THUẬT TOÁN LOGIC TOÁN HỌC & KIỂM TRA KẾT CẤU (EC2)
gamma_c, gamma_s = 1.5, 1.15
fcd = 0.85 * fck / gamma_c
fyd = fyk / gamma_s
Es = 200000.0

# Kiểm tra hàm lượng cốt thép tối thiểu theo EC2 (Mục 9.5.2)
# As,min = max(0.10 * N_Ed / fyd, 0.002 * Ac)
Ac = b * h
As_min_structural = 0.002 * Ac
As_min_load = (0.10 * abs(N_Ed) * 1000) / fyd if fyd > 0 else 0
As_min = max(As_min_structural, As_min_load)
rebar_ratio = (As_total / Ac) * 100
rebar_min_check = As_total >= As_min

# Tính toán tọa độ cốt thép vỉ phục vụ vẽ tiết diện
rebar_coords = []
dx = (b - 2*cc - bar_dia) / (n_x - 1) if n_x > 1 else 0
dy = (h - 2*cc - bar_dia) / (n_y - 1) if n_y > 1 else 0

for i in range(n_x):
    rebar_coords.append((cc + bar_dia/2 + i*dx - b/2, cc + bar_dia/2 - h/2))
    rebar_coords.append((cc + bar_dia/2 + i*dx - b/2, h/2 - cc - bar_dia/2))
for j in range(1, n_y - 1):
    rebar_coords.append((cc + bar_dia/2 - b/2, cc + bar_dia/2 + j*dy - h/2))
    rebar_coords.append((b/2 - cc - bar_dia/2, cc + bar_dia/2 + j*dy - h/2))

# THUẬT TOÁN ĐƯỜNG CONG TƯƠNG TÁC SẮP XẾP MỊN (HẾT VẶN XOẮN BIỂU ĐỒ)
def generate_smooth_curve(dim_b, dim_h):
    N_pts, M_pts = [], []
    d_eff = dim_h - cc - 10 - bar_dia/2
    d_prime = cc + 10 + bar_dia/2
    
    # Bước 1: Điểm nén thuần túy (Trục trung hòa vô hạn)
    N_pure_comp = (fcd * dim_b * dim_h + fyd * As_total) / 1000
    N_pts.append(N_pure_comp)
    M_pts.append(0.0)
    
    # Bước 2: Quét mịn trục trung hòa giảm dần từ trạng thái nén hoàn toàn đến kéo hoàn toàn (15 điểm mịn)
    xu_list = np.linspace(dim_h * 1.2, 0.01, 15)
    for xu in xu_list:
        if xu >= dim_h:
            Fcc = fcd * dim_b * dim_h
            z_cc = 0.0
        else:
            Fcc = fcd * dim_b * 0.8 * xu
            z_cc = dim_h / 2 - 0.4 * xu
            
        strain_comp = 0.0035
        # Kiểm tra điều kiện biến dạng cốt thép biên kéo và biên nén
        sig_s1 = min(max(-fyd, strain_comp * (d_eff - xu) / xu * Es), fyd) if xu > 0 else -fyd
        sig_s2 = min(max(-fyd, strain_comp * (xu - d_prime) / xu * Es), fyd) if xu > 0 else -fyd
        
        F_s1 = (As_total / 2) * sig_s1
        F_s2 = (As_total / 2) * sig_s2
        
        N_cur = (Fcc + F_s2 + F_s1) / 1000
        M_cur = (Fcc * z_cc + F_s2 * (dim_h/2 - d_prime) - F_s1 * (d_eff - dim_h/2)) / 1e6
        
        N_pts.append(N_cur)
        M_pts.append(M_cur)
        
    # Bước 3: Điểm kéo thuần túy
    N_pts.append(-As_total * fyd / 1000)
    M_pts.append(0.0)
    
    return N_pts, M_pts

N_curve_x, M_curve_x = generate_smooth_curve(b, h)
N_curve_y, M_curve_y = generate_smooth_curve(h, b)

# Nội suy chính xác năng lực kháng uốn ứng với lực dọc N_Ed
MRdx = np.interp(N_Ed, N_curve_x[::-1], M_curve_x[::-1])
MRdy = np.interp(N_Ed, N_curve_y[::-1], M_curve_y[::-1])

# Tính toán số mũ kiểm tra uốn hai phương (EC2 Cl. 5.8.9)
N_Rd = (fcd * b * h + fyd * As_total) / 1000
N_ratio = np.clip(N_Ed / N_Rd, 0.0, 1.0)
if N_ratio <= 0.1: a_exp = 1.0
elif N_ratio >= 0.7: a_exp = 2.0
else: a_exp = 1.0 + (N_ratio - 0.1) * (2.0 - 1.0) / (0.7 - 0.1)

biaxial_check = (M_Edx / max(MRdx, 1.0))**a_exp + (M_Edy / max(MRdy, 1.0))**a_exp
is_pass = biaxial_check <= 1.0 and rebar_min_check

# 4. GIAO DIỆN HIỂN THỊ ĐỒ HỌA TRÊN WEB
col_sec, col_charts, col_summary = st.columns([0.8, 1.4, 0.8])

with col_sec:
    st.subheader("🖼️ Section View")
    fig_sec = go.Figure()
    fig_sec.add_shape(type="rect", x0=-b/2, y0=-h/2, x1=b/2, y1=h/2, line=dict(color="#2C3E50", width=4), fillcolor="rgba(189, 195, 199, 0.3)")
    fig_sec.add_shape(type="rect", x0=-b/2+cc, y0=-h/2+cc, x1=b/2-cc, y1=h/2-cc, line=dict(color="#7F8C8D", width=2, dash="dash"))
    xs, ys = zip(*rebar_coords)
    fig_sec.add_trace(go.Scatter(x=xs, y=ys, mode='markers', marker=dict(size=bar_dia*0.8, color='#E74C3C', line=dict(width=1, color='black'))))
    fig_sec.update_layout(xaxis_range=[-b*0.7, b*0.7], yaxis_range=[-h*0.7, h*0.7], width=260, height=360, showlegend=False, xaxis=dict(visible=False), yaxis=dict(visible=False), margin=dict(l=10, r=10, t=10, b=10))
    st.plotly_chart(fig_sec, use_container_width=True)

with col_charts:
    st.subheader("📈 Interaction Curve (Corrected & Smooth)")
    tab1, tab2 = st.tabs(["Trục X (Mx)", "Trục Y (My)"])
    with tab1:
        fig_x = go.Figure()
        fig_x.add_trace(go.Scatter(x=M_curve_x, y=N_curve_x, mode='lines+markers', name='Capacity Boundary', line=dict(color='#1B365D', width=2.5)))
        fig_x.add_trace(go.Scatter(x=[M_Edx], y=[N_Ed], mode='markers', name='Design Load', marker=dict(color='Red' if not is_pass else 'Green', size=12, symbol='cross')))
        fig_x.update_layout(xaxis_title="Moment M_Edx (kNm)", yaxis_title="Axial Force N_Ed (kN)", height=350, margin=dict(l=10, r=10, t=10, b=10))
        st.plotly_chart(fig_x, use_container_width=True)
    with tab2:
        fig_y = go.Figure()
        fig_y.add_trace(go.Scatter(x=M_curve_y, y=N_curve_y, mode='lines+markers', name='Capacity Boundary', line=dict(color='#008080', width=2.5)))
        fig_y.add_trace(go.Scatter(x=[M_Edy], y=[N_Ed], mode='markers', name='Design Load', marker=dict(color='Red' if not is_pass else 'Green', size=12, symbol='cross')))
        fig_y.update_layout(xaxis_title="Moment M_Edy (kNm)", yaxis_title="Axial Force N_Ed (kN)", height=350, margin=dict(l=10, r=10, t=10, b=10))
        st.plotly_chart(fig_y, use_container_width=True)

with col_summary:
    st.subheader("📋 Verification Results")
    st.metric(label="Biaxial Utilization Ratio", value=f"{round(biaxial_check, 2)}", delta="Limit: 1.0", delta_color="inverse" if biaxial_check > 1.0 else "normal")
    
    # Hiển thị kiểm tra hàm lượng cốt thép tối thiểu
    st.markdown("**Hàm lượng thép tối thiểu (EC2):**")
    st.write(f"- Thép yêu cầu $A_{{s,min}}$: **{int(As_min)}** mm²")
    st.write(f"- Thép bố trí $A_{{s,prov}}$: **{int(As_total)}** mm² (Tỷ lệ: {round(rebar_ratio, 2)}%)")
    if rebar_min_check:
        st.success("✅ Hàm lượng thép: ĐẠT")
    else:
        st.error("❌ Hàm lượng thép: THIẾU")
        
    if is_pass:
        st.success("🎉 TIẾT DIỆN ĐẠT YÊU CẦU")
    else:
        st.error("💥 TIẾT DIỆN KHÔNG ĐẠT")

# 5. LOGIC TẠO VÀ XUẤT BÁO CÁO PDF (PROKON STYLE)
def generate_pdf_report():
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
    styles = getSampleStyleSheet()
    
    # Khởi tạo style tiêu đề và văn bản bản vẽ
    title_style = ParagraphStyle('Title', parent=styles['Heading1'], fontName='Helvetica-Bold', fontSize=20, leading=24, textColor=colors.HexColor('#1B365D'), spaceAfter=15)
    section_style = ParagraphStyle('Section', parent=styles['Heading2'], fontName='Helvetica-Bold', fontSize=14, leading=18, textColor=colors.HexColor('#2C3E50'), spaceBefore=12, spaceAfter=8)
    normal_style = ParagraphStyle('Normal', parent=styles['Normal'], fontName='Helvetica', fontSize=10, leading=14)
    
    elements = []
    elements.append(Paragraph("STRUCTURAL DESIGN REPORT — REINFORCED CONCRETE COLUMN", title_style))
    elements.append(Paragraph("Design Code: Eurocode 2 (EN 1992-1-1) | Analysis: Biaxial Bending", normal_style))
    elements.append(Spacer(1, 15))
    
    # Bảng thông số đầu vào hình học và vật liệu
    elements.append(Paragraph("1. Geometry and Material Properties", section_style))
    data_geo = [
        ["Parameter", "Value", "Parameter", "Value"],
        ["Width b (mm)", str(b), "Concrete fck (MPa)", str(fck)],
        ["Depth h (mm)", str(h), "Steel fyk (MPa)", str(fyk)],
        ["Cover c_nom (mm)", str(cc), "Rebar Layout", f"{total_bars}xT{bar_dia}"]
    ]
    t_geo = Table(data_geo, colWidths=[130, 130, 130, 130])
    t_geo.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1B365D')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
        ('PADDING', (0,0), (-1,-1), 6),
    ]))
    elements.append(t_geo)
    elements.append(Spacer(1, 15))
    
    # Bảng số liệu tải trọng tác dụng và kết quả kiểm tra
    elements.append(Paragraph("2. Design Actions & Capacity Checks", section_style))
    data_check = [
        ["Design Action / Check", "Applied Value", "Capacity Limit", "Status"],
        ["Axial Force N_Ed (kN)", str(N_Ed), str(round(N_Rd, 1)), "OK" if abs(N_Ed)<=N_Rd else "FAIL"],
        ["Moment M_Edx (kNm)", str(M_Edx), str(round(MRdx, 1)), "-"],
        ["Moment M_Edy (kNm)", str(M_Edy), str(round(MRdy, 1)), "-"],
        ["Min Reinforcement As (mm²)", str(int(As_total)), str(int(As_min)), "PASS" if rebar_min_check else "FAIL"],
        ["Biaxial Combined Ratio", f"{round(biaxial_check, 2)}", "1.00", "PASS" if is_pass else "FAIL"]
    ]
    t_check = Table(data_check, colWidths=[180, 110, 110, 120])
    t_check.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#2C3E50')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
        ('PADDING', (0,0), (-1,-1), 6),
        ('BACKGROUND', (3, 5), (3, 5), colors.HexColor('#C6EFCE') if is_pass else colors.HexColor('#FFC7CE')),
    ]))
    elements.append(t_check)
    
    doc.build(elements)
    buffer.seek(0)
    return buffer

st.markdown("---")
st.subheader("🖨️ Export PDF Calculation Report")
pdf_data = generate_pdf_report()

st.download_button(
    label="📥 Download PDF Design Report",
    data=pdf_data,
    file_name="Column_Design_Report_EC2.pdf",
    mime="application/pdf"
)
