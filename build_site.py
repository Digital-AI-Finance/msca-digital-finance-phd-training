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

TITLE_OVERRIDES = {
    "homepage": "MSCA Digital Finance \u2014 Homepage",
    "team": "Our People",
}


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
# Sidebar helpers
# ---------------------------------------------------------------------------
def make_heading_id(text, seen_ids):
    """Generate a unique heading ID, appending -2, -3, etc. for duplicates."""
    base = re.sub(r'[^a-z0-9]+', '-', re.sub(r'<[^>]+>', '', text).lower()).strip('-')
    if not base:
        base = 'section'
    slug = base
    counter = 2
    while slug in seen_ids:
        slug = f"{base}-{counter}"
        counter += 1
    seen_ids.add(slug)
    return slug


def extract_headings(html_body):
    """Extract h2/h3 headings with their id attributes from HTML."""
    headings = []
    for m in re.finditer(r'<h([23])\s+id="([^"]*)"[^>]*>(.*?)</h\1>', html_body):
        level = int(m.group(1))
        heading_id = m.group(2)
        text = re.sub(r'<[^>]+>', '', m.group(3))
        headings.append((level, text, heading_id))
    return headings


def build_sidebar(section, section_label, current_slug, section_pages, headings):
    """Build sidebar HTML with section nav and on-this-page TOC.

    section: URL segment (e.g., "training-modules")
    section_label: display name (e.g., "Training Modules")
    current_slug: slug of the current page for active highlighting
    section_pages: list[(slug, title)] -- all pages in this section
    headings: list[(level, text, id)] -- h2/h3 headings for TOC
    """
    parts = ['<nav class="sidebar-nav">']
    parts.append('<div class="sidebar-section">')
    parts.append(f'<h3><a href="{BASE}/{section}/">{html_mod.escape(section_label)}</a></h3>')
    parts.append('<ul>')
    for pg_slug, pg_title in section_pages:
        active = ' class="active"' if pg_slug == current_slug else ''
        # For homepage sidebar, section_pages entries link to index pages
        if section == "home":
            parts.append(f'<li{active}><a href="{BASE}/{pg_slug}/">{html_mod.escape(pg_title)}</a></li>')
        else:
            parts.append(f'<li{active}><a href="{BASE}/{section}/{pg_slug}.html">{html_mod.escape(pg_title)}</a></li>')
    parts.append('</ul>')
    parts.append('</div>')

    if headings:
        parts.append('<div class="sidebar-toc">')
        parts.append('<h4>On this page</h4>')
        parts.append('<ul>')
        for level, text, hid in headings:
            indent_cls = ' class="toc-h3"' if level == 3 else ''
            parts.append(f'<li{indent_cls}><a href="#{hid}">{html_mod.escape(text)}</a></li>')
        parts.append('</ul>')
        parts.append('</div>')

    parts.append('</nav>')
    return '\n'.join(parts)


