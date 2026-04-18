from io import BytesIO
from django.core.files.base import ContentFile
from reportlab.lib.pagesizes import landscape, A4
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.utils import ImageReader
import qrcode


# ── Colour palette (matches React frontend exactly) ─────────────────────────
BLUE_LIGHT  = colors.HexColor('#BFDBFE')   # border-blue-300  – outer border
BLUE_MID    = colors.HexColor('#93C5FD')   # inner triangles
BLUE_DARK   = colors.HexColor('#1E3A5F')   # text-blue-900    – name text / inner border
BLUE_ACCENT = colors.HexColor('#2563EB')   # bg-blue-600      – logo box + course title
GREY_900    = colors.HexColor('#111827')   # text-gray-900
GREY_800    = colors.HexColor('#1F2937')   # text-gray-800    – cert-of-completion title
GREY_700    = colors.HexColor('#374151')   # text-gray-700    – body text
GREY_500    = colors.HexColor('#6B7280')   # text-gray-500    – small labels
GREY_400    = colors.HexColor('#9CA3AF')   # border-gray-400  – dividers / footer labels
WHITE       = colors.white


# ── Helpers ──────────────────────────────────────────────────────────────────

def _make_qr(data: str, size: int = 120) -> ImageReader:
    qr = qrcode.QRCode(box_size=4, border=1,
                       error_correction=qrcode.constants.ERROR_CORRECT_M)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color='black', back_color='white').convert('RGB')
    img = img.resize((size, size))
    buf = BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    return ImageReader(buf)


def _sig_path(c, cx, base_y):
    """Draw a small SVG-style squiggle signature above base_y."""
    # mirrors: M8 16 Q14 8,20 12 T40 16  (60×24 viewBox, centred on cx)
    p = c.beginPath()
    # shift so 60-unit-wide path centres on cx
    ox = cx - 20
    oy = base_y
    p.moveTo(ox + 8,  oy + 8)
    p.curveTo(ox + 14, oy + 16, ox + 20, oy + 12, ox + 26, oy + 14)
    p.curveTo(ox + 32, oy + 16, ox + 36, oy + 8,  ox + 40, oy + 8)
    c.setStrokeColor(GREY_700)
    c.setLineWidth(1.2)
    c.drawPath(p, stroke=1, fill=0)


# ── Main generator ───────────────────────────────────────────────────────────

