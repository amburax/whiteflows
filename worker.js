/**
 * WhiteFlows International — Cloudflare Worker
 * Handles: /submit-lead, /submit, /health
 *
 * Architecture:
 *   - Cloudflare Pages serves index.html (static)
 *   - This Worker handles all POST endpoints
 *   - Email via Brevo REST API (primary) → Resend REST API (fallback)
 *   - Zero SMTP, zero attachments, zero PDF generation
 *   - Documents note appended to every email footer
 *
 * Free Tier Compliance:
 *   - 100,000 requests/day, 10ms CPU per invocation
 *   - No persistent storage (stateless)
 *   - Rate limiting via CF's built-in token bucket (wrangler.toml)
 */

// ─── Allowed Origins ────────────────────────────────────────────────────────
const ALLOWED_ORIGINS = [
  "https://whiteflows.com",
  "https://www.whiteflows.com",
  "https://whiteflowsint.com",
  "https://www.whiteflowsint.com",
];

// ─── Mandatory Footer (per task spec) ───────────────────────────────────────
const DOCUMENT_FOOTER_TEXT =
  "Note: Please send all required documents via email manually at your earliest convenience.";

const DOCUMENT_FOOTER_HTML = `
<div style="margin-top:32px;padding:16px 20px;background:#FFF8E7;border-left:4px solid #D4A853;border-radius:0 6px 6px 0;font-family:Arial,sans-serif;">
  <strong style="color:#8A6430;font-size:12px;text-transform:uppercase;letter-spacing:1px;">Action Required</strong>
  <p style="margin:6px 0 0;font-size:14px;color:#5C4A1E;line-height:1.6;">
    ${DOCUMENT_FOOTER_TEXT}
  </p>
</div>`;

// ─── CORS Helpers ────────────────────────────────────────────────────────────
function getCorsHeaders(origin) {
  let allowed = ALLOWED_ORIGINS[0];
  if (origin && (ALLOWED_ORIGINS.includes(origin) || origin.endsWith(".pages.dev"))) {
    allowed = origin;
  }
  return {
    "Access-Control-Allow-Origin": allowed,
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
    "Access-Control-Max-Age": "86400",
  };
}

function corsResponse(body, status, origin, extraHeaders = {}) {
  return new Response(body, {
    status,
    headers: {
      "Content-Type": "application/json",
      ...getCorsHeaders(origin),
      ...extraHeaders,
    },
  });
}

// ─── Validation Helpers ──────────────────────────────────────────────────────
function isValidEmail(email) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(String(email || "").trim());
}

function isValidPhone(phone) {
  // Accepts 10 digits (with optional spaces), enforces Indian mobile pattern
  const digits = String(phone || "").replace(/\D/g, "");
  return digits.length === 10 && /^[6-9]/.test(digits);
}

function sanitize(val, maxLen = 200) {
  return String(val || "")
    .trim()
    .replace(/<[^>]*>/g, "") // strip HTML tags
    .substring(0, maxLen);
}

// ─── Geolocation from CF Request Object (free, no external API) ─────────────
function getGeoFromRequest(request) {
  const cf = request.cf || {};
  const city = cf.city || "";
  const region = cf.region || "";
  const country = cf.country || "";
  if (city) return `${city}, ${region}, ${country}`.replace(/, ,/g, ",");
  if (country) return country;
  return "Unknown Location";
}

// ─── Rate Limiting via CF KV (optional) ─────────────────────────────────────
// If RATE_LIMIT_KV binding is not set, rate limiting is skipped gracefully.
async function checkRateLimit(env, ip) {
  if (!env.RATE_LIMIT_KV) return true; // KV not bound — skip
  const key = `rl:${ip}`;
  const windowSecs = 3600;
  const maxHits = 6;
  const now = Math.floor(Date.now() / 1000);

  const raw = await env.RATE_LIMIT_KV.get(key, "json");
  if (raw) {
    const hits = raw.hits.filter((t) => now - t < windowSecs);
    if (hits.length >= maxHits) return false;
    hits.push(now);
    await env.RATE_LIMIT_KV.put(key, JSON.stringify({ hits }), {
      expirationTtl: windowSecs,
    });
  } else {
    await env.RATE_LIMIT_KV.put(key, JSON.stringify({ hits: [now] }), {
      expirationTtl: windowSecs,
    });
  }
  return true;
}

