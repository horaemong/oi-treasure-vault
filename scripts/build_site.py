from __future__ import annotations

import html
import json
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote

ROOT = Path(r"F:\workspace\obsidian-site")
SOURCE = Path(r"F:\workspace\obsidian\para")
OUT = ROOT / "site"
TEMPLATE = (ROOT / "templates" / "page.html").read_text(encoding="utf-8")
ASSETS = ROOT / "assets"

EXCLUDED_DIRS = {".obsidian", ".git", ".trash", "Attached file", "_system"}

@dataclass
class Note:
    src: Path
    rel: Path
    out_rel: Path
    title: str
    date: str
    html_body: str = ""


def url_for(rel: Path) -> str:
    return quote(rel.as_posix(), safe="/")


def rel_url(from_file: Path, to_file: Path) -> str:
    base = from_file.parent
    raw = Path(".") if base == to_file.parent and from_file.name == to_file.name else Path()
    rel = to_file.relative_to(base) if False else None
    import os
    value = os.path.relpath(OUT / to_file, (OUT / from_file).parent).replace("\\", "/")
    return quote(value, safe="/#")


def should_include(path: Path) -> bool:
    try:
        rel = path.relative_to(SOURCE)
    except ValueError:
        return False
    return not any(part in EXCLUDED_DIRS for part in rel.parts)


def parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    if not text.startswith("---"):
        return {}, text
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n?", text, re.S)
    if not match:
        return {}, text
    meta_text = match.group(1)
    body = text[match.end():]
    meta: dict[str, str] = {}
    current_key = None
    for line in meta_text.splitlines():
        if not line.strip():
            continue
        if re.match(r"^\s+-\s+", line) and current_key:
            meta[current_key] = (meta.get(current_key, "") + ", " + line.strip()[2:]).strip(", ")
            continue
        if ":" in line:
            key, value = line.split(":", 1)
            current_key = key.strip()
            meta[current_key] = value.strip().strip('"\'')
    return meta, body


def first_heading(text: str) -> str | None:
    for line in text.splitlines():
        m = re.match(r"^#\s+(.+?)\s*$", line)
        if m:
            return m.group(1).strip()
    return None


def collect_notes() -> list[Note]:
    notes: list[Note] = []
    for src in SOURCE.rglob("*.md"):
        if not should_include(src):
            continue
        rel = src.relative_to(SOURCE)
        raw = src.read_text(encoding="utf-8", errors="replace")
        meta, body = parse_frontmatter(raw)
        title = meta.get("title") or first_heading(body) or src.stem
        date = meta.get("date") or ""
        out_rel = rel.with_suffix(".html")
        notes.append(Note(src=src, rel=rel, out_rel=out_rel, title=title, date=date))
    notes.sort(key=lambda n: n.rel.as_posix().lower())
    return notes


def build_lookup(notes: list[Note]) -> dict[str, Note]:
    lookup: dict[str, Note] = {}
    for note in notes:
        keys = {note.src.stem, note.rel.with_suffix("").as_posix(), note.rel.as_posix()}
        for key in keys:
            lookup.setdefault(key, note)
    return lookup


def inline(text: str, current: Note, lookup: dict[str, Note]) -> str:
    text = html.escape(text)

    def code_repl(m: re.Match[str]) -> str:
        return f"<code>{m.group(1)}</code>"

    text = re.sub(r"`([^`]+)`", code_repl, text)

    def wiki_embed_repl(m: re.Match[str]) -> str:
        target = html.unescape(m.group(1).strip())
        label = target.split("|")[-1]
        return f'<span class="note-meta">이미지/첨부: {html.escape(label)}</span>'

    text = re.sub(r"!\[\[([^\]]+)\]\]", wiki_embed_repl, text)

    def wiki_repl(m: re.Match[str]) -> str:
        raw = html.unescape(m.group(1).strip())
        target, label = (raw.split("|", 1) + [raw])[:2] if "|" in raw else (raw, raw)
        target = target.split("#", 1)[0]
        found = lookup.get(target) or lookup.get(target + ".md")
        if found:
            href = rel_url(current.out_rel, found.out_rel)
            return f'<a href="{href}">{html.escape(label)}</a>'
        return f'<span class="missing-link">{html.escape(label)}</span>'

    text = re.sub(r"\[\[([^\]]+)\]\]", wiki_repl, text)

    def image_repl(m: re.Match[str]) -> str:
        alt = m.group(1)
        src = m.group(2)
        return f'<img alt="{alt}" src="{src}" />'

    text = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", image_repl, text)

    def link_repl(m: re.Match[str]) -> str:
        label = m.group(1)
        href = m.group(2)
        if href.endswith(".md"):
            href = href[:-3] + ".html"
        return f'<a href="{href}">{label}</a>'

    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", link_repl, text)
    return text


