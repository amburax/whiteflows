"""
WhiteFlows Application Server
Stateless: no file writes, no threading.
PDF is generated in the browser (jsPDF) and sent as base64.
The server only handles email sending.
"""

import os
import io
import time
import base64
import re
import hashlib
import traceback
import mimetypes
import aiosqlite
import jwt
import sqlite3
import json
import socket
import csv
from typing import Optional
import smtplib
from pathlib import Path
from datetime import datetime
import asyncio
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication

import uvicorn
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware
from dotenv import load_dotenv
import httpx

# Load environment variables
load_dotenv()

# Configuration
# Brevo API / SMTP Config
GMAIL_SENDER   = os.environ.get('GMAIL_SENDER',   'your-email@gmail.com')
GMAIL_PASSWORD = os.environ.get('GMAIL_PASSWORD', 'your-app-password')
GMAIL_RECEIVER = os.environ.get('GMAIL_RECEIVER', 'recipient-email@gmail.com')
BREVO_API_KEY  = os.environ.get('BREVO_API_KEY', '')
BREVO_SMTP_KEY = os.environ.get('BREVO_SMTP_KEY', '')
BREVO_LOGIN    = os.environ.get('BREVO_LOGIN', 'a72c85001@smtp-brevo.com')
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'whiteflows2026')
BACKUP_RECEIVER_EMAIL = os.environ.get('BACKUP_RECEIVER_EMAIL', '')

# Setup paths (for static assets only — no file writing)
BASE_DIR = Path(__file__).parent
DATABASE_PATH = str(BASE_DIR / "whiteflows.db")


