from io import BytesIO
from django.core.files.base import ContentFile
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from datetime import datetime


def generate_certificate_pdf(certificate):
    """Generate a PDF certificate for a completed course."""
    buffer = BytesIO()
    
    # Create PDF in landscape mode
    c = canvas.Canvas(buffer, pagesize=landscape(letter))
    width, height = landscape(letter)
    
    # Background border
    c.setStrokeColor(colors.HexColor('#00AEEF'))
    c.setLineWidth(10)
    c.rect(30, 30, width - 60, height - 60, stroke=1, fill=0)
    
    # Inner border
    c.setStrokeColor(colors.HexColor('#00AEEF'))
    c.setLineWidth(2)
    c.rect(50, 50, width - 100, height - 100, stroke=1, fill=0)
    
    # Title
    c.setFont("Helvetica-Bold", 48)
    c.setFillColor(colors.HexColor('#00AEEF'))
    c.drawCentredString(width / 2, height - 120, "CERTIFICATE")
    
    c.setFont("Helvetica", 24)
    c.setFillColor(colors.black)
    c.drawCentredString(width / 2, height - 160, "OF COMPLETION")
    
    # Decorative line
    c.setStrokeColor(colors.HexColor('#00AEEF'))
    c.setLineWidth(2)
    c.line(width / 2 - 150, height - 180, width / 2 + 150, height - 180)
    
    # "This is to certify that"
    c.setFont("Helvetica", 16)
    c.setFillColor(colors.grey)
    c.drawCentredString(width / 2, height - 230, "This is to certify that")
    
    # Learner name
    learner = certificate.enrollment.learner
    learner_name = f"{learner.first_name} {learner.last_name}".strip() or learner.username
    c.setFont("Helvetica-Bold", 32)
    c.setFillColor(colors.black)
    c.drawCentredString(width / 2, height - 280, learner_name)
    
    # Underline for name
    c.setStrokeColor(colors.HexColor('#00AEEF'))
    c.setLineWidth(1)
    name_width = c.stringWidth(learner_name, "Helvetica-Bold", 32)
    c.line(width / 2 - name_width / 2 - 20, height - 290, 
           width / 2 + name_width / 2 + 20, height - 290)
    
    # "has successfully completed"
    c.setFont("Helvetica", 16)
    c.setFillColor(colors.grey)
    c.drawCentredString(width / 2, height - 330, "has successfully completed the course")
    
    # Course title
    course_title = certificate.enrollment.course.title
    c.setFont("Helvetica-Bold", 24)
    c.setFillColor(colors.HexColor('#00AEEF'))
    c.drawCentredString(width / 2, height - 370, course_title)
    
    # Date
    c.setFont("Helvetica", 14)
    c.setFillColor(colors.black)
    issue_date = certificate.issued_at.strftime("%B %d, %Y")
    c.drawCentredString(width / 2, height - 420, f"Issued on {issue_date}")
    
    # Instructor signature section
    instructor = certificate.enrollment.course.instructor
    instructor_name = f"{instructor.first_name} {instructor.last_name}".strip() or instructor.username
    
    c.setFont("Helvetica", 12)
    c.setFillColor(colors.grey)
    c.drawCentredString(width / 2, 120, "Instructor")
    
    c.setFont("Helvetica-Bold", 14)
    c.setFillColor(colors.black)
    c.drawCentredString(width / 2, 100, instructor_name)
    
    # Signature line
    c.setStrokeColor(colors.black)
    c.setLineWidth(1)
    c.line(width / 2 - 100, 95, width / 2 + 100, 95)
    
    # Footer
    c.setFont("Helvetica", 10)
    c.setFillColor(colors.grey)
    c.drawCentredString(width / 2, 60, "ED3HUB - Web3 Learning Platform")
    
    # Save PDF
    c.showPage()
    c.save()
    
    # Save to certificate model
    buffer.seek(0)
    filename = f"certificate_{certificate.id}_{learner.username}.pdf"
    certificate.pdf_file.save(filename, ContentFile(buffer.read()), save=True)
    buffer.close()
    
    return certificate
