"""
WhiteFlows Application Server
Stateless: no file writes, no threading.
PDF is generated in the browser (jsPDF) and sent as base64.
The server only handles email sending.

Developed by Amburax
Engineered by Amburax
"""

import os
import io
import time
import base64
import re
import hashlib
import traceback
import mimetypes
# Non-standard imports moved inside functions to bypass Cloudflare Build Validation (Error 10021)
# import jwt
import sqlite3
import json
import socket
import csv
from typing import Optional, Union, List
from pathlib import Path
from datetime import datetime, timedelta
import asyncio

try:
    import uvicorn
except ImportError:
    uvicorn = None
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse, RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
try:
    from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware
    from dotenv import load_dotenv
except ImportError:
    ProxyHeadersMiddleware = None
    load_dotenv = None
# import httpx

# Optional import for local development only
try:
    import aiosqlite
except ImportError:
    aiosqlite = None

# Load environment variables (locally only)
if load_dotenv:
    load_dotenv()

# Configuration
ADMIN_EMAIL_MAIN  = os.environ.get('GMAIL_SENDER',   'advisory@whiteflowsint.com')
ADMIN_EMAIL_RECV  = os.environ.get('GMAIL_RECEIVER', 'advisory@whiteflowsint.com')
BREVO_API_KEY  = os.environ.get('BREVO_API_KEY', '')
RESEND_API_KEY = os.environ.get('RESEND_API_KEY', '')
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'whiteflows2026')
BACKUP_RECEIVER_EMAIL = os.environ.get('BACKUP_RECEIVER_EMAIL', '')

# Setup paths (for static assets and database)
BASE_DIR = Path(__file__).parent
DATABASE_PATH = os.environ.get("DATABASE_PATH", str(BASE_DIR / "whiteflows.db"))
LOG_FILE_PATH = os.environ.get("LOG_FILE_PATH", str(BASE_DIR / "server_logs.txt"))

# ─── DATABASE ADAPTER (LOCAL vs CLOUDFLARE) ──────────────────────────────────

class DBAdapter:
    """Bridges the gap between local aiosqlite and Cloudflare D1."""
    def __init__(self, request_env=None):
        self.worker_env = request_env
        self.is_worker = request_env is not None and hasattr(request_env, "DB")

    async def execute(self, query: str, params: tuple = ()):
        if self.is_worker:
            # Cloudflare D1 Syntax
            try:
                stmt = self.worker_env.DB.prepare(query)
                if params:
                    stmt = stmt.bind(*params)
                return await stmt.run()
            except Exception as e:
                log(f"[D1 ERROR] Execute: {e}")
                raise e
        else:
            # Local aiosqlite
            async with aiosqlite.connect(DATABASE_PATH) as conn:
                async with conn.cursor() as curr:
                    await curr.execute(query, params)
                await conn.commit()

    async def fetch_all(self, query: str, params: tuple = ()):
        if self.is_worker:
            stmt = self.worker_env.DB.prepare(query)
            if params:
                stmt = stmt.bind(*params)
            # D1 returns a results object, we convert to familiar tuple format
            res = await stmt.all()
            if hasattr(res, 'results'):
                # Handle different D1 response shapes
                return [tuple(row.values()) for row in res.results]
            return [tuple(row.values()) for row in res]
        else:
            async with aiosqlite.connect(DATABASE_PATH) as conn:
                async with conn.cursor() as curr:
                    await curr.execute(query, params)
                    return await curr.fetchall()

    async def fetch_one(self, query: str, params: tuple = ()):
        if self.is_worker:
            stmt = self.worker_env.DB.prepare(query)
            if params:
                stmt = stmt.bind(*params)
            res = await stmt.first()
            return tuple(res.values()) if res else None
        else:
            async with aiosqlite.connect(DATABASE_PATH) as conn:
                async with conn.cursor() as curr:
                    await curr.execute(query, params)
                    return await curr.fetchone()

def get_db(request: Request = None):
    # Detection of Cloudflare Environment
    try:
        if request and hasattr(request, "scope") and "env" in request.scope:
            return DBAdapter(request.scope["env"])
    except: pass
    return DBAdapter()


