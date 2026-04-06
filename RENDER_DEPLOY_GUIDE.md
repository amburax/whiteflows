# 🦅 WhiteFlows Elite: Render Deployment Guide

This guide ensures your platform is deployed with **bank-grade security** and **data persistence** using the custom configuration we've built.

---

## 🛠️ Step 1: Push Your Code
Ensure you have pushed the latest version to GitHub (all set! I just did this for you).
- Branch: `main`
- Status: **Ready for Deployment** 🚀

---

## ☁️ Step 2: Render Configuration

1.  **Log in**: Access your [Render Dashboard](https://dashboard.render.com).
2.  **New Blueprint**: Click the **"New"** button (top right) and select **"Blueprint"**.
3.  **Connect Repo**: Find your `WhiteFlows` repository and click **"Connect"**.
4.  **Instance Name**: Give your project a name (e.g., `whiteflows-prod`).
5.  **Service Name**: Ensure the service name matches `whiteflows-elite` (it should default correctly).

---

## 🗝️ Step 3: Secret Configuration

Render will detect the `render.yaml` file and prompt you for the following sensitive fields. **Copy these from your local `.env` file:**

| Variable | Description |
| :--- | :--- |
| `ADMIN_PASSWORD` | The password for your `/admin-dashboard-logs` dashboard. |
| `GMAIL_SENDER` | Your service email (e.g., `office@whiteflows.com`). |
| `GMAIL_PASSWORD` | Your **16-digit Gmail App Password**. |
| `GMAIL_RECEIVER` | Where admin notifications will be sent. |
| `BACKUP_RECEIVER_EMAIL` | (Optional) Email specifically for DB backups. |

> [!IMPORTANT]
> **JWT_SECRET**: You can leave this blank! Render will automatically generate a random, secure key for your sessions.

---

## 🔒 Step 4: Persistent Disk (Elite Feature)

Because our setup uses a **Persistent Disk** to keep your leads and applications safe:
1.  Render will prompt you that this requires the **"Standard" ($7/mo)** plan.
2.  Confirm the mount path is `/var/lib/whiteflows` (already set in our code).
3.  This ensures that when you update your code or restart the server, **not a single lead is lost.**

---

## 📊 Step 5: Verification

Once the deployment status turns **"Live"** (Green), verify your platform:
1.  **Frontend**: Visit `https://your-app-name.onrender.com`.
2.  **Admin**: Visit `https://your-app-name.onrender.com/admin-dashboard-logs`.
3.  **Test Lead**: Submit a test enquiry to confirm the email cascade and database are active.

---

### 🛡️ Post-Launch Tip: Custom Domain
For the ultimate premium experience, connect your custom domain (e.g., `whiteflows.com`) in the **"Settings"** tab of your Render Web Service.

**WhiteFlows Elite Platform**  
*Built for Global Reach. Secured for Ultimate Privacy.* 🚀💎👑
