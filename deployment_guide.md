# Deployment Guide: WhiteFlows Self-Hosted ("Everything Own")

This guide provides step-by-step instructions for deploying WhiteFlows on your own **Virtual Private Server (VPS)** using Ubuntu, Nginx, and Docker.

---

## 1. Server Prerequisites
- **OS**: Ubuntu 22.04 LTS (Recommended)
- **Specs**: 1 vCPU, 1GB RAM (Minimum)
- **Ports**: Ensure ports `80`, `443`, and `22` are open.

## 2. Server Environment Setup
Connect to your VPS via SSH and run:

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker & Docker Compose
sudo apt install docker.io docker-compose -y
sudo systemctl start docker
sudo systemctl enable docker
```

## 3. Upload & Configure
1. Upload the `WhiteFlows/` directory to your server (e.g., to `/home/ubuntu/whiteflows`).
2. Create or edit the `.env` file on the server:

```bash
nano .env
```

**Fill in your credentials:**
```env
GMAIL_SENDER=murtazajd53@gmail.com
GMAIL_PASSWORD=udmp apfh jjcp kiyz
GMAIL_RECEIVER=mra8135100@gmail.com
EMAIL_PROVIDER=smtp
```

## 4. Launch the Application
Run the following command to build and start the container in detached mode:

```bash
sudo docker-compose up -d --build
```
The app will now be running on `http://localhost:8001`.

## 5. Nginx Reverse Proxy (SSL Setup)
To map your domain (e.g., `app.whiteflows.com`) and add HTTPS:

```bash
# Install Nginx and Certbot
sudo apt install nginx certbot python3-certbot-nginx -y

# Create Nginx Config
sudo nano /etc/nginx/sites-available/whiteflows
```

**Paste this config (replace `yourdomain.com`):**
```nginx
server {
    listen 80;
    server_name yourdomain.com;

    location / {
        proxy_pass http://localhost:8001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

```bash
# Enable the site
sudo ln -s /etc/nginx/sites-available/whiteflows /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx

# Get SSL Certificate
sudo certbot --nginx -d yourdomain.com
```

## 6. Verification Checklist
- [ ] Accessible via `https://yourdomain.com`
- [ ] Forms submit successfully
- [ ] 5 Uploads + 1 Receipt = 6 Attachments (No duplicates)
- [ ] Logs can be viewed via `sudo docker-compose logs -f`

---
> [!TIP]
> Since you are hosting this yourself, you do not need to worry about Cloudflare Worker limits. The **Gmail SMTP** logic we built will work perfectly as long as your VPS provider allows outgoing traffic on port 465/587.