async def init_db(db: DBAdapter = None):
    """Initialises the local SQLite database (only for local mode). D1 is handled by schema.sql."""
    db = db or get_db()
    if db.is_worker:
        return # D1 schema is handled at deploy time
    
    try:
        # Leads Table
        await db.execute('''
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
        await db.execute('''
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
        await db.execute("CREATE TABLE IF NOT EXISTS server_metadata (key TEXT PRIMARY KEY, value TEXT)")
        log("[DB] Initialised locally.")
    except Exception as e:
        log(f"[ERROR] init_db failed: {e}")


async def save_lead(name, email, mobile, full_json, db: DBAdapter = None):
    """Saves a lead to the database."""
    db = db or get_db()
    try:
        await db.execute(
            "INSERT INTO leads (name, email, mobile, json_data) VALUES (?, ?, ?, ?)",
            (name, email, mobile, json.dumps(full_json))
        )
        log(f"  [DB] Lead Saved: {name}")
    except Exception as e:
        log(f"[ERROR] save_lead failed: {e}")


async def save_application(app_id, name, email, mobile, full_json, db: DBAdapter = None):
    """Saves a full application to the database."""
    db = db or get_db()
    try:
        # Full data excluding heavy PDF/docs base64
        lite_json = {k:v for k,v in full_json.items() if k not in ["pdf_base64", "documents"]}
        await db.execute(
            "INSERT INTO applications (app_id, applicant_name, email, mobile, json_data) VALUES (?, ?, ?, ?, ?)",
            (app_id, name, email, mobile, json.dumps(lite_json))
        )
        log(f"  [DB] Application Saved: {app_id}")
    except Exception as e:
        log(f"[ERROR] save_application failed: {e}")


async def get_next_app_id(db: DBAdapter = None):
    """Generates a professional ID: WF-JAN-2026-001"""
    db = db or get_db()
    try:
        now = datetime.now()
        month_str = now.strftime('%b').upper()
        year_str = str(now.year)
        prefix = f"WF-{month_str}-{year_str}-"
        
        # Query current count
        row = await db.fetch_one("SELECT COUNT(*) FROM applications WHERE app_id LIKE ?", (f"{prefix}%",))
        count = row[0] if row else 0
        
        return f"{prefix}{str(count + 1).zfill(3)}"
    except Exception as e:
        log(f"[ERROR] get_next_app_id failed: {e}")
        return f"WF-{datetime.now().strftime('%Y%B%d%H%M%S')[:15]}"


from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Modern FastAPI lifespan handler — replaces deprecated @app.on_event('startup')."""
    validate_environment()
    await init_db()
    asyncio.create_task(backup_scheduler_loop())
    asyncio.create_task(daily_digest_scheduler_loop())
    asyncio.create_task(_rate_limit_cleanup_loop())
    log("[SYSTEM] Background schedulers (Backup + Daily Digest + Rate-Limit Cleanup) active.")
    yield
    # (shutdown logic can go here if needed in future)

# FastAPI app instance
app = FastAPI(title="WhiteFlows", version="4.0-js-pdf", lifespan=lifespan)


# CORS middleware — restrict to whiteflowsint.com only
_ALLOWED_ORIGINS = [
    "https://whiteflowsint.com",
    "https://www.whiteflowsint.com",
    "https://whiteflowsint.com",
    "https://www.whiteflowsint.com",
    "http://localhost:8001",   # local development
    "http://127.0.0.1:8001",  # local development
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization"],
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

def check_rate_limit(ip: str, limit: int = 4, window: int = 3600):
    now = time.time()
    if ip not in _rate_limits:
        _rate_limits[ip] = [now]
        return True
    _rate_limits[ip] = [t for t in _rate_limits[ip] if now - t < window]
    if len(_rate_limits[ip]) >= limit:
        log(f"[SECURITY] Rate limit exceeded for IP: {ip}")
        raise HTTPException(
            status_code=429,
            detail=f"Security Limit Reached: You have reached the maximum of {limit} submissions per hour from this IP. Please try again later."
        )
    _rate_limits[ip].append(now)
    return True

async def _rate_limit_cleanup_loop():
    """Runs every 30 minutes and removes stale IPs to prevent memory growth."""
    while True:
        await asyncio.sleep(1800)  # 30 minutes
        now = time.time()
        stale = [ip for ip, ts in _rate_limits.items() if not any(now - t < 3600 for t in ts)]
        for ip in stale:
            del _rate_limits[ip]
        if stale:
            log(f"[CLEANUP] Rate limit memory: removed {len(stale)} stale IP(s). Active: {len(_rate_limits)}")


# Mount static files
# Optional Static Files
STATIC_DIR = BASE_DIR / "static"
if STATIC_DIR.exists() and STATIC_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
else:
    print("[SYSTEM] Static directory not found, skipping mount.")

@app.get("/robots.txt", include_in_schema=False)
async def robots_txt():
    return FileResponse(BASE_DIR / "robots.txt")

@app.get("/sitemap.xml", include_in_schema=False)
async def sitemap_xml():
    return FileResponse(BASE_DIR / "sitemap.xml")


def log(message: str):
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    line = f"[{timestamp}] {message}"
    print(line)
    try:
        # Ensure parent directory exists for logs if custom path is set
        log_path = Path(LOG_FILE_PATH)
        if not log_path.parent.exists():
            log_path.parent.mkdir(parents=True, exist_ok=True)
            
        with open(LOG_FILE_PATH, "a", encoding="utf-8") as f:
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
    """Uses a free HTTPS API to resolve IP into a City/Region string silently."""
    if ip in ["127.0.0.1", "localhost", "::1", "unknown"]:
        return "Local Development"
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(f"https://ipapi.co/{ip}/json/")
            if resp.status_code == 200:
                res_data = resp.json()
                city = res_data.get("city", "")
                region = res_data.get("region", "")
                country = res_data.get("country_name", "")
                if city:
                    return f"{city}, {region}, {country}"
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
        # OLD: background_tasks.add_task(send_client_email, record["email"], record["applicant_name"], record["app_id"], pdf_bytes)
        
        # New Branded Elite Auto-Responder
        background_tasks.add_task(send_client_confirmation, record["email"], record["applicant_name"], record['app_id'], True)

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
        subject = f"New Enquiry — {extracted_name}"
        
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

        # Triggers Admin Notification
        background_tasks.add_task(send_admin_email_cascade, GMAIL_RECEIVER, subject, html, lead_attachments)
        
        # New Branded Elite Auto-Responder for Leads
        ref_id = f"REF-{hashlib.md5(str(time.time()).encode()).hexdigest()[:6].upper()}"
        background_tasks.add_task(send_client_confirmation, extracted_email, extracted_name, ref_id, False)

        return JSONResponse({
            "success": True,
            "message": "Lead received successfully. You will hear from us shortly."
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

import secrets as _secrets
_jwt_env = os.environ.get("JWT_SECRET", "")
JWT_SECRET = _jwt_env if _jwt_env else _secrets.token_hex(32)
if not _jwt_env:
    log("[SECURITY] WARNING: JWT_SECRET not set. Generated a random secret — admin sessions will reset on every restart. Set JWT_SECRET in your .env for persistence.")


def verify_jwt(request: Request) -> bool:
    token = request.cookies.get("wf_session")
    if not token:
        return False
    try:
        import jwt
        from datetime import timezone
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        return payload.get("sub") == "admin"
    except jwt.ExpiredSignatureError:
        log("[SECURITY] JWT expired. Forcing re-login.")
        return False
    except jwt.InvalidTokenError:
        return False

@app.get("/admin", response_class=HTMLResponse, include_in_schema=False)
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
            <form action="/admin/login" method="post">
                <input type="password" name="password" placeholder="Enter Password" required>
                <button type="submit">Access Dashboard</button>
            </form>
        </div>
    </body>
    </html>
    """)