def generate_certificate_pdf(certificate):
    """
    Generate a landscape-A4 PDF that mirrors the React CertificatePreviewPage.

    Layout (top → bottom, all y coords in ReportLab pts from bottom-left):
      • Corner decorative triangles (opacity-25 large, opacity-35 small)
      • Outer border  border-8 border-blue-300 rounded
      • Inner border  border-2 border-blue-900  (inset-4 ≈ 16 pt from outer)
      • Logo row      e-box + "ed3hub" text
      • Divider line
      • "CERTIFICATE OF COMPLETION"
      • Divider line
      • "This is to certify that"
      • Learner name  (text-5xl font-bold text-blue-900)
      • "has successfully completed the course"
      • Underline
      • Course title  (text-2xl font-bold text-blue-600)
      • Description
      • Footer divider
      • 4-column footer: Date | Certificate ID | Instructor | QR
      • Verify URL
    """
    from django.conf import settings

    buffer = BytesIO()
    W, H = landscape(A4)          # 841.9 × 595.3 pt
    c = canvas.Canvas(buffer, pagesize=(W, H))

    # ── 1. Corner triangles ──────────────────────────────────────────────────
    # Large right-angle triangles – opacity ~0.25 → tinted fill (#DBEAFE)
    TINT_LARGE = colors.HexColor('#DBEAFE')
    TINT_SMALL = colors.HexColor('#C7DEFD')   # ~opacity-35 blend

    T = 200   # leg length for large triangles  (w-56 → 224 px ≈ 200 pt)

    c.setFillColor(TINT_LARGE)
    # top-right  (polygon points="200,0 200,200 0,0" → W,H ; W,H-T ; W-T,H)
    p = c.beginPath(); p.moveTo(W, H); p.lineTo(W, H - T); p.lineTo(W - T, H); p.close()
    c.drawPath(p, fill=1, stroke=0)
    # bottom-left (polygon points="0,200 0,0 200,200" → 0,0 ; 0,T ; T,0)
    p = c.beginPath(); p.moveTo(0, 0); p.lineTo(T, 0); p.lineTo(0, T); p.close()
    c.drawPath(p, fill=1, stroke=0)

    # Small equilateral-ish triangles – opacity ~0.35
    # React positions them absolute top-12 right-12 (≈48 pt) and bottom-12 left-12
    c.setFillColor(TINT_SMALL)
    ts = 90   # half-size of inner triangle region  (w-32 → 128 px ≈ 90 pt)

    # top-right inner pointing down: points="50,10 90,85 10,85"
    # centred at (W-48-64, H-48-64)
    icx, icy = W - 110, H - 110
    p = c.beginPath()
    p.moveTo(icx,        icy + ts * 0.4)
    p.lineTo(icx + ts,   icy - ts * 0.4)
    p.lineTo(icx - ts,   icy - ts * 0.4)
    p.close(); c.drawPath(p, fill=1, stroke=0)

    # bottom-left inner pointing up: points="50,90 10,15 90,15"
    icx, icy = 110, 110
    p = c.beginPath()
    p.moveTo(icx,        icy - ts * 0.4)
    p.lineTo(icx + ts,   icy + ts * 0.4)
    p.lineTo(icx - ts,   icy + ts * 0.4)
    p.close(); c.drawPath(p, fill=1, stroke=0)

    # ── 2. Borders ───────────────────────────────────────────────────────────
    # Outer: border-8 border-blue-300 rounded-lg  (inset-0)
    mo = 8
    c.setStrokeColor(BLUE_LIGHT)
    c.setLineWidth(8)
    c.roundRect(mo, mo, W - 2*mo, H - 2*mo, 6, stroke=1, fill=0)

    # Inner: border-2 border-blue-900  (inset-4 = 16 pt)
    mi = 24
    c.setStrokeColor(BLUE_DARK)
    c.setLineWidth(2)
    c.roundRect(mi, mi, W - 2*mi, H - 2*mi, 3, stroke=1, fill=0)

    # ── 3. Logo ──────────────────────────────────────────────────────────────
    # Start from top of content area with proper spacing
    logo_top = H - 80
    box_sz   = 36
    gap      = 12
    c.setFont('Helvetica-Bold', 26)
    hub_w = c.stringWidth('ed3hub', 'Helvetica-Bold', 26)
    group_w = box_sz + gap + hub_w
    gx = (W - group_w) / 2

    c.setFillColor(BLUE_ACCENT)
    c.roundRect(gx, logo_top, box_sz, box_sz, 5, fill=1, stroke=0)
    c.setFillColor(WHITE)
    c.setFont('Helvetica-Bold', 20)
    c.drawCentredString(gx + box_sz / 2, logo_top + 9, 'e')

    c.setFillColor(GREY_800)
    c.setFont('Helvetica-Bold', 26)
    c.drawString(gx + box_sz + gap, logo_top + 6, 'ed3hub')

    # ── 4. "CERTIFICATE OF COMPLETION" with dividers ─────────────────────────
    coc_y     = logo_top - 52
    rule_hw = 160

    c.setStrokeColor(GREY_400)
    c.setLineWidth(1.5)
    c.line(W/2 - rule_hw, coc_y + 18, W/2 + rule_hw, coc_y + 18)

    c.setFont('Helvetica-Bold', 16)
    c.setFillColor(GREY_800)
    c.drawCentredString(W / 2, coc_y, 'CERTIFICATE OF COMPLETION')

    c.line(W/2 - rule_hw, coc_y - 8, W/2 + rule_hw, coc_y - 8)

    # ── 5. "This is to certify that" ─────────────────────────────────────────
    certify_y = coc_y - 40
    c.setFont('Helvetica', 12)
    c.setFillColor(GREY_700)
    c.drawCentredString(W / 2, certify_y, 'This is to certify that')

    # ── 6. Learner name ──────────────────────────────────────────────────────
    learner      = certificate.enrollment.learner
    learner_name = (f"{learner.first_name} {learner.last_name}".strip()
                    or learner.username).upper()

    name_y = certify_y - 52
    c.setFont('Helvetica-Bold', 48)
    c.setFillColor(BLUE_DARK)
    c.drawCentredString(W / 2, name_y, learner_name)

    # ── 7. "has successfully completed the course" ───────────────────────────
    completed_y = name_y - 40
    c.setFont('Helvetica', 11)
    c.setFillColor(GREY_700)
    c.drawCentredString(W / 2, completed_y, 'has successfully completed the course')

    c.setStrokeColor(GREY_400)
    c.setLineWidth(1.5)
    c.line(W/2 - 120, completed_y - 8, W/2 + 120, completed_y - 8)

    # ── 8. Course title ──────────────────────────────────────────────────────
    course_title = certificate.enrollment.course.title.upper()
    course_y = completed_y - 38
    c.setFont('Helvetica-Bold', 18)
    c.setFillColor(BLUE_ACCENT)
    c.drawCentredString(W / 2, course_y, course_title)

    # ── 9. Description ───────────────────────────────────────────────────────
    desc_y = course_y - 28
    c.setFont('Helvetica', 10)
    c.setFillColor(GREY_700)
    c.drawCentredString(W / 2, desc_y,
        'on ed3hub, demonstrating proficiency and understanding of the'
    )
    c.drawCentredString(W / 2, desc_y - 12, 'subject matter.')

    # ── 10. Footer divider ───────────────────────────────────────────────────
    footer_line_y = desc_y - 38
    c.setStrokeColor(GREY_400)
    c.setLineWidth(1.5)
    c.line(mi + 20, footer_line_y, W - mi - 20, footer_line_y)

    # ── 11. Footer: 4 columns  Date | Cert ID | Instructor | QR ─────────────
    instructor      = certificate.enrollment.course.instructor
    instructor_name = (
        f"{instructor.first_name} {instructor.last_name}".strip()
        or instructor.username
    )
    issue_date   = certificate.issued_at.strftime('%B %d, %Y')
    cert_id      = certificate.certificate_id
    frontend_url = getattr(settings, 'FRONTEND_URL', 'https://ed3hub.com')
    verify_url   = f'{frontend_url}/certificate/verify/{cert_id}'

    pad      = mi + 28
    qr_sz    = 72
    qr_cx    = W - pad - qr_sz / 2 - 12
    col_span = (qr_cx - qr_sz / 2 - pad) / 3
    c1 = pad + col_span * 0.5
    c2 = pad + col_span * 1.5
    c3 = pad + col_span * 2.5

    lbl_y  = footer_line_y - 14
    val_y  = footer_line_y - 28
    sig_y  = footer_line_y - 48
    line_y = footer_line_y - 60
    role_y = footer_line_y - 70

    def col_label(x, txt):
        c.setFont('Helvetica', 9)
        c.setFillColor(GREY_700)
        c.drawCentredString(x, lbl_y, txt)

    def col_value(x, txt, max_width=160):
        c.setFont('Helvetica-Bold', 11)
        c.setFillColor(GREY_900)
        while c.stringWidth(txt, 'Helvetica-Bold', 11) > max_width and len(txt) > 6:
            txt = txt[:-4] + '...'
        c.drawCentredString(x, val_y, txt)

    def col_rule(x, half=32):
        c.setStrokeColor(GREY_400)
        c.setLineWidth(0.9)
        c.line(x - half, line_y, x + half, line_y)

    def col_role(x, txt):
        c.setFont('Helvetica', 7.5)
        c.setFillColor(GREY_500)
        c.drawCentredString(x, role_y, txt)

    # Date column
    col_label(c1, 'Date')
    col_value(c1, issue_date)
    _sig_path(c, c1, sig_y)
    col_rule(c1)
    col_role(c1, 'Issued On')

    # Certificate ID column
    col_label(c2, 'Certificate ID')
    col_value(c2, cert_id, max_width=180)
    col_rule(c2)
    col_role(c2, 'Verified')

    # Instructor column
    col_label(c3, 'Instructor')
    col_value(c3, instructor_name)
    _sig_path(c, c3, sig_y)
    col_rule(c3)
    col_role(c3, 'ed3hub')

    # QR column
    qr_img = _make_qr(verify_url, size=200)
    qr_top = footer_line_y - 14 - qr_sz
    c.drawImage(qr_img, qr_cx - qr_sz / 2, qr_top,
                width=qr_sz, height=qr_sz, preserveAspectRatio=True)
    c.setStrokeColor(colors.HexColor('#D1D5DB'))
    c.setLineWidth(1.5)
    c.rect(qr_cx - qr_sz / 2, qr_top, qr_sz, qr_sz, stroke=1, fill=0)
    c.setFont('Helvetica-Bold', 7)
    c.setFillColor(GREY_500)
    c.drawCentredString(qr_cx, qr_top - 9, 'Scan to Verify')

    # ── 12. Verify URL ───────────────────────────────────────────────────────
    c.setFont('Helvetica', 7)
    c.setFillColor(GREY_400)
    c.drawCentredString(W / 2, mi + 6, f'Verify: {verify_url}')

    # ── Finalise ─────────────────────────────────────────────────────────────
    c.showPage()
    c.save()

    buffer.seek(0)
    filename = f'certificate_{cert_id}_{learner.username}.pdf'
    certificate.pdf_file.save(filename, ContentFile(buffer.read()), save=False)
    buffer.close()

    generate_qr_code(certificate)
    certificate.save()
    return certificate


def generate_qr_code(certificate):
    """Generate and save a standalone QR code image for the certificate."""
    from django.conf import settings

    frontend_url = getattr(settings, 'FRONTEND_URL', 'https://ed3hub.com')
    verify_url   = f'{frontend_url}/certificate/verify/{certificate.certificate_id}'

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=2,
    )
    qr.add_data(verify_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color='black', back_color='white')

    buf = BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)

    filename = f'qr_{certificate.certificate_id}.png'
    certificate.qr_code.save(filename, ContentFile(buf.read()), save=False)
    buf.close()
    return certificate
