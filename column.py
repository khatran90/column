import streamlit as st
import numpy as np
import plotly.graph_objects as go
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

# 1. CẤU HÌNH TRANG WEB
st.set_page_config(page_title="EC2 Biaxial Column Designer (Prokon Style)", layout="wide")
st.title("🏛️ Concrete Column Design — Biaxial Bending (EC2) by KHA TRAN")
st.caption("Advanced True Biaxial Interaction Analysis ($N - M_{{design}}$) — Prokon Style")
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

# 3. THUẬT TOÁN LOGIC TOÁN HỌC XOAY TRỤC BIẾN DẠNG (TRUE BIAXIAL)
gamma_c, gamma_s = 1.5, 1.15
fcd = 0.85 * fck / gamma_c
fyd = fyk / gamma_s
Es = 200000.0

# Tính toán khả năng nén thuần túy giới hạn tổng thể của tiết diện
N_Rd = (fcd * b * h + fyd * As_total) / 1000

# Kiểm tra hàm lượng cốt thép tối thiểu theo EC2 (Mục 9.5.2)
Ac = b * h
As_min = max(0.002 * Ac, (0.10 * abs(N_Ed) * 1000) / fyd)
rebar_min_check = As_total >= As_min
rebar_ratio = (As_total / Ac) * 100

# Tạo tọa độ của từng thanh thép phục vụ xoay ma trận ứng suất
rebar_coords = []
dx = (b - 2*cc - bar_dia) / (n_x - 1) if n_x > 1 else 0
dy = (h - 2*cc - bar_dia) / (n_y - 1) if n_y > 1 else 0

for i in range(n_x):
    rebar_coords.append((cc + bar_dia/2 + i*dx - b/2, cc + bar_dia/2 - h/2))
    rebar_coords.append((cc + bar_dia/2 + i*dx - b/2, h/2 - cc - bar_dia/2))
for j in range(1, n_y - 1):
    rebar_coords.append((cc + bar_dia/2 - b/2, cc + bar_dia/2 + j*dy - h/2))
    rebar_coords.append((b/2 - cc - bar_dia/2, cc + bar_dia/2 + j*dy - h/2))
rebar_coords = list(set(rebar_coords)) # Loại bỏ trùng lặp góc

# TÍNH TOÁN M_DESIGN TỔNG HỢP VÀ GÓC LỆCH TẢI THETA
M_Ed_tot = np.sqrt(M_Edx**2 + M_Edy**2)
theta = np.arctan2(abs(M_Edy), abs(M_Edx)) if M_Edx > 0 else np.pi/2

def generate_biaaxial_profile(angle):
    """Tính toán đường bao tương tác chuẩn Prokon bằng cách quét phẳng xoay góc nghiêng trục trung hòa"""
    N_profile, M_profile = [], []
    
    # 1. Điểm nén thuần túy
    N_profile.append(N_Rd)
    M_profile.append(0.0)
    
    # Chiều dài hình chiếu lớn nhất của tiết diện lên phương vuông góc trục trung hòa xoay
    h_prime = abs(b * np.cos(angle)) + abs(h * np.sin(angle))
    
    # 2. Quét mịn qua 25 điểm chiều sâu trục trung hòa thực tế
    for xu in np.linspace(h_prime * 1.0, h_prime * 0.01, 25):
        # Tính toán diện tích khối nén bê tông quy đổi theo mặt cắt nghiêng góc angle
        area_ratio = min(xu / h_prime, 1.0)
        Fcc = fcd * b * h * area_ratio * 0.8
        z_cc = (h_prime / 2 - 0.4 * xu)
        
        F_steel_tot = 0.0
        M_steel_tot = 0.0
        
        # Tính toán biến dạng (strain) riêng biệt của từng thanh thép dựa theo ma trận xoay hình học
        for rx, ry in rebar_coords:
            # Hình chiếu khoảng cách thanh thép đến trục trung hòa xoay nghiêng
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
        
    # 3. Điểm kéo thuần túy
    N_profile.append(-As_total * fyd / 1000)
    M_profile.append(0.0)
    
    return N_profile, M_profile

# Gọi hàm tạo đường bao kháng uốn quy đổi tổng hợp thực tế
N_curve, M_curve = generate_biaaxial_profile(theta)

# Tìm khả năng kháng uốn giới hạn M_Rd ứng với lực dọc N_Ed hiện tại bằng nội suy
M_Rd = np.interp(N_Ed, N_curve[::-1], M_curve[::-1])
utilization = M_Ed_tot / max(M_Rd, 1.0)
is_pass = utilization <= 1.0 and rebar_min_check

