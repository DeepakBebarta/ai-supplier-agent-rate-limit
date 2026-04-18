"""
config/settings.py — Centralized configuration for Axension AI Agent 1.
All Twilio references removed. WhatsApp is now sent via Meta WABA only.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ─── Database ───
DB_URL = os.environ.get("DB_URL", "")

# ─── Redis / Celery ───
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

# ─── Meta WhatsApp Cloud API ───
WABA_TOKEN    = os.environ.get("WABA_TOKEN", "")
WABA_PHONE_ID = os.environ.get("WABA_PHONE_ID", "")
WABA_VERSION  = os.environ.get("WABA_VERSION", "v19.0")
WABA_VERIFY_TOKEN = os.environ.get("WABA_VERIFY_TOKEN", "axension_verify")

# ─── Phone Numbers ───
OWNER_PHONE = os.environ.get("OWNER_PHONE", "")   # E.164 without '+', e.g. 918121444200

# ─── Agent 1 Config ───
FACTORY_ID           = os.environ.get("FACTORY_ID", "factory_001")
MAX_MESSAGES_PER_RUN = int(os.environ.get("MAX_MESSAGES_PER_RUN", "3"))

# ─── Safety Rail ───
# true  → fake message ids, nothing leaves the box (testing)
# false → real WABA calls go out (production)
DRY_RUN = os.environ.get("DRY_RUN", "true").lower() == "true"

# ─── Dev Override ───
AGENT1_INTERVAL_MINUTES = os.environ.get("AGENT1_INTERVAL_MINUTES", None)
