#!/usr/bin/env python3
"""
Extract structured metadata from .firecrawl/ markdown files into JSON indexes.

Reads training-modules/*.md, events/*.md, and training-events/*.md,
extracts institution, ECTS, title, description, and other metadata,
then writes/updates the corresponding *-structured.json files.

Stdlib only — no external packages.
"""

import json
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
FIRECRAWL_DIR = PROJECT_ROOT / ".firecrawl"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def strip_wix_header(content: str) -> str:
    """Remove Wix boilerplate header up to and including [Partners Area]."""
    content = re.sub(
        r'^.*?\[Partners Area\]\([^)]+\)\s*\n\s*\n',
        '', content, count=1, flags=re.DOTALL,
    )
    return content


def extract_title(md: str, fallback: str) -> str:
    """Extract page title from markdown headings."""
    m = re.search(r'^#\s+(.+)', md, re.MULTILINE)
    if not m:
        m = re.search(r'^##\s+(.+)', md, re.MULTILINE)
    if not m:
        m = re.search(r'^###\s+\*\*(.+?)\*\*', md, re.MULTILINE)
    if not m:
        return fallback.replace('-', ' ').title()
    t = m.group(1).strip()
    t = re.sub(r'\*\*(.+?)\*\*', r'\1', t)  # strip bold
    t = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', t)  # strip links
    return t


def extract_institution(md: str) -> str:
    """Extract institution from 'Leading institution(s):' or 'Host institution:' lines."""
    m = re.search(
        r'[-*]\s*(?:Leading|Host)\s+institutions?:\s*(.+)',
        md, re.IGNORECASE,
    )
    if not m:
        # Try without bullet
        m = re.search(
            r'(?:Leading|Host)\s+institutions?:\s*(.+)',
            md, re.IGNORECASE,
        )
    if not m:
        return ""
    inst = m.group(1).strip()
    if not inst:
        return ""
    inst = re.sub(r'\*\*(.+?)\*\*', r'\1', inst)  # strip bold
    inst = inst.strip('* ')
    # Reject if it looks like an ECTS/EC line that was captured by mistake
    if re.match(r'^-?\s*EC', inst):
        return ""
    return inst


def extract_ects(md: str) -> int | None:
    """Extract ECTS credits from markdown content."""
    m = re.search(r'(\d+)\s*ECTS', md, re.IGNORECASE)
    if m:
        return int(m.group(1))
    # Try "EC: N" pattern
    m = re.search(r'EC:\s*(\d+)', md)
    if m:
        return int(m.group(1))
    return None


def extract_description(md: str, max_len: int = 300) -> str:
    """Extract first substantial paragraph as description."""
    # Skip headings, bullets, images, short lines
    for line in md.split('\n'):
        line = line.strip()
        if not line:
            continue
        if re.match(r'^#{1,4}\s+', line):
            continue
        if re.match(r'^[-*]\s+', line):
            continue
        if line.startswith('!'):
            continue
        if len(line) < 50:
            continue
        # Strip markdown formatting
        desc = re.sub(r'\*\*(.+?)\*\*', r'\1', line)
        desc = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', desc)
        if len(desc) > max_len:
            desc = desc[:max_len - 3] + "..."
        return desc
    return ""


# ---------------------------------------------------------------------------
# Training modules
# ---------------------------------------------------------------------------
def load_existing(json_path: Path) -> dict:
    """Load existing JSON data keyed by slug for merging."""
    if not json_path.exists():
        return {}
    with open(json_path, encoding='utf-8') as f:
        data = json.load(f)
    key = "modules" if "modules" in data else "events"
    return {item["slug"]: item for item in data.get(key, [])}


def extract_training_modules() -> dict:
    """Extract structured data from training-modules/*.md.

    Merges with existing JSON: extracted values take priority for institution
    (if non-empty), but existing ECTS values are preserved when extraction
    finds nothing (ECTS is rarely in the markdown).
    """
    src_dir = FIRECRAWL_DIR / "training-modules"
    existing = load_existing(FIRECRAWL_DIR / "training-modules-structured.json")
    modules = []

    for md_file in sorted(src_dir.glob("*.md")):
        slug = md_file.stem
        raw = md_file.read_text(encoding='utf-8', errors='replace')
        cleaned = strip_wix_header(raw)
        old = existing.get(slug, {})

        title = extract_title(cleaned, slug)
        institution = extract_institution(raw) or old.get("institution") or None
        ects = extract_ects(raw) or old.get("ects")
        description = extract_description(cleaned) or old.get("description", "")

        modules.append({
            "title": title,
            "slug": slug,
            "institution": institution,
            "ects": ects,
            "description": description,
            "file": f"training-modules/{md_file.name}",
        })

    return {
        "count": len(modules),
        "modules": modules,
    }


# ---------------------------------------------------------------------------
# Training events
# ---------------------------------------------------------------------------
def extract_training_events() -> dict:
    """Extract structured data from training-events/*.md."""
    src_dir = FIRECRAWL_DIR / "training-events"
    events = []

    for md_file in sorted(src_dir.glob("*.md")):
        slug = md_file.stem
        raw = md_file.read_text(encoding='utf-8', errors='replace')
        cleaned = strip_wix_header(raw)

        title = extract_title(cleaned, slug)
        description = extract_description(cleaned)

        events.append({
            "title": title,
            "slug": slug,
            "description": description,
            "file": f"training-events/{md_file.name}",
        })

    return {
        "count": len(events),
        "events": events,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def write_json(path: Path, data: dict):
    """Write JSON with pretty formatting."""
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"  Wrote {path.name}: {len(data.get('modules', data.get('events', [])))} entries")


def main():
    print("=== Extracting structured metadata from .firecrawl/ ===")
    print()

    # Training modules
    print("[1/2] Training modules ...")
    tm_data = extract_training_modules()
    write_json(FIRECRAWL_DIR / "training-modules-structured.json", tm_data)

    # Check for missing institutions
    missing = [m["slug"] for m in tm_data["modules"] if not m["institution"]]
    if missing:
        print(f"  WARNING: {len(missing)} modules with no institution: {', '.join(missing)}")

    # Training events
    print("[2/2] Training events ...")
    te_data = extract_training_events()
    write_json(FIRECRAWL_DIR / "training-events-structured.json", te_data)

    print()
    print("=== Done ===")
    print()
    print("NOTE: events-structured.json is NOT regenerated by this script.")
    print("      Events metadata (dates, locations, URLs) requires manual curation")
    print("      because that data is not reliably extractable from markdown alone.")


if __name__ == "__main__":
    main()
