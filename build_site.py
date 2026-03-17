#!/usr/bin/env python3
"""
Build static HTML site from .firecrawl/ markdown sources into docs/.
Stdlib only -- no external packages.
"""

import os
import re
import json
import shutil
import glob
import html as html_mod
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
BASE = "/msca-digital-finance-phd-training"
PROJECT_ROOT = Path(__file__).resolve().parent
FIRECRAWL_DIR = PROJECT_ROOT / ".firecrawl"
DOCS_DIR = PROJECT_ROOT / "docs"

PRESERVE_FILES = {"booklet.pdf", "eu-funded.png", ".nojekyll"}

ROOT_PAGES = [
    "homepage", "research-projects", "irps", "media",
    "presentations", "wp6-doctoral-training", "team",
]

CATEGORIES = {
    "Foundational Training": [
        "foundation-data-science", "intro-ai-finance", "xai-methods",
        "intro-blockchain", "sustainable-finance", "ethics-digital",
        "reinforcement-learning",
    ],
    "Advanced Scientific Training": [
        "synthetic-data", "anomaly-detection", "nlp-transformers",
        "dependence-hf-data", "ml-industry", "deep-learning",
        "data-centric-ai", "cybersecurity", "ai-design",
        "barriers-adoption", "xai-finance", "regulation",
        "history-prospects", "blockchains", "industrial-doctoral",
        "green-finance", "multi-criteria",
    ],
    "Transferable Skills": [
        "scientific-writing", "scientific-communication",
        "communication-skills", "project-management", "he-framework",
        "entrepreneurship", "entrepreneurial-finance", "startups-transfer",
        "research-ethics", "ethical-dimensions", "environmental-aspects",
        "open-science", "citizen-science", "gender-diversity",
        "ip-patenting", "job-applications", "labor-market",
    ],
}

# ---------------------------------------------------------------------------
# Source URL lookup (built at startup by build_source_url_index)
# ---------------------------------------------------------------------------
_source_urls = {}  # (section, slug) -> URL

ROOT_PAGE_URLS = {
    "homepage": "https://www.digital-finance-msca.com/",
    "research-projects": "https://www.digital-finance-msca.com/research-projects",
    "irps": "https://www.digital-finance-msca.com/individual-research-projects",
    "media": "https://www.digital-finance-msca.com/media",
    "presentations": "https://www.digital-finance-msca.com/presentations",
    "wp6-doctoral-training": "https://www.digital-finance-msca.com/wp6-doctoral-training",
    "team": "https://www.digital-finance-msca.com/our-people",
}

EVENTS_FALLBACK_URL = "https://www.digital-finance-msca.com/events"
TRAINING_MODULES_URL = "https://www.digital-finance-msca.com/trainings"
TRAINING_EVENTS_URL = "https://www.digital-finance-msca.com/wp6-doctoral-training"


def build_source_url_index():
    """Populate _source_urls from events-structured.json and hardcoded mappings."""
    # Events from JSON: slug -> event URL
    json_path = FIRECRAWL_DIR / "events-structured.json"
    if json_path.exists():
        with open(json_path, encoding="utf-8") as f:
            data = json.load(f)
        for key in ("upcoming_events", "past_events_2026", "past_events_2025", "past_events_2024"):
            for ev in data.get(key, []):
                dp = ev.get("detail_page", "")
                url = ev.get("url", "")
                if dp and url:
                    if dp.endswith("README.md"):
                        slug = Path(dp).parent.name
                    else:
                        slug = Path(dp).stem
                    _source_urls[("events", slug)] = url

    # Root pages
    for slug, url in ROOT_PAGE_URLS.items():
        _source_urls[("pages", slug)] = url


def get_source_url(section: str, slug: str) -> str:
    """Resolve the source URL for a given section and slug."""
    cached = _source_urls.get((section, slug))
    if cached:
        return cached
    if section == "events":
        return EVENTS_FALLBACK_URL
    if section == "training-modules":
        return TRAINING_MODULES_URL
    if section == "training-events":
        return TRAINING_EVENTS_URL
    return ""


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------
stats = {"html": 0, "images": 0, "warnings": []}


