import os
import shutil

from html2image import Html2Image


def generate_all_assets():
    os.makedirs("docs/assets", exist_ok=True)
    hti = Html2Image(output_path="docs/assets")

    # 1. Hero Light Banner (1200x675)
    hero_html = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
    <meta charset="UTF-8">
    <style>
      * { box-sizing: border-box; margin: 0; padding: 0; }
      body {
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
        background: linear-gradient(135deg, #ffffff 0%, #f1f5f9 50%, #e2e8f0 100%);
        width: 1200px;
        height: 675px;
        padding: 48px;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
        color: #0f172a;
        overflow: hidden;
        position: relative;
      }
      .bg-blob-1 {
        position: absolute;
        width: 500px;
        height: 500px;
        background: radial-gradient(circle, rgba(16, 185, 129, 0.12) 0%, rgba(255,255,255,0) 70%);
        top: -150px;
        right: -100px;
        z-index: 0;
      }
      .bg-blob-2 {
        position: absolute;
        width: 600px;
        height: 600px;
        background: radial-gradient(circle, rgba(37, 99, 235, 0.1) 0%, rgba(255,255,255,0) 70%);
        bottom: -200px;
        left: -150px;
        z-index: 0;
      }
      .content {
        position: relative;
        z-index: 1;
        display: flex;
        flex-direction: column;
        height: 100%;
        justify-content: space-between;
      }
      .top-nav {
        display: flex;
        justify-content: space-between;
        align-items: center;
      }
      .brand {
        display: flex;
        align-items: center;
        gap: 12px;
      }
      .brand-icon {
        width: 44px;
        height: 44px;
        background: linear-gradient(135deg, #10b981 0%, #059669 100%);
        border-radius: 12px;
        display: flex;
        align-items: center;
        justify-content: center;
        color: white;
        font-size: 24px;
        font-weight: 800;
        box-shadow: 0 4px 12px rgba(16, 185, 129, 0.3);
      }
      .brand-name {
        font-size: 22px;
        font-weight: 800;
        letter-spacing: -0.5px;
        color: #0f172a;
      }
      .badges {
        display: flex;
        gap: 10px;
      }
      .badge {
        font-size: 12px;
        font-weight: 700;
        padding: 6px 14px;
        border-radius: 20px;
        border: 1px solid #cbd5e1;
        background: rgba(255, 255, 255, 0.85);
        color: #334155;
        backdrop-filter: blur(8px);
      }
      .badge-success {
        background: rgba(220, 252, 231, 0.8);
        border-color: #86efac;
        color: #15803d;
      }
      .badge-primary {
        background: rgba(219, 234, 254, 0.8);
        border-color: #93c5fd;
        color: #1d4ed8;
      }
      .hero-title-area {
        margin-top: 10px;
      }
      .hero-title {
        font-size: 42px;
        font-weight: 800;
        line-height: 1.15;
        letter-spacing: -1.2px;
        color: #0f172a;
        margin-bottom: 12px;
      }
      .hero-highlight {
        background: linear-gradient(135deg, #059669 0%, #2563eb 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
      }
      .hero-subtitle {
        font-size: 18px;
        color: #475569;
        font-weight: 500;
        max-width: 900px;
        line-height: 1.45;
      }
      .cards-grid {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 20px;
        margin-top: 15px;
      }
      .card {
        background: rgba(255, 255, 255, 0.9);
        border: 1px solid #e2e8f0;
        border-radius: 16px;
        padding: 22px;
        box-shadow: 0 10px 25px -5px rgba(0,0,0,0.05), 0 8px 10px -6px rgba(0,0,0,0.03);
      }
      .card-header {
        display: flex;
        align-items: center;
        gap: 10px;
        margin-bottom: 12px;
      }
      .card-icon {
        font-size: 22px;
      }
      .card-title {
        font-size: 16px;
        font-weight: 700;
        color: #0f172a;
      }
      .card-desc {
        font-size: 13px;
        color: #64748b;
        line-height: 1.45;
        margin-bottom: 12px;
      }
      .card-meta {
        font-size: 11px;
        font-weight: 600;
        color: #059669;
        background: #f0fdf4;
        padding: 4px 8px;
        border-radius: 6px;
        display: inline-block;
      }
      .footer-bar {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding-top: 15px;
        border-top: 1px solid #e2e8f0;
        font-size: 13px;
        color: #64748b;
        font-weight: 500;
      }
      .status-indicator {
        display: flex;
        align-items: center;
        gap: 8px;
      }
      .dot {
        width: 9px;
        height: 9px;
        background: #10b981;
        border-radius: 50%;
        box-shadow: 0 0 8px #10b981;
      }
    </style>
    </head>
    <body>
      <div class="bg-blob-1"></div>
      <div class="bg-blob-2"></div>
      <div class="content">
        <div class="top-nav">
          <div class="brand">
            <div class="brand-icon">D</div>
            <div class="brand-name">Datheon Autonomous Sales Bot</div>
          </div>
          <div class="badges">
            <span class="badge badge-success">● 39/39 Tests Passing (100%)</span>
            <span class="badge badge-primary">FastAPI • Pydantic V2 • SQLAlchemy</span>
            <span class="badge">Enterprise Ready</span>
          </div>
        </div>

        <div class="hero-title-area">
          <h1 class="hero-title">
            Conversational Sales Intelligence &<br>
            <span class="hero-highlight">Autonomous WhatsApp CRM Qualification</span>
          </h1>
          <p class="hero-subtitle">
            Extract actionable BANT intelligence from unstructured WhatsApp chats, prevent hallucinations with strict guardrails, book Google Calendar demos autonomously, and sync records reliably via the Transactional Outbox pattern.
          </p>
        </div>

        <div class="cards-grid">
          <div class="card">
            <div class="card-header">
              <span class="card-icon">🛡️</span>
              <span class="card-title">Ingestion & Security</span>
            </div>
            <p class="card-desc">HMAC-SHA256 signature verification, idempotency deduplication lock, ReDoS guards, and prompt-injection defense.</p>
            <span class="card-meta">STRIDE Hardened • Zero-Trust</span>
          </div>

          <div class="card">
            <div class="card-header">
              <span class="card-icon">🧠</span>
              <span class="card-title">BANT Qualification & FSM</span>
            </div>
            <p class="card-desc">Stateful Finite State Machine extracting Budget, Authority, Need, and Timeline with schema validation.</p>
            <span class="card-meta">Score 94/100 • Auto-Transition</span>
          </div>

          <div class="card">
            <div class="card-header">
              <span class="card-icon">📅</span>
              <span class="card-title">Autonomous Booking & CRM</span>
            </div>
            <p class="card-desc">Cal.com & Google Calendar slot reservation, Airtable CRM pipeline updates, and human escalation via Slack.</p>
            <span class="card-meta">Transactional Outbox • DLQ</span>
          </div>
        </div>

        <div class="footer-bar">
          <div class="status-indicator">
            <div class="dot"></div>
            <span>System Status: Fully Operational (Production Architecture v1.0.0)</span>
          </div>
          <div>MIT License • 2026 Maheswari • Open Source</div>
        </div>
      </div>
    </body>
    </html>
    """

    print("Generating hero_light_banner.png...")
    hti.screenshot(html_str=hero_html, save_as="hero_light_banner.png", size=(1200, 675))

    # 2. WhatsApp Chat Mockup (800x650)
    mockup_html = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
    <meta charset="UTF-8">
    <style>
      * { box-sizing: border-box; margin: 0; padding: 0; }
      body {
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
        background: #f8fafc;
        width: 800px;
        height: 650px;
        padding: 30px;
        display: flex;
        gap: 24px;
        color: #0f172a;
      }
      .phone-frame {
        flex: 1.1;
        background: #ffffff;
        border: 2px solid #e2e8f0;
        border-radius: 28px;
        box-shadow: 0 20px 35px -10px rgba(0,0,0,0.08);
        display: flex;
        flex-direction: column;
        overflow: hidden;
      }
      .wa-header {
        background: #ffffff;
        border-bottom: 1px solid #e2e8f0;
        padding: 16px;
        display: flex;
        align-items: center;
        gap: 12px;
      }
      .avatar {
        width: 40px;
        height: 40px;
        background: #10b981;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        color: white;
        font-weight: 700;
        font-size: 16px;
      }
      .wa-contact {
        flex: 1;
      }
      .wa-name {
        font-size: 15px;
        font-weight: 700;
        color: #0f172a;
        display: flex;
        align-items: center;
        gap: 6px;
      }
      .verified-badge {
        color: #10b981;
        font-size: 14px;
      }
      .wa-status {
        font-size: 11px;
        color: #10b981;
        font-weight: 600;
      }
      .chat-body {
        flex: 1;
        padding: 16px;
        background: #fafafa;
        background-image: radial-gradient(#cbd5e1 0.75px, transparent 0.75px);
        background-size: 12px 12px;
        display: flex;
        flex-direction: column;
        gap: 12px;
        justify-content: center;
      }
      .bubble {
        max-width: 82%;
        padding: 10px 14px;
        border-radius: 12px;
        font-size: 12.5px;
        line-height: 1.4;
        position: relative;
      }
      .bubble-incoming {
        align-self: flex-start;
        background: #ffffff;
        color: #1e293b;
        border: 1px solid #e2e8f0;
        border-top-left-radius: 2px;
      }
      .bubble-outgoing {
        align-self: flex-end;
        background: #dcf8c6;
        color: #064e3b;
        border-top-right-radius: 2px;
      }
      .time {
        font-size: 9.5px;
        color: #64748b;
        text-align: right;
        margin-top: 4px;
      }
      .dossier-panel {
        flex: 0.9;
        display: flex;
        flex-direction: column;
        gap: 16px;
      }
      .dossier-card {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 18px;
        padding: 20px;
        box-shadow: 0 10px 20px -5px rgba(0,0,0,0.04);
      }
      .dossier-title {
        font-size: 15px;
        font-weight: 700;
        color: #0f172a;
        margin-bottom: 14px;
        display: flex;
        justify-content: space-between;
        align-items: center;
      }
      .score-pill {
        background: #ecfdf5;
        border: 1px solid #a7f3d0;
        color: #059669;
        font-size: 11px;
        font-weight: 700;
        padding: 4px 8px;
        border-radius: 12px;
      }
      .dossier-row {
        display: flex;
        justify-content: space-between;
        padding: 7px 0;
        border-bottom: 1px solid #f1f5f9;
        font-size: 12px;
      }
      .dossier-label {
        color: #64748b;
        font-weight: 500;
      }
      .dossier-value {
        font-weight: 600;
        color: #0f172a;
      }
      .event-item {
        display: flex;
        align-items: center;
        gap: 10px;
        padding: 10px 12px;
        background: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 10px;
        font-size: 12px;
        margin-top: 8px;
      }
      .event-icon {
        font-size: 16px;
      }
      .event-text {
        font-weight: 600;
        color: #334155;
      }
    </style>
    </head>
    <body>
      <div class="phone-frame">
        <div class="wa-header">
          <div class="avatar">D</div>
          <div class="wa-contact">
            <div class="wa-name">Datheon Sales AI <span class="verified-badge">✔</span></div>
            <div class="wa-status">Online • Verified Business Account</div>
          </div>
        </div>
        <div class="chat-body">
          <div class="bubble bubble-incoming">
            Hi! We need an enterprise WhatsApp sales qualification bot for our 50-person sales team. Our annual budget is $25,000.
            <div class="time">10:14 AM</div>
          </div>
          <div class="bubble bubble-outgoing">
            Hello! 👋 Thanks for reaching out. With a 50-person team and $25k budget, you qualify for our Enterprise Acceleration plan! Would tomorrow at 3:00 PM EST work for a demo?
            <div class="time">10:14 AM</div>
          </div>
          <div class="bubble bubble-incoming">
            Yes, tomorrow at 3 PM works perfectly!
            <div class="time">10:15 AM</div>
          </div>
          <div class="bubble bubble-outgoing">
            Awesome! 📅 I've reserved your slot for tomorrow at 3:00 PM EST via Google Calendar. You'll receive a calendar invite shortly. Looking forward to speaking!
            <div class="time">10:15 AM</div>
          </div>
        </div>
      </div>

      <div class="dossier-panel">
        <div class="dossier-card">
          <div class="dossier-title">
            <span>Live Extracted Dossier</span>
            <span class="score-pill">QUALIFIED (95/100)</span>
          </div>
          <div class="dossier-row">
            <span class="dossier-label">State Machine:</span>
            <span class="dossier-value" style="color: #059669;">DEMO_BOOKED</span>
          </div>
          <div class="dossier-row">
            <span class="dossier-label">Team Size:</span>
            <span class="dossier-value">50 sales reps</span>
          </div>
          <div class="dossier-row">
            <span class="dossier-label">Annual Budget:</span>
            <span class="dossier-value">$25,000.00</span>
          </div>
          <div class="dossier-row">
            <span class="dossier-label">Authority:</span>
            <span class="dossier-value">Confirmed Decision Maker</span>
          </div>
          <div class="dossier-row">
            <span class="dossier-label">Timeline:</span>
            <span class="dossier-value">Immediate (Q4)</span>
          </div>
          <div class="dossier-row" style="border-bottom: none;">
            <span class="dossier-label">Calendar Sync:</span>
            <span class="dossier-value">Google Calendar / Cal.com</span>
          </div>
        </div>

        <div class="dossier-card">
          <div class="dossier-title" style="margin-bottom: 8px;">
            <span>Transactional Outbox Events</span>
          </div>
          <div class="event-item">
            <span class="event-icon">📅</span>
            <span class="event-text">google_calendar.event_created (Dispatched)</span>
          </div>
          <div class="event-item">
            <span class="event-icon">📊</span>
            <span class="event-text">airtable.lead_upserted (Dispatched)</span>
          </div>
          <div class="event-item">
            <span class="event-icon">🔔</span>
            <span class="event-text">slack.qualified_lead_alert (Dispatched)</span>
          </div>
        </div>
      </div>
    </body>
    </html>
    """

    print("Generating whatsapp_chat_mockup.png...")
    hti.screenshot(html_str=mockup_html, save_as="whatsapp_chat_mockup.png", size=(800, 650))

    # 3. LinkedIn Showcase Banner / image.png (1200x675)
    linkedin_html = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
    <meta charset="UTF-8">
    <style>
      * { box-sizing: border-box; margin: 0; padding: 0; }
      body {
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
        background: #ffffff;
        width: 1200px;
        height: 675px;
        padding: 44px;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
        color: #0f172a;
        border: 1px solid #cbd5e1;
        position: relative;
        overflow: hidden;
      }
      .decor-top-right {
        position: absolute;
        top: -100px;
        right: -80px;
        width: 420px;
        height: 420px;
        background: radial-gradient(circle, rgba(37,99,235,0.08) 0%, rgba(255,255,255,0) 70%);
        z-index: 0;
      }
      .decor-bottom-left {
        position: absolute;
        bottom: -100px;
        left: -80px;
        width: 450px;
        height: 450px;
        background: radial-gradient(circle, rgba(16,185,129,0.08) 0%, rgba(255,255,255,0) 70%);
        z-index: 0;
      }
      .main-content {
        position: relative;
        z-index: 1;
        display: flex;
        flex-direction: column;
        height: 100%;
        justify-content: space-between;
      }
      .top-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
      }
      .category-tag {
        font-size: 13px;
        font-weight: 800;
        letter-spacing: 1px;
        text-transform: uppercase;
        color: #2563eb;
        background: #eff6ff;
        border: 1px solid #bfdbfe;
        padding: 6px 14px;
        border-radius: 20px;
        display: flex;
        align-items: center;
        gap: 8px;
      }
      .headline {
        font-size: 38px;
        font-weight: 800;
        letter-spacing: -1px;
        color: #0f172a;
        line-height: 1.2;
        margin-top: 14px;
      }
      .subhead {
        font-size: 17px;
        color: #475569;
        font-weight: 500;
        line-height: 1.4;
        margin-top: 8px;
        max-width: 950px;
      }
      .bento-grid {
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 16px;
        margin-top: 18px;
      }
      .bento-card {
        background: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 14px;
        padding: 18px;
        box-shadow: 0 4px 6px -1px rgba(0,0,0,0.03);
      }
      .bento-icon {
        font-size: 24px;
        margin-bottom: 10px;
      }
      .bento-title {
        font-size: 15px;
        font-weight: 700;
        color: #0f172a;
        margin-bottom: 6px;
      }
      .bento-desc {
        font-size: 12px;
        color: #64748b;
        line-height: 1.4;
      }
      .metrics-strip {
        background: #f1f5f9;
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        padding: 14px 20px;
        display: flex;
        justify-content: space-around;
        align-items: center;
        margin-top: 18px;
      }
      .metric-item {
        text-align: center;
      }
      .metric-num {
        font-size: 18px;
        font-weight: 800;
        color: #059669;
      }
      .metric-label {
        font-size: 11px;
        color: #64748b;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.5px;
      }
      .card-footer {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding-top: 12px;
        font-size: 12px;
        font-weight: 600;
        color: #64748b;
      }
      .author {
        display: flex;
        align-items: center;
        gap: 8px;
        color: #0f172a;
      }
    </style>
    </head>
    <body>
      <div class="decor-top-right"></div>
      <div class="decor-bottom-left"></div>
      <div class="main-content">
        <div>
          <div class="top-row">
            <span class="category-tag">🚀 OPEN-SOURCE LAUNCH | AGENTIC AI</span>
            <span style="font-weight: 700; color: #10b981; font-size: 13px;">✔ 39/39 Passing Pytest Suite</span>
          </div>

          <h1 class="headline">Datheon Autonomous WhatsApp CRM & Lead Qualification Bot</h1>
          <p class="subhead">
            Production-grade conversational AI turning inbound WhatsApp chats into qualified CRM pipeline, scheduled demos, and revenue opportunities with zero human intervention.
          </p>
        </div>

        <div class="bento-grid">
          <div class="bento-card">
            <div class="bento-icon">🛡️</div>
            <div class="bento-title">Webhook Security</div>
            <div class="bento-desc">HMAC-SHA256 signature verification, idempotency locking, and prompt-injection guardrails.</div>
          </div>
          <div class="bento-card">
            <div class="bento-icon">🧠</div>
            <div class="bento-title">BANT Qualification</div>
            <div class="bento-desc">Structured dossier extraction (Budget, Authority, Need, Timeline) with deterministic FSM states.</div>
          </div>
          <div class="bento-card">
            <div class="bento-icon">📅</div>
            <div class="bento-title">Autonomous Booking</div>
            <div class="bento-desc">Zero-collision slot reservations via Cal.com & Google Calendar APIs with instant confirmation.</div>
          </div>
          <div class="bento-card">
            <div class="bento-icon">⚡</div>
            <div class="bento-title">Transactional Outbox</div>
            <div class="bento-desc">Reliable async event dispatching, dead-letter queues, Airtable sync, and Slack escalations.</div>
          </div>
        </div>

        <div>
          <div class="metrics-strip">
            <div class="metric-item">
              <div class="metric-num">39 / 39</div>
              <div class="metric-label">Tests Passed (100%)</div>
            </div>
            <div class="metric-item">
              <div class="metric-num" style="color: #2563eb;">FastAPI + V2</div>
              <div class="metric-label">Pydantic + Async SQLAlchemy</div>
            </div>
            <div class="metric-item">
              <div class="metric-num" style="color: #7c3aed;">STRIDE Ready</div>
              <div class="metric-label">Zero-Trust Hardened</div>
            </div>
            <div class="metric-item">
              <div class="metric-num" style="color: #059669;">100% Non-Root</div>
              <div class="metric-label">Production Multi-Stage Docker</div>
            </div>
          </div>

          <div class="card-footer">
            <div class="author">
              <span>👤 Created by Maheswari</span>
              <span>•</span>
              <span>Datheon WhatsApp CRM Lead Qualification Platform</span>
            </div>
            <div>github.com/maheswari9080/Datheon_Autonomous_WhatsApp_CRM_Lead_Qualification_Bot</div>
          </div>
        </div>
      </div>
    </body>
    </html>
    """

    print("Generating linkedin_banner.png & image.png...")
    hti.screenshot(html_str=linkedin_html, save_as="linkedin_banner.png", size=(1200, 675))
    shutil.copyfile("docs/assets/linkedin_banner.png", "image.png")
    print("All image assets generated successfully!")


if __name__ == "__main__":
    generate_all_assets()
