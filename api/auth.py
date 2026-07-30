import logging
import os
from typing import Optional

logger = logging.getLogger("api.auth")


class AuthProvider:
    def __init__(self, mode: str = "anonymous", api_key: Optional[str] = None):
        self.mode = mode
        self._api_key = api_key or os.environ.get("API_KEY", "")

    async def authenticate(self, token: Optional[str]) -> tuple[bool, str]:
        if self.mode == "anonymous":
            return True, "anonymous"

        if self.mode == "api_key":
            if not token:
                return False, "Missing API key"
            if token == self._api_key:
                return True, "api_key_user"
            return False, "Invalid API key"

        return False, f"Unknown auth mode: {self.mode}"

    @property
    def is_anonymous(self) -> bool:
        return self.mode == "anonymous"