# ---------------------------------------------------------------------------
# HTML template
# ---------------------------------------------------------------------------
def page_template(title, breadcrumbs, content):
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{html_mod.escape(title)} — MSCA DIGITAL Finance</title>
  <style>
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; color: #1a1a2e; background: #f8f9fa; line-height: 1.7; }}
    .site-header {{ background: #003399; color: #fff; padding: 1rem 0; }}
    .site-header .container {{ max-width: 1100px; margin: 0 auto; padding: 0 1.5rem; display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 0.5rem; }}
    .site-header a {{ color: #fff; text-decoration: none; font-weight: 600; }}
    .site-header nav a {{ font-weight: 400; margin-left: 1.5rem; opacity: 0.9; }}
    .site-header nav a:hover {{ opacity: 1; text-decoration: underline; }}
    main {{ max-width: 900px; margin: 0 auto; padding: 2rem 1.5rem; }}
    .breadcrumbs {{ font-size: 0.85rem; color: #666; margin-bottom: 1.5rem; }}
    .breadcrumbs a {{ color: #003399; text-decoration: none; }}
    .breadcrumbs a:hover {{ text-decoration: underline; }}
    article h1 {{ font-size: 1.8rem; color: #003399; margin: 1.5rem 0 1rem; }}
    article h2 {{ font-size: 1.4rem; color: #003399; margin: 1.5rem 0 0.75rem; border-bottom: 2px solid #e8e8e8; padding-bottom: 0.3rem; }}
    article h3 {{ font-size: 1.15rem; color: #1a1a2e; margin: 1.25rem 0 0.5rem; }}
    article h4 {{ font-size: 1rem; color: #444; margin: 1rem 0 0.5rem; }}
    article p {{ margin: 0.75rem 0; }}
    article ul, article ol {{ margin: 0.75rem 0 0.75rem 1.5rem; }}
    article li {{ margin: 0.3rem 0; }}
    article img {{ max-width: 100%; height: auto; border-radius: 6px; margin: 1rem 0; }}
    article a {{ color: #003399; }}
    article a:hover {{ text-decoration: underline; }}
    article hr {{ border: none; border-top: 1px solid #ddd; margin: 1.5rem 0; }}
    .card-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 1.25rem; margin: 1.5rem 0; }}
    .card {{ background: #fff; border: 1px solid #e0e0e0; border-radius: 8px; padding: 1.25rem; transition: box-shadow 0.2s; }}
    .card:hover {{ box-shadow: 0 4px 12px rgba(0,0,0,0.1); }}
    .card h3 {{ margin-top: 0; font-size: 1.05rem; }}
    .card h3 a {{ color: #003399; text-decoration: none; }}
    .card h3 a:hover {{ text-decoration: underline; }}
    .card .meta {{ font-size: 0.85rem; color: #666; margin-top: 0.5rem; }}
    .section-group {{ margin: 2rem 0; }}
    .section-group h2 {{ font-size: 1.3rem; color: #003399; border-bottom: 2px solid #003399; padding-bottom: 0.3rem; margin-bottom: 1rem; }}
    .site-footer {{ background: #f0f0f0; border-top: 1px solid #ddd; padding: 2rem 0; margin-top: 3rem; text-align: center; font-size: 0.85rem; color: #666; }}
    .site-footer img {{ max-width: 200px; margin-bottom: 0.75rem; }}
    .site-footer a {{ color: #003399; text-decoration: none; }}
    .site-footer a:hover {{ text-decoration: underline; }}
    .hub-hero {{ text-align: center; padding: 2rem 0 1rem; }}
    .hub-hero h1 {{ font-size: 2rem; }}
    .hub-hero .subtitle {{ color: #555; margin-top: 0.5rem; }}
    .hub-description {{ max-width: 700px; margin: 1rem auto 2rem; text-align: left; }}
    .download-btn {{ display: inline-block; background: #003399; color: #fff; padding: 0.75rem 1.75rem; border-radius: 6px; text-decoration: none; font-weight: 600; margin: 1rem 0; }}
    .download-btn:hover {{ background: #002266; }}
    .source-link {{ margin-top: 2rem; padding-top: 1rem; border-top: 1px solid #e0e0e0; font-size: 0.8rem; color: #888; }}
    .source-link a {{ color: #666; text-decoration: none; }}
    .source-link a:hover {{ color: #003399; text-decoration: underline; }}
    .person-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(140px, 1fr)); gap: 1rem; margin: 1rem 0; }}
    .person-card {{ text-align: center; }}
    .person-card img {{ width: 120px; height: 120px; border-radius: 50%; object-fit: cover; }}
    .person-card p {{ font-size: 0.85rem; margin-top: 0.5rem; }}
    .person-card a {{ color: #003399; text-decoration: none; }}
    @media (max-width: 600px) {{
      .site-header .container {{ flex-direction: column; text-align: center; }}
      .site-header nav a {{ margin-left: 0.5rem; margin-right: 0.5rem; }}
      main {{ padding: 1rem; }}
      .card-grid {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <header class="site-header">
    <div class="container">
      <a href="{BASE}/">MSCA DIGITAL Finance</a>
      <nav>
        <a href="{BASE}/training-modules/">Training Modules</a>
        <a href="{BASE}/events/">Events</a>
        <a href="{BASE}/training-events/">Network Events</a>
        <a href="{BASE}/pages/">Pages</a>
        <a href="{BASE}/booklet.pdf">Booklet PDF</a>
      </nav>
    </div>
  </header>
  <main>
    <div class="breadcrumbs">{breadcrumbs}</div>
    <article>{content}</article>
  </main>
  <footer class="site-footer">
    <img src="{BASE}/images/eu-funded.png" alt="Funded by the European Union">
    <p>Funded by the European Union — Grant No. 101119635</p>
    <p><a href="https://www.digital-finance-msca.com/">www.digital-finance-msca.com</a></p>
  </footer>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Strip Wix boilerplate
# ---------------------------------------------------------------------------
def strip_wix(content: str) -> str:
    # Header: remove everything up to and including [Partners Area](...) + blank lines
    content = re.sub(
        r'^.*?\[Partners Area\]\([^)]+\)\s*\n\s*\n',
        '', content, count=1, flags=re.DOTALL,
    )
    # Footer: remove from the EU-funded image onward
    content = re.sub(
        r'\!\[unnamed\.png\]\(https://static\.wixstatic\.com/media/1cd49e_17065ba4e0cc4fb4a7aa36bfa3ae687e~mv2.*$',
        '', content, flags=re.DOTALL,
    )
    # Also strip any remaining "bottom of page", social icons, copyright
    content = re.sub(r'(?m)^bottom of page\s*$', '', content)
    content = re.sub(r'(?m)^top of page\s*$', '', content)
    content = re.sub(r'(?m)^Skip to Main Content\s*$', '', content)
    # Strip trailing "Follow us" section + social icons if still present
    content = re.sub(r'####\s*Follow us.*$', '', content, flags=re.DOTALL)
    # Strip copyright line
    content = re.sub(r'(?m)^\s*©.*$', '', content)
    # Strip "Privacy Policy" links at the end
    content = re.sub(r'\[Privacy Policy\]\([^)]+\)\s*$', '', content, flags=re.DOTALL)
    return content.strip()


# ---------------------------------------------------------------------------
# Image URL rewriting helpers
# ---------------------------------------------------------------------------
_image_index = {}  # hash -> filename


def build_image_index():
    img_dir = DOCS_DIR / "images"
    if not img_dir.exists():
        return
    for f in os.listdir(img_dir):
        # Extract the hash portion: prefix_hash~mv2.ext
        m = re.match(r'([0-9a-f]+_[0-9a-f]+~mv2)', f)
        if m:
            _image_index[m.group(1)] = f
        else:
            # Also index event-* and other named files by their full stem
            _image_index[Path(f).stem] = f


def rewrite_image_urls(html_content: str) -> str:
    def replacer(m):
        full_url = m.group(0)
        # Try to extract hash like 1cd49e_abcdef123456~mv2
        hash_match = re.search(r'([0-9a-f]+_[0-9a-f]+~mv2)', full_url)
        if hash_match:
            h = hash_match.group(1)
            if h in _image_index:
                return f'{BASE}/images/{_image_index[h]}'
        return full_url
    return re.sub(
        r'https://static\.wixstatic\.com/media/[^\s"\')<>]+',
        replacer, html_content,
    )


def dedup_images(html_content: str) -> str:
    """Remove duplicate blur versions of Wix images (blur+sharp pairs)."""
    def replacer(m):
        img1, img2 = m.group(1), m.group(2)
        hash1 = re.search(r'([0-9a-f]+_[0-9a-f]+~mv2)', img1)
        hash2 = re.search(r'([0-9a-f]+_[0-9a-f]+~mv2)', img2)
        if hash1 and hash2 and hash1.group(1) == hash2.group(1):
            # Same image — keep the sharp (non-blur) version
            if 'blur' in img1:
                return img2
            return img1
        return m.group(0)
    return re.sub(
        r'(<img\s[^>]+>)\s*(<img\s[^>]+>)',
        replacer, html_content,
    )


def build_person_grid(html_content: str) -> str:
    """Detect committee sections and wrap person entries in a CSS grid."""
    # Match committee heading and content until next h2 or end
    pattern = r'(<h2>(?:Organizing|Scientific)\s+Committee</h2>)(.*?)(?=<h2>|$)'
    def section_replacer(m):
        heading = m.group(1)
        body = m.group(2)
        # Find person patterns: <a href="url"><img ...>[<img ...>]Name</a>
        persons = re.findall(
            r'<a\s+href="([^"]+)">\s*(?:<img\s+src="([^"]+)"[^>]*>\s*)+([^<]+?)\s*</a>',
            body,
        )
        if not persons:
            return m.group(0)
        cards = []
        for url, img_src, name in persons:
            name = name.strip()
            if not name:
                continue
            cards.append(
                f'<div class="person-card">'
                f'<a href="{url}">'
                f'<img src="{img_src}" alt="{html_mod.escape(name)}">'
                f'<p>{html_mod.escape(name)}</p>'
                f'</a></div>'
            )
        if not cards:
            return m.group(0)
        grid = '<div class="person-grid">\n' + '\n'.join(cards) + '\n</div>'
        return heading + '\n' + grid
    return re.sub(pattern, section_replacer, html_content, flags=re.DOTALL)


# ---------------------------------------------------------------------------
# Markdown -> HTML (regex-based, no deps)
# ---------------------------------------------------------------------------
def md_to_html(md: str) -> str:
    # Strip Wix-style line breaks — join lines (don't leave blank lines)
    md = md.replace('\\\\\n', '')  # \\ + newline → join
    md = md.replace('\\\n', '')    # \ + newline → join
    # Strip standalone backslash lines
    md = re.sub(r'(?m)^\\\\$', '', md)
    md = re.sub(r'(?m)^\\$', '', md)
    lines = md.split('\n')
    out_blocks = []
    i = 0

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # Blank line
        if not stripped:
            i += 1
            continue

        # Horizontal rule
        if re.match(r'^---+\s*$', stripped):
            out_blocks.append('<hr>')
            i += 1
            continue

        # Headings
        hm = re.match(r'^(#{1,4})\s+(.*)', stripped)
        if hm:
            level = len(hm.group(1))
            text = hm.group(2).strip()
            # Strip bold markers inside headings
            text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
            text = inline_format(text)
            out_blocks.append(f'<h{level}>{text}</h{level}>')
            i += 1
            continue

        # Unordered list
        if re.match(r'^[-*]\s+', stripped):
            items = []
            while i < len(lines) and re.match(r'^\s*[-*]\s+', lines[i]):
                item_text = re.sub(r'^\s*[-*]\s+', '', lines[i]).strip()
                items.append(f'<li>{inline_format(item_text)}</li>')
                i += 1
            out_blocks.append('<ul>' + '\n'.join(items) + '</ul>')
            continue

        # Ordered list
        if re.match(r'^\d+\.\s+', stripped):
            items = []
            while i < len(lines) and re.match(r'^\s*\d+\.\s+', lines[i]):
                item_text = re.sub(r'^\s*\d+\.\s+', '', lines[i]).strip()
                items.append(f'<li>{inline_format(item_text)}</li>')
                i += 1
            out_blocks.append('<ol>' + '\n'.join(items) + '</ol>')
            continue

        # Paragraph: collect consecutive non-blank, non-special lines
        para_lines = []
        while i < len(lines):
            s = lines[i].strip()
            if not s:
                i += 1
                break
            if re.match(r'^#{1,4}\s+', s):
                break
            if re.match(r'^---+\s*$', s):
                break
            if re.match(r'^[-*]\s+', s):
                break
            if re.match(r'^\d+\.\s+', s):
                break
            para_lines.append(s)
            i += 1

        if para_lines:
            text = ' '.join(para_lines)
            text = inline_format(text)
            # If the paragraph is purely an image tag, don't wrap in <p>
            if re.match(r'^<img\s[^>]+>\s*$', text.strip()):
                out_blocks.append(text.strip())
            else:
                out_blocks.append(f'<p>{text}</p>')

    return '\n'.join(out_blocks)


def inline_format(text: str) -> str:
    # Fix escaped pipes from Firecrawl
    text = text.replace('\\|', '|')
    # Strip double-backslash Wix line breaks
    text = text.replace('\\\\', '')
    # Strip any trailing single backslash
    text = text.rstrip('\\')
    # Images BEFORE links (![alt](url))
    text = re.sub(
        r'!\[([^\]]*)\]\(([^)]+)\)',
        r'<img src="\2" alt="\1">',
        text,
    )
    # Links [text](url) -- but not images (already converted)
    text = re.sub(
        r'\[([^\]]+)\]\(([^)]+)\)',
        r'<a href="\2">\1</a>',
        text,
    )
    # Bold **text**
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    # Italic *text* (but not inside already-converted tags)
    text = re.sub(r'(?<![<\w/])\*([^*]+?)\*(?![>])', r'<em>\1</em>', text)
    return text


# ---------------------------------------------------------------------------
# Title extraction
# ---------------------------------------------------------------------------
def extract_title(md: str, fallback: str) -> str:
    # Try # Title first (highest level = page title)
    m = re.search(r'^#\s+(.+)', md, re.MULTILINE)
    if m:
        t = m.group(1).strip()
        t = re.sub(r'\*\*(.+?)\*\*', r'\1', t)
        return t
    # Try ## Title
    m = re.search(r'^##\s+(.+)', md, re.MULTILINE)
    if m:
        t = m.group(1).strip()
        t = re.sub(r'\*\*(.+?)\*\*', r'\1', t)
        return t
    # Try ### **Title**
    m = re.search(r'^###\s+\*\*(.+?)\*\*', md, re.MULTILINE)
    if m:
        return m.group(1).strip()
    return fallback.replace('-', ' ').title()


# ---------------------------------------------------------------------------
# File helpers
# ---------------------------------------------------------------------------
def read_md(path: Path) -> str:
    return path.read_text(encoding='utf-8', errors='replace')


def write_html(path: Path, content: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding='utf-8')
    stats["html"] += 1


def slug_to_title(slug: str) -> str:
    return slug.replace('-', ' ').title()


# ---------------------------------------------------------------------------
# 1. Clean docs/
# ---------------------------------------------------------------------------
def clean_docs():
    if not DOCS_DIR.exists():
        DOCS_DIR.mkdir(parents=True)
        return
    for item in os.listdir(DOCS_DIR):
        p = DOCS_DIR / item
        if item in PRESERVE_FILES:
            continue
        if p.is_dir():
            shutil.rmtree(p)
        elif item.endswith('.html'):
            p.unlink()


# ---------------------------------------------------------------------------
# 2. Copy images
# ---------------------------------------------------------------------------
def copy_images():
    src = FIRECRAWL_DIR / "images"
    dst = DOCS_DIR / "images"
    dst.mkdir(parents=True, exist_ok=True)

    if src.exists():
        for f in os.listdir(src):
            shutil.copy2(src / f, dst / f)
            stats["images"] += 1

    # Copy eu-funded.png into images/ so footer reference works
    eu_src = DOCS_DIR / "eu-funded.png"
    if eu_src.exists():
        shutil.copy2(eu_src, dst / "eu-funded.png")


# ---------------------------------------------------------------------------
# 3. Create output directories
# ---------------------------------------------------------------------------
def create_dirs():
    for d in ["training-modules", "events", "training-events", "pages", "images"]:
        (DOCS_DIR / d).mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# 7. Generate individual pages
# ---------------------------------------------------------------------------
def build_page(md_path: Path, section: str, section_label: str, section_url: str, slug: str):
    raw = read_md(md_path)
    cleaned = strip_wix(raw)
    title = extract_title(cleaned, slug)
    html_body = md_to_html(cleaned)
    html_body = dedup_images(html_body)       # before rewrite so blur URLs detectable
    html_body = rewrite_image_urls(html_body)
    html_body = build_person_grid(html_body)

    # Append source link for individual pages
    source_url = get_source_url(section, slug)
    if source_url:
        html_body += (
            f'\n<div class="source-link">'
            f'<a href="{html_mod.escape(source_url)}" target="_blank" rel="noopener">'
            f'View original page on digital-finance-msca.com</a></div>'
        )

    bc = (
        f'<a href="{BASE}/">Home</a> &rsaquo; '
        f'<a href="{BASE}/{section_url}/">{section_label}</a> &rsaquo; '
        f'{html_mod.escape(title)}'
    )

    full_html = page_template(title, bc, html_body)
    out_path = DOCS_DIR / section / f"{slug}.html"
    write_html(out_path, full_html)
    return title


def build_training_modules():
    src_dir = FIRECRAWL_DIR / "training-modules"
    titles = {}
    for md_file in sorted(src_dir.glob("*.md")):
        slug = md_file.stem
        t = build_page(md_file, "training-modules", "Training Modules", "training-modules", slug)
        titles[slug] = t
    return titles


def build_events():
    ev_dir = FIRECRAWL_DIR / "events"
    titles = {}

    # Subdirectory events (dir/README.md)
    for d in sorted(ev_dir.iterdir()):
        if d.is_dir():
            readme = d / "README.md"
            if readme.exists():
                slug = d.name
                t = build_page(readme, "events", "Events", "events", slug)
                titles[slug] = t

    # Standalone .md files
    for md_file in sorted(ev_dir.glob("*.md")):
        if md_file.name == "README.md":
            continue
        slug = md_file.stem
        t = build_page(md_file, "events", "Events", "events", slug)
        titles[slug] = t

    return titles


def build_training_events():
    src_dir = FIRECRAWL_DIR / "training-events"
    titles = {}
    for md_file in sorted(src_dir.glob("*.md")):
        slug = md_file.stem
        t = build_page(md_file, "training-events", "Network Events", "training-events", slug)
        titles[slug] = t
    return titles


def build_root_pages():
    titles = {}
    for name in ROOT_PAGES:
        md_file = FIRECRAWL_DIR / f"{name}.md"
        if md_file.exists():
            t = build_page(md_file, "pages", "Pages", "pages", name)
            titles[name] = t
        else:
            stats["warnings"].append(f"Root page not found: {name}.md")
    return titles


# ---------------------------------------------------------------------------
# 8. Generate index pages
# ---------------------------------------------------------------------------
def build_hub_index():
    content = f"""
<div class="hub-hero">
  <h1>MSCA DIGITAL Finance PhD Training</h1>
  <p class="subtitle">Marie Sk&#322;odowska-Curie Doctoral Network on Digital Finance</p>
</div>
<div class="hub-description">
  <p>Welcome to the training programme of the <strong>MSCA DIGITAL Finance</strong> doctoral network.
  This site collects all training modules, events, and programme resources for the
  15 doctoral candidates funded under Horizon Europe Grant No. 101119635.</p>
  <p><a class="download-btn" href="{BASE}/booklet.pdf">Download Programme Booklet (PDF)</a></p>
</div>
<div class="card-grid">
  <div class="card">
    <h3><a href="{BASE}/training-modules/">Training Modules</a></h3>
    <p>41 courses — mandatory, elective, and transferable skills</p>
  </div>
  <div class="card">
    <h3><a href="{BASE}/events/">Events</a></h3>
    <p>39 events from 2024–2026</p>
  </div>
  <div class="card">
    <h3><a href="{BASE}/training-events/">Network Events</a></h3>
    <p>8 planned network training events</p>
  </div>
  <div class="card">
    <h3><a href="{BASE}/pages/">Programme Pages</a></h3>
    <p>Homepage, research, team, media</p>
  </div>
</div>
"""
    bc = '<a href="' + BASE + '/">Home</a>'
    html = page_template("MSCA DIGITAL Finance PhD Training", bc, content)
    write_html(DOCS_DIR / "index.html", html)


def build_training_modules_index():
    # Load structured data
    with open(FIRECRAWL_DIR / "training-modules-structured.json", encoding="utf-8") as f:
        data = json.load(f)

    # Build lookup: slug -> module info
    modules_by_slug = {}
    for m in data.get("modules", []):
        modules_by_slug[m["slug"]] = m

    content_parts = ['<h1>Training Modules</h1>']
    content_parts.append(f'<p>{data.get("count", 41)} doctoral training courses across foundational, advanced, and transferable skills.</p>')

    for cat_name, slugs in CATEGORIES.items():
        content_parts.append(f'<div class="section-group"><h2>{html_mod.escape(cat_name)}</h2>')
        content_parts.append('<div class="card-grid">')
        for slug in slugs:
            info = modules_by_slug.get(slug, {})
            title = info.get("title", slug_to_title(slug))
            institution = info.get("institution") or ""
            ects = info.get("ects")
            ects_str = f"{ects} ECTS" if ects else ""
            meta_parts = [x for x in [institution, ects_str] if x]
            meta = " — ".join(meta_parts)
            content_parts.append(
                f'<div class="card">'
                f'<h3><a href="{BASE}/training-modules/{slug}.html">{html_mod.escape(title)}</a></h3>'
                f'<p class="meta">{html_mod.escape(meta)}</p>'
                f'</div>'
            )
        content_parts.append('</div></div>')

    bc = (
        f'<a href="{BASE}/">Home</a> &rsaquo; Training Modules'
    )
    html = page_template("Training Modules", bc, '\n'.join(content_parts))
    write_html(DOCS_DIR / "training-modules" / "index.html", html)


def build_events_index():
    with open(FIRECRAWL_DIR / "events-structured.json", encoding="utf-8") as f:
        data = json.load(f)

    content_parts = ['<h1>Events</h1>']

    sections = [
        ("Upcoming Events", "upcoming_events"),
        ("Past Events 2026", "past_events_2026"),
        ("Past Events 2025", "past_events_2025"),
        ("Past Events 2024", "past_events_2024"),
    ]

    for label, key in sections:
        events = data.get(key, [])
        if not events:
            continue
        content_parts.append(f'<div class="section-group"><h2>{label}</h2>')
        content_parts.append('<div class="card-grid">')
        for ev in events:
            title = ev.get("title", "Event")
            date = ev.get("date", "")
            location = ev.get("location", "")

            # Determine slug for linking
            slug = _event_slug(ev)
            meta_parts = [x for x in [date, location] if x]
            meta = " — ".join(meta_parts)

            if slug:
                content_parts.append(
                    f'<div class="card">'
                    f'<h3><a href="{BASE}/events/{slug}.html">{html_mod.escape(title)}</a></h3>'
                    f'<p class="meta">{html_mod.escape(meta)}</p>'
                    f'</div>'
                )
            else:
                # No detail page -- show without link, or link to original URL
                url = ev.get("url", "")
                if url:
                    content_parts.append(
                        f'<div class="card">'
                        f'<h3><a href="{html_mod.escape(url)}">{html_mod.escape(title)}</a></h3>'
                        f'<p class="meta">{html_mod.escape(meta)}</p>'
                        f'</div>'
                    )
                else:
                    content_parts.append(
                        f'<div class="card">'
                        f'<h3>{html_mod.escape(title)}</h3>'
                        f'<p class="meta">{html_mod.escape(meta)}</p>'
                        f'</div>'
                    )
        content_parts.append('</div></div>')

    bc = f'<a href="{BASE}/">Home</a> &rsaquo; Events'
    html = page_template("Events", bc, '\n'.join(content_parts))
    write_html(DOCS_DIR / "events" / "index.html", html)


def _event_slug(ev: dict) -> str:
    """Extract slug from an event dict. Returns empty string if no detail page."""
    dp = ev.get("detail_page", "")
    if dp:
        if dp.endswith("README.md"):
            # events/slug/README.md -> slug
            return Path(dp).parent.name
        else:
            # events/slug.md -> slug
            return Path(dp).stem

    # Fallback: try to derive slug from URL
    url = ev.get("url", "")
    if url:
        # Check if we have a matching file
        parts = url.rstrip('/').split('/')
        if parts:
            candidate = parts[-1]
            # Check against our generated event files
            event_html = DOCS_DIR / "events" / f"{candidate}.html"
            if event_html.exists():
                return candidate

    return ""


def build_training_events_index():
    with open(FIRECRAWL_DIR / "training-events-structured.json", encoding="utf-8") as f:
        data = json.load(f)

    content_parts = ['<h1>Network Training Events</h1>']
    content_parts.append(f'<p>{data.get("count", 8)} planned network training events across the doctoral programme.</p>')
    content_parts.append('<div class="card-grid">')

    for ev in data.get("events", []):
        slug = ev.get("slug", "")
        title = ev.get("title", slug_to_title(slug))
        # If title looks like a slug, prettify it
        if title == slug:
            title = slug_to_title(slug)
        desc = ev.get("description", "")
        if len(desc) > 150:
            desc = desc[:147] + "..."
        content_parts.append(
            f'<div class="card">'
            f'<h3><a href="{BASE}/training-events/{slug}.html">{html_mod.escape(title)}</a></h3>'
            f'<p class="meta">{html_mod.escape(desc)}</p>'
            f'</div>'
        )

    content_parts.append('</div>')

    bc = f'<a href="{BASE}/">Home</a> &rsaquo; Network Events'
    html = page_template("Network Training Events", bc, '\n'.join(content_parts))
    write_html(DOCS_DIR / "training-events" / "index.html", html)


def build_pages_index(page_titles: dict):
    content_parts = ['<h1>Programme Pages</h1>']
    content_parts.append('<div class="card-grid">')

    for slug in ROOT_PAGES:
        title = page_titles.get(slug, slug_to_title(slug))
        content_parts.append(
            f'<div class="card">'
            f'<h3><a href="{BASE}/pages/{slug}.html">{html_mod.escape(title)}</a></h3>'
            f'</div>'
        )

    content_parts.append('</div>')

    bc = f'<a href="{BASE}/">Home</a> &rsaquo; Pages'
    html = page_template("Programme Pages", bc, '\n'.join(content_parts))
    write_html(DOCS_DIR / "pages" / "index.html", html)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    print("=== Building MSCA DIGITAL Finance static site ===")
    print(f"Source:  {FIRECRAWL_DIR}")
    print(f"Output:  {DOCS_DIR}")
    print()

    # 1. Clean
    print("[1/9] Cleaning docs/ ...")
    clean_docs()

    # 2-3. Create dirs and copy images
    print("[2/9] Creating directories ...")
    create_dirs()

    print("[3/9] Copying images ...")
    copy_images()

    # Build image index for URL rewriting
    build_image_index()

    # Build source URL index for "View original page" links
    build_source_url_index()

    # 7. Build individual pages
    print("[4/9] Building training module pages ...")
    tm_titles = build_training_modules()
    print(f"       {len(tm_titles)} training modules")

    print("[5/9] Building event pages ...")
    ev_titles = build_events()
    print(f"       {len(ev_titles)} events")

    print("[6/9] Building training event pages ...")
    te_titles = build_training_events()
    print(f"       {len(te_titles)} training events")

    print("[7/9] Building root pages ...")
    rp_titles = build_root_pages()
    print(f"       {len(rp_titles)} pages")

    # 8. Build index pages
    print("[8/9] Building index pages ...")
    build_hub_index()
    build_training_modules_index()
    build_events_index()
    build_training_events_index()
    build_pages_index(rp_titles)
    print("       5 index pages")

    # 9. Summary
    print()
    print("=== Build complete ===")
    print(f"  HTML files generated: {stats['html']}")
    print(f"  Images copied:        {stats['images']}")
    if stats["warnings"]:
        print(f"  Warnings ({len(stats['warnings'])}):")
        for w in stats["warnings"]:
            print(f"    - {w}")
    else:
        print("  Warnings:             0")
    print()


if __name__ == "__main__":
    main()