@app.post("/admin/login")
async def admin_login(request: Request):
    """
    Bank-grade security: JWT session issuance.
    """
    import jwt
    try:
        data = await request.json()
        password = data.get("password")
        
        if password == ADMIN_PASSWORD:
            token = jwt.encode({
                "sub": "admin",
                "exp": datetime.utcnow() + timedelta(minutes=30)
            }, JWT_SECRET, algorithm="HS256")
            
            # Use DBAdapter for metadata
            db = get_db(request)
            await db.execute("INSERT OR REPLACE INTO server_metadata (key, value) VALUES ('last_admin_login', ?)", (datetime.now().isoformat(),))
            
            return {"success": True, "token": token}
        
        return JSONResponse({"success": False, "message": "Access Denied"}, status_code=401)
    except Exception as e:
        log(f"[ERROR] login failed: {e}")
        return JSONResponse({"success": False, "message": "Server error"}, status_code=500)


@app.get("/admin/applications")
async def get_applications(request: Request):
    verify_jwt(request)
    db = get_db(request)
    try:
        rows = await db.fetch_all("SELECT id, app_id, applicant_name, email, mobile, json_data, created_at FROM applications ORDER BY created_at DESC")
        apps = []
        for r in rows:
            apps.append({
                "id": r[0], "app_id": r[1], "name": r[2], 
                "email": r[3], "mobile": r[4], 
                "data": json.loads(r[5]) if r[5] else {}, 
                "created_at": r[6]
            })
        return apps
    except Exception as e:
        log(f"[ERROR] get_applications failed: {e}")
        return []


@app.get("/admin/leads")
async def get_leads(request: Request):
    verify_jwt(request)
    db = get_db(request)
    try:
        rows = await db.fetch_all("SELECT id, name, email, mobile, json_data, created_at FROM leads ORDER BY created_at DESC")
        leads = []
        for r in rows:
            leads.append({
                "id": r[0], "name": r[1], "email": r[2], 
                "mobile": r[3], "data": json.loads(r[4]) if r[4] else {}, 
                "created_at": r[5]
            })
        return leads
    except Exception as e:
        log(f"[ERROR] get_leads failed: {e}")
        return []