def markdown_to_html(md: str, current: Note, lookup: dict[str, Note]) -> str:
    _meta, body = parse_frontmatter(md)
    lines = body.splitlines()
    out: list[str] = []
    paragraph: list[str] = []
    in_code = False
    code_lines: list[str] = []
    in_ul = False
    in_ol = False

    def flush_paragraph() -> None:
        nonlocal paragraph
        if paragraph:
            out.append(f"<p>{inline(' '.join(paragraph).strip(), current, lookup)}</p>")
            paragraph = []

    def close_lists() -> None:
        nonlocal in_ul, in_ol
        if in_ul:
            out.append("</ul>")
            in_ul = False
        if in_ol:
            out.append("</ol>")
            in_ol = False

    for line in lines:
        if line.strip().startswith("```"):
            flush_paragraph()
            close_lists()
            if not in_code:
                in_code = True
                code_lines = []
            else:
                out.append("<pre><code>" + html.escape("\n".join(code_lines)) + "</code></pre>")
                in_code = False
            continue

        if in_code:
            code_lines.append(line)
            continue

        if not line.strip():
            flush_paragraph()
            close_lists()
            continue

        heading = re.match(r"^(#{1,6})\s+(.+)$", line)
        if heading:
            flush_paragraph()
            close_lists()
            level = len(heading.group(1))
            out.append(f"<h{level}>{inline(heading.group(2).strip(), current, lookup)}</h{level}>")
            continue

        if line.startswith(">"):
            flush_paragraph()
            close_lists()
            out.append(f"<blockquote>{inline(line.lstrip('> ').strip(), current, lookup)}</blockquote>")
            continue

        ul = re.match(r"^\s*[-*]\s+(.+)$", line)
        if ul:
            flush_paragraph()
            if not in_ul:
                close_lists()
                out.append("<ul>")
                in_ul = True
            out.append(f"<li>{inline(ul.group(1), current, lookup)}</li>")
            continue

        ol = re.match(r"^\s*\d+[.)]\s+(.+)$", line)
        if ol:
            flush_paragraph()
            if not in_ol:
                close_lists()
                out.append("<ol>")
                in_ol = True
            out.append(f"<li>{inline(ol.group(1), current, lookup)}</li>")
            continue

        paragraph.append(line.strip())

    flush_paragraph()
    close_lists()
    if in_code:
        out.append("<pre><code>" + html.escape("\n".join(code_lines)) + "</code></pre>")
    return "\n".join(out)


def folder_nav(current_out: Path) -> str:
    links = []
    for folder in ["Area", "Project", "Recource", "Archive"]:
        target = Path(folder) / "index.html"
        href = rel_url(current_out, target)
        links.append(f'<li><a href="{href}">{html.escape(folder)}</a></li>')
    return '<ul class="folder-list">' + "\n".join(links) + "</ul>"


def render_page(title: str, content: str, out_rel: Path, breadcrumb: str) -> str:
    depth = len(out_rel.parts) - 1
    asset_prefix = "../" * depth
    return (TEMPLATE
        .replace("{{title}}", html.escape(title))
        .replace("{{asset_prefix}}", asset_prefix)
        .replace("{{breadcrumb}}", html.escape(breadcrumb))
        .replace("{{folder_nav}}", folder_nav(out_rel))
        .replace("{{content}}", content))


def write_note(note: Note, lookup: dict[str, Note]) -> None:
    raw = note.src.read_text(encoding="utf-8", errors="replace")
    body = markdown_to_html(raw, note, lookup)
    meta = f'<div class="note-meta">{html.escape(note.rel.as_posix())}</div>'
    if note.date:
        meta += f'<div class="note-meta">{html.escape(note.date)}</div>'
    content = f"<h1>{html.escape(note.title)}</h1>\n{meta}\n{body}"
    html_text = render_page(note.title, content, note.out_rel, note.rel.parent.as_posix() or "root")
    dest = OUT / note.out_rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(html_text, encoding="utf-8")


def write_index(out_rel: Path, title: str, notes: list[Note], folders: list[Path], breadcrumb: str) -> None:
    items: list[str] = []
    for folder in sorted(folders, key=lambda p: p.as_posix().lower()):
        href = quote((folder / "index.html").as_posix(), safe="/")
        # Make relative to this index location.
        href = rel_url(out_rel, folder / "index.html")
        items.append(f'<li><a href="{href}">{html.escape(folder.name)}</a><div class="note-meta">folder</div></li>')
    for note in sorted(notes, key=lambda n: n.title.lower()):
        href = rel_url(out_rel, note.out_rel)
        meta = html.escape(note.rel.as_posix())
        items.append(f'<li><a href="{href}">{html.escape(note.title)}</a><div class="note-meta">{meta}</div></li>')
    content = f"<h1>{html.escape(title)}</h1>\n<ul class=\"note-list\">\n" + "\n".join(items) + "\n</ul>"
    html_text = render_page(title, content, out_rel, breadcrumb)
    dest = OUT / out_rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(html_text, encoding="utf-8")


def write_indexes(notes: list[Note]) -> None:
    dirs = {Path(".")}
    for note in notes:
        parent = note.rel.parent
        while str(parent) != ".":
            dirs.add(parent)
            parent = parent.parent
        dirs.add(note.rel.parent)

    for directory in dirs:
        dir_notes = [n for n in notes if n.rel.parent == directory]
        child_dirs = sorted({n.rel.parent for n in notes if n.rel.parent.parent == directory and n.rel.parent != directory})
        if str(directory) == ".":
            out_rel = Path("index.html")
            title = "Obsidian Archive"
            breadcrumb = "root"
        else:
            out_rel = directory / "index.html"
            title = directory.name
            breadcrumb = directory.as_posix()
        write_index(out_rel, title, dir_notes, child_dirs, breadcrumb)


def main() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    shutil.copytree(ASSETS, OUT / "assets")

    notes = collect_notes()
    lookup = build_lookup(notes)
    for note in notes:
        note.html_body = markdown_to_html(note.src.read_text(encoding="utf-8", errors="replace"), note, lookup)
        write_note(note, lookup)
    write_indexes(notes)

    summary = {
        "source": str(SOURCE),
        "output": str(OUT),
        "notes": len(notes),
        "includes_diary": any(n.rel.as_posix().startswith("Area/100. 일기/") for n in notes),
    }
    (OUT / ".nojekyll").write_text("", encoding="utf-8")
    (OUT / "build-summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()


