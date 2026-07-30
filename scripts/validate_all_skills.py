#!/usr/bin/env python3
"""
Validate all CTF skills — checks frontmatter, cross-references,
directory structure, and optional security audit.

Usage:
    python scripts/validate_all_skills.py [--skills-dir SKILLS_DIR] [--audit] [--json]
"""

import argparse
import json
import logging
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
logger = logging.getLogger("validate_skills")


def main():
    parser = argparse.ArgumentParser(description="Validate all CTF skills")
    parser.add_argument(
        "--skills-dir",
        default="skills",
        help="Path to the skills directory (default: skills)",
    )
    parser.add_argument(
        "--audit",
        action="store_true",
        help="Run security audit on skill content",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON",
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
        return

    known_names = {s["frontmatter"].get("name", "") for s in skills}

    validator = SkillValidator(skills_dir)
    validator.set_known_skills(known_names)
    results = validator.validate_all(skills)

    failures = [r for r in results if not r.passed]
    warnings = [r for r in results if r.passed and r.warnings]

    if args.json:
        report = {
            "total": len(results),
            "passed": len([r for r in results if r.passed]),
            "failed": len(failures),
            "warnings": len(warnings),
            "results": [r.to_dict() for r in results],
        }
        print(json.dumps(report, indent=2))
    else:
        logger.info("=" * 50)
        logger.info("Validation Results: %d total, %d passed, %d failed, %d with warnings",
                     len(results), len(results) - len(failures), len(failures), len(warnings))
        logger.info("=" * 50)
        for r in failures:
            logger.error("FAIL: %s", r.skill_name)
            for err in r.errors:
                logger.error("  - %s", err)
        for r in warnings:
            logger.warning("WARN: %s", r.skill_name)
            for w in r.warnings:
                logger.warning("  - %s", w)

    if args.audit:
        try:
            from skills_engine.auditor import SkillAuditor
            auditor = SkillAuditor(skills_dir)
            audit_results = auditor.audit_all(skills)
            critical = [a for a in audit_results if a.severity == "CRITICAL"]
            high = [a for a in audit_results if a.severity == "HIGH"]
            logger.info("Audit: %d critical, %d high, %d info",
                         len(critical), len(high), len(audit_results) - len(critical) - len(high))
            if args.json:
                pass
            elif critical:
                logger.error("CRITICAL audit findings:")
                for a in critical:
                    logger.error("  %s: %s", a.skill_name, a.message)
        except ImportError:
            logger.warning("SkillAuditor not available (skills_engine.auditor not yet implemented)")

    if failures:
        sys.exit(1)


if __name__ == "__main__":
    main()