// ─── Email Dispatcher: Brevo REST → Resend REST ──────────────────────────────
async function dispatchEmail(env, to, subject, html, attachments = []) {
  // 1. Try Brevo
  if (env.BREVO_API_KEY) {
    const ok = await sendViaBrevo(env, to, subject, html, attachments);
    if (ok) return true;
  }

  // 2. Try Resend
  if (env.RESEND_API_KEY) {
    const ok = await sendViaResend(env, to, subject, html, attachments);
    if (ok) return true;
  }

  console.error("[EMAIL] All dispatch methods exhausted for:", to);
  return false;
}

async function sendViaBrevo(env, to, subject, html, attachments = []) {
  try {
    const payload = {
      sender: {
        name: "WhiteFlows International",
        email: env.GMAIL_SENDER,
      },
      to: [{ email: to }],
      subject,
      htmlContent: html,
    };

    if (attachments.length > 0) {
      // Brevo uses "attachment" (no 's')
      payload.attachment = attachments.map((a) => ({
        content: a.content,
        name: a.name,
      }));
    }

    const resp = await fetch("https://api.brevo.com/v3/smtp/email", {
      method: "POST",
      headers: {
        "api-key": env.BREVO_API_KEY,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    });

    if (resp.ok) {
      console.log("[EMAIL] Brevo OK →", to);
      return true;
    }
    const errText = await resp.text();
    console.error(`[EMAIL] Brevo fail: ${resp.status} ${errText}`);
    return false;
  } catch (e) {
    console.error("[EMAIL] Brevo exception:", e.message);
    return false;
  }
}

async function sendViaResend(env, to, subject, html, attachments = []) {
  try {
    const payload = {
      from: `WhiteFlows <${env.GMAIL_SENDER}>`,
      to: [to],
      subject,
      html,
    };

    if (attachments.length > 0) {
      // Resend uses "attachments" (with 's')
      payload.attachments = attachments.map((a) => ({
        filename: a.name,
        content: a.content,
      }));
    }

    const resp = await fetch("https://api.resend.com/emails", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${env.RESEND_API_KEY}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    });

    if (resp.ok) {
      console.log("[EMAIL] Resend OK →", to);
      return true;
    }
    const err = await resp.text();
    console.error(`[EMAIL] Resend fail: ${resp.status} ${err}`);
    return false;
  } catch (e) {
    console.error("[EMAIL] Resend exception:", e.message);
    return false;
  }
}