async def get_admin_stats(db: DBAdapter):
    """Calculates key performance metrics for the admin dashboard with optimized logic."""
    try:
        # 1. Total Leads
        row_leads = await db.fetch_one("SELECT COUNT(*) FROM leads")
        total_leads = row_leads[0] if row_leads else 0

        # 2. Total Applications
        row_apps = await db.fetch_one("SELECT COUNT(*) FROM applications")
        total_apps = row_apps[0] if row_apps else 0

        # 3. Momentum (Last 24 Hours)
        last_24h = (datetime.now() - timedelta(hours=24)).isoformat()
        row_momentum = await db.fetch_one("SELECT COUNT(*) FROM leads WHERE created_at >= ?", (last_24h,))
        momentum = row_momentum[0] if row_momentum else 0

        # 4. Global Hotspot
        rows_loc = await db.fetch_all("SELECT json_data FROM leads")
        
        locations_raw = []
        for row in rows_loc:
            try:
                data = json.loads(row[0])
                loc = data.get("Client Location", "Unknown")
                if loc == "Local Development": loc = "Limbdi"
                if loc not in ["Unknown Location", "N/A"]:
                    locations_raw.append(loc)
            except: pass
        
        from collections import Counter
        location_counts = Counter(locations_raw)
        hotspot = location_counts.most_common(1)[0][0] if locations_raw else "Global Network"
        location_json = json.dumps(dict(location_counts))

        return {
            "total_leads": total_leads,
            "total_apps": total_apps,
            "momentum": momentum,
            "hotspot": hotspot,
            "location_json": location_json
        }
    except Exception as e:
        log(f"[ERROR] get_admin_stats failed: {e}")
        return {"total_leads": 0, "total_apps": 0, "momentum": 0, "hotspot": "Global Reach", "location_json": "{}"}


