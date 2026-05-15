"""
Email Service for sending expert consultation requests
Uses Gmail SMTP to send emails directly from the backend
"""
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import os
from typing import Optional
import logging
from dotenv import load_dotenv

# Load .env file FIRST before reading env vars
load_dotenv(override=True)

logger = logging.getLogger(__name__)

# Email configuration - using Gmail App Password
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_EMAIL = os.getenv("SMTP_EMAIL", "deekshithpoojari2004@gmail.com")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
COMPANY_EMAIL = "deekshithpoojari2004@gmail.com"

# Log configuration at startup
logger.info(f"Email Config: SMTP_EMAIL={SMTP_EMAIL}, COMPANY_EMAIL={COMPANY_EMAIL}")
logger.info(f"SMTP_PASSWORD configured: {'Yes' if SMTP_PASSWORD else 'No'}")


def send_expert_request_email(
    farmer_name: str,
    farmer_email: str,
    farmer_phone: str,
    category: str,
    issue_description: str,
    image_path: Optional[str] = None
) -> dict:
    """
    Send expert consultation request email to company email
    
    Args:
        farmer_name: Name of the farmer
        farmer_email: Email of the farmer (from Firebase login)
        farmer_phone: Phone number of the farmer
        category: Issue category (disease, pest, soil, etc.)
        issue_description: Detailed description of the issue
        image_path: Optional path to attached image
        
    Returns:
        dict with success status and message
    """
    
    # If no SMTP password configured, just log and return success
    # This allows the app to work without email configured
    if not SMTP_PASSWORD:
        logger.warning("SMTP_PASSWORD not configured. Email not sent but ticket created.")
        return {
            "success": True,
            "message": "Ticket created. Email notifications disabled (SMTP not configured).",
            "email_sent": False
        }
    
    try:
        # Create message
        msg = MIMEMultipart()
        msg['From'] = f"{farmer_name} <{SMTP_EMAIL}>"  # Show farmer name
        msg['To'] = COMPANY_EMAIL
        msg['Reply-To'] = farmer_email  # Reply goes to farmer's email!
        msg['Subject'] = f"[Expert Request] {category} - from {farmer_name} ({farmer_email})"
        
        # Email body
        body = f"""
═══════════════════════════════════════════════════════
           EXPERT CONSULTATION REQUEST
═══════════════════════════════════════════════════════

📧 REPLY TO THIS EMAIL TO CONTACT THE FARMER DIRECTLY

FARMER DETAILS:
---------------
Name:  {farmer_name}
Email: {farmer_email}  ← Click Reply to respond
Phone: {farmer_phone}

ISSUE CATEGORY: {category}

PROBLEM DESCRIPTION:
--------------------
{issue_description}

═══════════════════════════════════════════════════════
Sent via Farm AI Assistant App
To reply, simply click "Reply" - it will go to {farmer_email}
═══════════════════════════════════════════════════════
        """
        
        msg.attach(MIMEText(body, 'plain'))
        
        # Attach image if provided
        if image_path and os.path.exists(image_path):
            try:
                with open(image_path, 'rb') as attachment:
                    # Determine MIME type based on extension
                    file_ext = os.path.splitext(image_path)[1].lower()
                    if file_ext in ['.jpg', '.jpeg']:
                        maintype, subtype = 'image', 'jpeg'
                    elif file_ext == '.png':
                        maintype, subtype = 'image', 'png'
                    elif file_ext == '.gif':
                        maintype, subtype = 'image', 'gif'
                    elif file_ext == '.bmp':
                        maintype, subtype = 'image', 'bmp'
                    else:
                        maintype, subtype = 'application', 'octet-stream'
                    
                    part = MIMEBase(maintype, subtype)
                    part.set_payload(attachment.read())
                    encoders.encode_base64(part)
                    filename = os.path.basename(image_path)
                    part.add_header(
                        'Content-Disposition',
                        f'attachment; filename="{filename}"'
                    )
                    msg.attach(part)
                    logger.info(f"Attached image: {filename} (type: {maintype}/{subtype})")
            except Exception as e:
                logger.error(f"Failed to attach image: {e}", exc_info=True)
        
        # Send email
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_EMAIL, SMTP_PASSWORD)
            server.sendmail(SMTP_EMAIL, COMPANY_EMAIL, msg.as_string())
        
        logger.info(f"Expert request email sent for {farmer_name}")
        return {
            "success": True,
            "message": "Email sent successfully",
            "email_sent": True
        }
        
    except smtplib.SMTPAuthenticationError:
        logger.error("SMTP authentication failed. Check SMTP_PASSWORD (App Password)")
        return {
            "success": True,  # Ticket still created
            "message": "Ticket created but email failed (auth error)",
            "email_sent": False
        }
    except Exception as e:
        logger.error(f"Failed to send email: {e}")
        return {
            "success": True,  # Ticket still created
            "message": f"Ticket created but email failed: {str(e)}",
            "email_sent": False
        }