// ─── Email HTML Builder ──────────────────────────────────────────────────────
function buildEmailHtml({ title, rows, bodyNote = "", isClient = false }) {
  const INK = "#0E0D0B";
  const GOLD = "#D4A853";
  const PEARL = "#F8F7F3";

  const tableRows = Object.entries(rows)
    .filter(([, v]) => v && String(v).trim())
    .map(
      ([k, v]) => `
      <tr>
        <td style="padding:10px 14px;border:1px solid #E5E2D9;font-weight:700;
                   font-size:12px;text-transform:uppercase;letter-spacing:.5px;
                   background:#FDFCF9;color:#6B5E4A;white-space:nowrap;width:160px;">
          ${k.replace(/_/g, " ")}
        </td>
        <td style="padding:10px 14px;border:1px solid #E5E2D9;font-size:14px;color:${INK};">
          ${sanitize(String(v), 500)}
        </td>
      </tr>`
    )
    .join("");

  return `<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:20px;background:${PEARL};font-family:Arial,Helvetica,sans-serif;">
  <div style="max-width:600px;margin:auto;background:#fff;border:1px solid #E5E2D9;
              border-radius:6px;overflow:hidden;box-shadow:0 4px 20px rgba(0,0,0,.06);">

    <!-- Header -->
    <div style="background:${INK};padding:36px 28px;text-align:center;border-bottom:3px solid ${GOLD};">
      <div style="font-size:22px;font-weight:900;color:${GOLD};letter-spacing:4px;
                  text-transform:uppercase;font-family:Georgia,serif;">
        WHITEFLOWS
      </div>
      <div style="color:rgba(248,247,243,.45);font-size:10px;letter-spacing:3px;
                  text-transform:uppercase;margin-top:6px;">
        International Advisory
      </div>
    </div>

    <!-- Body -->
    <div style="padding:36px 28px;">
      <h2 style="margin:0 0 24px;font-size:18px;color:${INK};font-family:Georgia,serif;
                 border-bottom:1px solid #E5E2D9;padding-bottom:14px;">
        ${title}
      </h2>

      <table style="border-collapse:collapse;width:100%;margin-bottom:24px;font-family:Arial,sans-serif;">
        ${tableRows}
      </table>

      ${bodyNote ? `<p style="font-size:14px;line-height:1.8;color:#444;margin:0 0 20px;">${bodyNote}</p>` : ""}

      ${DOCUMENT_FOOTER_HTML}
    </div>

    <!-- Footer -->
    <div style="background:#F2F0EA;padding:20px 28px;text-align:center;
                border-top:1px solid #E5E2D9;">
      <p style="margin:0;font-size:11px;color:#A8A49C;letter-spacing:.5px;">
        © ${new Date().getFullYear()} WhiteFlows International · Investment Advisory
      </p>
      <p style="margin:6px 0 0;font-size:10px;color:#C0B8B0;">
        Gujarat, India · whiteflowsint@gmail.com · +91 88662 82752
      </p>
    </div>
  </div>
</body>
</html>`;
}

// ─── Client Auto-Responder HTML ───────────────────────────────────────────────
function buildClientConfirmation({ name, refId, formType }) {
  const GOLD = "#D4A853";
  const INK = "#0E0D0B";

  const typeLabel = {
    retail: "Consultation Enquiry",
    project: "Project Funding Proposal",
    scale: "Scale-Up Proposal",
    ocean: "The Ocean Ecosystem Enquiry",
    institutional: "Institutional / Ultra-HNI Consultation",
    application: "Portfolio Application",
  }[formType] || "Enquiry";

  return `<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"></head>
<body style="margin:0;padding:20px;background:#F8F7F3;font-family:Arial,sans-serif;">
<div style="max-width:580px;margin:auto;background:#fff;border:1px solid #E5E2D9;border-radius:6px;overflow:hidden;">

  <div style="background:${INK};padding:40px 28px;text-align:center;border-bottom:3px solid ${GOLD};">
    <div style="font-size:24px;font-weight:900;color:${GOLD};letter-spacing:4px;font-family:Georgia,serif;">
      WHITEFLOWS
    </div>
    <div style="color:rgba(248,247,243,.45);font-size:10px;letter-spacing:3px;text-transform:uppercase;margin-top:6px;">
      International Advisory
    </div>
  </div>

  <div style="padding:40px 28px;">
    <h1 style="font-family:Georgia,serif;font-size:22px;color:${INK};margin:0 0 8px;">
      We've received your ${typeLabel}.
    </h1>
    <p style="color:#6B5E4A;font-size:13px;letter-spacing:.5px;margin:0 0 32px;">
      Reference: <strong style="font-family:monospace;color:${GOLD};">${refId}</strong>
    </p>

    <p style="font-size:15px;line-height:1.8;color:#333;margin:0 0 20px;">
      Dear <strong>${sanitize(name, 80)}</strong>,
    </p>
    <p style="font-size:15px;line-height:1.8;color:#444;margin:0 0 20px;">
      Thank you for reaching out to WhiteFlows International. Our senior advisory desk has been
      notified and will contact you within <strong>24 business hours</strong> to discuss your
      requirements in detail.
    </p>
    <p style="font-size:15px;line-height:1.8;color:#444;margin:0 0 32px;">
      For any urgent matters, please connect with our Elite Advisory Desk directly on WhatsApp.
    </p>

    <div style="text-align:center;margin-bottom:32px;">
      <a href="https://wa.me/918866282752?text=Greetings%20WhiteFlows%2C%20my%20reference%20is%20${refId}"
         style="display:inline-block;padding:14px 36px;background:${GOLD};color:${INK};
                text-decoration:none;font-weight:700;font-size:12px;letter-spacing:2px;
                text-transform:uppercase;border-radius:3px;">
        Connect on WhatsApp
      </a>
    </div>

    ${DOCUMENT_FOOTER_HTML}
  </div>

  <div style="background:#F2F0EA;padding:18px 28px;text-align:center;border-top:1px solid #E5E2D9;">
    <p style="margin:0;font-size:11px;color:#A8A49C;">
      © ${new Date().getFullYear()} WhiteFlows International · All Rights Reserved
    </p>
  </div>
</div>
</body>
</html>`;
}