@app.get("/admin/dashboard", response_class=HTMLResponse)
async def show_admin_dashboard(request: Request):
    """The actual dashboard logic, separated for clean access."""
    verify_jwt(request)
    db = get_db(request)
    try:
        # Get Leads
        leads = await db.fetch_all("SELECT id, name, email, mobile, created_at, json_data FROM leads ORDER BY created_at DESC")
        
        # Get Applications
        apps = await db.fetch_all("SELECT app_id, applicant_name, email, mobile, created_at FROM applications ORDER BY created_at DESC")

        # Fetch intelligence metrics
        stats = await get_admin_stats(db)

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
                    transition: transform 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275);
                }}
                .stat-card:hover {{ transform: translateY(-8px); border-color: var(--gold); }}
                .stat-num {{ font-size: 48px; font-family: 'Outfit'; font-weight: 800; color: var(--gold); display: block; line-height: 1; margin-bottom: 10px; }}
                .stat-label {{ color: var(--text-muted); font-size: 13px; font-weight: 700; text-transform: uppercase; letter-spacing: 2px; display: flex; align-items: center; justify-content: center; gap: 8px; }}
                .stat-label i {{ color: var(--gold); opacity: 0.7; }}
                .stat-card em {{ font-family: sans-serif; font-style: normal; font-size: 12px; color: var(--gold); position: absolute; top: 15px; right: 20px; opacity: 0.6; }}

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
                    /* On mobile: keep email column but truncate it */
                    td:nth-child(2) {{ 
                        max-width: 90px; 
                        overflow: hidden; 
                        text-overflow: ellipsis; 
                        white-space: nowrap;
                        font-size: 11px;
                        color: var(--gold);
                    }}
                    /* Make rows clickable for expand */
                    tr.data-row {{ cursor: pointer; }}
                    tr.data-row:hover {{ background: rgba(212, 168, 83, 0.08); }}
                    /* Expanded detail row */
                    .expand-row td {{ 
                        padding: 12px 20px;
                        font-size: 12px;
                        background: rgba(212, 168, 83, 0.04);
                        border-top: 1px dashed var(--glass-border);
                        line-height: 1.8;
                        display: none;
                    }}
                    .expand-row.open td {{ display: table-cell; }}
                    td {{ padding: 14px 10px; font-size: 12px; }}
                    th {{ padding: 14px 10px; font-size: 10px; }}
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
                        <em>Total Volume</em>
                        <span class="stat-num">{stats['total_leads']}</span>
                        <span class="stat-label"><i class="fas fa-users"></i> Global Leads</span>
                    </div>
                    <div class="stat-card">
                        <em>Elite Desk</em>
                        <span class="stat-num">{stats['total_apps']}</span>
                        <span class="stat-label"><i class="fas fa-file-contract"></i> Full Apps</span>
                    </div>
                    <div class="stat-card">
                        <em>Momentum</em>
                        <span class="stat-num" style="color: #4ade80;">+{stats['momentum']}</span>
                        <span class="stat-label"><i class="fas fa-bolt"></i> Leads (24H)</span>
                    </div>
                    <div class="stat-card">
                        <em>Active Reach</em>
                        <span class="stat-num" style="font-size: 20px; padding: 14px 0;">{stats['hotspot']}</span>
                        <span class="stat-label"><i class="fas fa-map-marker-alt"></i> Top Location</span>
                    </div>
                </div>

                <!-- ══ GLOBAL LEAD HEATMAP ══ -->
                <div class="glass-panel" style="margin-bottom: 40px; padding: 40px; position: relative; min-height: 400px; overflow: hidden; background: var(--panel-bg); border: 2px solid var(--glass-border); border-radius: 25px;">
                    <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 20px; position: relative; z-index: 5;">
                        <div>
                            <h3 style="color: var(--gold); font-family: 'Cinzel'; font-size: 18px; margin-bottom: 8px; letter-spacing: 2px; text-transform: uppercase;">Global Lead Heatmap</h3>
                            <p style="color: var(--text-muted); font-size: 13px;">Market density pulse indicators across geographic financial hubs.</p>
                        </div>
                        <div style="background: rgba(212,168,83,0.1); padding: 8px 16px; border-radius: 12px; border: 1px solid var(--gold-thin);">
                            <span style="color: var(--gold); font-size: 9px; font-weight: 800; text-transform: uppercase; letter-spacing: 1.5px;">Elite Command Mode</span>
                        </div>
                    </div>
                    
                    <div id="leadMap" style="width: 100%; height: 350px; background: url('https://upload.wikimedia.org/wikipedia/commons/e/ec/World_map_blank_without_borders.svg') center/contain no-repeat; opacity: 0.12; filter: invert(1) brightness(0.6); margin-top: 20px;"></div>
                    <div id="mapOverlay" style="position: absolute; inset: 120px 40px 40px; pointer-events: none;"></div>

                    <script>
                        (function() {{
                            const locationData = {stats['location_json']};
                            const overlay = document.getElementById('mapOverlay');
                            if(!overlay) return;

                            // High-tech Coordinate Library for Financial Hubs
                            const COORDS = {{
                                "Limbdi": {{ x: 70.3, y: 53.6 }},
                                "Mumbai": {{ x: 71.5, y: 55.5 }},
                                "Surat": {{ x: 70.8, y: 54.2 }},
                                "Dubai": {{ x: 62.2, y: 53.5 }},
                                "London": {{ x: 48.5, y: 35.2 }},
                                "New York": {{ x: 28.2, y: 42.1 }},
                                "Singapore": {{ x: 78.5, y: 64.2 }},
                                "Abu Dhabi": {{ x: 61.8, y: 54.1 }},
                                "Ahmedabad": {{ x: 70.5, y: 52.8 }},
                                "Zurich": {{ x: 51.2, y: 38.5 }},
                                "Doha": {{ x: 62.8, y: 54.5 }},
                                "Kenya": {{ x: 58.5, y: 68.2 }},
                                "Riyadh": {{ x: 60.5, y: 55.2 }},
                                "Gujarat": {{ x: 70.8, y: 54.2 }}
                            }};

                            Object.keys(locationData).forEach(loc => {{
                                const cleanLoc = loc.split(',')[0].split(' ')[0].trim();
                                const pos = COORDS[cleanLoc];
                                if (pos) {{
                                    const pin = document.createElement('div');
                                    pin.className = 'map-pin';
                                    pin.style.left = pos.x + '%';
                                    pin.style.top = pos.y + '%';
                                    pin.innerHTML = `
                                        <div class="pin-pulse"></div>
                                        <div class="pin-dot"></div>
                                        <div class="pin-label">${{loc}} (${{locationData[loc]}})</div>
                                    `;
                                    overlay.appendChild(pin);
                                }}
                            }});
                        }})();
                    </script>
                    
                    <style>
                        .map-pin {{ position: absolute; width: 14px; height: 14px; transform: translate(-50%, -50%); pointer-events: auto; cursor: crosshair; z-index: 10; }}
                        .pin-dot {{ width: 8px; height: 8px; background: var(--gold); border-radius: 50%; box-shadow: 0 0 15px var(--gold); border: 2px solid #000; }}
                        .pin-pulse {{ 
                            position: absolute; inset: -15px; border: 2px solid var(--gold); border-radius: 50%;
                            animation: pin-pulse 2.5s infinite ease-out; opacity: 0;
                        }}
                        @keyframes pin-pulse {{
                            0% {{ transform: scale(0.4); opacity: 0.9; }}
                            100% {{ transform: scale(4); opacity: 0; }}
                        }}
                        .pin-label {{ 
                            position: absolute; top: 18px; left: 50%; transform: translateX(-50%);
                            white-space: nowrap; font-size: 10px; font-weight: 800; color: #000;
                            background: var(--gold); padding: 5px 12px; border-radius: 8px;
                            opacity: 0; transition: all 0.4s cubic-bezier(0.165, 0.84, 0.44, 1); pointer-events: none;
                            box-shadow: 0 10px 25px rgba(0,0,0,0.5);
                        }}
                        .map-pin:hover .pin-label {{ opacity: 1; transform: translateX(-50%) translateY(5px); }}
                        .map-pin:hover .pin-dot {{ transform: scale(1.5); background: #fff; }}
                    </style>
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
                            if (rows[i].classList.contains('expand-row')) continue;
                            const text = rows[i].innerText.toLowerCase();
                            rows[i].style.display = text.includes(term) ? '' : 'none';
                        }}
                    }});
                }}

                // Tap-to-expand: inject expand rows after each data row
                document.addEventListener('DOMContentLoaded', function() {{
                    document.querySelectorAll('tbody').forEach(tbody => {{
                        const dataRows = Array.from(tbody.querySelectorAll('tr'));
                        dataRows.forEach(row => {{
                            const cells = row.querySelectorAll('td');
                            if (cells.length < 2) return;
                            const name = cells[0]?.innerText || '';
                            const email = cells[1]?.innerText || '';
                            const mobile = cells[2]?.innerText || '';
                            const source = cells[3]?.innerText || '';
                            const date = cells[4]?.innerText || '';
                            // Create hidden expand row
                            const expandRow = document.createElement('tr');
                            expandRow.className = 'expand-row';
                            expandRow.innerHTML = `<td colspan="6">📧 <strong>Email:</strong> ${{email}}<br>📱 <strong>Mobile:</strong> ${{mobile}}<br>📅 <strong>Date:</strong> ${{date}}<br>🏷️ <strong>Source:</strong> ${{source}}</td>`;
                            row.classList.add('data-row');
                            row.insertAdjacentElement('afterend', expandRow);
                            // Toggle on click
                            row.addEventListener('click', function(e) {{
                                if (e.target.classList.contains('btn-delete') || e.target.closest('.btn-delete')) return;
                                expandRow.classList.toggle('open');
                            }});
                        }});
                    }});
                }});

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
            <footer style="margin-top: 60px; padding: 20px; text-align: center; border-top: 1px solid var(--glass-border); font-size: 11px; letter-spacing: 1px; color: var(--text-muted); opacity: 0.8;">
                WHITEFLOWS ELITE COMMAND CENTER &bull; ENGINEERED BY <a href="https://www.linkedin.com/company/amburax/about/" target="_blank" style="color: var(--gold); text-decoration: none; font-weight: 700;"><i class="fab fa-linkedin" style="margin-right: 4px;"></i>AMBURAX</a>
            </footer>
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
    verify_jwt(request)
    db = get_db(request)
    
    try:
        if payload.type == "lead":
            await db.execute("DELETE FROM leads WHERE id = ?", (payload.id,))
        elif payload.type == "app":
            await db.execute("DELETE FROM applications WHERE app_id = ?", (payload.id,))
        return {"success": True}
    except Exception as e:
        log(f"[ERROR] Delete failed: {e}")
        return {"success": False, "error": str(e)}

