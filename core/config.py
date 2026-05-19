"""
core/config.py
Loads user_config.yaml and provides typed access throughout the app.
"""

import yaml
from pathlib import Path
from loguru import logger

CONFIG_PATH = Path(__file__).parent.parent / "config" / "user_config.yaml"


class Config:
    """Singleton config loader. Access via: from core.config import cfg"""
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._loaded = False
        return cls._instance

    def load(self, path: str = None):
        config_file = Path(path) if path else CONFIG_PATH
        if not config_file.exists():
            raise FileNotFoundError(f"Config not found: {config_file}")
        with open(config_file, "r") as f:
            self._data = yaml.safe_load(f)
        self._validate()
        self._loaded = True
        logger.info(f"Config loaded from {config_file}")
        return self

    def _validate(self):
        errors = []
        required = {
            "groq.api_key": self.groq_api_key,
            "user.name": self.user_name,
            "user.phone": self.user_phone,
            "microsoft.email": self.ms_email,
        }
        for field, val in required.items():
            if not val or str(val).startswith("<YOUR_"):
                errors.append(f"  ⚠️  {field} not set in user_config.yaml")
        if errors:
            logger.warning("Config issues found:\n" + "\n".join(errors))

    def _get(self, *keys, default=None):
        d = self._data
        for k in keys:
            if isinstance(d, dict):
                d = d.get(k, default)
            else:
                return default
        return d

    # User
    @property
    def user_name(self): return self._get("user", "name", default="")
    @property
    def user_email(self): return self._get("user", "email", default="")
    @property
    def user_phone(self): return self._get("user", "phone", default="")
    @property
    def account_type(self): return self._get("user", "account_type", default="student")

    # Microsoft
    @property
    def ms_email(self): return self._get("microsoft", "email", default="")
    @property
    def ms_password(self): return self._get("microsoft", "password", default="")
    @property
    def use_playwright(self): return self._get("microsoft", "use_playwright_fallback", default=True)

    # Groq
    @property
    def groq_api_key(self): return self._get("groq", "api_key", default="")
    @property
    def primary_model(self): return self._get("groq", "primary_model", default="llama-3.3-70b-versatile")
    @property
    def coding_model(self): return self._get("groq", "coding_model", default="deepseek-r1-distill-llama-70b")
    @property
    def vision_model(self): return self._get("groq", "vision_model", default="llava-v1.5-7b")
    @property
    def max_tokens(self): return self._get("groq", "max_tokens", default=8192)
    @property
    def temperature(self): return self._get("groq", "temperature", default=0.1)

    # WhatsApp
    @property
    def wa_provider(self): return self._get("whatsapp", "provider", default="callmebot")
    @property
    def wa_phone(self): return self._get("whatsapp", "your_phone", default="")
    @property
    def callmebot_key(self): return self._get("whatsapp", "callmebot_apikey", default="")
    @property
    def meta_token(self): return self._get("whatsapp", "meta_token", default="")
    @property
    def meta_phone_id(self): return self._get("whatsapp", "meta_phone_id", default="")

    # Google Drive
    @property
    def drive_service_account(self): return self._get("google_drive", "service_account_json", default="")
    @property
    def drive_folder(self): return self._get("google_drive", "folder_name", default="AutoAssign_Submissions")
    @property
    def drive_enabled(self): return self._get("google_drive", "enabled", default=True)

    # Approval
    @property
    def require_approval(self): return self._get("approval", "require_approval", default=True)
    @property
    def approval_timeout(self): return self._get("approval", "timeout_minutes", default=30)
    @property
    def auto_submit(self): return self._get("approval", "auto_submit_on_timeout", default=True)

    # Schedule
    @property
    def check_interval(self): return self._get("schedule", "check_interval_minutes", default=5)
    @property
    def active_start(self): return self._get("schedule", "active_hours_start", default="08:00")
    @property
    def active_end(self): return self._get("schedule", "active_hours_end", default="02:00")
    @property
    def timezone(self): return self._get("schedule", "timezone", default="Asia/Karachi")


cfg = Config()
