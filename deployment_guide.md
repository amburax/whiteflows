# WhiteFlows Elite: Global Deployment Guide 🚀🌍

This guide explains how to take your WhiteFlows Elite platform from your local machine to the global web using **Render** or **Hostinger**.

---

## 📋 Pre-Deployment Checklist
Before you begin, ensure you have:
1.  **GitHub Access**: Your code must be pushed to your repository.
2.  **SMTP Credentials**: Your Gmail App Password or Brevo API Key ready.
3.  **Domain Name**: Purchased through Hostinger or Cloudflare.

---

## 1. Option A: Deploying on Render (Easiest) ☁️
Render is perfect for quick launches and automatic updates.

1.  **Create an Account**: Log in to [Render.com](https://render.com).
2.  **New Web Service**: Click `New` > `Web Service`.
3.  **Connect GitHub**: Select your `WhiteFlows` repository.
4.  **Settings**:
    - **Runtime**: `Python 3`
    - **Build Command**: `pip install -r requirements.txt`
    - **Start Command**: `gunicorn -w 4 -k uvicorn.workers.UvicornWorker server:app --bind 0.0.0.0:$PORT`
5.  **Environment Variables**: Click `Advanced` > `Add Environment Variable`. Add ALL keys from your `.env` (ADMIN_PASSWORD, GMAIL_SENDER, etc.).
6.  **Deploy**: Click `Create Web Service`. Your site will be live in minutes!

---

## 2. Option B: Deploying on Hostinger VPS (Elite Performance) 🏗️
Recommended for maximum control and speed.

### Step 1: Server Preparation
1.  **Access VPS**: Log in via SSH: `ssh root@your_server_ip`.
2.  **Install Python**: 
    - `sudo apt update && sudo apt install python3-pip python3-venv git -y`

### Step 2: Code Setup
1.  **Clone Repo**: `git clone https://github.com/amburax/whiteflows.git`
2.  **Enter Folder**: `cd whiteflows`
3.  **Create Environment**: 
    - `python3 -m venv venv`
    - `source venv/bin/activate`
    - `pip install -r requirements.txt`

### Step 3: Persistence with PM2
To keep the server running 24/7 after you close the terminal:
1.  **Install PM2**: `sudo npm install pm2 -g`
2.  **Launch App**: `pm2 start "python3 server.py" --name whiteflows`
3.  **Save List**: `pm2 save && pm2 startup`

---

## 3. Secret Configuration (Environment Variables) 🗝️
Since we are using the **Safe Method** (where `.env` is NOT on GitHub), you must manually tell your server what your passwords and API keys are. 

### **A. How to Configure on Render:**
1.  Log in to your **Render Dashboard**.
2.  Click on your **Web Service** name.
3.  On the left menu, click **Environment**.
4.  Click **Add Environment Variable** and copy your keys from your local `.env` exactly like this:
    - **Key**: `GMAIL_SENDER` | **Value**: `whiteflowsinc@gmail.com`
    - **Key**: `GMAIL_PASSWORD` | **Value**: `zbhl obsm ycsb yjib`
    - ... (add all other keys from your .env).
5.  Click **Save Changes**. Render will automatically restart and your emails will start working!

### **B. How to Configure on Hostinger (VPS):**
1.  Connect to your VPS via SSH (`ssh root@ip`).
2.  Navigate to your folder: `cd whiteflows`.
3.  Create the file: `nano .env`.
4.  Paste your entire local `.env` content into the terminal.
5.  Press **CTRL + O** (to save) then **Enter**, then **CTRL + X** (to exit).
6.  Restart your app: `pm2 restart whiteflows`.

---

## 4. Post-Deployment: Domain & SSL 🛡️
- **Cloudflare**: Connect your domain to Cloudflare and point the **A Record** to your server IP. Enable **"Full (Strict)" SSL**.
- **Port Forwarding**: Ensure port `8001` (or your custom port) is open in your Hostinger firewall.

---

**WhiteFlows Elite Platform**  
*Built for Global Reach. Secured for Ultimate Privacy.* 🚀📈👑
