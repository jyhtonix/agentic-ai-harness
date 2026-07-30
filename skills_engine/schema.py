from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field, model_validator


class TokenBudget(BaseModel):
    frontmatter: int = 200
    full_content: int = 1500


class FrameworkMapping(BaseModel):
    mitre_attack: list[str] = Field(default_factory=list)
    nist_csf: list[str] = Field(default_factory=list)
    kill_chain: list[str] = Field(default_factory=list)


class SkillMetadata(BaseModel):
    path: str
    content_hash: str
    file_count: int = 1
    total_lines: int = 0
    loaded_at: str = ""


class SkillFrontmatter(BaseModel):
    name: str = Field(..., min_length=1, max_length=64, pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$")
    description: str = Field(..., min_length=20)
    domain: str = Field(default="ctf", pattern=r"^[a-z]+(-[a-z]+)*$")
    subdomain: str = Field(..., min_length=1)
    category: str = Field(default="", min_length=1)
    tags: list[str] = Field(default_factory=lambda: ["ctf"], min_length=1)
    version: str = Field(default="1.0", pattern=r"^\d+\.\d+\.\d+$|^\d+\.\d+$")
    author: str = ""
    license: str = "MIT"

    frameworks: FrameworkMapping = Field(default_factory=FrameworkMapping)
    allowed_tools: list[str] = Field(default_factory=list)
    requires: list[str] = Field(default_factory=list)
    user_invocable: bool = False
    argument_hint: str = ""
    token_budget: TokenBudget = Field(default_factory=TokenBudget)
    metadata: dict = Field(default_factory=dict)

    @model_validator(mode="after")
    def check_argument_hint_if_invocable(self):
        if self.user_invocable and not self.argument_hint:
            self.argument_hint = f"[{self.name}_task]"
        return self

    @model_validator(mode="after")
    def check_category_default(self):
        if not self.category:
            self.category = self.subdomain
        return self


VALID_SUBDOMAINS = {
    "web", "pwn", "crypto", "reverse", "forensics",
    "osint", "malware", "ai-ml", "misc", "blockchain",
    "mobile", "cloud", "network", "stego", "binary",
    "hardware", "quantum", "general",
}

VALID_DOMAINS = {"ctf", "cybersecurity", "soc", "general"}