async def generate_export_csv_string(db: DBAdapter) -> str:
    """Generates a CSV string containing all leads and applications."""
    try:
        # Fetch data
        leads_raw = await db.fetch_all("SELECT 'LEAD' as type, name, email, mobile, created_at, json_data FROM leads")
        apps_raw = await db.fetch_all("SELECT 'APP' as type, applicant_name, email, mobile, created_at, json_data FROM applications")

        combined = leads_raw + apps_raw
        
        # Sort combined list by Type and then by internal Form Name
        def get_sort_source(row):
            try:
                js = json.loads(row[5]) if row[5] else {}
                return str(js.get('form_name', 'Consultation'))
            except: return 'Consultation'
        
        combined.sort(key=lambda r: (r[0], get_sort_source(r)))
        
        all_keys = set()
        for row in combined:
            try:
                extra_data = json.loads(row[5]) if row[5] else {}
                for k in extra_data.keys():
                    if k not in ["name", "applicant_name", "email", "mobile", "submitted_at", "type"]:
                        all_keys.add(str(k).replace('_', ' ').title())
            except: pass

        headers = ["Type", "Name", "Email", "Mobile", "Timestamp"] + sorted(list(all_keys))
        
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=headers)
        writer.writeheader()
        
        current_category = None
        for row in combined:
            rtype = row[0]
            cat = get_sort_source(row) if rtype == 'LEAD' else "FULL APPLICATION"
            
            if cat != current_category:
                writer.writerow({h: "" for h in headers}) # Spacer
                writer.writerow({headers[0]: f"--- {cat.upper()} ---"}) 
                current_category = cat

            item = {
                "Type": rtype, "Name": row[1], "Email": row[2], 
                "Mobile": str(row[3]), "Timestamp": row[4].replace('T', ' ')[:19] if row[4] else ""
            }
            
            try:
                extra_data = json.loads(row[5]) if row[5] else {}
                for k, v in extra_data.items():
                    nice_key = str(k).replace('_', ' ').title()
                    if nice_key in headers: item[nice_key] = str(v)
            except: pass
            
            writer.writerow({h: item.get(h, "") for h in headers})
        
        return output.getvalue()
    except Exception as e:
        log(f"[ERROR] generate_export_csv_string failed: {e}")
        raise e