async def init_db():
    """Initialises the local SQLite database."""
    try:
        async with aiosqlite.connect(DATABASE_PATH) as conn:
            async with conn.cursor() as curr:
                # Leads Table
                await curr.execute('''
                    CREATE TABLE IF NOT EXISTS leads (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT,
                        email TEXT,
                        mobile TEXT,
                        json_data TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                # Applications Table
                await curr.execute('''
                    CREATE TABLE IF NOT EXISTS applications (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        app_id TEXT UNIQUE,
                        applicant_name TEXT,
                        email TEXT,
                        mobile TEXT,
                        json_data TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                # Metadata Table
                await curr.execute("CREATE TABLE IF NOT EXISTS server_metadata (key TEXT PRIMARY KEY, value TEXT)")
                
            await conn.commit()
        log(f"[DB] Initialised: {DATABASE_PATH}")
    except Exception as e:
        log(f"[ERROR] init_db failed: {e}")


async def save_lead(name, email, mobile, full_json):
    """Saves a lead to the SQLite database."""
    try:
        async with aiosqlite.connect(DATABASE_PATH) as conn:
            async with conn.cursor() as curr:
                await curr.execute(
                    "INSERT INTO leads (name, email, mobile, json_data) VALUES (?, ?, ?, ?)",
                    (name, email, mobile, json.dumps(full_json))
                )
            await conn.commit()
        log(f"  [DB] Lead Saved: {name}")
    except Exception as e:
        log(f"[ERROR] save_lead failed: {e}")


async def save_application(app_id, name, email, mobile, full_json):
    """Saves a full application to the SQLite database."""
    try:
        # Full data excluding heavy PDF/docs base64
        lite_json = {k:v for k,v in full_json.items() if k not in ["pdf_base64", "documents"]}
        async with aiosqlite.connect(DATABASE_PATH) as conn:
            async with conn.cursor() as curr:
                await curr.execute(
                    "INSERT INTO applications (app_id, applicant_name, email, mobile, json_data) VALUES (?, ?, ?, ?, ?)",
                    (app_id, name, email, mobile, json.dumps(lite_json))
                )
            await conn.commit()
        log(f"  [DB] Application Saved: {app_id}")
    except Exception as e:
        log(f"[ERROR] save_application failed: {e}")


async def get_next_app_id():
    """Generates a professional ID: WF-JAN-2026-001"""
    try:
        now = datetime.now()
        month_str = now.strftime('%b').upper() # e.g. APR
        year_str = str(now.year)
        prefix = f"WF-{month_str}-{year_str}-"
        
        async with aiosqlite.connect(DATABASE_PATH) as conn:
            async with conn.cursor() as curr:
                # Count current applications for this specific month/year
                await curr.execute("SELECT COUNT(*) FROM applications WHERE app_id LIKE ?", (f"{prefix}%",))
                row = await curr.fetchone()
                count = row[0]
        
        return f"{prefix}{str(count + 1).zfill(3)}"
    except Exception as e:
        log(f"[ERROR] get_next_app_id failed: {e}")
        return f"WF-{datetime.now().strftime('%Y%B%d%H%M%S')[:15]}"


# FastAPI app instance
app = FastAPI(title="WhiteFlows", version="4.0-js-pdf")

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

# Proxy headers (for Nginx compatibility)
app.add_middleware(ProxyHeadersMiddleware, trusted_hosts="*")

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

def check_rate_limit(ip: str, limit: int = 100, window: int = 3600):
    now = time.time()
    if ip not in _rate_limits:
        _rate_limits[ip] = [now]
        return True
    _rate_limits[ip] = [t for t in _rate_limits[ip] if now - t < window]
    if len(_rate_limits[ip]) >= limit:
        log(f"[SECURITY] Rate limit exceeded for IP: {ip}")
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded. You can only send {limit} submissions per hour. Please try again later."
        )
    _rate_limits[ip].append(now)
    return True


# Mount static files
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


def log(message: str):
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    line = f"[{timestamp}] {message}"
    print(line)
    try:
        with open(BASE_DIR / "server_logs.txt", "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def decode_base64_data_url(data_url: str) -> bytes:
    """
    Decodes a standard base64 data URL (e.g. data:image/png;base64,iVBORw0...)
    Returns the raw bytes.
    """
    try:
        if not data_url or "," not in data_url:
            return b""
        header, encoded = data_url.split(",", 1)
        return base64.b64decode(encoded)
    except Exception as ex:
        log(f"[ERROR] Failed to decode base64: {ex}")
        return b""


def get_safe_filename(doc_info: dict, default_key: str) -> str:
    """
    Ensures the filename is unique by prefixing it with the document key.
    """
    prefix = str(default_key).replace("doc_", "").title()
    raw_name = doc_info.get("originalName") or doc_info.get("name") or doc_info.get("label") or "File"
    ext = ""
    if "." in raw_name:
        parts = raw_name.split(".")
        if len(parts[-1].lower()) in ["pdf", "jpg", "jpeg", "png", "webp"]:
            ext = "." + parts[-1]
            raw_name = "._".join(parts[:-1])
    if not ext:
        mime_type = doc_info.get("type", "").lower()
        if "pdf" in mime_type: ext = ".pdf"
        elif "png" in mime_type: ext = ".png"
        elif "jpeg" in mime_type or "jpg" in mime_type: ext = ".jpg"
        else: ext = ".pdf"
    clean_name = re.sub(r'[^a-zA-Z0-9_-]', '_', raw_name)
    return f"{prefix}_{clean_name}{ext}"


async def fetch_ip_location(ip: str) -> str:
    """Uses a free API to resolve IP into a City/Region string silently."""
    if ip in ["127.0.0.1", "localhost", "::1", "unknown"]:
        return "Local Development"
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(f"http://ip-api.com/json/{ip}")
            if resp.status_code == 200:
                res_data = resp.json()
                if res_data.get("status") == "success":
                    return f"{res_data.get('city')}, {res_data.get('regionName')}, {res_data.get('country')}"
    except Exception as e:
        log(f"  [WARN] Geo IP lookup failed: {e}")
    return "Unknown Location"

# ─── Routes ─────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def serve_index():
    index_path = BASE_DIR / "index.html"
    if index_path.exists():
        return HTMLResponse(content=index_path.read_text(encoding="utf-8"))
    return HTMLResponse(content="<h1>WhiteFlows</h1>", status_code=200)


@app.get("/health")
async def health():
    return {"status": "ok", "version": "4.0-js-pdf", "timestamp": datetime.now().isoformat()}


@app.post("/submit")
async def submit_application(request: Request, background_tasks: BackgroundTasks):
    """
    Handles full application form submission (JSON + Base64 Docs).
    Now uses BackgroundTasks for instant feedback.
    """
    try:
        # Rate limiting (identifies real IP behind Nginx/Proxy)
        client_ip = request.headers.get("X-Forwarded-For", "unknown").split(",")[0].strip()
        check_rate_limit(client_ip)

        # Parse JSON payload
        data = await request.json()

        # Extract real geography for data pipeline
        location = await fetch_ip_location(client_ip)
        data["Client IP"] = client_ip
        data["Client Location"] = location

        app_id = await get_next_app_id()
        # Extract text fields
        record = {
            "app_id":         app_id,
            "portfolio":      data.get("portfolio", ""),
            "applicant_name": data.get("applicant_name", ""),
            "email":          data.get("email", ""),
            "mobile":         data.get("mobile", ""),
            "nominee_name":   data.get("nominee_name", ""),
            "nominee_pan":    data.get("nominee_pan", ""),
        }

        log(f"[APPLICATION] New submission — {record['app_id']} from {record['applicant_name']} in {location}")

        # Persistent Logging: Save to SQLite (non-blocking)
        await save_application(record['app_id'], record['applicant_name'], record['email'], record['mobile'], data)

        # Get the pre-built PDF from the browser (base64 encoded)
        pdf_base64 = data.get("pdf_base64", "")
        pdf_bytes = b""
        if pdf_base64:
            try:
                # Strip data URL prefix if present (data:application/pdf;base64,...)
                if "," in pdf_base64:
                    pdf_base64 = pdf_base64.split(",", 1)[1]
                pdf_bytes = base64.b64decode(pdf_base64)
                log(f"  [PDF] Received from browser ({len(pdf_bytes)} bytes)")
            except Exception as ex:
                log(f"  [WARN] PDF decode failed: {ex}")

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

        # Send emails in the background (Instantly returns success to browser)
        background_tasks.add_task(send_admin_email, record, pdf_bytes, uploaded_docs)
        background_tasks.add_task(send_client_email, record["email"], record["applicant_name"], record["app_id"], pdf_bytes)

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
async def submit_lead(request: Request, background_tasks: BackgroundTasks):
    """
    Handles enquiry/lead form submission (JSON).
    Now uses BackgroundTasks for instant feedback.
    """
    try:
        # Rate limiting (identifies real IP behind Nginx/Proxy)
        client_ip = request.headers.get("X-Forwarded-For", "unknown").split(",")[0].strip()
        check_rate_limit(client_ip)

        # Parse JSON
        data = await request.json()
        
        # Extract real geography for data pipeline
        location = await fetch_ip_location(client_ip)
        data["Client IP"] = client_ip
        data["Client Location"] = location
        
        # Universal Key Extraction (Handles different form types)
        extracted_name = data.get('name') or data.get('applicant_name') or data.get('contact_person') or data.get('entity_name') or "Unknown"
        extracted_email = data.get('email', 'N/A')
        extracted_mobile = data.get('phone') or data.get('mobile') or data.get('contact') or "N/A"
        
        log(f"[LEAD] New enquiry from {extracted_name} ({extracted_email}) in {location}")

        # Separate text fields from documents to prevent base64 DB leaking
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
                continue
            if isinstance(v, dict) and "data" in v and str(v.get("data", "")).startswith("data:"):
                filename = get_safe_filename(v, k)
                file_bytes = decode_base64_data_url(v["data"])
                if file_bytes:
                    attachments[filename] = file_bytes
                    log(f"  [DECODE-FLAT-LEAD] {k}: {filename} ({len(file_bytes)} bytes)")
            else:
                clean_data[k] = v

        # Persistent Logging: Save to SQLite (non-blocking) using clean_data ONLY
        await save_lead(extracted_name, extracted_email, extracted_mobile, clean_data)

        # Send lead notification to admin
        subject = f"New Enquiry — {data.get('name', 'WhiteFlows Lead')}"
        
        # Select primary sender for identity
        from_email = BREVO_LOGIN if (BREVO_SMTP_KEY or BREVO_API_KEY) else GMAIL_SENDER
        
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

        lead_attachments = []
        attached_hashes = set()
        for filename, file_bytes in attachments.items():
            if file_bytes:
                content_hash = hashlib.md5(file_bytes).hexdigest()
                if content_hash in attached_hashes:
                    log(f"  [SKIP-LEAD] Skipping duplicate attachment content: {filename}")
                    continue
                attached_hashes.add(content_hash)
                lead_attachments.append({
                    "filename": filename,
                    "content": file_bytes,
                    "hash": content_hash
                })

        # Send lead email in the background
        background_tasks.add_task(dispatch_email, GMAIL_RECEIVER, subject, html, lead_attachments)
        log(f"  [OK] LEAD EMAIL DISPATCHED WITH {len(lead_attachments)} ATTACHMENTS")

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


# ─── Admin Dashboard Routes ──────────────────────────────────────────────────

# ─── Admin Dashboard Routes ──────────────────────────────────────────────────

JWT_SECRET = os.environ.get("JWT_SECRET", "whiteflows-secret-2026")

def verify_jwt(request: Request) -> bool:
    token = request.cookies.get("wf_session")
    if not token:
        return False
    try:
        from datetime import timezone
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        return payload.get("sub") == "admin"
    except jwt.ExpiredSignatureError:
        log("[SECURITY] JWT expired. Forcing re-login.")
        return False
    except jwt.InvalidTokenError:
        return False

@app.get("/admin-dashboard-logs", response_class=HTMLResponse)
async def admin_login_page(request: Request):
    """Simple login page for the admin dashboard."""
    # Check if already logged in via strict JWT cookie
    if verify_jwt(request):
        return await show_admin_dashboard(request)

    return HTMLResponse(content="""
    <html>
    <head>
        <title>WhiteFlows | Admin Login</title>
        <style>
            body { font-family: sans-serif; background: #F8F7F3; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; }
            .login-box { background: #fff; padding: 40px; border: 1px solid #D4A853; border-radius: 8px; width: 320px; box-shadow: 0 10px 25px rgba(0,0,0,0.05); }
            h2 { color: #0E0D0B; text-align: center; margin-bottom: 30px; text-transform: uppercase; letter-spacing: 1px; }
            input { width: 100%; padding: 12px; margin-bottom: 20px; border: 1px solid #ddd; border-radius: 4px; box-sizing: border-box; }
            button { width: 100%; background: #D4A853; color: #0E0D0B; border: none; padding: 12px; cursor: pointer; font-weight: bold; border-radius: 4px; transition: 0.3s; }
            button:hover { background: #0E0D0B; color: #D4A853; }
        </style>
    </head>
    <body>
        <div class="login-box">
            <h2>Admin Login</h2>
            <form action="/admin-login" method="post">
                <input type="password" name="password" placeholder="Enter Password" required>
                <button type="submit">Access Dashboard</button>
            </form>
        </div>
    </body>
    </html>
    """)


@app.post("/admin-login")
async def admin_login(request: Request):
    """Handles login and sets a secure cookie."""
    form_data = await request.form()
    pwd = (form_data.get("password") or "").strip()
    
    # Use .strip() to avoid hidden space issues from .env
    target_pwd = ADMIN_PASSWORD.strip() if ADMIN_PASSWORD else "whiteflows2026"
    
    if pwd == target_pwd:
        # Create a RedirectResponse to the dashboard
        response = RedirectResponse(url="/admin-dashboard-logs", status_code=303)
        # Create JWT token valid for 30 minutes (Bank-Grade Strictness)
        from datetime import timedelta, timezone
        expire = datetime.now(timezone.utc) + timedelta(minutes=30)
        token_payload = {
            "sub": "admin",
            "exp": expire
        }
        token_str = jwt.encode(token_payload, JWT_SECRET, algorithm="HS256")
        response.set_cookie(key="wf_session", value=token_str, httponly=True)
        return response
    else:
        log(f"  [LOGIN] Failed attempt: {pwd[:2]}***")
        return HTMLResponse(content="<script>alert('Incorrect Password'); window.history.back();</script>", status_code=401)


async def show_admin_dashboard(request: Request):
    """The actual dashboard logic, separated for clean access."""
    try:
        async with aiosqlite.connect(DATABASE_PATH) as conn:
            async with conn.cursor() as curr:
                # Get Leads (include json_data to extract form source)
                await curr.execute("SELECT id, name, email, mobile, created_at, json_data FROM leads ORDER BY created_at DESC")
                leads = await curr.fetchall()
                
                # Get Applications
                await curr.execute("SELECT app_id, applicant_name, email, mobile, created_at FROM applications ORDER BY created_at DESC")
                apps = await curr.fetchall()

        def get_lead_source(js_str):
            try:
                d = json.loads(js_str) if js_str else {}
                return d.get('form_name', 'Consultation')
            except: return 'Consultation'

        # Categorize leads
        categories = {
            "Retail/HNI Consult": [],
            "Project Funding": [],
            "The Ocean Ecosystem": [],
            "Institutional/Ultra-HNI": [],
            "Scale-Up Enquiry": [],
            "Other Enquiries": []
        }

        for l in leads:
            source = get_lead_source(l[5])
            if source in categories:
                categories[source].append(l)
            else:
                categories["Other Enquiries"].append(l)

        leads_sections_html = ""
        for cat_name, items in categories.items():
            if not items: continue
            rows = "".join([f"<tr><td>{l[1]}</td><td>{l[2]}</td><td>{l[3]}</td><td style='font-weight:bold; color:#D4A853;'>{cat_name}</td><td>{l[4]}</td><td style='text-align:center;'><button class='btn-delete' onclick=\"deleteRecord('lead', '{l[0]}')\"><i class='fas fa-trash'></i></button></td></tr>" for l in items])
            leads_sections_html += f"""
                <div class="cat-header">
                    <h2>{cat_name}</h2>
                    <span>{len(items)} ENTRIES</span>
                </div>
                <div class="glass-table-wrapper">
                    <table>
                        <thead><tr><th>Name</th><th>Email</th><th>Mobile</th><th>Source</th><th>Date</th><th style="width:60px;">Action</th></tr></thead>
                        <tbody>{rows}</tbody>
                    </table>
                </div>
            """

        apps_html = "".join([f"<tr><td>{a[0]}</td><td>{a[1]}</td><td>{a[2]}</td><td>{a[3]}</td><td>Full Application</td><td>{a[4]}</td><td style='text-align:center;'><button class='btn-delete' onclick=\"deleteRecord('app', '{a[0]}')\"><i class='fas fa-trash'></i></button></td></tr>" for a in apps])

        html_content = f"""
        <html>
        <head>
            <title>WhiteFlows | Elite Command Center</title>
            <link rel="preconnect" href="https://fonts.googleapis.com">
            <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
            <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700;800&family=Inter:wght@400;500;700&display=swap" rel="stylesheet">
            <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">
            <style>
                :root {{
                    --bg-gradient: linear-gradient(135deg, #F8F7F4 0%, #EFEBE4 100%);
                    --panel-bg: rgba(255, 255, 255, 0.85);
                    --glass-border: rgba(184, 142, 62, 0.25);
                    --glass-shine: rgba(255, 255, 255, 0.5);
                    --text-main: #0E0D0B;
                    --text-muted: #333;
                    --gold: #B88E3E;
                    --gold-glow: rgba(184, 142, 62, 0.2);
                    --danger: #ef4444;
                    --shadow: 0 20px 50px rgba(0, 0, 0, 0.08);
                    --blur: blur(15px);
                }}

                body.dark-mode {{
                    --bg-gradient: linear-gradient(135deg, #0A0A0A 0%, #151515 100%);
                    --panel-bg: rgba(24, 24, 24, 0.75);
                    --glass-border: rgba(212, 168, 83, 0.25);
                    --glass-shine: rgba(255, 255, 255, 0.03);
                    --text-main: #F8F7F4;
                    --text-muted: #aaa;
                    --gold: #D4A853;
                    --shadow: 0 20px 50px rgba(0, 0, 0, 0.4);
                }}

                * {{ margin: 0; padding: 0; box-sizing: border-box; }}
                body {{ 
                    font-family: 'Inter', sans-serif; 
                    background: var(--bg-gradient); 
                    color: var(--text-main); 
                    min-height: 100vh;
                    transition: background 0.4s, color 0.4s;
                }}

                h1, h2, h3 {{ font-family: 'Outfit', sans-serif; font-weight: 700; text-transform: uppercase; letter-spacing: 2px; color: var(--gold); }}

                .layout {{ display: flex; flex-direction: column; max-width: 1300px; margin: auto; padding: 40px 20px; }}

                /* LUXURY HEADER */
                .navbar {{ 
                    display: flex; justify-content: space-between; align-items: center; 
                    padding: 20px 30px; border-radius: 20px;
                    background: var(--panel-bg); backdrop-filter: var(--blur); 
                    border: 1px solid var(--glass-border); 
                    box-shadow: var(--shadow); margin-bottom: 40px;
                    position: sticky; top: 20px; z-index: 1000;
                }}
                .navbar-left h1 {{ font-size: 20px; color: var(--text-main); display: flex; align-items: center; gap: 10px; font-weight: 700; }}
                .navbar-left h1 i {{ color: var(--gold); }}
                .navbar-right {{ display: flex; gap: 15px; align-items: center; }}

                /* BUTTONS */
                .btn {{ 
                    padding: 10px 20px; border-radius: 12px; font-weight: 700; cursor: pointer; border: none; font-size: 13px;
                    display: flex; align-items: center; gap: 8px; transition: 0.3s cubic-bezier(0.4, 0, 0.2, 1); text-decoration: none;
                }}
                .btn-gold {{ background: var(--gold); color: #FFF; box-shadow: 0 4px 15px var(--gold-glow); }}
                .btn-gold:hover {{ transform: translateY(-2px); box-shadow: 0 8px 25px var(--gold-glow); background: #96722D; }}
                .btn-glass {{ background: var(--panel-bg); border: 1px solid var(--glass-border); color: var(--text-main); }}
                .btn-glass:hover {{ background: var(--gold); color: #FFF; }}

                /* THEME TOGGLE */
                .theme-toggle {{ 
                    width: 44px; height: 44px; border-radius: 50%; display: flex; align-items: center; justify-content: center;
                    background: var(--panel-bg); border: 1px solid var(--glass-border); cursor: pointer; color: var(--gold); font-size: 18px;
                }}

                /* STAT CARDS */
                .stats-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin-bottom: 40px; }}
                .stat-card {{ 
                    background: var(--panel-bg); backdrop-filter: var(--blur); 
                    border: 2px solid var(--glass-border); padding: 35px; border-radius: 20px;
                    text-align: center; box-shadow: var(--shadow); position: relative; overflow: hidden;
                    transition: transform 0.3s;
                }}
                .stat-card:hover {{ transform: translateY(-5px); border-color: var(--gold); }}
                .stat-num {{ font-size: 48px; font-family: 'Outfit'; font-weight: 800; color: var(--gold); display: block; line-height: 1; margin-bottom: 10px; }}
                .stat-label {{ color: var(--text-muted); font-size: 13px; font-weight: 700; text-transform: uppercase; letter-spacing: 2px; }}

                /* SEARCH */
                .search-container {{ margin-bottom: 40px; position: relative; }}
                .search-container input {{ 
                    width: 100%; padding: 20px 60px; border-radius: 20px; background: var(--panel-bg); backdrop-filter: var(--blur);
                    border: 1px solid var(--glass-border); color: var(--text-main); font-size: 16px; outline: none; box-shadow: var(--shadow);
                }}
                .search-container i {{ position: absolute; left: 25px; top: 50%; transform: translateY(-50%); color: var(--gold); font-size: 20px; }}

                /* TABLES */
                .cat-header {{ margin: 50px 0 20px; display: flex; align-items: center; gap: 15px; }}
                .cat-header span {{ padding: 6px 12px; background: var(--gold); color: #000; border-radius: 8px; font-size: 10px; font-weight: 700; }}
                
                .glass-table-wrapper {{ 
                    background: var(--panel-bg); backdrop-filter: var(--blur); 
                    border: 1px solid var(--glass-border); border-radius: 20px; overflow: hidden; box-shadow: var(--shadow); margin-bottom: 40px;
                }}
                table {{ width: 100%; border-collapse: collapse; }}
                th {{ background: rgba(0,0,0,0.05); color: var(--gold); text-transform: uppercase; font-size: 11px; padding: 20px; text-align: left; letter-spacing: 1px; }}
                td {{ padding: 20px; color: var(--text-main); border-bottom: 1px solid var(--glass-border); font-size: 14px; }}
                tr:last-child td {{ border-bottom: none; }}
                tr:hover {{ background: rgba(212, 168, 83, 0.05); }}
                
                .btn-delete {{ 
                    width: 36px; height: 36px; border-radius: 10px; border: none; background: rgba(239, 68, 68, 0.1); color: var(--danger);
                    cursor: pointer; transition: 0.3s;
                }}
                .btn-delete:hover {{ background: var(--danger); color: white; transform: rotate(10deg); }}

                /* MODAL */
                .modal-overlay {{ 
                    display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; 
                    background: rgba(0,0,0,0.6); backdrop-filter: blur(5px); z-index: 2000; align-items: center; justify-content: center;
                }}
                .modal-content {{ 
                    background: var(--panel-bg); border: 1px solid var(--glass-border); padding: 40px; border-radius: 25px;
                    width: 90%; max-width: 450px; text-align: center; box-shadow: var(--shadow); transform: scale(0.9); transition: 0.3s;
                }}
                .modal-content.active {{ transform: scale(1); }}
                .modal-icon {{ font-size: 60px; color: var(--danger); margin-bottom: 20px; opacity: 0.8; }}
                
                .auto-timer {{ font-size: 12px; color: var(--text-muted); display: flex; align-items: center; gap: 5px; }}
                .dot {{ width: 8px; height: 8px; background: var(--gold); border-radius: 50%; display: inline-block; animation: pulse 2s infinite; }}
                @keyframes pulse {{ 0% {{ opacity: 0.4; }} 50% {{ opacity: 1; }} 100% {{ opacity: 0.4; }} }}

                @media (max-width: 768px) {{
                    .navbar {{ flex-direction: column; gap: 20px; }}
                    th:nth-child(2), td:nth-child(2) {{ display: none; }} /* Hide email on small mobile */
                }}
            </style>
        </head>
        <body class="dark-mode">
            <div class="layout">
                <nav class="navbar">
                    <div class="navbar-left">
                        <h1><i class="fas fa-shield-halved"></i> WhiteFlows Command Center</h1>
                    </div>
                    <div class="navbar-right">
                        <div class="auto-timer"><span class="dot"></span> Live • <span id="timer">30s</span></div>
                        <button class="theme-toggle" onclick="toggleTheme()" title="Toggle Dark/Light Mode">
                            <i class="fas fa-moon" id="theme-icon"></i>
                        </button>
                        <button class="btn btn-glass" onclick="location.reload()"><i class="fas fa-sync"></i> Refresh</button>
                        <a href="/admin-export-csv" class="btn btn-gold"><i class="fas fa-file-export"></i> Export CSV</a>
                        <a href="/admin-logout" class="btn btn-glass" style="color:var(--danger); border-color:rgba(239, 68, 68, 0.2);"><i class="fas fa-sign-out-alt"></i></a>
                    </div>
                </nav>

                <div class="stats-grid">
                    <div class="stat-card">
                        <span class="stat-num">{len(leads)}</span>
                        <span class="stat-label">Total Leads</span>
                    </div>
                    <div class="stat-card">
                        <span class="stat-num">{len(apps)}</span>
                        <span class="stat-label">Total Applications</span>
                    </div>
                </div>

                <div class="search-container">
                    <i class="fas fa-search"></i>
                    <input type="text" id="searchInput" placeholder="Search leads, names, emails or dates..." onkeyup="filterTables()">
                </div>

                {leads_sections_html}

                <div class="cat-header">
                    <h2>Recent Full Applications</h2>
                    <span>PRIORITY</span>
                </div>
                <div class="glass-table-wrapper">
                    <table id="appsTable">
                        <thead><tr><th>App ID</th><th>Name</th><th>Email</th><th>Mobile</th><th>Source</th><th>Date</th><th style="width:60px;">Action</th></tr></thead>
                        <tbody>{apps_html}</tbody>
                    </table>
                </div>
            </div>

            <div id="deleteModal" class="modal-overlay">
                <div class="modal-content" id="modalBox">
                    <div class="modal-icon"><i class="fas fa-circle-exclamation"></i></div>
                    <h2>Confirm Deletion</h2>
                    <p style="margin: 15px 0 30px; color:var(--text-muted);">Are you sure you want to permanently delete this record? This action cannot be undone.</p>
                    <div style="display:flex; justify-content:center; gap:15px;">
                        <button class="btn btn-glass" onclick="closeModal()" style="width:120px;">Cancel</button>
                        <button class="btn btn-gold" onclick="confirmDelete()" style="width:120px; background:var(--danger); color:white; border:none; box-shadow:none;">Delete</button>
                    </div>
                </div>
            </div>

            <script>
                // Theme Logic
                function toggleTheme() {{
                    document.body.classList.toggle('dark-mode');
                    const isDark = document.body.classList.contains('dark-mode');
                    localStorage.setItem('wf_theme', isDark ? 'dark' : 'light');
                    updateThemeIcon();
                }}

                function updateThemeIcon() {{
                    const icon = document.getElementById('theme-icon');
                    if(document.body.classList.contains('dark-mode')) {{
                        icon.className = 'fas fa-sun';
                    }} else {{
                        icon.className = 'fas fa-moon';
                    }}
                }}

                // Load saved theme
                const savedTheme = localStorage.getItem('wf_theme');
                if(savedTheme === 'light') {{
                    document.body.classList.remove('dark-mode');
                    updateThemeIcon();
                }}

                var secs = 30;
                var timerEl = document.getElementById('timer');
                setInterval(function() {{
                    secs--;
                    if (secs <= 0) {{ location.reload(); }}
                    timerEl.textContent = secs + 's';
                }}, 1000);

                function filterTables() {{
                    const term = document.getElementById('searchInput').value.toLowerCase();
                    const tables = Array.from(document.querySelectorAll('table'));
                    tables.forEach(table => {{
                        const tbody = table.getElementsByTagName('tbody')[0];
                        if (!tbody) return;
                        const rows = tbody.getElementsByTagName('tr');
                        for (let i = 0; i < rows.length; i++) {{
                            const text = rows[i].innerText.toLowerCase();
                            rows[i].style.display = text.includes(term) ? '' : 'none';
                        }}
                    }});
                }}

                let pendingDelete = null;
                function deleteRecord(type, id) {{
                    pendingDelete = {{ type: type, id: id }};
                    const modal = document.getElementById('deleteModal');
                    modal.style.display = 'flex';
                    setTimeout(() => document.getElementById('modalBox').classList.add('active'), 10);
                }}
                
                function closeModal() {{
                    document.getElementById('modalBox').classList.remove('active');
                    setTimeout(() => {{
                        document.getElementById('deleteModal').style.display = 'none';
                        pendingDelete = null;
                    }}, 200);
                }}
                
                async function confirmDelete() {{
                    if (!pendingDelete) return;
                    const payload = pendingDelete;
                    closeModal();
                    try {{
                        const res = await fetch('/admin-delete', {{
                            method: 'POST',
                            headers: {{'Content-Type': 'application/json'}},
                            body: JSON.stringify(payload)
                        }});
                        const data = await res.json();
                        if (data.success) {{ location.reload(); }}
                        else {{ alert("Failed to delete: " + data.error); }}
                    }} catch (e) {{ alert("Error during deletion: " + e); }}
                }}
            </script>
        </body>
        </html>
        """
        return HTMLResponse(content=html_content)
    except Exception as e:
        return HTMLResponse(content=f"Dashboard Error: {e}", status_code=500)


@app.get("/admin-logout")
async def admin_logout():
    """Logs out and clears the session cookie."""
    response = HTMLResponse(content="<script>window.location.href='/admin-dashboard-logs';</script>")
    response.delete_cookie("wf_session")
    return response

class DeleteRequest(BaseModel):
    type: str # "lead" or "app"
    id: str

@app.post("/admin-delete")
async def admin_delete(payload: DeleteRequest, request: Request):
    """Securely deletes a specific record permanently using JWT."""
    if not verify_jwt(request):
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    try:
        async with aiosqlite.connect(DATABASE_PATH) as conn:
            async with conn.cursor() as curr:
                if payload.type == "lead":
                    await curr.execute("DELETE FROM leads WHERE id = ?", (payload.id,))
                elif payload.type == "app":
                    await curr.execute("DELETE FROM applications WHERE app_id = ?", (payload.id,))
            await conn.commit()
        return {"success": True}
    except Exception as e:
        log(f"[ERROR] Delete failed: {e}")
        return {"success": False, "error": str(e)}

async def generate_export_csv_string() -> str:
    """Generates a CSV string containing all leads and applications."""
    try:
        async with aiosqlite.connect(DATABASE_PATH) as conn:
            async with conn.cursor() as curr:
                # Fetch data
                await curr.execute("SELECT 'LEAD' as type, name, email, mobile, created_at, json_data FROM leads")
                leads_raw = await curr.fetchall()
                await curr.execute("SELECT 'APP' as type, applicant_name, email, mobile, created_at, json_data FROM applications")
                apps_raw = await curr.fetchall()

        combined = leads_raw + apps_raw
        
        # Sort combined list by Type and then by internal Form Name
        def get_sort_source(row):
            try:
                js = json.loads(row[5]) if row[5] else {}
                return str(js.get('form_name', 'Consultation'))
            except: return 'Consultation'
        
        combined.sort(key=lambda r: (r[0], get_sort_source(r)))
        
        parsed_data = []
        all_keys = set()
        
        # We will iterate once to find all keys across all records
        for row in combined:
            try:
                extra_data = json.loads(row[5]) if row[5] else {}
                for k in extra_data.keys():
                    if k not in ["name", "applicant_name", "email", "mobile", "submitted_at", "type"]:
                        all_keys.add(str(k).replace('_', ' ').title())
            except: pass

        base_cols = ["Type", "Name", "Email", "Mobile", "Timestamp"]
        extra_cols = sorted(list(all_keys))
        headers = base_cols + extra_cols
        
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=headers)
        writer.writeheader()
        
        current_category = None
        
        for row in combined:
            rtype = row[0]
            cat = get_sort_source(row) if rtype == 'LEAD' else "FULL APPLICATION"
            
            # Insert a visual separator row when the category changes
            if cat != current_category:
                writer.writerow({h: "" for h in headers}) # Empty spacer row
                writer.writerow({headers[0]: f"--- {cat.upper()} ---"}) # Header row
                current_category = cat

            # Parse Timestamp
            raw_ts = row[4]
            clean_ts = raw_ts.replace('T', ' ')[:19] if (raw_ts and 'T' in raw_ts) else raw_ts
                
            item = {
                "Type": rtype, 
                "Name": row[1], 
                "Email": row[2], 
                "Mobile": str(row[3]),
                "Timestamp": clean_ts
            }
            
            try:
                extra_data = json.loads(row[5]) if row[5] else {}
                for k, v in extra_data.items():
                    nice_key = str(k).replace('_', ' ').title()
                    if nice_key in headers:
                        item[nice_key] = str(v)
            except: pass
                
            clean_item = {h: item.get(h, "") for h in headers}
            writer.writerow(clean_item)
        
        return output.getvalue()
    except Exception as e:
        log(f"[ERROR] generate_export_csv_string failed: {e}")
        raise eiter(output, fieldnames=headers)
        writer.writeheader()
        
        for item in parsed_data:
            clean_item = {h: item.get(h, "") for h in headers}
            writer.writerow(clean_item)
        
        return output.getvalue()
    except Exception as e:
        log(f"[ERROR] generate_export_csv_string failed: {e}")
        raise e

@app.get("/admin-export-csv")
async def export_csv(request: Request):
    """Generates a CSV of all leads and applications with JSON data fully parsed into columns."""
    if not verify_jwt(request):
        raise HTTPException(status_code=401, detail="Unauthorized")

    try:
        csv_string = await generate_export_csv_string()
        filename = f"whiteflows_export_{datetime.now().strftime('%Y%m%d')}.csv"
        
        return StreamingResponse(
            iter([csv_string]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    except Exception as e:
        log(f"[ERROR] CSV Export failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def send_admin_email(record: dict, pdf_bytes: bytes, uploaded_docs: dict):
    """
    Send application notification to admin with PDF receipt and uploaded documents.
    """
    app_id = record.get("app_id", "UNKNOWN")
    subject = f"NEW APPLICATION — {record.get('applicant_name', 'Unknown')} [{app_id}]"
    
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

    attachments = []
    attached_hashes = set()

    # 1. Add Receipt
    if pdf_bytes:
        pdf_hash = hashlib.md5(pdf_bytes).hexdigest()
        attached_hashes.add(pdf_hash)
        attachments.append({
            "filename": f"Receipt_{app_id}.pdf",
            "content": pdf_bytes,
            "hash": pdf_hash
        })

    # 2. Add Uploads
    for filename, file_bytes in uploaded_docs.items():
        if file_bytes:
            content_hash = hashlib.md5(file_bytes).hexdigest()
            if content_hash in attached_hashes:
                log(f"  [SKIP] Skipping duplicate attachment content: {filename}")
                continue
            attached_hashes.add(content_hash)
            attachments.append({
                "filename": filename,
                "content": file_bytes,
                "hash": content_hash
            })

    await dispatch_email(GMAIL_RECEIVER, subject, html, attachments)
    log(f"  [OK] ADMIN EMAIL DISPATCHED — {app_id}")


async def send_client_email(client_email: str, client_name: str, app_id: str, pdf_bytes: bytes):
    """
    Send confirmation email to client.
    """
    if not client_email: return
    
    INK = "#1A1714"; GOLD = "#D4A853"; PEARL = "#FDFCF9"
    subject = "Application Received — WhiteFlows International"
    html = f"""
    <!DOCTYPE html>
    <html>
    <body style="font-family:Arial,sans-serif;background:{PEARL};margin:0;padding:20px;color:{INK};">
        <div style="max-width:600px;margin:auto;background:#fff;border:1px solid {GOLD};border-radius:4px;overflow:hidden;">
            <div style="background:{INK};padding:40px 20px;text-align:center;border-bottom:3px solid {GOLD};">
                <h1 style="color:{GOLD};margin:0;font-size:28px;letter-spacing:4px;text-transform:uppercase;">WhiteFlows</h1>
                <p style="color:#E8C88A;margin:8px 0 0;font-size:11px;letter-spacing:2px;text-transform:uppercase;">A Legacy of 37 Years in Wealth Creation</p>
            </div>
            <div style="padding:50px 40px;line-height:1.8;">
                <h2 style="color:{INK};font-size:20px;margin-top:0;">Dear {client_name},</h2>
                <p style="font-size:15px;color:#444;">Thank you for choosing WhiteFlows International. We have successfully received your application.</p>
                <p style="margin-top:40px;font-size:14px;color:{INK};">Best regards,<br/><strong style="color:{GOLD};">WhiteFlows Management</strong></p>
            </div>
        </div>
    </body>
    </html>
    """
    
    attachments = []
    if pdf_bytes:
        attachments.append({
            "filename": f"WhiteFlows_Receipt_{app_id}.pdf",
            "content": pdf_bytes
        })

    await dispatch_email(client_email, subject, html, attachments)
    log(f"  [OK] CLIENT EMAIL DISPATCHED to {client_email}")


async def dispatch_email(to_email: str, subject: str, html: str, attachments: list):
    """
    3-Step Cascade: Brevo SMTP → Brevo API → Gmail SMTP
    Tries each method in order. Moves to next only if previous fails.
    """
    # Step 1: Brevo SMTP
    if BREVO_SMTP_KEY:
        success = await send_via_brevo_smtp(to_email, subject, html, attachments)
        if success:
            return
        log("  [CASCADE] Brevo SMTP failed, trying Brevo API...")

    # Step 2: Brevo API
    if BREVO_API_KEY:
        success = await send_via_brevo_api(to_email, subject, html, attachments)
        if success:
            return
        log("  [CASCADE] Brevo API failed, trying Gmail SMTP...")

    # Step 3: Gmail SMTP (final fallback)
    log("  [CASCADE] Falling back to Gmail SMTP...")
    await send_via_gmail_smtp(to_email, subject, html, attachments)


async def generate_daily_digest_html():
    """Gathers intelligence from the last 24 hours and builds a professional summary."""
    try:
        now = datetime.now()
        yesterday = now - timedelta(days=1)
        
        async with aiosqlite.connect(DATABASE_PATH) as conn:
            async with conn.cursor() as curr:
                # Query leads from the last 24H
                await curr.execute("SELECT name, email, mobile, json_data FROM leads WHERE created_at >= ?", (yesterday.isoformat(),))
                leads = await curr.fetchall()
                
                # Query applications from the last 24H
                await curr.execute("SELECT app_id, applicant_name, email FROM applications WHERE created_at >= ?", (yesterday.isoformat(),))
                apps = await curr.fetchall()

        # Categorization Logic
        summary = {}
        for l in leads:
            try:
                js = json.loads(l[3]) if l[3] else {}
                cat = js.get('form_name', 'Consultation')
            except: cat = 'Consultation'
            
            if cat not in summary: summary[cat] = []
            summary[cat].append(f"<li><b>{l[0]}</b> - {l[1]} ({l[2]})</li>")

        lead_list_html = ""
        for cat, items in summary.items():
            lead_list_html += f"<h3>{cat}</h3><ul>{''.join(items)}</ul>"

        app_list_html = "".join([f"<li><b>{a[0]}</b>: {a[1]} ({a[2]})</li>" for a in apps]) if apps else "<li>No full applications yesterday.</li>"

        html = f"""
        <html>
        <body style="font-family: sans-serif; color: #0E0D0B; background: #F8F7F3; padding: 20px;">
            <div style="max-width: 600px; margin: auto; background: #fff; padding: 40px; border: 1px solid #D4A853; border-radius: 8px;">
                <h1 style="color: #D4A853; text-transform: uppercase;">Lead Intelligence Digest</h1>
                <p style="color: #666;">Report for: {yesterday.strftime('%Y-%m-%d')} to {now.strftime('%Y-%m-%d')}</p>
                <hr style="border: 0; border-top: 1px solid #eee; margin: 30px 0;">
                
                <h2 style="color: #B88E3E;">Summary</h2>
                <p>New Leads: <b>{len(leads)}</b></p>
                <p>Full Applications: <b>{len(apps)}</b></p>
                
                <hr style="border: 0; border-top: 1px solid #eee; margin: 30px 0;">
                
                <h2 style="color: #B88E3E;">New Enquiries by Category</h2>
                {lead_list_html if leads else "<p>No new enquiries yesterday.</p>"}
                
                <h2 style="color: #B88E3E;">Priority Applications</h2>
                <ul>{app_list_html}</ul>
                
                <p style="margin-top: 50px; font-size: 11px; color: #999;">Automated Daily Intelligence System — WhiteFlows Enterprise Security</p>
            </div>
        </body>
        </html>
        """
        return html
    except Exception as e:
        log(f"[ERROR] generate_daily_digest_html failed: {e}")
        return None


async def send_via_brevo_smtp(to_email: str, subject: str, html: str, attachments: list):
    """Send via Brevo Pro SMTP Relay. Returns True on success, False on failure."""
    try:
        msg = MIMEMultipart()
        msg["Subject"] = subject
        msg["From"] = f"WhiteFlows <{GMAIL_SENDER}>"
        msg["To"] = to_email
        msg.attach(MIMEText(html, "html"))

        for att in attachments:
            part = MIMEApplication(att["content"])
            part.add_header("Content-Disposition", "attachment", filename=att["filename"])
            msg.attach(part)

        with smtplib.SMTP("smtp-relay.brevo.com", 587) as server:
            server.starttls()
            server.login(BREVO_LOGIN, BREVO_SMTP_KEY)
            server.sendmail(BREVO_LOGIN, to_email, msg.as_bytes())
        log(f"  [OK] Brevo SMTP Success: {to_email}")
        return True
    except Exception as e:
        log(f"  [ERROR] Brevo SMTP failed: {e}")
        return False



async def send_via_brevo_api(to_email: str, subject: str, html: str, attachments: list):
    """Send via Brevo HTTP API. Returns True on success, False on failure."""
    try:
        url = "https://api.brevo.com/v3/smtp/email"
        headers = {
            "api-key": BREVO_API_KEY,
            "x-sib-api-key": BREVO_API_KEY,
            "Content-Type": "application/json"
        }
        
        brevo_attachments = []
        for att in attachments:
            brevo_attachments.append({
                "content": base64.b64encode(att["content"]).decode('utf-8'),
                "name": att["filename"]
            })

        payload = {
            "sender": {"name": "WhiteFlows", "email": GMAIL_SENDER},
            "to": [{"email": to_email}],
            "subject": subject,
            "htmlContent": html,
            "attachment": brevo_attachments
        }

        async with httpx.AsyncClient() as client:
            resp = await client.post(url, headers=headers, json=payload, timeout=20.0)
            if resp.status_code < 300:
                log(f"  [OK] Brevo API Success: {to_email}")
                return True
            else:
                log(f"  [ERROR] Brevo API Fail: {resp.text}")
                return False
    except Exception as e:
        log(f"  [ERROR] Brevo API exception: {e}")
        return False



async def send_via_gmail_smtp(to_email: str, subject: str, html: str, attachments: list):
    """Fallback to Gmail SMTP."""
    if GMAIL_PASSWORD == "your-app-password": return
    try:
        msg = MIMEMultipart()
        msg["Subject"] = subject
        msg["From"] = f"WhiteFlows <{GMAIL_SENDER}>"
        msg["To"] = to_email
        msg.attach(MIMEText(html, "html"))
        for att in attachments:
            part = MIMEApplication(att["content"])
            part.add_header("Content-Disposition", "attachment", filename=att["filename"])
            msg.attach(part)

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(GMAIL_SENDER, GMAIL_PASSWORD)
            smtp.sendmail(GMAIL_SENDER, to_email, msg.as_bytes())
        log(f"  [OK] Gmail SMTP Success: {to_email}")
    except Exception as e:
        log(f"  [ERROR] Gmail SMTP failed: {e}")


async def send_database_backup():
    try:
        log("[BACKUP] Initiating scheduled database backup sequence...")
        timestamp_str = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # 1. Database File
        db_filename = f"whiteflows_backup_{timestamp_str}.db"
        db_path = os.path.join(os.path.dirname(DATABASE_PATH), db_filename)
        import shutil
        shutil.copy2(DATABASE_PATH, db_path)
        with open(db_path, "rb") as f:
            db_bytes = f.read()

        # 2. CSV File
        csv_filename = f"whiteflows_backup_{timestamp_str}.csv"
        try:
            csv_str = await generate_export_csv_string()
            csv_bytes = csv_str.encode('utf-8')
        except Exception as e:
            log(f"[WARNING] Failed to generate CSV backup: {e}")
            csv_bytes = b""
            
        # Main email attachment block
        attachments_main = [{"filename": db_filename, "content": db_bytes}]
        if csv_bytes:
            attachments_main.append({"filename": csv_filename, "content": csv_bytes})
        
        # Send to primary official email
        await dispatch_email(GMAIL_RECEIVER, subject, html, attachments_main)
            
        # Send exclusively to the backup email (with server logs included)
        if BACKUP_RECEIVER_EMAIL and BACKUP_RECEIVER_EMAIL != GMAIL_RECEIVER:
            attachments_backup = list(attachments_main)
            try:
                log_path = BASE_DIR / "server_logs.txt"
                if log_path.exists():
                    with open(log_path, "rb") as fl:
                        attachments_backup.append({"filename": "server_logs.txt", "content": fl.read()})
            except Exception as e:
                log(f"[WARNING] Could not attach server_logs.txt: {e}")
                
            await dispatch_email(BACKUP_RECEIVER_EMAIL, subject, html, attachments_backup)
            
        if os.path.exists(db_path):
            os.remove(db_path)
            
        log("[BACKUP] Database & CSV backup completed and emailed successfully.")
        return True
    except Exception as e:
        log(f"[ERROR] Database backup failed: {e}")
        return False


async def backup_scheduler_loop():
    """Runs continuously in the background, checking every hour if 3 days have passed since last backup."""
    # Wait 10 seconds initially for server to fully boot
    await asyncio.sleep(10)
    while True:
        try:
            async with aiosqlite.connect(DATABASE_PATH) as conn:
                async with conn.cursor() as curr:
                    await curr.execute("CREATE TABLE IF NOT EXISTS server_metadata (key TEXT PRIMARY KEY, value TEXT)")
                    
                    await curr.execute("SELECT value FROM server_metadata WHERE key = 'last_backup'")
                    row = await curr.fetchone()
                    
                    needs_backup = False
                    now = datetime.now()
                    
                    if row:
                        last_backup = datetime.fromisoformat(row[0])
                        if (now - last_backup).days >= 3:
                            needs_backup = True
                    else:
                        # If no previous backup, backup immediately
                        needs_backup = True
                        
                    if needs_backup:
                        success = await send_database_backup()
                        if success:
                            await curr.execute("INSERT OR REPLACE INTO server_metadata (key, value) VALUES ('last_backup', ?)", (now.isoformat(),))
                            await conn.commit()
                            
        except Exception as e:
            log(f"[ERROR] Backup scheduler error: {e}")
            
        # Sleep for 1 hour
        await asyncio.sleep(3600)

async def daily_digest_scheduler_loop():
    """Triggers the intelligence digest every morning at 8:00 AM."""
    # Delay first check slightly to let server stabilize
    await asyncio.sleep(20)
    while True:
        try:
            now = datetime.now()
            # If it's between 8 AM and 9 AM
            if now.hour == 8:
                async with aiosqlite.connect(DATABASE_PATH) as conn:
                    async with conn.cursor() as curr:
                        await curr.execute("CREATE TABLE IF NOT EXISTS server_metadata (key TEXT PRIMARY KEY, value TEXT)")
                        
                        await curr.execute("SELECT value FROM server_metadata WHERE key = 'last_digest_date'")
                        row = await curr.fetchone()
                        
                        today_str = now.strftime('%Y-%m-%d')
                        if not row or row[0] != today_str:
                            log(f"[SYSTEM] Generating Daily Lead Intelligence Digest for {today_str}...")
                            html = await generate_daily_digest_html()
                            if html:
                                await send_admin_email_cascade(
                                    ADMIN_EMAIL, 
                                    f"DAILY INTELLIGENCE — {today_str}", 
                                    html
                                )
                                await curr.execute("INSERT OR REPLACE INTO server_metadata (key, value) VALUES ('last_digest_date', ?)", (today_str,))
                                await conn.commit()
                            
        except Exception as e:
            log(f"[ERROR] Daily digest scheduler error: {e}")
            
        # Check every 30 minutes
        await asyncio.sleep(1800)

def validate_environment():
    """Runs a pre-flight check to warn about insecure configurations."""
    warnings = []
    if ADMIN_PASSWORD == 'whiteflows2026':
        warnings.append("[SECURITY WARNING] ADMIN_PASSWORD is still 'whiteflows2026'. Change it before making this public!")
    if 'your-email' in GMAIL_SENDER or 'your-app-password' in GMAIL_PASSWORD:
        warnings.append("[SECURITY WARNING] Gmail credentials perfectly match .env.example values. Email cascade will fail over!")
    if not BREVO_API_KEY and not BREVO_SMTP_KEY:
        warnings.append("[CONFIG WARNING] No Brevo keys provided. System relying solely on Gmail 500 emails/day quota.")
        
    for w in warnings:
        log(w)
    if warnings:
        log("[SYSTEM] Please review the above warnings. Plausible to ignore only for local testing.")

@app.on_event("startup")
async def startup_event():
    validate_environment()
    await init_db()
    asyncio.create_task(backup_scheduler_loop())
    asyncio.create_task(daily_digest_scheduler_loop())
    log("[SYSTEM] Background schedulers (Backup + Daily Digest) active.")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8001))
    uvicorn.run(app, host="0.0.0.0", port=port)