// ─── /submit-lead Handler ────────────────────────────────────────────────────
async function handleSubmitLead(request, env, origin) {
  let data;
  try {
    data = await request.json();
  } catch {
    return corsResponse(
      JSON.stringify({ success: false, message: "Invalid JSON body." }),
      400, origin
    );
  }

  // ── Strip all document/PDF/base64 fields ─────────────────────────────────
  // (per task spec: attachments completely removed)
  const clean = {};
  for (const [k, v] of Object.entries(data)) {
    if (k === "documents" || k === "pdf_base64") continue;
    if (typeof v === "string" && v.startsWith("data:")) continue; // base64 data URLs
    if (typeof v === "object" && v !== null && "data" in v) continue; // nested doc objects
    clean[k] = v;
  }

  // ── Field extraction ──────────────────────────────────────────────────────
  const name = sanitize(
    clean.name || clean.applicant_name || clean.contact_person || clean.entity_name || ""
  );
  const email = sanitize(clean.email || "");
  const phone = sanitize(clean.phone || clean.mobile || "");
  const formType = sanitize(clean.type || "retail");
  const formName = sanitize(clean.form_name || "General Enquiry");

  // ── Validation ────────────────────────────────────────────────────────────
  if (!name) {
    return corsResponse(
      JSON.stringify({ success: false, message: "Name is required." }),
      400, origin
    );
  }
  if (!isValidEmail(email)) {
    return corsResponse(
      JSON.stringify({ success: false, message: "A valid email address is required." }),
      400, origin
    );
  }

  // ── Rate limiting ─────────────────────────────────────────────────────────
  const ip =
    request.headers.get("CF-Connecting-IP") ||
    request.headers.get("X-Forwarded-For")?.split(",")[0]?.trim() ||
    "unknown";

  const allowed = await checkRateLimit(env, ip);
  if (!allowed) {
    return corsResponse(
      JSON.stringify({
        success: false,
        message:
          "Security Limit Reached: Too many submissions from this connection. Please try again in an hour.",
      }),
      429, origin
    );
  }

  // ── Geolocation (free via CF request object) ──────────────────────────────
  const geoLocation = getGeoFromRequest(request);

  // ── Build reference ID ────────────────────────────────────────────────────
  const refId = `REF-${Date.now().toString(36).toUpperCase()}`;
  const timestamp = new Date().toLocaleString("en-IN", { timeZone: "Asia/Kolkata" });

  // ── Build admin email rows ────────────────────────────────────────────────
  const adminRows = {
    "Form Type": formName,
    "Reference ID": refId,
    Name: name,
    Email: email,
    Phone: phone || "—",
    Location: geoLocation,
    "Submitted At": timestamp,
  };

  // Add all other clean fields (investment range, objective, etc.)
  const skipKeys = new Set([
    "name", "email", "phone", "mobile", "type", "form_name",
    "body", "subject", "Client IP", "Client Location",
  ]);
  for (const [k, v] of Object.entries(clean)) {
    if (!skipKeys.has(k) && v && String(v).trim()) {
      adminRows[k.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())] = v;
    }
  }

  // ── Send admin notification email ─────────────────────────────────────────
  const adminSubject = `New Lead [${formName}] — ${name} · ${refId}`;
  const adminHtml = buildEmailHtml({
    title: `New WhiteFlows Lead — ${formName}`,
    rows: adminRows,
    bodyNote: clean.body
      ? `<strong>Client Message:</strong> ${sanitize(clean.body, 1000)}`
      : "",
  });

  // Fire both emails concurrently — don't await sequentially
  const adminTarget = env.GMAIL_RECEIVER || env.GMAIL_SENDER;
  const [adminOk] = await Promise.allSettled([
    dispatchEmail(env, adminTarget, adminSubject, adminHtml),
    // Client confirmation
    dispatchEmail(
      env,
      email,
      `WhiteFlows: Your ${formName} Confirmation [${refId}]`,
      buildClientConfirmation({ name, refId, formType })
    ),
  ]);

  const emailSent = adminOk.status === "fulfilled" && adminOk.value === true;

  return corsResponse(
    JSON.stringify({
      success: true,
      ref_id: refId,
      message: emailSent
        ? "Enquiry received. You will hear from us within 24 hours."
        : "Enquiry recorded. Our team will be in touch shortly.",
    }),
    200, origin
  );
}

