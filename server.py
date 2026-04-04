"""
WhiteFlows Application Server - Cloudflare Workers Edition
Fully stateless: no file writes, no threading. 
Generates PDFs in memory and sends them directly via email.
"""

import os
import io
import json
import time
from typing import Optional
import smtplib
from pathlib import Path
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from email.mime.application import MIMEApplication
from fpdf import FPDF

import traceback
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
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

# Setup paths (for static assets only - no file writing)
BASE_DIR = Path(__file__).parent

# FastAPI app instance
app = FastAPI(title="WhiteFlows", version="3.0-cloudflare")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Gzip middleware
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Cache headers middleware
@app.middleware("http")
async def add_cache_control_header(request: Request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/static"):
        response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    elif request.url.path == "/":
        response.headers["Cache-Control"] = "public, max-age=3600"
    return response


# In-memory rate limiting
_rate_limits = {}

def check_rate_limit(ip: str, limit: int = 10, window: int = 3600):
    now = time.time()
    if ip not in _rate_limits:
        _rate_limits[ip] = [now]
        return True
    _rate_limits[ip] = [t for t in _rate_limits[ip] if now - t < window]
    if len(_rate_limits[ip]) >= limit:
        log(f"[SECURITY] Rate limit exceeded for IP: {ip}")
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded. You can only send 10 submissions per hour. Please try again later."
        )
    _rate_limits[ip].append(now)
    return True


# Mount static files
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


def log(message: str):
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{timestamp}] {message}")


def create_pdf_in_memory(record: dict) -> bytes:
    """
    Generates a branded PDF receipt entirely in memory.
    Returns raw PDF bytes — no file is saved to disk.
    """
    try:
        pdf = FPDF()
        pdf.add_page()

        # Colors
        INK = (14, 13, 11)
        GOLD = (212, 168, 83)
        IVORY = (248, 247, 243)

        # Background
        pdf.set_fill_color(*IVORY)
        pdf.rect(0, 0, 210, 297, 'F')

        # Header borders
        pdf.set_draw_color(*GOLD)
        pdf.line(10, 10, 200, 10)
        pdf.line(10, 50, 200, 50)

        # Logo
        logo_path = BASE_DIR / "static" / "images" / "asset_10.png"
        if logo_path.exists():
            pdf.image(str(logo_path), x=10, y=15, h=25)

        # Title
        pdf.set_font("Helvetica", "B", 24)
        pdf.set_text_color(*GOLD)
        pdf.cell(0, 40, "CERTIFICATE OF APPLICATION", ln=True, align="R")

        pdf.ln(20)

        # Details table
        pdf.set_font("Helvetica", "", 12)
        pdf.set_text_color(*INK)
        pdf.cell(0, 10, f"Application ID: {record.get('app_id', 'N/A')}", ln=True)
        pdf.cell(0, 10, f"Date: {datetime.now().strftime('%d %B %Y, %H:%M')}", ln=True)
        pdf.ln(10)

        details = [
            ("Portfolio Choice", record.get("portfolio", "N/A")),
            ("Applicant Name", record.get("applicant_name", "N/A")),
            ("Email Address", record.get("email", "N/A")),
            ("Mobile Number", record.get("mobile", "N/A")),
            ("Nominee Name", record.get("nominee_name", "N/A")),
            ("Nominee PAN", record.get("nominee_pan", "N/A"))
        ]

        pdf.set_fill_color(255, 255, 255)
        pdf.set_draw_color(230, 230, 230)
        for label, val in details:
            pdf.set_font("Helvetica", "B", 10)
            pdf.set_text_color(120, 120, 120)
            pdf.cell(50, 12, label, border=1, fill=True)
            pdf.set_font("Helvetica", "", 10)
            pdf.set_text_color(*INK)
            pdf.cell(0, 12, str(val), border=1, ln=True, fill=True)

        pdf.ln(20)

        # Compliance footer
        pdf.set_font("Helvetica", "I", 9)
        pdf.set_text_color(150, 150, 150)
        pdf.multi_cell(0, 5,
            "This is a computer-generated confirmation of your application to WhiteFlows International. "
            "Our advisory desk will review your documents and verify your identity within 24 working hours. "
            "SEBI Registered Investment Advisory."
        )

        # Footer line
        pdf.line(10, 280, 200, 280)
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_text_color(*GOLD)
        pdf.set_y(282)
        pdf.cell(0, 5, "WHITEFLOWS INTERNATIONAL — SEBI REGISTERED INVESTMENT ADVISORY", align="C")

        # Return PDF as bytes — key change: dest='S' keeps it in memory
        pdf_bytes = pdf.output(dest='S')
        if isinstance(pdf_bytes, str):
            return pdf_bytes.encode('latin-1')
        return bytes(pdf_bytes)

    except Exception as ex:
        log(f"[ERROR] PDF generation failed: {ex}")
        return b""


