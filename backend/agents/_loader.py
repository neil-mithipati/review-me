"""Loads system prompts from agents/<name>.md, stripping YAML frontmatter."""
from pathlib import Path

_AGENTS_DIR = Path(__file__).parent


def load_system_prompt(name: str) -> str:
    content = (_AGENTS_DIR / f"{name}.md").read_text()
    if content.startswith("---"):
        end = content.index("---", 3)
        return content[end + 3:].strip()
    return content.strip()