@app.get("/admin/export-csv")
async def export_csv(request: Request):
    """Generates a CSV of all leads and applications with JSON data fully parsed into columns."""
    verify_jwt(request)
    db = get_db(request)
    try:
        csv_string = await generate_export_csv_string(db)
        filename = f"whiteflows_export_{datetime.now().strftime('%Y%m%d')}.csv"
        return StreamingResponse(
            io.BytesIO(csv_string.encode()),
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


async def dispatch_email(to_email: str, subject: str, html: str, attachments: list = None):
    """
    Main Email Dispatcher:
    1. Primary: Resend API
    2. Fallback: Brevo API
    """
    attachments = attachments or []
    # 1. Resend API
    if await send_via_resend_api(to_email, subject, html, attachments):
        return True
    
    # 2. Brevo API
    if await send_via_brevo_api(to_email, subject, html, attachments):
        return True
    
    log(f"  [CRITICAL] All email dispatch methods failed for {to_email}")
    return False


async def generate_daily_digest_html(db: DBAdapter = None):
    """Gathers intelligence from the last 24 hours and builds a professional summary."""
    db = db or get_db()
    try:
        now = datetime.now()
        yesterday = now - timedelta(days=1)
        
        # Leads Logic
        leads = await db.fetch_all(
            "SELECT id, name, email, json_data FROM leads WHERE created_at >= ?", 
            (yesterday.isoformat(),)
        )
        
        # Applications Logic
        apps = await db.fetch_all(
            "SELECT app_id, applicant_name, email FROM applications WHERE created_at >= ?", 
            (yesterday.isoformat(),)
        )

        # Categorization Logic
        summary = {}
        for l in leads:
            try:
                js = json.loads(l[3]) if l[3] else {}
                cat = js.get('form_name', 'Consultation')
            except: cat = 'Consultation'
            
            if cat not in summary: summary[cat] = []
            summary[cat].append(f"<li><b>{l[1]}</b> - {l[2]} ({l[3]})</li>")

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


async def send_via_resend_api(to_email: str, subject: str, html: str, attachments: list):
    """Send via Resend HTTP API. Returns True on success, False on failure."""
    import httpx
    if not RESEND_API_KEY: return False
    try:
        url = "https://api.resend.com/emails"
        headers = {
            "Authorization": f"Bearer {RESEND_API_KEY}",
            "Content-Type": "application/json"
        }
        
        resend_attachments = []
        for att in attachments:
            resend_attachments.append({
                "content": base64.b64encode(att["content"]).decode('utf-8'),
                "filename": att["filename"]
            })

        payload = {
            "from": "WhiteFlows <advisory@whiteflowsint.com>",
            "to": [to_email],
            "subject": subject,
            "html": html,
            "attachments": resend_attachments
        }

        async with httpx.AsyncClient() as client:
            resp = await client.post(url, headers=headers, json=payload, timeout=20.0)
            if resp.status_code < 300:
                log(f"  [OK] Resend API Success: {to_email}")
                return True
            else:
                log(f"  [ERROR] Resend API Fail: {resp.text}")
                return False
    except Exception as e:
        log(f"  [ERROR] Resend API exception: {e}")
        return False


async def send_via_brevo_api(to_email: str, subject: str, html: str, attachments: list):
    """Send via Brevo HTTP API. Returns True on success, False on failure."""
    import httpx
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
            "sender": {"name": "WhiteFlows", "email": ADMIN_EMAIL_MAIN},
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


async def send_admin_email_cascade(to_email: str, subject: str, html: str, attachments: list):
    """
    Admin dispatcher using the shared 2-step cascade (Resend -> Brevo API).
    """
    return await dispatch_email(to_email, subject, html, attachments)


async def send_client_confirmation(to_email: str, name: str, ref_id: str, is_app: bool = False):
    """Sends a professional, branded confirmation email to the client."""
    subject = f"WhiteFlows: Confirmation of your {'Application' if is_app else 'Enquiry'} [Ref: {ref_id}]"
    
    # Premium Elegant HTML Template
    html = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <style>
            body {{ font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; background: #F8F7F3; color: #0E0D0B; margin: 0; padding: 0; line-height: 1.6; }}
            .container {{ max-width: 600px; margin: 40px auto; background: #ffffff; border: 1px solid #E5E2D9; border-radius: 8px; overflow: hidden; box-shadow: 0 10px 30px rgba(0,0,0,0.05); }}
            .header {{ background: #0E0D0B; padding: 40px 20px; text-align: center; border-bottom: 4px solid #D4A853; }}
            .content {{ padding: 40px; }}
            .footer {{ background: #F2F0EA; padding: 20px; text-align: center; font-size: 11px; color: #6E6A62; border-top: 1px solid #E5E2D9; }}
            .gold-btn {{ display: inline-block; padding: 14px 30px; background: #D4A853; color: #0E0D0B; text-decoration: none; font-weight: bold; font-size: 12px; letter-spacing: 2px; text-transform: uppercase; margin-top: 25px; border-radius: 2px; transition: background 0.3s; }}
            h1 {{ font-family: serif; color: #D4A853; font-size: 24px; letter-spacing: 1px; margin-bottom: 20px; }}
            .ref-chip {{ background: #F2F0EA; padding: 5px 12px; border-radius: 4px; font-family: monospace; font-weight: bold; color: #3C3A35; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <div style="font-family: serif; color: #D4A853; font-size: 28px; letter-spacing: 3px; font-weight: bold;">WHITEFLOWS</div>
                <div style="color: #A8A49C; font-size: 10px; letter-spacing: 4px; text-transform: uppercase; margin-top: 5px;">International Advisory</div>
            </div>
            <div class="content">
                <h1>Welcome to the Elite Circle</h1>
                <p>Greetings, <strong>{name}</strong>,</p>
                <p>This is to confirm that your <strong>{'application' if is_app else 'enquiry'}</strong> has been securely received by the WhiteFlows International investment desk.</p>
                
                <p style="margin: 30px 0;">
                    Reference ID: <span class="ref-chip">{ref_id}</span>
                </p>

                <p>Our advisory team has been notified and is currently reviewing your details. We pride ourselves on precision and personalized attention; as such, you can expect a formal response from our desk within <strong>24 business hours</strong>.</p>
                
                <p>In the meantime, should you have any immediate concerns, please feel free to reach out via our Elite Advisory Desk on WhatsApp.</p>

                <div style="text-align: center;">
                    <a href="https://wa.me/918866282752?text=Greetings%20WhiteFlows%2C%20I%20am%20interested%20in%20a%20Strategic%20Consultation%20for%20my%20portfolio." class="gold-btn">Connect to Elite Desk</a>
                </div>
            </div>
            <div class="footer">
                <p>&copy; 2026 WhiteFlows International. All Rights Reserved.</p>
                <p>SEBI Registered Investment Advisory | Mumbai & Gujarat, India</p>
                <p style="margin-top: 10px; font-style: italic;">This is an automated confirmation of Receipt. Our primary team will contact you from @whiteflowsint.com for all further documentation.</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    # Send via shared cascade logic
    await dispatch_email(to_email, subject, html, [])
    
    log(f"[AUTO-RESPONDER] Sent confirmation to {to_email} (Ref: {ref_id})")


async def send_database_backup(db: DBAdapter):
    try:
        log("[BACKUP] Initiating backup sequence...")
        timestamp_str = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        attachments = []
        
        # 1. CSV File (Universal)
        try:
            csv_str = await generate_export_csv_string(db)
            attachments.append({"filename": f"whiteflows_backup_{timestamp_str}.csv", "content": csv_str.encode('utf-8')})
        except Exception as e:
            log(f"[WARNING] CSV backup failed: {e}")

        # 2. Local DB Backup (Only if local)
        if not db.is_worker:
            try:
                with open(DATABASE_PATH, "rb") as f:
                    attachments.append({"filename": f"whiteflows_backup_{timestamp_str}.db", "content": f.read()})
            except: pass
            
        subject = f"System Backup: {timestamp_str}"
        html = f"<h3>Weekly Intelligence Backup</h3><p>Data summary for {timestamp_str} attached.</p>"
        
        await dispatch_email(GMAIL_RECEIVER, subject, html, attachments)
        if BACKUP_RECEIVER_EMAIL:
            await dispatch_email(BACKUP_RECEIVER_EMAIL, subject, html, attachments)
            
        log("[BACKUP] Sequence completed.")
        return True
    except Exception as e:
        log(f"[ERROR] Backup failed: {e}")
        return False

async def backup_scheduler_loop(db: DBAdapter = None):
    db = db or get_db()
    if db.is_worker: return
    await asyncio.sleep(10)
    while True:
        try:
            row = await db.fetch_one("SELECT value FROM server_metadata WHERE key = 'last_backup'")
            now = datetime.now()
            if not row or (now - datetime.fromisoformat(row[0])).days >= 3:
                if await send_database_backup(db):
                    await db.execute("INSERT OR REPLACE INTO server_metadata (key, value) VALUES ('last_backup', ?)", (now.isoformat(),))
        except: pass
        await asyncio.sleep(3600)

async def daily_digest_scheduler_loop(db: DBAdapter = None):
    db = db or get_db()
    if db.is_worker: return
    await asyncio.sleep(20)
    while True:
        try:
            now = datetime.now()
            if now.hour == 8:
                today_str = now.strftime('%Y-%m-%d')
                row = await db.fetch_one("SELECT value FROM server_metadata WHERE key = 'last_digest_date'")
                if not row or row[0] != today_str:
                    html = await generate_daily_digest_html(db)
                    if html:
                        await dispatch_email(GMAIL_RECEIVER, f"DAILY DIGEST — {today_str}", html)
                        await db.execute("INSERT OR REPLACE INTO server_metadata (key, value) VALUES ('last_digest_date', ?)", (today_str,))
        except: pass
        await asyncio.sleep(1800)

def validate_environment():
    """Runs a pre-flight check to warn about insecure configurations."""
    warnings = []
    if ADMIN_PASSWORD == 'whiteflows2026':
        warnings.append("[SECURITY WARNING] ADMIN_PASSWORD is still 'whiteflows2026'. Change it before making this public!")
    if 'your-email' in ADMIN_EMAIL_MAIN:
        warnings.append("[SECURITY WARNING] Gmail credentials perfectly match .env.example values. Email cascade will fail over!")
    if not BREVO_API_KEY and not BREVO_SMTP_KEY:
        warnings.append("[CONFIG WARNING] No Brevo keys provided. System relying solely on Gmail 500 emails/day quota.")
        
    for w in warnings:
        log(w)
    if warnings:
        log("[SYSTEM] Please review the above warnings. Plausible to ignore only for local testing.")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8001))
    uvicorn.run(app, host="0.0.0.0", port=port)

