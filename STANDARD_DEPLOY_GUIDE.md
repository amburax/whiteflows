# 🏛️ WhiteFlows Elite: Standard Server Deployment Guide

This guide covers the deployment of the WhiteFlows platform as a **Standard Python Application**. This setup is designed for maximum stability, utilizing a local SQLite database and modern API-based email dispatching (Resend + Brevo).

---

## 🏗️ Step 1: Environment Setup

1.  **Clone the Repository**: Ensure your code is on your server (VPS, local machine, etc.).
2.  **Install Python 3.12+**: Ensure you have the latest Python version.
3.  **Create a Virtual Environment**:
    ```bash
    python -m venv .venv
    source .venv/bin/activate  # Linux/macOS
    .venv\Scripts\activate     # Windows
    ```
4.  **Install Dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

---

## 🗝️ Step 2: Configure Secrets

Create a `.env` file in the root directory (copy from `.env.example`).

| Variable | Description |
| :--- | :--- |
| `ADMIN_PASSWORD` | Secure password for the admin dashboard. |
| `GMAIL_SENDER` | Your verified sender email (must match Resend/Brevo verified domains). |
| `GMAIL_RECEIVER` | Primary admin email for lead alerts. |
| `RESEND_API_KEY` | Your **Resend** API Key (Primary Sender). |
| `BREVO_API_KEY` | Your **Brevo** API Key (Secondary Backup). |
| `DATABASE_PATH` | (Optional) Path to your `whiteflows.db`. Defaults to local directory. |

---

## 🚀 Step 3: Launching the Platform

### Option A: Direct Run (Development)
```bash
python server.py
```
The server will start at `http://0.0.0.0:8001`.

### Option B: Production (Background)
Using `PM2` is recommended for automatic restarts:
```bash
pm2 start "python server.py" --name whiteflows-prod
```

---

## ☁️ Step 4: Making it Public (Cloudflare)

### Using Cloudflare Tunnel (Recommended)
This is the most secure way to expose your local or VPS server without opening firewall ports.

1.  **Install `cloudflared`** on your server.
2.  **Authenticate**: `cloudflared tunnel login`.
3.  **Create Tunnel**: `cloudflared tunnel create whiteflows`.
4.  **Configure**: Point your tunnel to `http://localhost:8001`.
5.  **Route**: Map your domain (e.g., `whiteflows.com`) to the tunnel in your Cloudflare dashboard.

---

## 💾 Step 5: Data Persistence & Backups

- **Local DB**: Your data lives in `whiteflows.db`. **Never delete this file.**
- **Automatic Backups**: The system sends a full database backup and CSV to your `GMAIL_RECEIVER` every **24 hours**.
- **Daily Digest**: Every morning at **8:00 AM**, you will receive an "Intelligence Report" summarizing new activity.

---

### 🛡️ Security Note
Ensure your `ADMIN_PASSWORD` is significantly complex. All sensitive data is encrypted/hashed, and the administrative console requires this password for access.

**WhiteFlows Elite System**  
*Pure Performance. Absolute Privacy. Zero Compromise.* 🚀💎👑
