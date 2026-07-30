import logging
import os
from pathlib import Path
from typing import Optional

import yaml

from challenges_engine.models import ChallengeDefinition

logger = logging.getLogger("challenges_engine.loader")

REQUIRED_FIELDS = {"name", "category", "difficulty", "description"}


class ChallengeLoader:
    def __init__(self, challenges_dir: Optional[str] = None):
        self._challenges_dir = challenges_dir or self._default_challenges_dir()

    @staticmethod
    def _default_challenges_dir() -> str:
        return str((Path(__file__).parent.parent / "challenges").resolve())

    def discover(self) -> list[str]:
        base = Path(self._challenges_dir)
        if not base.exists():
            logger.warning("Challenges directory does not exist: %s", base)
            return []
        result = []
        for entry in sorted(base.iterdir()):
            if not entry.is_dir() or entry.name.startswith("."):
                continue
            if (entry / "challenge.yaml").exists():
                result.append(entry.name)
        return result

    def load(self, challenge_id: str) -> Optional[ChallengeDefinition]:
        base = Path(self._challenges_dir)
        challenge_dir = base / challenge_id
        yaml_path = challenge_dir / "challenge.yaml"

        if not challenge_dir.exists():
            logger.warning("Challenge directory not found: %s", challenge_dir)
            return None
        if not yaml_path.exists():
            logger.warning("challenge.yaml not found in %s", challenge_dir)
            return None

        try:
            with open(yaml_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            logger.warning("YAML parse error in %s: %s", yaml_path, e)
            return None
        except OSError as e:
            logger.warning("Cannot read %s: %s", yaml_path, e)
            return None

        if not isinstance(data, dict):
            logger.warning("challenge.yaml is not a dict: %s", yaml_path)
            return None

        missing = REQUIRED_FIELDS - set(data.keys())
        if missing:
            logger.warning("challenge.yaml missing fields %s: %s", missing, yaml_path)
            return None

        definition = ChallengeDefinition(
            name=data["name"],
            category=data["category"],
            difficulty=data["difficulty"],
            description=data["description"],
            challenge_dir=str(challenge_dir.resolve()),
            required_skills=data.get("required_skills", []),
            allowed_tools=data.get("allowed_tools", []),
            verification=data.get("verification", {"type": "exact_flag"}),
            flag_format=data.get("flag_format", ""),
            expected_flag=data.get("expected_flag", ""),
        )

        definition.hints = self._load_hints(challenge_dir)
        definition.files = self._list_files(challenge_dir / "files")

        return definition

    @staticmethod
    def _load_hints(challenge_dir: Path) -> list[str]:
        hints_dir = challenge_dir / "hints"
        if not hints_dir.exists():
            return []
        hints = []
        for f in sorted(hints_dir.iterdir()):
            if f.is_file() and f.suffix == ".txt":
                try:
                    hints.append(f.read_text(encoding="utf-8").strip())
                except OSError:
                    pass
        return hints

    @staticmethod
    def _list_files(files_dir: Path) -> list[str]:
        if not files_dir.exists():
            return []
        return sorted(
            str(f.relative_to(files_dir.parent)) for f in files_dir.iterdir() if f.is_file()
        )

    def load_all(self) -> list[ChallengeDefinition]:
        return [self.load(cid) for cid in self.discover() if self.load(cid) is not None]