async def send_admin_email(record: dict, pdf_bytes: bytes, uploaded_docs: dict):
    """
    Send application notification to admin with PDF receipt and uploaded documents.
    Everything stays in memory — no files are written to disk.
    """
    if GMAIL_PASSWORD == "your-app-password":
        log("  ADMIN EMAIL SKIPPED — Gmail not configured")
        return

    try:
        app_id = record.get("app_id", "UNKNOWN")
        msg = MIMEMultipart()
        msg["Subject"] = f"NEW APPLICATION — {record.get('applicant_name', 'Unknown')} [{app_id}]"
        msg["From"] = GMAIL_SENDER
        msg["To"] = GMAIL_RECEIVER

        # HTML body for admin
        html = f"""
        <div style="font-family:Arial,sans-serif;max-width:600px;margin:auto;">
            <h2 style="color:#D4A853;">New WhiteFlows Application Received</h2>
            <table style="border-collapse:collapse;width:100%;">
                <tr><td style="padding:8px;border:1px solid #eee;font-weight:bold;">App ID</td><td style="padding:8px;border:1px solid #eee;">{app_id}</td></tr>
                <tr><td style="padding:8px;border:1px solid #eee;font-weight:bold;">Applicant</td><td style="padding:8px;border:1px solid #eee;">{record.get("applicant_name","")}</td></tr>
                <tr><td style="padding:8px;border:1px solid #eee;font-weight:bold;">Email</td><td style="padding:8px;border:1px solid #eee;">{record.get("email","")}</td></tr>
                <tr><td style="padding:8px;border:1px solid #eee;font-weight:bold;">Mobile</td><td style="padding:8px;border:1px solid #eee;">{record.get("mobile","")}</td></tr>
                <tr><td style="padding:8px;border:1px solid #eee;font-weight:bold;">Portfolio</td><td style="padding:8px;border:1px solid #eee;">{record.get("portfolio","")}</td></tr>
                <tr><td style="padding:8px;border:1px solid #eee;font-weight:bold;">Nominee</td><td style="padding:8px;border:1px solid #eee;">{record.get("nominee_name","")} (PAN: {record.get("nominee_pan","")})</td></tr>
                <tr><td style="padding:8px;border:1px solid #eee;font-weight:bold;">Timestamp</td><td style="padding:8px;border:1px solid #eee;">{datetime.now().strftime('%d %B %Y, %H:%M:%S')}</td></tr>
            </table>
        </div>
        """
        msg.attach(MIMEText(html, "html"))

        # Attach PDF receipt
        if pdf_bytes:
            part = MIMEApplication(pdf_bytes, _subtype="pdf")
            part.add_header("Content-Disposition", "attachment", filename=f"Receipt_{app_id}.pdf")
            msg.attach(part)

        # Attach uploaded documents (in memory)
        for filename, file_bytes in uploaded_docs.items():
            if file_bytes:
                doc_part = MIMEApplication(file_bytes)
                doc_part.add_header("Content-Disposition", "attachment", filename=filename)
                msg.attach(doc_part)

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(GMAIL_SENDER, GMAIL_PASSWORD)
            smtp.sendmail(GMAIL_SENDER, GMAIL_RECEIVER, msg.as_bytes())

        log(f"  [OK] ADMIN EMAIL SENT — {app_id}")

    except Exception as ex:
        log(f"  [ERROR] Admin email failed: {type(ex).__name__}: {ex}")
        raise