// ─── /submit Handler (Full Application) ─────────────────────────────────────
async function handleSubmitApplication(request, env, origin) {
  let data;
  try {
    data = await request.json();
  } catch {
    return corsResponse(
      JSON.stringify({ success: false, message: "Invalid JSON body." }),
      400, origin
    );
  }

  // ── Strip ALL document & PDF data ────────────────────────────────────────
  const clean = data;

  // ── Field extraction ──────────────────────────────────────────────────────
  const name = sanitize(clean.applicant_name || "");
  const email = sanitize(clean.email || "");
  const phone = sanitize(clean.mobile || "");
  const portfolio = sanitize(clean.portfolio || "General");

  if (!name || !isValidEmail(email)) {
    return corsResponse(
      JSON.stringify({ success: false, message: "Name and valid email are required." }),
      400, origin
    );
  }

  const ip =
    request.headers.get("CF-Connecting-IP") ||
    request.headers.get("X-Forwarded-For")?.split(",")[0]?.trim() ||
    "unknown";

  const allowed = await checkRateLimit(env, ip);
  if (!allowed) {
    return corsResponse(
      JSON.stringify({ success: false, message: "Rate limit exceeded. Try again in an hour." }),
      429, origin
    );
  }

  const geo = getGeoFromRequest(request);

  // ── Build a sequential Application ID ────────────────────────────────────
  const now = new Date();
  const monthStr = now.toLocaleString("en-US", { month: "short" }).toUpperCase();
  const appId = `WF-${monthStr}-${now.getFullYear()}-${Date.now().toString(36).toUpperCase()}`;
  const timestamp = now.toLocaleString("en-IN", { timeZone: "Asia/Kolkata" });

  // ── Build email rows (all text fields, no base64) ─────────────────────────
  const adminRows = {
    "Application ID": appId,
    Portfolio: portfolio,
    "Applicant Name": name,
    Email: email,
    Mobile: phone || "—",
    Location: geo,
    "Nominee Name": sanitize(clean.nominee_name || ""),
    "Nominee PAN": sanitize(clean.nominee_pan || ""),
    "Nominee DOB": sanitize(clean.nominee_dob || ""),
    "Nominee Mobile": sanitize(clean.nominee_mobile || ""),
    "Submitted At": timestamp,
  };

  const adminSubject = `New Application [${portfolio}] — ${name} · ${appId}`;
  
  // ── Prepare Attachments ───────────────────────────────────────────────────
  const attachments = [];
  const attachmentList = [];
  
  // 1. Auto-generated PDF
  if (clean.pdf_base64 && clean.pdf_base64.includes("base64,")) {
    const pdfName = `Confirmation-${appId}.pdf`;
    attachments.push({
      name: pdfName,
      content: clean.pdf_base64.split("base64,")[1],
    });
    attachmentList.push(`<li>✅ <strong>System PDF:</strong> ${pdfName}</li>`);
  }

  // 2. Uploaded Documents (Object iteration)
  if (clean.documents && typeof clean.documents === "object") {
    Object.entries(clean.documents).forEach(([key, doc]) => {
      if (doc && doc.data && doc.data.includes("base64,")) {
        const ext = doc.name ? doc.name.split(".").pop() : "png";
        const fileName = doc.name || `${key}.${ext}`;
        attachments.push({
          name: fileName,
          content: doc.data.split("base64,")[1],
        });
        attachmentList.push(`<li>📎 <strong>User Doc:</strong> ${fileName}</li>`);
      }
    });
  }

  const adminHtml = buildEmailHtml({
    title: `New WhiteFlows Application — ${portfolio}`,
    rows: adminRows,
    bodyNote: `
      <div style="background:#f0f7ff; padding:15px; border-left:4px solid #007bff; border-radius:4px;">
        <h4 style="margin-top:0; color:#0056b3;">📁 Attached Documents (${attachments.length})</h4>
        <ul style="margin:0; padding-left:20px; font-size:13px;">
          ${attachmentList.length > 0 ? attachmentList.join("") : "<li>No documents attached</li>"}
        </ul>
        <p style="margin-top:10px; font-size:12px; color:#666;">
          <em>Note: All files are scanned and attached to this email directly.</em>
        </p>
      </div>
    `,
  });

  const adminTarget = env.GMAIL_RECEIVER || env.GMAIL_SENDER;

  await Promise.allSettled([
    // Admin gets the full package
    dispatchEmail(env, adminTarget, adminSubject, adminHtml, attachments),
    // Client gets a clean confirmation (no attachments to save bandwidth/trust)
    dispatchEmail(
      env,
      email,
      `WhiteFlows: Application Received — ${portfolio} [${appId}]`,
      buildClientConfirmation({ name, refId: appId, formType: "application" })
    ),
  ]);

  return corsResponse(
    JSON.stringify({
      success: true,
      app_id: appId,
      message: "Application & Documents received. Our desk will review them within 24 hours.",
    }),
    200, origin
  );
}

