# WhiteFlows International

SEBI Registered Investment Advisory website.

## What Changed (v4.0)

**Problem:** `fpdf2` (Python PDF library) is not supported in Cloudflare Workers.

**Solution:** PDF generation moved to the browser using **jsPDF** (loaded via CDN — no install needed).

- The browser generates the Certificate of Application PDF client-side
- The PDF is sent to the server as base64 in the request payload
- The server receives the ready-made PDF and attaches it to emails
- No Python PDF libraries required — fully Cloudflare compatible

## Setup

1. Copy `.env.example` to `.env` and fill in your Gmail credentials
2. For Cloudflare: set secrets via `wrangler secret put GMAIL_SENDER` etc.

## Running Locally

```bash
pip install -r requirements.txt
python server.py
```

Open: http://localhost:8001

## Deploying to Cloudflare Workers

```bash
wrangler deploy
wrangler secret put GMAIL_SENDER
wrangler secret put GMAIL_PASSWORD
wrangler secret put GMAIL_RECEIVER
```

## Deploying to Render.com (full Python support)

1. Connect repo to Render
2. Build command: `pip install -r requirements.txt`
3. Start command: `python server.py`
4. Set environment variables in Render dashboard
