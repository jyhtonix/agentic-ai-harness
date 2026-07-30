import logging
from pathlib import Path
from typing import Optional

from challenges_engine.models import ChallengeDefinition

logger = logging.getLogger("challenges_engine.validator")


class ValidationError:
    def __init__(self, field: str, message: str):
        self.field = field
        self.message = message

    def __repr__(self):
        return f"ValidationError(field='{self.field}', message='{self.message}')"


class ValidationResult:
    def __init__(self):
        self.errors: list[ValidationError] = []

    def add_error(self, field: str, message: str) -> None:
        self.errors.append(ValidationError(field, message))

    @property
    def is_valid(self) -> bool:
        return len(self.errors) == 0

    def __bool__(self):
        return self.is_valid


class ChallengeValidator:
    VALID_CATEGORIES = {
        "steganography", "malware", "cryptography",
        "web_security", "forensics", "general",
    }
    VALID_DIFFICULTIES = {"beginner", "intermediate", "advanced", "expert"}

    def validate(self, challenge: ChallengeDefinition) -> ValidationResult:
        result = ValidationResult()
        if not challenge:
            result.add_error("challenge", "Challenge definition is None")
            return result

        self._validate_name(challenge, result)
        self._validate_category(challenge, result)
        self._validate_difficulty(challenge, result)
        self._validate_description(challenge, result)
        self._validate_skills(challenge, result)
        self._validate_tools(challenge, result)
        self._validate_verification(challenge, result)
        self._validate_files(challenge, result)
        self._validate_expected_flag(challenge, result)

        return result

    @staticmethod
    def _validate_name(challenge: ChallengeDefinition, result: ValidationResult) -> None:
        if not challenge.name or len(challenge.name.strip()) == 0:
            result.add_error("name", "Challenge name is required")

    @staticmethod
    def _validate_category(challenge: ChallengeDefinition, result: ValidationResult) -> None:
        if not challenge.category:
            result.add_error("category", "Challenge category is required")
        elif challenge.category not in ChallengeValidator.VALID_CATEGORIES:
            result.add_error(
                "category",
                f"Invalid category '{challenge.category}'. Valid: {sorted(ChallengeValidator.VALID_CATEGORIES)}",
            )

    @staticmethod
    def _validate_difficulty(challenge: ChallengeDefinition, result: ValidationResult) -> None:
        if not challenge.difficulty:
            result.add_error("difficulty", "Challenge difficulty is required")
        elif challenge.difficulty not in ChallengeValidator.VALID_DIFFICULTIES:
            result.add_error(
                "difficulty",
                f"Invalid difficulty '{challenge.difficulty}'. Valid: {sorted(ChallengeValidator.VALID_DIFFICULTIES)}",
            )

    @staticmethod
    def _validate_description(challenge: ChallengeDefinition, result: ValidationResult) -> None:
        if not challenge.description or len(challenge.description.strip()) == 0:
            result.add_error("description", "Challenge description is required")

    @staticmethod
    def _validate_skills(challenge: ChallengeDefinition, result: ValidationResult) -> None:
        if not challenge.required_skills:
            result.add_error("required_skills", "At least one required skill is recommended")
        else:
            for skill in challenge.required_skills:
                if not skill or len(skill.strip()) == 0:
                    result.add_error("required_skills", "Skill name cannot be empty")

    @staticmethod
    def _validate_tools(challenge: ChallengeDefinition, result: ValidationResult) -> None:
        if not challenge.allowed_tools:
            result.add_error("allowed_tools", "At least one allowed tool is recommended")

    @staticmethod
    def _validate_verification(challenge: ChallengeDefinition, result: ValidationResult) -> None:
        vtype = challenge.verification.get("type", "") if isinstance(challenge.verification, dict) else ""
        valid_types = {"exact_flag", "regex", "evidence"}
        if vtype and vtype not in valid_types:
            result.add_error(
                "verification.type",
                f"Invalid verification type '{vtype}'. Valid: {sorted(valid_types)}",
            )

    @staticmethod
    def _validate_expected_flag(challenge: ChallengeDefinition, result: ValidationResult) -> None:
        if not challenge.expected_flag:
            result.add_error("expected_flag", "Expected flag is required for verification")

    @staticmethod
    def _validate_files(challenge: ChallengeDefinition, result: ValidationResult) -> None:
        if challenge.challenge_dir:
            d = Path(challenge.challenge_dir)
            files_dir = d / "files"
            if files_dir.exists():
                file_count = len([f for f in files_dir.iterdir() if f.is_file()])
                if file_count == 0:
                    result.add_error("files", "files directory exists but contains no files")