# 4. GIAO DIỆN HIỂN THỊ ĐỒ HỌA TRÊN WEB (UI/UX)
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
    st.subheader(f"📈 True Biaxial Interaction Curve (Angle: {round(np.degrees(theta), 1)}°)")
    
    fig_inter = go.Figure()
    fig_inter.add_trace(go.Scatter(
        x=M_curve, y=N_curve, 
        mode='lines+markers', 
        name='Biaxial Capacity Envelope', 
        line=dict(color='#1B365D', width=3),
        fill='toself',
        fillcolor='rgba(27, 54, 93, 0.04)'
    ))
    fig_inter.add_trace(go.Scatter(
        x=[M_Ed_tot], y=[N_Ed], 
        mode='markers', 
        name='Design Point (M_design)', 
        marker=dict(color='Red' if not is_pass else 'Green', size=14, symbol='cross')
    ))
    fig_inter.update_layout(
        xaxis_title="Design Moment M_design = sqrt(Mx² + My²) (kNm)", 
        yaxis_title="Axial Force N_Ed (kN)", 
        height=380, 
        margin=dict(l=10, r=10, t=10, b=10)
    )
    st.plotly_chart(fig_inter, use_container_width=True)

with col_summary:
    st.subheader("📋 Verification Results")
    st.metric(label="Biaxial Utilization Ratio", value=f"{round(utilization, 2)}", delta="Limit: 1.0", delta_color="inverse" if utilization > 1.0 else "normal")
    
    st.markdown("**Thông số Mô-men quy đổi:**")
    st.write(f"- $M_{{Ed,tot}} (M_{{design}})$: **{round(M_Ed_tot, 1)}** kNm")
    st.write(f"- Khả năng kháng uốn tổng hợp $M_{{Rd}}$: **{round(M_Rd, 1)}** kNm")
    
    st.markdown("**Hàm lượng cốt thép tối thiểu:**")
    st.write(f"- Thép yêu cầu $A_{{s,min}}$: **{int(As_min)}** mm²")
    st.write(f"- Thép thực tế $A_{{s,prov}}$: **{int(As_total)}** mm² ({round(rebar_ratio, 2)}%)")
    
    st.markdown("---")
    if is_pass:
        st.success("🎉 TIẾT DIỆN ĐẠT YÊU CẦU")
    else:
        st.error("💥 TIẾT DIỆN KHÔNG ĐẠT")

# 5. LOGIC TẠO VÀ XUẤT BÁO CÁO PDF ĐÃ SỬA LỖI KHAI BÁO BIẾN
def generate_pdf_report():
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle('Title', parent=styles['Heading1'], fontName='Helvetica-Bold', fontSize=18, leading=22, textColor=colors.HexColor('#1B365D'), spaceAfter=15)
    section_style = ParagraphStyle('Section', parent=styles['Heading2'], fontName='Helvetica-Bold', fontSize=12, leading=16, textColor=colors.HexColor('#2C3E50'), spaceBefore=12, spaceAfter=8)
    normal_style = ParagraphStyle('Normal', parent=styles['Normal'], fontName='Helvetica', fontSize=10, leading=14)
    
    elements = []
    elements.append(Paragraph("STRUCTURAL DESIGN REPORT — BIAXIAL COLUMN ANALYSIS", title_style))
    elements.append(Paragraph("Code: Eurocode 2 (EN 1992-1-1) | Method: True Section Vector Rotation", normal_style))
    elements.append(Spacer(1, 15))
    
    elements.append(Paragraph("1. Cross-Section Geometry & Material Properties", section_style))
    data_geo = [
        ["Parameter", "Value", "Parameter", "Value"],
        ["Width b (mm)", str(b), "Concrete fck (MPa)", str(fck)],
        ["Depth h (mm)", str(h), "Steel fyk (MPa)", str(fyk)],
        ["Cover c_nom (mm)", str(cc), "Total Main Bars", f"{total_bars}xT{bar_dia}"]
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
    
    elements.append(Paragraph("2. Load Combinations & Ultimate Capacity Checks", section_style))
    data_check = [
        ["Design Parameter", "Applied Value", "Capacity Limit", "Utilization / Status"],
        ["Axial Force N_Ed (kN)", str(N_Ed), str(round(N_Rd, 1)), "OK" if abs(N_Ed)<=N_Rd else "OVERLOADED"],
        ["Biaxial Moment M_design (kNm)", str(round(M_Ed_tot, 1)), str(round(M_Rd, 1)), f"{round(utilization, 2)}"],
        ["Min Reinforcement Area As (mm²)", str(int(As_total)), str(int(As_min)), "PASS" if rebar_min_check else "FAIL"],
        ["Final Structural Status", "-", "-", "PASS" if is_pass else "FAIL"]
    ]
    t_check = Table(data_check, colWidths=[180, 110, 110, 120])
    t_check.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#2C3E50')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
        ('PADDING', (0,0), (-1,-1), 6),
        ('BACKGROUND', (3, 4), (3, 4), colors.HexColor('#C6EFCE') if is_pass else colors.HexColor('#FFC7CE')),
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
    file_name="Biaxial_Column_Design_Report.pdf",
    mime="application/pdf"
)