async def send_client_email(client_email: str, client_name: str, app_id: str, pdf_bytes: bytes):
    """
    Send confirmation email to client with their PDF receipt.
    Everything in memory.
    """
    if not client_email or GMAIL_PASSWORD == "your-app-password":
        log("  CLIENT EMAIL SKIPPED — Config or email missing")
        return

    try:
        INK = "#1A1714"
        GOLD = "#D4A853"
        PEARL = "#FDFCF9"

        html = f"""
        <!DOCTYPE html>
        <html>
        <head><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
        <body style="font-family:Arial,sans-serif;background:{PEARL};margin:0;padding:20px;color:{INK};">
            <div style="max-width:600px;margin:auto;background:#fff;border:1px solid {GOLD};border-radius:4px;overflow:hidden;">
                <div style="background:{INK};padding:40px 20px;text-align:center;border-bottom:3px solid {GOLD};">
                    <h1 style="color:{GOLD};margin:0;font-size:28px;letter-spacing:4px;text-transform:uppercase;">WhiteFlows</h1>
                    <p style="color:#E8C88A;margin:8px 0 0;font-size:11px;letter-spacing:2px;text-transform:uppercase;">A Legacy of 37 Years in Wealth Creation</p>
                </div>
                <div style="padding:50px 40px;line-height:1.8;">
                    <h2 style="color:{INK};font-size:20px;margin-top:0;">Dear {client_name},</h2>
                    <p style="font-size:15px;color:#444;">Thank you for choosing WhiteFlows International. We have successfully received your application and documents for review.</p>
                    <p style="font-size:15px;color:#444;">Our advisory team has been notified and will conduct a thorough assessment of your submission. You can expect a response within <strong>1-2 business days</strong>.</p>
                    <div style="background:{PEARL};border:1px solid rgba(212,168,83,0.15);padding:25px;border-radius:4px;margin:30px 0;">
                        <p style="color:{GOLD};font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:1px;margin:0 0 10px;">Next Steps</p>
                        <p style="color:#666;font-size:13px;margin:0;">Our compliance desk will verify the uploaded KYC documents. Once approved, you will receive your personalized investment mandate.</p>
                    </div>
                    <p style="margin-top:40px;font-size:14px;color:{INK};">
                        Best regards,<br/>
                        <strong style="color:{GOLD};">WhiteFlows Management</strong>
                    </p>
                </div>
                <div style="background:#f9f9f9;padding:30px;border-top:1px solid #eee;text-align:center;">
                    <p style="color:#999;font-size:10px;margin:5px 0;letter-spacing:1px;text-transform:uppercase;">© 2026 WhiteFlows International. All Rights Reserved.</p>
                    <span style="display:inline-block;padding:4px 12px;border:1px solid rgba(0,0,0,0.1);font-size:9px;color:#777;">SEBI REGISTERED INVESTMENT ADVISORY</span>
                </div>
            </div>
        </body>
        </html>
        """

        msg = MIMEMultipart()
        msg["Subject"] = "Application Received — WhiteFlows International"
        msg["From"] = GMAIL_SENDER
        msg["To"] = client_email
        msg["Reply-To"] = GMAIL_RECEIVER
        msg.attach(MIMEText(html, "html"))

        if pdf_bytes:
            part = MIMEApplication(pdf_bytes, _subtype="pdf")
            part.add_header("Content-Disposition", "attachment", filename=f"WhiteFlows_Receipt_{app_id}.pdf")
            msg.attach(part)

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(GMAIL_SENDER, GMAIL_PASSWORD)
            smtp.sendmail(GMAIL_SENDER, client_email, msg.as_bytes())

        log(f"  [OK] CLIENT EMAIL SENT to {client_email}")

    except Exception as ex:
        log(f"  [ERROR] Client email failed: {type(ex).__name__}: {ex}")


import base64
import re

# ... (rest of imports remain the same)

# ─── Utility: Decode Base64 Data URL ──────────────────────────────────────────

def decode_base64_data_url(data_url: str) -> bytes:
    """
    Decodes a standard base64 data URL (e.g. data:image/png;base64,iVBORw0...)
    Returns the raw bytes.
    """
    try:
        if not data_url or "," not in data_url:
            return b""
        
        # Split on the first comma
        header, encoded = data_url.split(",", 1)
        return base64.b64decode(encoded)
    except Exception as ex:
        log(f"[ERROR] Failed to decode base64: {ex}")
        return b""

import mimetypes

# ─── Utility: Get Safe Filename with Extension ──────────────────────────────

