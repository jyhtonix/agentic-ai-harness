#!/usr/bin/env python3
"""
Build skill index — scans the skills/ directory, validates all skills,
and generates skills/index.json.

Usage:
    python scripts/build_index.py [--skills-dir SKILLS_DIR] [--validate]
"""

import argparse
import logging
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
logger = logging.getLogger("build_index")


def main():
    parser = argparse.ArgumentParser(description="Build CTF skill index")
    parser.add_argument(
        "--skills-dir",
        default="skills",
        help="Path to the skills directory (default: skills)",
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Run validation before building index",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output path for index.json (default: skills/index.json)",
    )
    args = parser.parse_args()

    skills_dir = Path(args.skills_dir)
    if not skills_dir.exists():
        logger.error("Skills directory not found: %s", skills_dir)
        sys.exit(1)

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

    from skills_engine.loader import SkillLoader
    from skills_engine.validator import SkillValidator

    loader = SkillLoader(skills_dir)
    skills = loader.load_all()

    if not skills:
        logger.warning("No skills found in %s", skills_dir)
        sys.exit(0)

    if args.validate:
        known_names = {s["frontmatter"].get("name", "") for s in skills}
        validator = SkillValidator(skills_dir)
        validator.set_known_skills(known_names)
        results = validator.validate_all(skills)
        failures = [r for r in results if not r.passed]
        if failures:
            logger.error("Validation failed for %d skill(s):", len(failures))
            for r in failures:
                for err in r.errors:
                    logger.error("  %s: %s", r.skill_name, err)
            sys.exit(1)
        logger.info("All %d skills passed validation", len(skills))

    index = loader.build_index(skills)
    if args.output:
        output_path = Path(args.output)
    else:
        output_path = skills_dir / "index.json"

    import json
    output_path.write_text(
        json.dumps(index, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    logger.info("Index written to %s (%d skills)", output_path, index["total_skills"])


if __name__ == "__main__":
    main()
