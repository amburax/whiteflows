"""
WhiteFlows Application Server - FastAPI Edition
Modern async server with uvicorn for better performance and error handling
"""

import os
import json
from typing import Optional
import threading
import smtplib
from pathlib import Path
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from fpdf import FPDF

import traceback
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
GMAIL_SENDER = os.environ.get('GMAIL_SENDER', 'your-email@gmail.com')
GMAIL_PASSWORD = os.environ.get('GMAIL_PASSWORD', 'your-app-password')
GMAIL_RECEIVER = os.environ.get('GMAIL_RECEIVER', 'recipient-email@gmail.com')

# Setup paths
BASE_DIR = Path(__file__).parent
APPLICATIONS_DIR = BASE_DIR / "applications"
APPLICATIONS_DIR.mkdir(parents=True, exist_ok=True)

# FastAPI app instance
app = FastAPI(title="WhiteFlows", version="2.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Gzip middleware for better performance
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Caching middleware for static assets
@app.middleware("http")
async def add_cache_control_header(request: Request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/static"):
        # Cache static assets for 1 year
        response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    elif request.url.path == "/":
        # Cache HTML for 1 hour
        response.headers["Cache-Control"] = "public, max-age=3600"
    return response


# Rate limiting state (in-memory)
# Format: {ip: [timestamp1, timestamp2, ...]}
_rate_limits = {}

def check_rate_limit(ip: str, limit: int = 3, window: int = 3600):
    """
    Stricter in-memory rate limiter (Default: 3 per hour).
    Returns True if allowed, raises HTTPException if limit exceeded.
    """
    now = datetime.now().timestamp()
    if ip not in _rate_limits:
        _rate_limits[ip] = [now]
        return True
    
    # Filter timestamps within the window
    _rate_limits[ip] = [t for t in _rate_limits[ip] if now - t < window]
    
    if len(_rate_limits[ip]) >= limit:
        log(f"[SECURITY] Rate limit exceeded for IP: {ip}")
        raise HTTPException(
            status_code=429, 
            detail="Rate limit exceeded. You can only send 3 submissions per hour. Please try again later."
        )
    
    _rate_limits[ip].append(now)
    return True


# Mount static files directory for downloads
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

# Logging function
def log(message: str):
    """Log messages with timestamp"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{timestamp}] {message}")
    
    # Also write to log file
    log_file = BASE_DIR / "server.log"
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {message}\n")


def send_client_confirmation_email(client_email: str, client_name: str, app_id: Optional[str] = None, receipt_path: Optional[Path] = None):
    """
    Send auto-reply confirmation email to client
    """
    if GMAIL_PASSWORD == "YOUR_APP_PASSWORD_HERE":
        log(f"  CLIENT EMAIL SKIPPED — Gmail App Password not configured")
        return
    
    def _send():
        try:
            # Premium brand colors
            INK = "#1A1714"
            GOLD = "#D4A853"
            PEARL = "#FDFCF9"
            GOLD_LT = "#E8C88A"

            # Build HTML confirmation email
            html_body = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <style>
                    body {{ font-family: 'Segoe UI', Arial, sans-serif; background-color: {PEARL}; margin:0; padding:20px; color: {INK}; }}
                    .wrapper {{ max-width: 600px; margin: auto; background: #FFF; border: 1px solid {GOLD}; border-radius: 4px; overflow: hidden; box-shadow: 0 10px 30px rgba(0,0,0,0.05); }}
                    .header {{ background: {INK}; padding: 40px 20px; text-align: center; border-bottom: 3px solid {GOLD}; }}
                    .header h1 {{ color: {GOLD}; margin: 0; font-size: 28px; letter-spacing: 4px; text-transform: uppercase; font-weight: 700; }}
                    .header p {{ color: {GOLD_LT}; margin: 8px 0 0; font-size: 11px; letter-spacing: 2px; text-transform: uppercase; opacity: 0.8; }}
                    .content {{ padding: 50px 40px; line-height: 1.8; }}
                    .content h2 {{ color: {INK}; font-size: 20px; margin-top: 0; letter-spacing: 0.5px; }}
                    .message {{ font-size: 15px; color: #444; margin-bottom: 25px; }}
                    .cta-box {{ background: {PEARL}; border: 1px solid rgba(212,168,83,0.15); padding: 25px; border-radius: 4px; margin: 30px 0; }}
                    .footer {{ background: #F9F9F9; padding: 30px; border-top: 1px solid #EEE; text-align: center; }}
                    .footer p {{ color: #999; font-size: 10px; margin: 5px 0; letter-spacing: 1px; text-transform: uppercase; }}
                    .sebi-tag {{ display: inline-block; padding: 4px 12px; border: 1px solid rgba(0,0,0,0.1); margin-top: 15px; font-size: 9px; color: #777; }}
                </style>
            </head>
            <body>
                <div class="wrapper">
                    <div class="header">
                        <h1>WhiteFlows</h1>
                        <p>A Legacy of 37 Years in Wealth Creation</p>
                    </div>
                    <div class="content">
                        <h2>Dear {client_name},</h2>
                        <div class="message">
                            <p>Thank you for choosing WhiteFlows International. We have successfully received your application and documents for review.</p>
                            <p>Our advisory team has been notified and will conduct a thorough assessment of your submission. You can expect a response within **1-2 business days**.</p>
                        </div>
                        <div class="cta-box">
                            <table width="100%" cellspacing="0" cellpadding="0">
                                <tr>
                                    <td style="color:{GOLD}; font-size:11px; font-weight:700; text-transform:uppercase; letter-spacing:1px; padding-bottom:10px;">Next Steps</td>
                                </tr>
                                <tr>
                                    <td style="color:#666; font-size:13px;">Our compliance desk will verify the uploaded KYC documents. Once approved, you will receive your personalized investment mandate.</td>
                                </tr>
                            </table>
                        </div>
                        <p style="margin-top:40px; font-size:14px; color:{INK};">
                            Best regards,<br/>
                            <strong style="color:{GOLD};">WhiteFlows Management</strong>
                        </p>
                    </div>
                    <div class="footer">
                        <p>© 2026 WHITEFLOWS INTERNATIONAL. ALL RIGHTS RESERVED.</p>
                        <div class="sebi-tag">SEBI REGISTERED INVESTMENT ADVISORY</div>
                    </div>
                </div>
            </body>
            </html>
            """
            
            # Build MIME message
            msg = MIMEMultipart()
            msg["Subject"] = "Application Received - WhiteFlows International"
            msg["From"] = GMAIL_SENDER
            msg["To"] = client_email
            msg["Reply-To"] = GMAIL_RECEIVER
            
            # Attach HTML body
            msg.attach(MIMEText(html_body, "html"))

            # Attach PDF Receipt if provided
            if receipt_path and receipt_path.exists():
                try:
                    with open(receipt_path, "rb") as attachment:
                        part = MIMEBase("application", "octet-stream")
                        part.set_payload(attachment.read())
                    
                    encoders.encode_base64(part)
                    part.add_header(
                        "Content-Disposition",
                        f"attachment; filename=WhiteFlows_Receipt_{app_id}.pdf"
                    )
                    msg.attach(part)
                    log(f"  [OK] PDF Receipt attached to client email ({app_id})")
                except Exception as e:
                    log(f"  [ERROR] Failed to attach PDF to client email: {e}")
            
            # Send via Gmail SMTP
            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
                smtp.login(GMAIL_SENDER, GMAIL_PASSWORD)
                smtp.sendmail(GMAIL_SENDER, client_email, msg.as_bytes())
            
            log(f"  [OK] CLIENT CONFIRMATION EMAIL SENT to {client_email}")
            
        except smtplib.SMTPAuthenticationError as e:
            log(f"  CLIENT EMAIL FAILED — SMTP Authentication Error: {e}")
            log(f"  -> Check Gmail App Password at: https://myaccount.google.com/apppasswords")
        except smtplib.SMTPException as e:
            log(f"  CLIENT EMAIL FAILED — SMTP Error: {e}")
        except Exception as ex:
            log(f"  CLIENT EMAIL FAILED — {type(ex).__name__}: {ex}")
    
    # Run in background
    log(f"  Sending confirmation email to client: {client_email}")
    t = threading.Thread(target=_send, daemon=True)
    t.start()


def create_pdf_receipt(record: dict, output_path: Path):
    """
    Generates a branded PDF receipt for the application
    """
    try:
        pdf = FPDF()
        pdf.add_page()
        
        # Colors (Ink & Gold)
        INK = (14, 13, 11)
        GOLD = (212, 168, 83)
        IVORY = (248, 247, 243)
        
        # Background
        pdf.set_fill_color(*IVORY)
        pdf.rect(0, 0, 210, 297, 'F')
        
        # Header Border
        pdf.set_draw_color(*GOLD)
        pdf.line(10, 10, 200, 10)
        pdf.line(10, 50, 200, 50)
        
        # Logo (if possible)
        logo_path = BASE_DIR / "static" / "images" / "asset_10.png"
        if logo_path.exists():
            pdf.image(str(logo_path), x=10, y=15, h=25)
        
        # Title
        pdf.set_font("Helvetica", "B", 24)
        pdf.set_text_color(*GOLD)
        pdf.cell(0, 40, "CERTIFICATE OF APPLICATION", ln=True, align="R")
        
        pdf.ln(20)
        
        # Main Body
        pdf.set_font("Helvetica", "", 12)
        pdf.set_text_color(*INK)
        
        pdf.cell(0, 10, f"Application ID: {record['app_id']}", ln=True)
        pdf.cell(0, 10, f"Date: {datetime.now().strftime('%d %B %Y, %H:%M')}", ln=True)
        pdf.ln(10)
        
        # Table of Details
        pdf.set_fill_color(255, 255, 255)
        pdf.set_draw_color(230, 230, 230)
        
        details = [
            ("Portfolio Choice", record.get("portfolio", "N/A")),
            ("Applicant Name", record.get("applicant_name", "N/A")),
            ("Email Address", record.get("email", "N/A")),
            ("Mobile Number", record.get("mobile", "N/A")),
            ("Nominee Name", record.get("nominee_name", "N/A")),
            ("Nominee PAN", record.get("nominee_pan", "N/A"))
        ]
        
        for label, val in details:
            pdf.set_font("Helvetica", "B", 10)
            pdf.set_text_color(120, 120, 120)
            pdf.cell(50, 12, label, border=1, fill=True)
            pdf.set_font("Helvetica", "", 10)
            pdf.set_text_color(*INK)
            pdf.cell(0, 12, str(val), border=1, ln=True, fill=True)
            
        pdf.ln(20)
        
        # Compliance Text
        pdf.set_font("Helvetica", "I", 9)
        pdf.set_text_color(150, 150, 150)
        pdf.multi_cell(0, 5, "This is a computer-generated confirmation of your application to WhiteFlows International. Our advisory desk will review your documents and verify your identity within 24 working hours. Your investment journey is backed by 13+ years of market mastery and SEBI-registered ethics.")
        
        # Footer
        pdf.set_y(-30)
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(*GOLD)
        pdf.cell(0, 10, "SAFE . SECURE . TRANSPARENT", ln=True, align="C")
        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(180, 180, 180)
        pdf.cell(0, 5, "WhiteFlows International | SEBI Reg: INA0000123456", ln=True, align="C")
        
        pdf.output(str(output_path))
        return True
    except Exception as e:
        log(f"  [ERROR] PDF Generation failed: {e}")
        return False


def send_email_with_docs(record, doc_dir):
    """
    Sends admin notification email with application details and attachments
    Enhanced error logging for better troubleshooting
    """
    if GMAIL_PASSWORD == "YOUR_APP_PASSWORD_HERE":
        log("  ADMIN EMAIL SKIPPED — Gmail App Password not configured in .env")
        log("  -> Set GMAIL_PASSWORD in your .env file")
        return
    
    def _send():
        try:
            r = record
            
            # Build HTML body for admin
            doc_items = ""
            for v in r["documents"].values():
                doc_items += f"""
                <tr style="border-bottom: 1px solid #F0F0F0;">
                    <td style="padding: 12px 0; color: #666; width: 40%; font-size: 13px;">{v['label']}</td>
                    <td style="padding: 12px 0; color: #1A1714; font-size: 13px; font-weight: 600;">{v['filename']}</td>
                </tr>"""
            if not doc_items:
                doc_items = "<tr><td colspan='2' style='color:#999; padding:20px; text-align:center;'>No documents uploaded</td></tr>"
            
            # Premium brand colors
            INK = "#1A1714"
            GOLD = "#D4A853"
            PEARL = "#FDFCF9"

            html_body = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <style>
                    body {{ font-family: 'Segoe UI', Arial, sans-serif; background-color: {PEARL}; margin:0; padding:20px; }}
                    .wrapper {{ max-width: 650px; margin: auto; background: #FFF; border: 1px solid {GOLD}; border-radius: 4px; overflow: hidden; }}
                    .header {{ background: {INK}; padding: 30px; text-align: center; }}
                    .header h1 {{ color: {GOLD}; margin: 0; font-size: 22px; letter-spacing: 3px; text-transform: uppercase; }}
                    .section {{ padding: 40px; }}
                    .section-h {{ font-size: 11px; font-weight: 800; text-transform: uppercase; letter-spacing: 2px; color: {GOLD}; margin-bottom: 20px; border-bottom: 1px solid rgba(212,168,83,0.2); padding-bottom: 8px; }}
                    .data-table {{ width: 100%; border-collapse: collapse; margin-bottom: 30px; }}
                    .data-table td {{ padding: 10px 0; border-bottom: 1px solid #F5F5F5; font-size: 14px; }}
                    .label {{ color: #999; width: 35%; }}
                    .val {{ color: {INK}; font-weight: 600; }}
                    .doc-box {{ background: #FAFAFA; border: 1px dashed {GOLD}; padding: 20px; border-radius: 4px; }}
                    .app-id {{ font-family: monospace; background: #EEE; padding: 2px 6px; border-radius: 3px; font-size: 13px; }}
                </style>
            </head>
            <body>
                <div class="wrapper">
                    <div class="header">
                        <h1>WhiteFlows <span style="font-weight:300; opacity:0.6;">Admin</span></h1>
                    </div>
                    <div class="section">
                        <div style="margin-bottom:30px;">
                            <h2 style="margin:0; font-size:24px; color:{INK};">New Application Received</h2>
                            <p style="margin:5px 0 0; color:#888;">ID: <span class="app-id">{r['app_id']}</span> | Portfolio: <strong style="color:{GOLD};">{r['portfolio']}</strong></p>
                        </div>

                        <div class="section-h">Applicant Details</div>
                        <table class="data-table">
                            <tr><td class="label">Primary Name</td><td class="val">{r['applicant_name']}</td></tr>
                            <tr><td class="label">Email Address</td><td class="val">{r['email']}</td></tr>
                            <tr><td class="label">Contact Number</td><td class="val">{r['mobile']}</td></tr>
                            <tr><td class="label">Submission Date</td><td class="val">{r['submitted_at']}</td></tr>
                        </table>

                        <div class="section-h">Nominee Information</div>
                        <table class="data-table">
                            <tr><td class="label">Full Name</td><td class="val">{r['nominee_name']}</td></tr>
                            <tr><td class="label">PAN Number</td><td class="val">{r['nominee_pan']}</td></tr>
                            <tr><td class="label">Date of Birth</td><td class="val">{r['nominee_dob']}</td></tr>
                            <tr><td class="label">Mobile</td><td class="val">{r['nominee_mobile']}</td></tr>
                        </table>

                        <div class="section-h">Verified Documents</div>
                        <div class="doc-box">
                            <table class="data-table" style="margin-bottom:0;">
                                {doc_items}
                            </table>
                        </div>
                    </div>
                </div>
            </body>
            </html>
            """
            
            # Build MIME message
            msg = MIMEMultipart()
            msg["Subject"] = f"NEW APPLICATION — {r['applicant_name']} — {r['portfolio']}"
            msg["From"] = GMAIL_SENDER
            msg["To"] = GMAIL_RECEIVER
            msg["Reply-To"] = r["email"]
            
            # Attach HTML body
            msg.attach(MIMEText(html_body, "html"))
            
            # Attach files
            attached = 0
            for doc_info in r["documents"].values():
                filepath = doc_dir / doc_info["filename"]
                if not filepath.exists():
                    log(f"  ⚠️  Attachment missing: {filepath}")
                    continue
                
                with open(filepath, "rb") as f:
                    part = MIMEBase("application", "octet-stream")
                    part.set_payload(f.read())
                encoders.encode_base64(part)
                part.add_header("Content-Disposition", f'attachment; filename="{doc_info["filename"]}"')
                msg.attach(part)
                attached += 1
            
            # Send via Gmail SMTP
            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
                smtp.login(GMAIL_SENDER, GMAIL_PASSWORD)
                smtp.sendmail(GMAIL_SENDER, GMAIL_RECEIVER, msg.as_bytes())
            
            log(f"  [OK] ADMIN EMAIL SENT to {GMAIL_RECEIVER} ({attached} attachment(s))")
            
        except smtplib.SMTPAuthenticationError as e:
            log(f"  [ERROR] ADMIN EMAIL FAILED — SMTP Authentication Error")
            log(f"     Error details: {e}")
            log(f"     -> Verify Gmail App Password at: https://myaccount.google.com/apppasswords")
            log(f"     -> Ensure 2-Step Verification is enabled on your Google Account")
        except smtplib.SMTPRecipientsRefused as e:
            log(f"  [ERROR] ADMIN EMAIL FAILED — Invalid recipient address")
            log(f"     Error details: {e}")
            log(f"     -> Check GMAIL_RECEIVER in .env file")
        except smtplib.SMTPException as e:
            log(f"  [ERROR] ADMIN EMAIL FAILED — SMTP Error: {type(e).__name__}")
            log(f"     Error details: {e}")
        except Exception as ex:
            log(f"  [ERROR] ADMIN EMAIL FAILED — {type(ex).__name__}: {ex}")
            log(f"     Full error: {str(ex)}")
    
    # Run in background
    log(f"  Starting admin email for {record['applicant_name']}...")
    t = threading.Thread(target=_send, daemon=True)
    t.start()


def send_lead_email(lead_data, lead_id, doc_dir=None):
    """
    Sends email notification for new consultation leads
    Optionally attaches uploaded documents from doc_dir
    """
    if GMAIL_PASSWORD == "YOUR_APP_PASSWORD_HERE":
        log("  LEAD EMAIL SKIPPED — Gmail App Password not configured")
        return

    def _send():
        try:
            # Build summary of lead data (skip internal / document fields)
            skip_keys = {'type', 'subject', 'body', 'documents'}
            lead_summary = ""
            for k, v in lead_data.items():
                if k in skip_keys:
                    continue
                label = k.replace('_', ' ').title()
                lead_summary += f"<tr><td style='color:#999;padding:12px 0;border-bottom:1px solid #F5F5F5;font-size:14px;width:35%;'>{label}:</td><td style='color:#1A1714;padding:12px 0;border-bottom:1px solid #F5F5F5;font-size:14px;font-weight:600;'>{v}</td></tr>"

            # Document attachment summary for email body
            doc_items = ""
            documents = lead_data.get('documents', {})
            if documents:
                for doc_key, doc_info in documents.items():
                    doc_items += f"<tr><td style='color:#999;padding:8px 0;font-size:13px;'>{doc_info.get('label', doc_key)}</td><td style='color:#1A1714;font-size:13px;font-weight:600;'>{doc_info.get('filename', 'N/A')}</td></tr>"

            # Premium brand colors
            INK = "#1A1714"
            GOLD = "#D4A853"
            PEARL = "#FDFCF9"

            docs_section = ""
            if doc_items:
                docs_section = f"""
                    <div style="margin-top:30px;">
                        <div style="font-size:11px;font-weight:800;text-transform:uppercase;letter-spacing:2px;color:{GOLD};margin-bottom:12px;border-bottom:1px solid rgba(212,168,83,0.2);padding-bottom:8px;">Attached Documents</div>
                        <div style="background:#FAFAFA;border:1px dashed {GOLD};padding:20px;border-radius:4px;">
                            <table style="width:100%;border-collapse:collapse;">{doc_items}</table>
                        </div>
                    </div>
                """

            html_body = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <style>
                    body {{ font-family: 'Segoe UI', Arial, sans-serif; background-color: {PEARL}; margin:0; padding:20px; }}
                    .wrapper {{ max-width: 600px; margin: auto; background: #FFF; border: 1px solid {GOLD}; border-radius: 4px; overflow: hidden; box-shadow: 0 5px 20px rgba(0,0,0,0.05); }}
                    .header {{ background: {INK}; padding: 30px; text-align: center; border-bottom: 2px solid {GOLD}; }}
                    .header h1 {{ color: {GOLD}; margin: 0; font-size: 20px; letter-spacing: 3px; text-transform: uppercase; }}
                    .content {{ padding: 40px; }}
                    .subject-box {{ background: {PEARL}; border-left: 4px solid {GOLD}; padding: 15px 20px; margin-bottom: 30px; }}
                    .subject-box h3 {{ margin: 0; font-size: 16px; color: {INK}; }}
                    .data-table {{ width: 100%; border-collapse: collapse; }}
                    .message-area {{ margin-top: 30px; padding: 20px; background: #F9F9F9; border-radius: 4px; color: #444; font-size: 14px; line-height: 1.6; }}
                </style>
            </head>
            <body>
                <div class="wrapper">
                    <div class="header">
                        <h1>New Strategic Lead</h1>
                    </div>
                    <div class="content">
                        <div class="subject-box">
                            <p style="margin:0 0 5px; font-size:11px; color:{GOLD}; font-weight:800; text-transform:uppercase;">Inquiry Type: {lead_data.get('type', 'General')}</p>
                            <h3>{lead_data.get('subject', 'Consultation Request')}</h3>
                        </div>
                        
                        <table class="data-table">
                            {lead_summary}
                        </table>

                        {docs_section}

                        {f'<div class="message-area"><strong>Notes:</strong><br/>{lead_data.get("body", "")}</div>' if lead_data.get('body') else ''}
                        
                        <div style="margin-top:30px; padding-top:20px; border-top:1px solid #EEE; text-align:center;">
                            <p style="color:#AAA; font-size:10px; letter-spacing:1px; text-transform:uppercase;">Sent via WhiteFlows Strategic Gateway</p>
                        </div>
                    </div>
                </div>
            </body>
            </html>
            """

            # Build MIME message
            msg = MIMEMultipart()
            name = lead_data.get('first_name', lead_data.get('name', 'New Client'))
            msg["Subject"] = f"NEW LEAD — {name} — {lead_data.get('type', 'Consultation')}"
            msg["From"] = GMAIL_SENDER
            msg["To"] = GMAIL_RECEIVER
            
            email_addr = lead_data.get('email', '')
            if email_addr:
                msg["Reply-To"] = email_addr

            msg.attach(MIMEText(html_body, "html"))

            # Attach document files if doc_dir is provided
            attached = 0
            if doc_dir and documents:
                for doc_key, doc_info in documents.items():
                    filepath = doc_dir / doc_info.get("filename", "")
                    if not filepath.exists():
                        log(f"  ⚠️  Lead attachment missing: {filepath}")
                        continue
                    with open(filepath, "rb") as f:
                        part = MIMEBase("application", "octet-stream")
                        part.set_payload(f.read())
                    encoders.encode_base64(part)
                    part.add_header("Content-Disposition", f'attachment; filename="{doc_info["filename"]}"')
                    msg.attach(part)
                    attached += 1

            # Send
            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
                smtp.login(GMAIL_SENDER, GMAIL_PASSWORD)
                smtp.sendmail(GMAIL_SENDER, GMAIL_RECEIVER, msg.as_bytes())

            log(f"  [OK] LEAD EMAIL SENT to {GMAIL_RECEIVER} ({attached} attachment(s))")

        except Exception as ex:
            log(f"  [ERROR] LEAD EMAIL FAILED — {type(ex).__name__}: {ex}")

    # Run in background
    t = threading.Thread(target=_send, daemon=True)
    t.start()


import zipfile
import shutil

@app.get("/", response_class=HTMLResponse)
async def serve_homepage():
    """Serve the main HTML file"""
    html_file = BASE_DIR / "index.html"
    if not html_file.exists():
        raise HTTPException(status_code=404, detail="HTML file not found")
    return FileResponse(html_file, headers={"Cache-Control": "public, max-age=3600"})


@app.post("/api/submit")
@app.post("/submit")
async def submit_application(request: Request):
    """Handle application form submission"""
    client_ip = request.client.host
    check_rate_limit(client_ip)
    
    try:
        data = await request.json()
        
        # Generate application ID
        app_id = datetime.now().strftime('%Y%m%d%H%M%S')
        
        # Create application directory
        app_dir = APPLICATIONS_DIR / app_id
        app_dir.mkdir(parents=True, exist_ok=True)
        
        # Process documents
        documents = data.get('documents', {})
        processed_docs = {}
        
        for doc_key, doc_data in documents.items():
            if doc_data:
                # Save base64 document
                import base64
                file_data = doc_data['data'].split(',')[1] if ',' in doc_data['data'] else doc_data['data']
                file_bytes = base64.b64decode(file_data)
                
                ext = doc_data.get('type', 'pdf')
                if '/' in ext:
                    ext = ext.split('/')[-1]
                
                filename = f"{doc_key}_{app_id}.{ext}"
                filepath = app_dir / filename
                
                with open(filepath, 'wb') as f:
                    f.write(file_bytes)
                
                processed_docs[doc_key] = {
                    'label': doc_data.get('label', doc_key),
                    'filename': filename,
                    'size_kb': round(len(file_bytes) / 1024, 2)
                }
        
        # Create record
        record = {
            'app_id': app_id,
            'portfolio': data.get('portfolio', 'Unknown'),
            'applicant_name': data.get('applicant_name', ''),
            'email': data.get('email', ''),
            'mobile': data.get('mobile', ''),
            'nominee_name': data.get('nominee_name', ''),
            'nominee_pan': data.get('nominee_pan', ''),
            'nominee_dob': data.get('nominee_dob', ''),
            'nominee_mobile': data.get('nominee_mobile', ''),
            'submitted_at': data.get('submitted_at', datetime.now().isoformat()),
            'documents': processed_docs
        }
        
        # Save JSON record
        json_file = app_dir / "application.json"
        with open(json_file, 'w') as f:
            json.dump(record, f, indent=2)
        
        # Generate PDF Receipt
        receipt_filename = f"Receipt_{app_id}.pdf"
        receipt_path = app_dir / receipt_filename
        receipt_ok = create_pdf_receipt(record, receipt_path)
        
        log(f"[OK] Application {app_id} saved: {record['applicant_name']}")
        
        # Send emails (both admin and client)
        send_email_with_docs(record, app_dir)
        send_client_confirmation_email(record['email'], record['applicant_name'], app_id, receipt_path if receipt_ok else None)
        
        return JSONResponse({
            "success": True,
            "message": "Application submitted successfully",
            "app_id": app_id
        })
        
    except Exception as e:
        log(f"[ERROR] Error processing application: {e}")
        log(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/submit-lead")
@app.post("/submit-lead")
async def submit_lead(request: Request):
    """Handle consultation form submission (with optional document uploads)"""
    client_ip = request.client.host
    check_rate_limit(client_ip)
    
    try:
        import base64
        data = await request.json()
        
        # Create leads directory if not exists
        leads_dir = BASE_DIR / "leads"
        leads_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate lead ID
        lead_id = datetime.now().strftime('%Y%m%d%H%M%S')
        
        # Create a dedicated folder for this lead (for storing documents)
        lead_dir = leads_dir / lead_id
        lead_dir.mkdir(parents=True, exist_ok=True)
        
        # Process uploaded documents (base64-encoded, same format as /submit)
        raw_documents = data.pop('documents', {})
        processed_docs = {}
        
        for doc_key, doc_data in raw_documents.items():
            if doc_data and isinstance(doc_data, dict) and doc_data.get('data'):
                try:
                    file_data_str = doc_data['data']
                    # Strip base64 data-URI prefix if present
                    if ',' in file_data_str:
                        file_data_str = file_data_str.split(',')[1]
                    file_bytes = base64.b64decode(file_data_str)
                    
                    ext = doc_data.get('type', 'pdf')
                    if '/' in ext:
                        ext = ext.split('/')[-1]
                    
                    filename = f"{doc_key}_{lead_id}.{ext}"
                    filepath = lead_dir / filename
                    
                    with open(filepath, 'wb') as f:
                        f.write(file_bytes)
                    
                    processed_docs[doc_key] = {
                        'label': doc_data.get('label', doc_key.replace('_', ' ').title()),
                        'filename': filename,
                        'size_kb': round(len(file_bytes) / 1024, 2)
                    }
                    log(f"  [OK] Document saved: {filename} ({processed_docs[doc_key]['size_kb']} KB)")
                except Exception as doc_err:
                    log(f"  [WARN] Failed to save document '{doc_key}': {doc_err}")
        
        # Add processed docs back into data for the JSON record
        if processed_docs:
            data['documents'] = processed_docs
        
        # Save lead JSON record
        lead_file = lead_dir / "lead.json"
        with open(lead_file, 'w') as f:
            json.dump(data, f, indent=2)
        
        doc_count = len(processed_docs)
        log(f"[OK] Lead {lead_id} saved: {data.get('name', 'Unknown')} ({doc_count} document(s))")
        
        # Send email notification (with document directory for attachments)
        send_lead_email(data, lead_id, doc_dir=lead_dir if processed_docs else None)
        
        return JSONResponse({
            "success": True,
            "message": "Consultation request received",
            "lead_id": lead_id
        })
        
    except Exception as e:
        log(f"[ERROR] Error processing lead: {e}")
        log(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/applications")
@app.get("/applications")
async def list_applications():
    """List all applications (admin view)"""
    try:
        applications = []
        for app_dir in APPLICATIONS_DIR.iterdir():
            if app_dir.is_dir():
                json_file = app_dir / "application.json"
                if json_file.exists():
                    with open(json_file, 'r') as f:
                        applications.append(json.load(f))
        
        applications.sort(key=lambda x: x['app_id'], reverse=True)
        return JSONResponse(applications)
        
    except Exception as e:
        log(f"✗ Error listing applications: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/download-zip")
@app.get("/download-zip")
async def download_optimized_zip():
    """Create and serve a downloadable ZIP of the optimized WhiteFlows project"""
    zip_path = BASE_DIR / "static" / "WhiteFlows_Optimized.zip"
    
    # Build the ZIP with essential project files
    exclude_dirs = {'.venv', '__pycache__', '.idea', '.git', 'node_modules', 'applications', 'leads'}
    exclude_files = {'server.log', 'WhiteFlows_UPDATED_v2.zip', 'WhiteFlows_Optimized.zip'}
    
    with zipfile.ZipFile(str(zip_path), 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(str(BASE_DIR)):
            # Skip excluded directories
            dirs[:] = [d for d in dirs if d not in exclude_dirs and not d.startswith('.')]
            rel_root = os.path.relpath(root, str(BASE_DIR))
            
            for file in files:
                if file in exclude_files:
                    continue
                filepath = os.path.join(root, file)
                arcname = os.path.join("WhiteFlows_Optimized", rel_root, file) if rel_root != '.' else os.path.join("WhiteFlows_Optimized", file)
                zf.write(filepath, arcname)
    
    return FileResponse(
        str(zip_path),
        media_type="application/zip",
        filename="WhiteFlows_Optimized.zip",
        headers={"Content-Disposition": "attachment; filename=WhiteFlows_Optimized.zip"}
    )


@app.get("/WhiteFlows_UPDATED_v2.zip")
async def download_updated_zip():
    """Download the updated WhiteFlows v2.0 ZIP file"""
    zip_file = BASE_DIR / "WhiteFlows_UPDATED_v2.zip"
    if not zip_file.exists():
        raise HTTPException(status_code=404, detail="ZIP file not found")
    return FileResponse(
        zip_file,
        media_type="application/zip",
        filename="WhiteFlows_UPDATED_v2.zip"
    )


if __name__ == "__main__":
    import uvicorn
    
    log("=" * 60)
    log("WhiteFlows Server (FastAPI Edition) Starting...")
    log("=" * 60)
    log(f"Gmail Sender: {GMAIL_SENDER}")
    log(f"Gmail Receiver: {GMAIL_RECEIVER}")
    log(f"Password Configured: {'Yes' if GMAIL_PASSWORD != 'YOUR_APP_PASSWORD_HERE' else 'No (using placeholder)'}")
    log("=" * 60)
    
    uvicorn.run(app, host="0.0.0.0", port=8001, log_level="info")