def get_safe_filename(doc_info: dict, default_key: str) -> str:
    """
    Ensures the filename has a valid extension based on:
    1. originalName field (sent by some forms)
    2. name field
    3. label field
    4. MIME type (if no extension found)
    """
    raw_name = doc_info.get("originalName") or doc_info.get("name") or doc_info.get("label") or f"{default_key}"
    
    # Check if name already has a reasonable extension
    if "." in raw_name and len(raw_name.split(".")[-1]) in [3, 4]:
        return raw_name
        
    # Attempt to guess extension from MIME type
    mime_type = doc_info.get("type", "")
    ext = mimetypes.guess_extension(mime_type)
    
    # Fallbacks for common types if guess fail
    if not ext:
        if "pdf" in mime_type.lower(): ext = ".pdf"
        elif "png" in mime_type.lower(): ext = ".png"
        elif "jpg" in mime_type.lower() or "jpeg" in mime_type.lower(): ext = ".jpg"
        else: ext = ".pdf" # Default fallback for this financial app
        
    return f"{raw_name}{ext}"

# ─── Routes ─────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def serve_index():
    index_path = BASE_DIR / "index.html"
    if index_path.exists():
        return HTMLResponse(content=index_path.read_text(encoding="utf-8"))
    return HTMLResponse(content="<h1>WhiteFlows</h1>", status_code=200)


@app.get("/health")
async def health():
    return {"status": "ok", "version": "3.2-extended-filenames", "timestamp": datetime.now().isoformat()}


@app.post("/submit")
async def submit_application(request: Request):
    """
    Handles full application form submission (JSON + Base64 Docs).
    Synchronized with index.html submitRegForm.
    """
    try:
        # Rate limiting
        client_ip = request.headers.get("CF-Connecting-IP") or request.headers.get("X-Forwarded-For", "unknown")
        check_rate_limit(client_ip)

        # Parse JSON payload
        data = await request.json()

        # Extract text fields
        record = {
            "app_id": f"WF-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            "portfolio": data.get("portfolio", ""),
            "applicant_name": data.get("applicant_name", ""),
            "email": data.get("email", ""),
            "mobile": data.get("mobile", ""),
            "nominee_name": data.get("nominee_name", ""),
            "nominee_pan": data.get("nominee_pan", ""),
        }

        log(f"[APPLICATION] New submission — {record['app_id']} from {record['applicant_name']}")

        # Collect uploaded documents from base64 Data URLs
        uploaded_docs = {}
        docs_payload = data.get("documents", {})
        
        for key, doc_info in docs_payload.items():
            if isinstance(doc_info, dict) and "data" in doc_info:
                filename = get_safe_filename(doc_info, key)
                file_bytes = decode_base64_data_url(doc_info["data"])
                if file_bytes:
                    uploaded_docs[filename] = file_bytes
                    log(f"  [DECODE] {key}: {filename} ({len(file_bytes)} bytes)")

        # Generate PDF receipt in memory
        pdf_bytes = create_pdf_in_memory(record)
        log(f"  [PDF] Generated in memory ({len(pdf_bytes)} bytes)")

        # Send emails
        await send_admin_email(record, pdf_bytes, uploaded_docs)
        await send_client_email(record["email"], record["applicant_name"], record["app_id"], pdf_bytes)

        return JSONResponse({
            "success": True,
            "app_id": record["app_id"],
            "message": "Application submitted successfully. Check your email for confirmation."
        })

    except HTTPException:
        raise
    except Exception as ex:
        log(f"[ERROR] submit_application: {traceback.format_exc()}")
        return JSONResponse(
            {"success": False, "message": f"Server error: {str(ex)}"},
            status_code=500
        )


