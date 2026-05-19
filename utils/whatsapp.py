"""
utils/whatsapp.py
WhatsApp notifications — supports Callmebot (Phase 1) and Meta API (Phase 4).
"""

import requests
from urllib.parse import quote
from loguru import logger
from core.config import cfg


class WhatsApp:
    """
    Unified WhatsApp sender.
    Usage:
        from utils.whatsapp import whatsapp
        whatsapp.send("Assignment ready! View: https://drive.google.com/...")
    """

    def send(self, message: str, phone: str = None) -> bool:
        """Send a WhatsApp message using configured provider."""
        phone = phone or cfg.wa_phone
        if not phone:
            logger.error("No phone number configured for WhatsApp")
            return False

        provider = cfg.wa_provider
        if provider == "meta":
            return self._send_meta(phone, message)
        else:
            return self._send_callmebot(phone, message)

    # ── Callmebot (Phase 1) ───────────────────────────────────

    def _send_callmebot(self, phone: str, message: str) -> bool:
        """
        Send via Callmebot free API.
        Setup: Save +34 644 82 85 27 and send "I allow callmebot to send me messages"
        """
        apikey = cfg.callmebot_key
        if not apikey or apikey.startswith("<YOUR_"):
            logger.error("Callmebot API key not configured")
            return False
        try:
            encoded_msg = quote(message)
            url = (
                f"https://api.callmebot.com/whatsapp.php"
                f"?phone={phone}&text={encoded_msg}&apikey={apikey}"
            )
            resp = requests.get(url, timeout=15)
            if resp.status_code == 200 and "Message queued" in resp.text:
                logger.info(f"Callmebot message sent to {phone}")
                return True
            logger.warning(f"Callmebot response: {resp.status_code} — {resp.text[:100]}")
            return False
        except Exception as e:
            logger.error(f"Callmebot send failed: {e}")
            return False

    # ── Meta WhatsApp API (Phase 4) ───────────────────────────

    def _send_meta(self, phone: str, message: str) -> bool:
        """Send via Meta WhatsApp Cloud API."""
        token = cfg.meta_token
        phone_id = cfg.meta_phone_id
        if not token or not phone_id:
            logger.error("Meta WhatsApp credentials not configured")
            return False
        try:
            url = f"https://graph.facebook.com/v18.0/{phone_id}/messages"
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            }
            payload = {
                "messaging_product": "whatsapp",
                "to": phone.replace("+", ""),
                "type": "text",
                "text": {"body": message},
            }
            resp = requests.post(url, json=payload, headers=headers, timeout=15)
            if resp.status_code == 200:
                logger.info(f"Meta WhatsApp message sent to {phone}")
                return True
            logger.warning(f"Meta API error: {resp.status_code} — {resp.text[:200]}")
            return False
        except Exception as e:
            logger.error(f"Meta WhatsApp send failed: {e}")
            return False

    def send_assignment_ready(self, subject: str, deadline: str,
                               drive_link: str, confidence: int) -> bool:
        """Pre-formatted assignment ready notification."""
        message = (
            f"✅ *Assignment Ready!*\n\n"
            f"📚 Subject: {subject}\n"
            f"⏰ Deadline: {deadline}\n"
            f"🎯 Confidence: {confidence}%\n\n"
            f"📄 Review PDF:\n{drive_link}\n\n"
            f"Reply *YES* to submit now\n"
            f"_(Auto-submits in 30 min if no reply)_"
        )
        return self.send(message)

    def send_submission_done(self, subject: str) -> bool:
        """Notify that submission completed."""
        message = f"✅ *Submitted!*\n\n{subject} has been submitted successfully."
        return self.send(message)

    def send_error(self, subject: str, error: str) -> bool:
        """Notify about an error."""
        message = f"❌ *Error — {subject}*\n\n{error}\n\nCheck dashboard for details."
        return self.send(message)


whatsapp = WhatsApp()