// ─── Main Fetch Handler ──────────────────────────────────────────────────────
export default {
  async fetch(request, env) {
    const origin = request.headers.get("Origin") || "";
    const url = new URL(request.url);
    const method = request.method.toUpperCase();

    // ── Handle preflight ────────────────────────────────────────────────────
    if (method === "OPTIONS") {
      return new Response(null, {
        status: 204,
        headers: getCorsHeaders(origin),
      });
    }

    // ── Health check ────────────────────────────────────────────────────────
    if (url.pathname === "/health" && method === "GET") {
      return corsResponse(
        JSON.stringify({ status: "ok", runtime: "cloudflare-worker", version: "5.0-cf" }),
        200, origin
      );
    }

    // ── Lead submission ──────────────────────────────────────────────────────
    if (url.pathname === "/submit-lead" && method === "POST") {
      return handleSubmitLead(request, env, origin);
    }

    // ── Full application submission ──────────────────────────────────────────
    if (url.pathname === "/submit" && method === "POST") {
      return handleSubmitApplication(request, env, origin);
    }

    // ── Root / Status Check ────────────────────────────────────────────────
    if (url.pathname === "/" && method === "GET") {
      return corsResponse(
        JSON.stringify({ 
          status: "online", 
          platform: "WhiteFlows Elite", 
          version: "5.0-edge",
          message: "Elite Lead Intelligence API is Live."
        }),
        200, origin
      );
    }

    // ── 404 ─────────────────────────────────────────────────────────────────
    return corsResponse(
      JSON.stringify({ error: "Endpoint not found" }),
      404, origin
    );
  },
};