@app.post("/submit-lead")
async def submit_lead(request: Request):
    """
    Handles enquiry/lead form submission (JSON).
    Synchronized with index.html doSendEmail / submitRetail / submitProject.
    Fixes the raw JSON/Base64 display by attaching files correctly.
    Ensures every file has a proper extension.
    """
    try:
        # Rate limiting
        client_ip = request.headers.get("CF-Connecting-IP") or request.headers.get("X-Forwarded-For", "unknown")
        check_rate_limit(client_ip)

        # Parse JSON
        data = await request.json()
        
        log(f"[LEAD] New enquiry from {data.get('name', 'Unknown')} ({data.get('email', 'N/A')})")

        # Separate text fields from documents
        clean_data = {}
        attachments = {}
        
        # 1. Unpack nested "documents" key if present (used in Scale-Up form)
        docs_payload = data.get("documents", {})
        if isinstance(docs_payload, dict):
            for doc_key, doc_info in docs_payload.items():
                if isinstance(doc_info, dict) and "data" in doc_info:
                    filename = get_safe_filename(doc_info, doc_key)
                    file_bytes = decode_base64_data_url(doc_info["data"])
                    if file_bytes:
                        attachments[filename] = file_bytes
                        log(f"  [DECODE-NESTED-LEAD] {doc_key}: {filename} ({len(file_bytes)} bytes)")

        # 2. Iterate through the rest of the data (legacy or flat support)
        for k, v in data.items():
            if k == 'documents':
                continue # Already handled above
                
            # Check if this value is a standalone document object
            if isinstance(v, dict) and "data" in v and str(v.get("data", "")).startswith("data:"):
                filename = get_safe_filename(v, k)
                file_bytes = decode_base64_data_url(v["data"])
                if file_bytes:
                    attachments[filename] = file_bytes
                    log(f"  [DECODE-FLAT-LEAD] {k}: {filename} ({len(file_bytes)} bytes)")
            else:
                # Regular field
                clean_data[k] = v

        # Send simplified lead notification to admin
        if GMAIL_PASSWORD != "your-app-password":


            try:
                msg = MIMEMultipart()
                msg["Subject"] = f"NEW ENQUIRY — {clean_data.get('subject', 'Consultation Lead')}"
                msg["From"] = GMAIL_SENDER
                msg["To"] = GMAIL_RECEIVER

                # Build HTML table for text data only
                rows = ""
                for k, v in clean_data.items():
                    if k != 'body' and k != 'subject':
                        rows += f"<tr><td style='padding:8px;border:1px solid #eee;font-weight:bold;text-transform:capitalize;'>{k.replace('_',' ')}</td><td style='padding:8px;border:1px solid #eee;'>{v}</td></tr>"

                html = f"""
                <div style="font-family:Arial,sans-serif;max-width:600px;margin:auto;border:1px solid #D4A853;border-radius:4px;overflow:hidden;">
                    <div style="background:#0E0D0B;padding:20px;text-align:center;border-bottom:3px solid #D4A853;">
                        <h2 style="color:#D4A853;margin:0;font-size:18px;letter-spacing:2px;text-transform:uppercase;">WhiteFlows Lead Management</h2>
                    </div>
                    <div style="padding:30px;">
                        <table style="border-collapse:collapse;width:100%;margin-bottom:20px;font-size:14px;">
                            {rows}
                        </table>
                        <div style="margin-top:20px;padding:20px;background:#f9f9f9;border-left:4px solid #D4A853;border-radius:2px;">
                            <strong style="color:#D4A853;font-size:11px;text-transform:uppercase;letter-spacing:1px;">Client Message:</strong><br/>
                            <p style="margin-top:10px;line-height:1.6;color:#333;">{clean_data.get('body', 'No message body provided.')}</p>
                        </div>
                    </div>
                </div>
                """
                msg.attach(MIMEText(html, "html"))

                # Attach decoded documents
                for filename, file_bytes in attachments.items():
                    part = MIMEApplication(file_bytes)
                    part.add_header("Content-Disposition", "attachment", filename=filename)
                    msg.attach(part)

                with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
                    smtp.login(GMAIL_SENDER, GMAIL_PASSWORD)
                    smtp.sendmail(GMAIL_SENDER, GMAIL_RECEIVER, msg.as_bytes())

                log(f"  [OK] LEAD EMAIL SENT WITH {len(attachments)} ATTACHMENTS")
            except Exception as e:
                log(f"  [ERROR] Lead email failed: {e}")
        else:
            log("  LEAD EMAIL SKIPPED — Gmail not configured")

        return JSONResponse({
            "success": True,
            "message": "Enquiry received. Our team will contact you shortly."
        })

    except HTTPException:
        raise
    except Exception as ex:
        log(f"[ERROR] submit_lead: {str(ex)}")
        return JSONResponse(
            {"success": False, "message": f"Server error: {str(ex)}"},
            status_code=500
        )


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8001))
    uvicorn.run(app, host="0.0.0.0", port=port)