# ---------------------------------------------------------------------------
# HTML template
# ---------------------------------------------------------------------------
def page_template(title, breadcrumbs, content, current_section="", sidebar_html=""):
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{html_mod.escape(title)} — MSCA DIGITAL Finance</title>
  <style>
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; color: #1a1a2e; background: #f8f9fa; line-height: 1.6; }}
    .skip-link {{ position: absolute; left: -9999px; top: auto; width: 1px; height: 1px; overflow: hidden; z-index: 1000; }}
    .skip-link:focus {{ position: fixed; left: 1rem; top: 1rem; width: auto; height: auto; overflow: visible; background: #003399; color: #fff; padding: 0.5rem 1rem; border-radius: 4px; font-size: 0.9rem; z-index: 1000; text-decoration: none; }}
    .site-header {{ background: #003399; color: #fff; padding: 0.75rem 1.5rem; display: flex; align-items: center; gap: 1rem; }}
    .site-header a {{ color: #fff; text-decoration: none; font-weight: 600; }}
    .site-logo {{ white-space: nowrap; }}
    .layout {{ display: flex; min-height: calc(100vh - 60px - 120px); }}
    .sidebar {{ width: 240px; flex-shrink: 0; background: #f0f2f5; border-right: 1px solid #ddd; padding: 1rem 0; overflow-y: auto; position: sticky; top: 0; max-height: 100vh; }}
    main {{ flex: 1; min-width: 0; padding: 2rem 2.5rem; }}
    .breadcrumbs {{ font-size: 0.85rem; color: #666; margin-bottom: 1rem; }}
    .breadcrumbs a {{ color: #003399; text-decoration: none; }}
    .breadcrumbs a:hover {{ text-decoration: underline; }}
    article h1 {{ font-size: 1.8rem; color: #003399; margin: 1rem 0 0.75rem; }}
    article h2 {{ font-size: 1.4rem; color: #003399; margin: 1rem 0 0.5rem; border-bottom: 2px solid #e8e8e8; padding-bottom: 0.3rem; }}
    article h3 {{ font-size: 1.15rem; color: #1a1a2e; margin: 1.25rem 0 0.5rem; }}
    article h4 {{ font-size: 1rem; color: #444; margin: 1rem 0 0.5rem; }}
    article p {{ margin: 0.5rem 0; }}
    article ul, article ol {{ margin: 0.5rem 0 0.5rem 1.5rem; }}
    article li {{ margin: 0.2rem 0; }}
    article img {{ max-width: 100%; height: auto; border-radius: 6px; margin: 1rem 0; }}
    article a {{ color: #003399; }}
    article a:hover {{ text-decoration: underline; }}
    article hr {{ border: none; border-top: 1px solid #ddd; margin: 1.5rem 0; }}
    .section-group {{ margin: 2rem 0; }}
    .section-group h2 {{ font-size: 1.3rem; color: #003399; border-bottom: 2px solid #003399; padding-bottom: 0.3rem; margin-bottom: 1rem; }}
    .summary-table {{ width: 100%; border-collapse: collapse; margin: 1rem 0; font-size: 0.9rem; }}
    .summary-table th {{ text-align: left; background: #f0f2f5; padding: 0.5rem 0.75rem; border-bottom: 2px solid #003399; font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.03em; color: #666; }}
    .summary-table td {{ padding: 0.4rem 0.75rem; border-bottom: 1px solid #e8e8e8; }}
    .summary-table tr:hover {{ background: #f8f9ff; }}
    .summary-table a {{ color: #003399; text-decoration: none; }}
    .summary-table a:hover {{ text-decoration: underline; }}
    .site-footer {{ background: #f0f0f0; border-top: 1px solid #ddd; padding: 2rem 0; margin-top: 3rem; text-align: center; font-size: 0.85rem; color: #666; }}
    .site-footer img {{ max-width: 200px; margin-bottom: 0.75rem; }}
    .site-footer a {{ color: #003399; text-decoration: none; }}
    .site-footer a:hover {{ text-decoration: underline; }}
    .footer-nav {{ margin-bottom: 1.5rem; display: flex; flex-wrap: wrap; justify-content: center; gap: 1rem; }}
    .footer-nav a {{ color: #003399; text-decoration: none; font-size: 0.9rem; }}
    .footer-nav a:hover {{ text-decoration: underline; }}
    .hub-hero {{ text-align: center; padding: 1.5rem 0 0.75rem; }}
    .hub-hero h1 {{ font-size: 2rem; }}
    .hub-hero .subtitle {{ color: #555; margin-top: 0.5rem; }}
    .hub-description {{ max-width: 700px; margin: 1rem auto 2rem; text-align: left; }}
    .download-btn {{ display: inline-block; background: #003399; color: #fff; padding: 0.75rem 1.75rem; border-radius: 6px; text-decoration: none; font-weight: 600; margin: 1rem 0; }}
    .download-btn:hover {{ background: #002266; }}
    .page-nav {{ display: flex; justify-content: space-between; align-items: center; margin-top: 2rem; padding-top: 1rem; border-top: 1px solid #e0e0e0; font-size: 0.9rem; gap: 1rem; }}
    .page-nav a {{ color: #003399; text-decoration: none; }}
    .page-nav a:hover {{ text-decoration: underline; }}
    .page-nav-prev {{ text-align: left; }}
    .page-nav-index {{ text-align: center; flex-shrink: 0; }}
    .page-nav-next {{ text-align: right; }}
    .source-link {{ margin-top: 2rem; padding-top: 1rem; border-top: 1px solid #e0e0e0; font-size: 0.8rem; color: #888; }}
    .source-link a {{ color: #666; text-decoration: none; }}
    .source-link a:hover {{ color: #003399; text-decoration: underline; }}
    .person-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(140px, 1fr)); gap: 1rem; margin: 1rem 0; }}
    .person-card {{ text-align: center; }}
    .person-card img {{ width: 120px; height: 120px; border-radius: 50%; object-fit: cover; }}
    .person-card p {{ font-size: 0.85rem; margin-top: 0.5rem; }}
    .person-card a {{ color: #003399; text-decoration: none; }}
    .sidebar-nav h3 {{ font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.05em; color: #666; padding: 0 1rem; margin-bottom: 0.5rem; }}
    .sidebar-nav h3 a {{ color: #003399; text-decoration: none; }}
    .sidebar-nav ul {{ list-style: none; padding: 0; }}
    .sidebar-nav li a {{ display: block; padding: 0.25rem 1rem; color: #333; text-decoration: none; font-size: 0.82rem; line-height: 1.4; border-left: 3px solid transparent; }}
    .sidebar-nav li a:hover {{ background: #e8eaf0; color: #003399; }}
    .sidebar-nav li.active a {{ background: #e0e4ee; color: #003399; font-weight: 600; border-left: 3px solid #003399; }}
    .sidebar-toc {{ margin-top: 1.5rem; border-top: 1px solid #ddd; padding-top: 1rem; }}
    .sidebar-toc h4 {{ font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.05em; color: #999; padding: 0 1rem; margin-bottom: 0.5rem; }}
    .sidebar-toc li a {{ font-size: 0.78rem; padding: 0.2rem 1rem; }}
    .sidebar-toc li.toc-h3 a {{ padding-left: 1.75rem; }}
    .mobile-sidebar-toggle {{ display: none; }}
    .mobile-sidebar-toggle summary {{ font-size: 1.5rem; cursor: pointer; list-style: none; background: none; border: none; color: #fff; }}
    .mobile-sidebar-toggle summary::-webkit-details-marker {{ display: none; }}
    @media (max-width: 768px) {{
      .sidebar {{ display: none; }}
      .mobile-sidebar-toggle {{ display: block; }}
      .mobile-sidebar-overlay {{ position: fixed; top: 0; left: 0; width: 280px; height: 100vh; background: #f0f2f5; z-index: 100; overflow-y: auto; box-shadow: 2px 0 8px rgba(0,0,0,0.2); padding: 1rem 0; }}
      main {{ padding: 1rem; }}
      .page-nav {{ flex-direction: column; text-align: center; }}
    }}
  </style>
</head>
<body>
  <a href="#content" class="skip-link">Skip to content</a>
  <header class="site-header">
    <details class="mobile-sidebar-toggle">
      <summary aria-label="Menu">&#9776;</summary>
      <div class="mobile-sidebar-overlay">
        {sidebar_html}
      </div>
    </details>
    <a href="{BASE}/" class="site-logo">MSCA DIGITAL Finance</a>
  </header>
  <div class="layout">
    <aside class="sidebar">{sidebar_html}</aside>
    <main id="content">
      <div class="breadcrumbs">{breadcrumbs}</div>
      <article>{content}</article>
    </main>
  </div>
  <footer class="site-footer">
    <nav class="footer-nav">
      <a href="{BASE}/">Home</a>
      <a href="{BASE}/training-modules/">Training Modules</a>
      <a href="{BASE}/events/">Events</a>
      <a href="{BASE}/training-events/">Network Events</a>
      <a href="{BASE}/pages/">Pages</a>
    </nav>
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
    pattern = r'(<h2[^>]*>(?:Organizing|Scientific)\s+Committee</h2>)(.*?)(?=<h2|$)'
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
    md = md.replace('\\\\\n', '')  # \\ + newline -> join
    md = md.replace('\\\n', '')    # \ + newline -> join
    # Strip standalone backslash lines
    md = re.sub(r'(?m)^\\\\$', '', md)
    md = re.sub(r'(?m)^\\$', '', md)
    lines = md.split('\n')
    out_blocks = []
    i = 0
    seen_ids = set()

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
            heading_id = make_heading_id(text, seen_ids)
            out_blocks.append(f'<h{level} id="{heading_id}">{text}</h{level}>')
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
    t = None
    # Try # Title first (highest level = page title)
    m = re.search(r'^#\s+(.+)', md, re.MULTILINE)
    if m:
        t = m.group(1).strip()
    # Try ## Title
    if not t:
        m = re.search(r'^##\s+(.+)', md, re.MULTILINE)
        if m:
            t = m.group(1).strip()
    # Try ### **Title**
    if not t:
        m = re.search(r'^###\s+\*\*(.+?)\*\*', md, re.MULTILINE)
        if m:
            t = m.group(1).strip()
    if not t:
        return fallback.replace('-', ' ').title()
    # Strip bold markers
    t = re.sub(r'\*\*(.+?)\*\*', r'\1', t)
    # Strip markdown links: [text](url) -> text
    t = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', t)
    return t


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
def build_page(md_path: Path, section: str, section_label: str, section_url: str, slug: str,
               prev_link=None, next_link=None, pre_title=None, section_pages=None):
    raw = read_md(md_path)
    cleaned = strip_wix(raw)
    title = TITLE_OVERRIDES.get(slug) or pre_title or extract_title(cleaned, slug)
    html_body = md_to_html(cleaned)
    html_body = dedup_images(html_body)       # before rewrite so blur URLs detectable
    html_body = rewrite_image_urls(html_body)
    html_body = build_person_grid(html_body)

    # Prev/next navigation (before source link)
    if prev_link or next_link:
        nav_parts = ['<nav class="page-nav">']
        if prev_link:
            nav_parts.append(
                f'<a href="{BASE}/{section}/{prev_link[0]}.html" class="page-nav-prev">'
                f'\u2190 {html_mod.escape(prev_link[1])}</a>')
        else:
            nav_parts.append('<span></span>')
        nav_parts.append(
            f'<a href="{BASE}/{section_url}/" class="page-nav-index">All {section_label}</a>')
        if next_link:
            nav_parts.append(
                f'<a href="{BASE}/{section}/{next_link[0]}.html" class="page-nav-next">'
                f'{html_mod.escape(next_link[1])} \u2192</a>')
        else:
            nav_parts.append('<span></span>')
        nav_parts.append('</nav>')
        html_body += '\n' + '\n'.join(nav_parts)

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

    # Build sidebar
    headings = extract_headings(html_body)
    sidebar = build_sidebar(section, section_label, slug, section_pages or [], headings)

    full_html = page_template(title, bc, html_body, current_section=section, sidebar_html=sidebar)
    out_path = DOCS_DIR / section / f"{slug}.html"
    write_html(out_path, full_html)
    return title


def build_training_modules():
    src_dir = FIRECRAWL_DIR / "training-modules"
    pages = [(md.stem, md) for md in sorted(src_dir.glob("*.md"))]
    # Pre-extract titles to avoid double reads for prev/next labels
    pre_titles = {}
    for slug, md_file in pages:
        raw = read_md(md_file)
        cleaned = strip_wix(raw)
        pre_titles[slug] = TITLE_OVERRIDES.get(slug) or extract_title(cleaned, slug)
    section_pages = [(slug, pre_titles[slug]) for slug, _ in pages]
    titles = {}
    for idx, (slug, md_file) in enumerate(pages):
        prev_link = (pages[idx-1][0], pre_titles[pages[idx-1][0]]) if idx > 0 else None
        next_link = (pages[idx+1][0], pre_titles[pages[idx+1][0]]) if idx < len(pages)-1 else None
        t = build_page(md_file, "training-modules", "Training Modules", "training-modules", slug,
                       prev_link=prev_link, next_link=next_link, pre_title=pre_titles[slug],
                       section_pages=section_pages)
        titles[slug] = t
    return titles


def build_events():
    ev_dir = FIRECRAWL_DIR / "events"
    # Collect all event pages: (slug, md_path)
    pages = []
    for d in sorted(ev_dir.iterdir()):
        if d.is_dir():
            readme = d / "README.md"
            if readme.exists():
                pages.append((d.name, readme))
    for md_file in sorted(ev_dir.glob("*.md")):
        if md_file.name == "README.md":
            continue
        pages.append((md_file.stem, md_file))
    # Pre-extract titles
    pre_titles = {}
    for slug, md_file in pages:
        raw = read_md(md_file)
        cleaned = strip_wix(raw)
        pre_titles[slug] = TITLE_OVERRIDES.get(slug) or extract_title(cleaned, slug)
    section_pages = [(slug, pre_titles[slug]) for slug, _ in pages]
    titles = {}
    for idx, (slug, md_file) in enumerate(pages):
        prev_link = (pages[idx-1][0], pre_titles[pages[idx-1][0]]) if idx > 0 else None
        next_link = (pages[idx+1][0], pre_titles[pages[idx+1][0]]) if idx < len(pages)-1 else None
        t = build_page(md_file, "events", "Events", "events", slug,
                       prev_link=prev_link, next_link=next_link, pre_title=pre_titles[slug],
                       section_pages=section_pages)
        titles[slug] = t
    return titles


def build_training_events():
    src_dir = FIRECRAWL_DIR / "training-events"
    pages = [(md.stem, md) for md in sorted(src_dir.glob("*.md"))]
    # Pre-extract titles
    pre_titles = {}
    for slug, md_file in pages:
        raw = read_md(md_file)
        cleaned = strip_wix(raw)
        pre_titles[slug] = TITLE_OVERRIDES.get(slug) or extract_title(cleaned, slug)
    section_pages = [(slug, pre_titles[slug]) for slug, _ in pages]
    titles = {}
    for idx, (slug, md_file) in enumerate(pages):
        prev_link = (pages[idx-1][0], pre_titles[pages[idx-1][0]]) if idx > 0 else None
        next_link = (pages[idx+1][0], pre_titles[pages[idx+1][0]]) if idx < len(pages)-1 else None
        t = build_page(md_file, "training-events", "Network Events", "training-events", slug,
                       prev_link=prev_link, next_link=next_link, pre_title=pre_titles[slug],
                       section_pages=section_pages)
        titles[slug] = t
    return titles


def build_root_pages():
    # Pre-extract titles for sidebar section_pages
    pre_titles = {}
    for name in ROOT_PAGES:
        md_file = FIRECRAWL_DIR / f"{name}.md"
        if md_file.exists():
            raw = read_md(md_file)
            cleaned = strip_wix(raw)
            pre_titles[name] = TITLE_OVERRIDES.get(name) or extract_title(cleaned, name)
    section_pages = [(slug, pre_titles.get(slug, slug_to_title(slug))) for slug in ROOT_PAGES if slug in pre_titles]
    titles = {}
    for name in ROOT_PAGES:
        md_file = FIRECRAWL_DIR / f"{name}.md"
        if md_file.exists():
            t = build_page(md_file, "pages", "Pages", "pages", name,
                           section_pages=section_pages, pre_title=pre_titles.get(name))
            titles[name] = t
        else:
            stats["warnings"].append(f"Root page not found: {name}.md")
    return titles


# ---------------------------------------------------------------------------
# 8. Generate index pages
# ---------------------------------------------------------------------------
def build_hub_index():
    # Build sidebar for homepage: 4 section links
    home_section_pages = [
        ("training-modules", "Training Modules"),
        ("events", "Events"),
        ("training-events", "Network Events"),
        ("pages", "Pages"),
    ]
    sidebar = build_sidebar("home", "Sections", "", home_section_pages, [])

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
<table class="summary-table">
  <thead><tr><th>Section</th><th>Contents</th></tr></thead>
  <tbody>
    <tr><td><a href="{BASE}/training-modules/">Training Modules</a></td><td>41 courses across 3 categories</td></tr>
    <tr><td><a href="{BASE}/events/">Events</a></td><td>39 events (2024-2026)</td></tr>
    <tr><td><a href="{BASE}/training-events/">Network Events</a></td><td>8 doctoral training events</td></tr>
    <tr><td><a href="{BASE}/pages/">Pages</a></td><td>Programme info, team, media</td></tr>
  </tbody>
</table>
"""
    bc = 'Home'
    html = page_template("MSCA DIGITAL Finance PhD Training", bc, content,
                         current_section="home", sidebar_html=sidebar)
    write_html(DOCS_DIR / "index.html", html)


def build_training_modules_index(section_pages=None):
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
        content_parts.append('<table class="summary-table">')
        content_parts.append('<thead><tr><th>Module</th><th>Institution</th><th>ECTS</th></tr></thead>')
        content_parts.append('<tbody>')
        for slug in slugs:
            info = modules_by_slug.get(slug, {})
            title = info.get("title", slug_to_title(slug))
            institution = info.get("institution") or ""
            ects = info.get("ects")
            ects_str = str(ects) if ects else ""
            content_parts.append(
                f'<tr>'
                f'<td><a href="{BASE}/training-modules/{slug}.html">{html_mod.escape(title)}</a></td>'
                f'<td>{html_mod.escape(institution)}</td>'
                f'<td>{html_mod.escape(ects_str)}</td>'
                f'</tr>'
            )
        content_parts.append('</tbody></table></div>')

    bc = (
        f'<a href="{BASE}/">Home</a> &rsaquo; Training Modules'
    )
    sidebar = build_sidebar("training-modules", "Training Modules", "", section_pages or [], [])
    html = page_template("Training Modules", bc, '\n'.join(content_parts),
                         current_section="training-modules", sidebar_html=sidebar)
    write_html(DOCS_DIR / "training-modules" / "index.html", html)


def build_events_index(section_pages=None):
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
        content_parts.append(f'<div class="section-group"><h2>{label} ({len(events)})</h2>')
        content_parts.append('<table class="summary-table">')
        content_parts.append('<thead><tr><th>Event</th><th>Date</th><th>Location</th></tr></thead>')
        content_parts.append('<tbody>')
        for ev in events:
            title = ev.get("title", "Event")
            date = ev.get("date", "")
            location = ev.get("location", "")

            # Determine slug for linking
            slug = _event_slug(ev)

            if slug:
                title_cell = f'<a href="{BASE}/events/{slug}.html">{html_mod.escape(title)}</a>'
            else:
                url = ev.get("url", "")
                if url:
                    title_cell = f'<a href="{html_mod.escape(url)}">{html_mod.escape(title)}</a>'
                else:
                    title_cell = html_mod.escape(title)

            content_parts.append(
                f'<tr>'
                f'<td>{title_cell}</td>'
                f'<td>{html_mod.escape(date)}</td>'
                f'<td>{html_mod.escape(location)}</td>'
                f'</tr>'
            )
        content_parts.append('</tbody></table></div>')

    bc = f'<a href="{BASE}/">Home</a> &rsaquo; Events'
    sidebar = build_sidebar("events", "Events", "", section_pages or [], [])
    html = page_template("Events", bc, '\n'.join(content_parts),
                         current_section="events", sidebar_html=sidebar)
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


def build_training_events_index(section_pages=None):
    with open(FIRECRAWL_DIR / "training-events-structured.json", encoding="utf-8") as f:
        data = json.load(f)

    content_parts = ['<h1>Network Training Events</h1>']
    content_parts.append(f'<p>{data.get("count", 8)} planned network training events across the doctoral programme.</p>')
    content_parts.append('<table class="summary-table">')
    content_parts.append('<thead><tr><th>Event</th><th>Description</th></tr></thead>')
    content_parts.append('<tbody>')

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
            f'<tr>'
            f'<td><a href="{BASE}/training-events/{slug}.html">{html_mod.escape(title)}</a></td>'
            f'<td>{html_mod.escape(desc)}</td>'
            f'</tr>'
        )

    content_parts.append('</tbody></table>')

    bc = f'<a href="{BASE}/">Home</a> &rsaquo; Network Events'
    sidebar = build_sidebar("training-events", "Network Events", "", section_pages or [], [])
    html = page_template("Network Training Events", bc, '\n'.join(content_parts),
                         current_section="training-events", sidebar_html=sidebar)
    write_html(DOCS_DIR / "training-events" / "index.html", html)


def build_pages_index(page_titles: dict, section_pages=None):
    content_parts = ['<h1>Programme Pages</h1>']
    content_parts.append('<table class="summary-table">')
    content_parts.append('<thead><tr><th>Page</th></tr></thead>')
    content_parts.append('<tbody>')

    for slug in ROOT_PAGES:
        title = page_titles.get(slug, slug_to_title(slug))
        content_parts.append(
            f'<tr>'
            f'<td><a href="{BASE}/pages/{slug}.html">{html_mod.escape(title)}</a></td>'
            f'</tr>'
        )

    content_parts.append('</tbody></table>')

    bc = f'<a href="{BASE}/">Home</a> &rsaquo; Pages'
    sidebar = build_sidebar("pages", "Pages", "", section_pages or [], [])
    html = page_template("Programme Pages", bc, '\n'.join(content_parts),
                         current_section="pages", sidebar_html=sidebar)
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

    # Collect section_pages for index builders
    tm_section_pages = [(slug, tm_titles[slug]) for slug in sorted(tm_titles)]
    ev_section_pages = [(slug, ev_titles[slug]) for slug in sorted(ev_titles)]
    te_section_pages = [(slug, te_titles[slug]) for slug in sorted(te_titles)]
    rp_section_pages = [(slug, rp_titles.get(slug, slug_to_title(slug))) for slug in ROOT_PAGES if slug in rp_titles]

    # 8. Build index pages
    print("[8/9] Building index pages ...")
    build_hub_index()
    build_training_modules_index(section_pages=tm_section_pages)
    build_events_index(section_pages=ev_section_pages)
    build_training_events_index(section_pages=te_section_pages)
    build_pages_index(rp_titles, section_pages=rp_section_pages)
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
