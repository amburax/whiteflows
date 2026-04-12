# WhiteFlows Master Blueprint
## The Definitive Technical & Operational Manual
**Version**: 4.0 "Elite"  
**Engineered by**: Amburax  
**Architecture**: Stateless / Resilient / High-Performance  

---

## 1. Executive Summary & DNA
WhiteFlows is a high-performance, business-grade investment advisory platform designed for scalability, security, and absolute reliability. Unlike standard websites, WhiteFlows is built as a **"Stateless Professional Application"**, meaning it does not rely on temporary server memory, making it immune to common crash types and easy to host globally.

### Core Philosophy
- **Speed First**: Sub-500ms response times for global transactions.
- **Resilience**: A "Mail Never Fails" architecture ensures no business lead is lost.
- **Security**: Bank-grade encryption for admin access and document transmission.

---

## 2. Global Frontend Architecture (The Client Experience)

### 2.1. Institutional Document Vault
The most secure entrance to WhiteFlows. It handles sensitive client identification (KYC) documents.
- **Technology**: Vanilla JS with Hardware-Accelerated Validation.
- **Security Envelope**: Enforces a strict **3MB file size limit** per document to ensure email servers accept the attachments without bouncing.
- **Real-time Sanitization**: Files are processed in-browser to prevent malicious code from reaching the server.

### 2.2. samyak & Halaal Portfolios
Dynamic, interactive strategy selection cards. 
- **Animation Engine**: Uses AOS (Animate On Scroll) for a premium, luxury feel.
- **Logic**: Each strategy triggers a specific workflow, routing the client to either a quick enquiry or a full institutional application.

### 2.3. Client Receipt Engine (The "Wealth Receipt")
Upon submission, the system generates a professional PDF receipt **instantly** on the client's screen.
- **Technology**: `jsPDF` library.
- **Process**: The PDF is built using the client's own computer power, converted to a Base64 string, and sent to the server as a finalized document.

---

## 3. The Backend Engine (The Resilience Cascade)

### 3.1. FastAPI Infrastructure
The backend is powered by **FastAPI (Python)**, one of the fastest modern web frameworks.
- **Asynchronous Execution**: The server can handle hundreds of users simultaneously without slowing down.
- **Background Workers**: When a form is submitted, the server sends a "Success" message to the user instantly, and then finishes the heavy work (sending emails, saving to DB) in the background.

### 3.2. The Triple-Layer Email Cascade (Resilience)
Communication is the lifeblood of the business. WhiteFlows uses a **3-step fail-over system** for every single alert:
1.  **Primary**: Brevo SMTP (Global Relay).
2.  **Secondary (Fail-over)**: Brevo REST API (If SMTP ports are blocked).
3.  **Tertiary (Last Resort)**: Gmail SMTP (Direct fallback).
*If one layer fails, the next tackles the task instantly. No lead left behind.*

### 3.3. Geolocation & Intelligence
Every enquiry is tagged with the sender's physical location. 
- **Privacy**: Only city/region level data is logged.
- **Purpose**: Allows leadership to see which regions (Dubai, London, Ahmedabad) are driving the most wealth interest.

---

## 4. Admin Command Center (Management Hub)

### 4.1. Real-time Dashboard
A private, secure area for the leadership to manage the firm's growth.
- **Security**: Protected by JWT (JSON Web Tokens) with a 30-minute auto-expiry.
- **Intelligence**: Heatmaps showing lead momentum and hot geographic zones.
- **Global Search**: Instantly filter thousands of leads by name, email, or date.

### 4.2. Secure Data Management
- **Permanent Deletion**: Admins can securely wipe records after onboarding is complete.
- **CSV Export**: One-click generation of lead spreadsheets for CRM integration.

---

## 5. Persistence & Business Continuity

### 5.1. SQLite Core
The system uses an **SQLite database**, which is a single-file database known for absolute stability and zero corruption risk.

### 5.2. Render Persistent Disk (Data Safety)
WhiteFlows is deployed with a **1GB Persistent Disk**. 
- Even if the server is restarted or updated, the database (`whiteflows.db`) lives on a separate physical drive that never resets.

### 5.3. Automated Backup Protocol
Managed by a background task that runs every hour:
- **3-Day Cycle**: Every 3 days, the system creates a full backup of the database and lead data.
- **Redundant Storage**: The backup is emailed to the primary admin and a secondary backup vault email.
- **Intelligence Digest**: Every morning at 8:00 AM, the leader receives a "Daily Intelligence Digest" summarizing all new business from the last 24 hours.

---

## 6. Heritage & Delivery
**Engineered by**: Amburax  
**Platform**: WhiteFlows International 2026  
**Status**: Production Ready  

> [!IMPORTANT]
> This platform is technically "Stateless" yet "Persistent." It provides the security of the cloud with the ownership of a local server.

---
© 2026 WHITEFLOWS INTERNATIONAL · GUJARAT, INDIA · ALL RIGHTS RESERVED
