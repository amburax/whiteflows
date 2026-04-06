# WhiteFlows Elite: Master Admin Guide 🦅👑

Welcome to your "State-of-the-Art" Lead Intelligence Platform. This guide covers every feature from A to Z to ensure you get the most out of your new Command Center.

---

## 1. Access & Security 🔒
- **Admin Dashboard**: Accessible at `/admin-dashboard-logs`.
- **Bank-Grade JWT**: Your session is secured with a JSON Web Token that **automatically expires every 30 minutes**. If you are inactive, the system will log you out for security.
- **Login Credentials**: Managed via your `.env` file (`ADMIN_PASSWORD`).

## 2. The Elite Command Center (UI/UX) ✨
- **Glassmorphism Aesthetic**: Your dashboard uses a "Frosted Glass" design with 12px blur layers for a modern, high-end feel.
- **Theme Toggle**: Switch between **Dark Mode** (Default) and **Bold Light Mode** using the sun/moon icon in the top-right. Your preference is saved locally.
- **Live Connection Pulse**: The pulsating green dot indicates your server is live and actively monitoring for leads.
- **Auto-Refresh**: The dashboard automatically refreshes every **30 seconds** to show new entries in real-time.

## 3. Lead Intelligence & Geolocation 🌍
- **Automatic IP Mapping**: Every time a lead is submitted, the server captures the user's IP and maps it to their **Physical Location** (City, Country, ISP). 
- **Visibility**: This data is shown in each lead's row, allowing you to see exactly where your traffic is coming from globally.

## 4. Categorized Management 🗂️
Your leads are automatically sorted into five specialized tables based on the originating form:
1. **Retail/HNI Consult**
2. **Project Funding**
3. **The Ocean Ecosystem**
4. **Institutional/Ultra-HNI**
5. **Scale-Up Enquiry**
6. **Other Enquiries** (Catch-all for miscellaneous pings)

*High-priority **Full Applications** are held in their own dedicated section at the bottom.*

## 5. Automated Intelligence Reports 📋
- **Daily Digest (8:00 AM)**: Every morning, you will receive a professional HTML email summarizing all leads from the last 24 hours.
- **Daily Backups**: The system automatically triggers a full database backup once a week (or upon manual request) and emails it to your admin address.

## 6. Data Export (Excel/CSV) 📊
- **Smart-Sorted CSV**: Clicking "Export CSV" generates an organized file where all leads are **grouped by their form source**. 
- **Visual Partitioning**: The file includes category header rows (e.g., `--- PROJECT FUNDING ---`) making it instantly readable in Excel.

## 7. Search & Deletion 🔍🗑️
- **Dynamic Live Search**: Uses the top-bar search to scan all tables simultaneously. It filters by Name, Email, Mobile, or Date in real-time.
- **Secure Deletion**: Uses a luxury-styled confirmation modal. Deleting a record is **permanent** and follows strict JWT verification protocols.

## 8. GitHub Maintenance 🛠️
To push new updates to your repository:
1. `git add .`
2. `git commit -m "Your update message"`
3. `git push origin main` (You will need your Personal Access Token).

---

**WhiteFlows Elite Platform v1.0**  
*Built for Global Reach. Secured for Ultimate Privacy.* 🚀📈👑
