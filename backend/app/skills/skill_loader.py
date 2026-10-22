"""
Skill Loader
Safely scans and parses SKILL.md files from .agents/skills and external/claude-trading-skills/skills.
Extracts YAML frontmatter, descriptions, reference formulas, and instruction sets.
Never executes arbitrary code.
"""
from pathlib import Path
from typing import Dict, Any, List, Optional
import re

SKILLS_DIR = Path(".agents/skills")
EXTERNAL_SKILLS_DIR = Path("external/claude-trading-skills/skills")

def _parse_yaml_frontmatter(content: str) -> Dict[str, str]:
    """Extract YAML frontmatter between triple dashes without requiring external yaml lib."""
    metadata: Dict[str, str] = {}
    if not content.startswith("---"):
        return metadata
    
    parts = content.split("---", 2)
    if len(parts) < 3:
        return metadata
    
    frontmatter_text = parts[1]
    for line in frontmatter_text.strip().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" in line:
            key, val = line.split(":", 1)
            metadata[key.strip()] = val.strip().strip("\"'")
    return metadata

class SkillDoc:
    def __init__(
        self,
        name: str,
        description: str,
        content: str,
        path: Path,
        has_scripts: bool = False,
        has_references: bool = False
    ):
        self.name = name
        self.description = description
        self.content = content
        self.path = path
        self.has_scripts = has_scripts
        self.has_references = has_references

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "has_scripts": self.has_scripts,
            "has_references": self.has_references,
            "path": str(self.path)
        }

class SkillLoader:
    def __init__(self, root_dir: Optional[Path] = None):
        if root_dir:
            self.root_dir = root_dir
        elif SKILLS_DIR.exists():
            self.root_dir = SKILLS_DIR
        elif EXTERNAL_SKILLS_DIR.exists():
            self.root_dir = EXTERNAL_SKILLS_DIR
        else:
            self.root_dir = Path(".")

    def load_all_skills(self) -> Dict[str, SkillDoc]:
        """Scan directory and parse all SKILL.md documents safely."""
        skills: Dict[str, SkillDoc] = {}
        if not self.root_dir.exists():
            return skills

        for item in self.root_dir.iterdir():
            if item.is_dir():
                skill_md = item / "SKILL.md"
                if skill_md.exists():
                    try:
                        raw = skill_md.read_text(encoding="utf-8", errors="ignore")
                        meta = _parse_yaml_frontmatter(raw)
                        name = meta.get("name", item.name)
                        description = meta.get("description", f"Quantitative skill: {name}")
                        has_scripts = (item / "scripts").exists()
                        has_references = (item / "references").exists()
                        
                        skills[name] = SkillDoc(
                            name=name,
                            description=description,
                            content=raw,
                            path=item,
                            has_scripts=has_scripts,
                            has_references=has_references
                        )
                    except Exception:
                        pass
        return skills

    def load_skill(self, name: str) -> Optional[SkillDoc]:
        """Load single skill document by name."""
        candidate = self.root_dir / name / "SKILL.md"
        if not candidate.exists() and EXTERNAL_SKILLS_DIR.exists():
            candidate = EXTERNAL_SKILLS_DIR / name / "SKILL.md"
        
        if not candidate.exists():
            return None

        raw = candidate.read_text(encoding="utf-8", errors="ignore")
        meta = _parse_yaml_frontmatter(raw)
        has_scripts = (candidate.parent / "scripts").exists()
        has_references = (candidate.parent / "references").exists()
        return SkillDoc(
            name=meta.get("name", name),
            description=meta.get("description", ""),
            content=raw,
            path=candidate.parent,
            has_scripts=has_scripts,
            has_references=has_references
        )

skill_loader = SkillLoader()
