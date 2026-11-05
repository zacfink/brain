#!/usr/bin/env python3
"""Rebuild INDEX.md from the markdown notes (the browsable view is the `brain` app).

Usage: python3 build.py   (notes folder = parent of this folder, or $BRAIN_NOTES)
Stdlib only. Safe to run any time; the output is fully regenerated.
"""
import datetime
import glob
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
NOTES = os.path.abspath(os.path.expanduser(os.environ.get("BRAIN_NOTES") or os.path.dirname(HERE)))
PROJECTS_DIR = os.path.expanduser(os.environ.get("BRAIN_PROJECTS_DIR", "~/Projects"))
SKIP_DIRS = {".brain", ".claude", ".git", ".obsidian", "agents", "phone"}  # agents/: run logs; phone/: the phone app's queue and state
OPEN_TASK = re.compile(r"^\s*[-*] \[ \] (.+)$", re.M)


def parse_frontmatter(text):
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---", 4)
    if end == -1:
        return {}, text
    meta = {}
    for line in text[4:end].splitlines():
        if ":" not in line or line.lstrip().startswith("#"):
            continue
        key, val = line.split(":", 1)
        # Only "  # comment" (2+ spaces) is a comment, so titles like "PR #28" survive.
        val = re.sub(r"\s{2,}#.*$", "", val).strip().strip('"').strip("'")
        if val.startswith("[") and val.endswith("]"):
            val = [v.strip().strip('"').strip("'") for v in val[1:-1].split(",") if v.strip()]
        meta[key.strip()] = val
    return meta, text[end + 4:].lstrip("\n")


def first_heading(body, fallback):
    m = re.search(r"^# (.+)$", body, re.M)
    return m.group(1).strip() if m else fallback


def tldr(body):
    m = re.search(r"\*\*TL;DR:\*\*\s*(.+)", body)
    return m.group(1).strip() if m else ""


def load_notes():
    docs = []
    for dirpath, dirnames, filenames in os.walk(NOTES):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        for fn in sorted(filenames):
            if not fn.endswith(".md") or fn == "INDEX.md":
                continue
            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, NOTES)
            with open(full, encoding="utf-8", errors="replace") as f:
                meta, body = parse_frontmatter(f.read())
            top = rel.split(os.sep)[0] if os.sep in rel else ""
            kind = {"sessions": "session", "projects": "project"}.get(top, "note")
            mtime = datetime.date.fromtimestamp(os.path.getmtime(full)).isoformat()
            docs.append({
                "path": rel,
                "kind": kind,
                "meta": meta,
                "title": meta.get("title") or meta.get("name") or first_heading(body, fn[:-3]),
                "date": str(meta.get("date") or meta.get("updated") or mtime),
                "tldr": tldr(body) or meta.get("summary", ""),
                "open": OPEN_TASK.findall(body),
                "body": body,
            })
    return docs


def decisions_due(notes, today):
    """Lines under a page's "## Key decisions" heading whose `check-by: YYYY-MM-DD` has arrived.
    A replaced decision moves to "## Superseded decisions", which is never read here."""
    out = []
    for path in sorted(glob.glob(os.path.join(notes, "projects", "*.md"))):
        with open(path, encoding="utf-8", errors="replace") as f:
            text = f.read()
        sec = re.search(r"^## Key decisions[^\n]*\n(.*?)(?=^## |\Z)", text, re.M | re.S)
        for line in (sec.group(1) if sec else "").splitlines():
            m = re.search(r"check-by:\s*(\d{4}-\d{2}-\d{2})", line)
            if line.startswith("- ") and m and m.group(1) <= today:
                what = re.sub(r"\*\*|\s*\(?check-by:[^)]*\)?\s*$", "", line[2:]).strip()
                out.append({"what": what, "check_by": m.group(1), "path": os.path.relpath(path, notes)})
    return sorted(out, key=lambda d: d["check_by"])


def sync_school_assessments(notes, today):
    """Refresh the generated School assessment block in now.md from the mirrored Assessment Map table."""
    source = os.path.join(notes, "school", "assessment-map-fall-2026.md")
    now_path = os.path.join(notes, "now.md")
    if not os.path.exists(source) or not os.path.exists(now_path):
        return False
    desktop_map = os.path.expanduser("~/Desktop/School/Year 3 - 2026-27/Semester 1/Assessment Map.md")
    if os.path.exists(desktop_map):
        with open(desktop_map, encoding="utf-8", errors="replace") as f:
            original = f.read()
        table = re.search(r"(?m)^## Dated assessments\s*\n(.*?)(?=^## |\Z)", original, re.S)
        if table:
            mirror = (
                "# Assessment Map feed — Fall 2026\n\n"
                "Source: `~/Desktop/School/Year 3 - 2026-27/Semester 1/Assessment Map.md`, section “Dated assessments”.\n"
                "This copy is refreshed automatically by `.brain/build.py` when the iCloud Desktop file is available.\n"
                "The cloud morning update reads this mirrored table; CISC 457 is excluded because it was dropped.\n\n"
                "## Dated assessments\n\n" + table.group(1).strip() + "\n"
            )
            with open(source, encoding="utf-8", errors="replace") as f:
                old_mirror = f.read()
            if mirror != old_mirror:
                with open(source, "w", encoding="utf-8") as f:
                    f.write(mirror)
                print("Refreshed assessment-map mirror from Desktop")
    with open(source, encoding="utf-8", errors="replace") as f:
        assessment_map = f.read()
    with open(now_path, encoding="utf-8", errors="replace") as f:
        now = f.read()
    if "## Dated assessments" not in assessment_map:
        return False

    heading = re.search(r"Fall\s+(20\d{2})", assessment_map)
    year = int(heading.group(1)) if heading else int(today[:4])
    months = {"sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12}
    rows = []
    table_started = False
    for line in assessment_map.splitlines():
        if line.strip() == "## Dated assessments":
            table_started = True
            continue
        if table_started and line.startswith("## "):
            break
        if not table_started or not line.startswith("|") or line.startswith("|-") or "| Date |" in line:
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 4:
            continue
        date_cell, course, item, weight = [re.sub(r"\*\*|`", "", c).strip() for c in cells[:4]]
        match = re.search(r"\b(Sept?|Oct|Nov|Dec)\s+(\d{1,2})(?:\s*[–-]\s*(\d{1,2}))?", date_cell)
        if not match:
            continue
        month, day, end_day = match.groups()
        month_num = months[month.lower()]
        due = datetime.date(year, month_num, int(day))
        if due.isoformat() < today:
            continue
        time = re.search(r"\b(\d{1,2}:\d{2})\b", date_cell)
        date_label = due.isoformat() + (" " + time.group(1) if time else "")
        details = []
        if end_day:
            details.append("exam period through %s %d" % (month, int(end_day)))
        details.append(item)
        details.append(weight)
        if course == "CISC 360" and "quiz" in item.lower():
            details.append("tentative")
        rows.append((course, item, "- %s · %s · %s" % (date_label, course, " · ".join(details))))

    start, end = "<!-- school-assessments:start -->", "<!-- school-assessments:end -->"
    section = re.search(r"(?m)^## Upcoming\s*\n(.*?)(?=^## |\Z)", now, re.S)
    if not section:
        return False
    body = section.group(1)
    if start in body and end in body:
        before, remainder = body.split(start, 1)
        _, after = remainder.split(end, 1)
        body = before + after

    kept = []
    for line in body.splitlines():
        if not line.startswith("- "):
            kept.append(line)
            continue
        if "CISC 457" in line:
            continue
        dated = re.match(r"- \d{4}-\d{2}-\d{2}(?: \d{1,2}:\d{2})? · (.*)", line)
        if dated:
            detail = dated.group(1)
            normalized = re.sub(r"[^a-z0-9]", "", detail.lower())
            if any(course.lower() in detail.lower() and re.sub(r"[^a-z0-9]", "", item.lower()) in normalized
                   for course, item, _ in rows):
                continue
        kept.append(line)

    generated = "\n".join([start] + [row[2] for row in rows] + [end])
    cleaned = re.sub(r"\n{3,}", "\n\n", "\n".join(kept)).strip("\n")
    new_body = generated + ("\n\n" + cleaned if cleaned else "")
    updated = now[:section.start(1)] + new_body + now[section.end(1):]
    if updated == now:
        return False
    with open(now_path, "w", encoding="utf-8") as f:
        f.write(updated)
    print("Synced %d Assessment Map rows into now.md" % len(rows))
    return True


def as_list(v):
    if isinstance(v, list):
        return v
    return [v] if v else []


def other_folders(known_paths):
    """~/Projects folders with no project note yet — listed, never summarized."""
    if not os.path.isdir(PROJECTS_DIR):
        return []
    known = {os.path.basename(os.path.expanduser(p).rstrip("/")) for p in known_paths}
    out = []
    for name in sorted(os.listdir(PROJECTS_DIR), key=str.lower):
        full = os.path.join(PROJECTS_DIR, name)
        if name.startswith(".") or not os.path.isdir(full) or name in known:
            continue
        out.append({"name": name, "path": "~/Projects/" + name,
                    "modified": datetime.date.fromtimestamp(os.path.getmtime(full)).isoformat()})
    return out


STATUS_ORDER = {"active": 0, "paused": 1, "done": 2, "abandoned": 3}


def sort_projects(projects):
    """Active first, then paused, done, abandoned; newest update first within each."""
    newest = sorted(projects, key=lambda d: d["meta"].get("updated", ""), reverse=True)
    return sorted(newest, key=lambda d: STATUS_ORDER.get(d["meta"].get("status"), 9))


def build_index(docs, folders):
    projects = sort_projects(d for d in docs if d["kind"] == "project")
    sessions = sorted((d for d in docs if d["kind"] == "session"),
                      key=lambda d: d["path"], reverse=True)
    others = [d for d in docs if d["kind"] == "note"]
    by_project = {}
    for s in sessions:
        for p in as_list(s["meta"].get("projects")) or ["misc"]:
            by_project.setdefault(p, []).append(s)

    L = ["# Notes index", "",
         "_Generated by `.brain/build.py` on %s. Do not edit by hand; edit the notes and rebuild._"
         % datetime.date.today().isoformat(), "",
         "Read this first. Open a project page before touching that project; open a session note only",
         "when you need the detail of what happened that day.", "",
         "## Projects", "",
         "| Project | Status | Updated | Summary |", "|---|---|---|---|"]
    for p in projects:
        m = p["meta"]
        L.append("| [%s](%s) | %s | %s | %s |" % (p["title"], p["path"], m.get("status", ""),
                                              m.get("updated", ""),
                                              (m.get("summary") or p["tldr"]).replace("|", "/")))
    L += ["", "## Recent sessions", ""]
    for s in sessions[:25]:
        L.append("- %s · [%s](%s) · `%s` · %s" % (
            s["meta"].get("date", ""), s["title"], s["path"],
            ", ".join(as_list(s["meta"].get("projects"))), s["meta"].get("status", "")))
    if len(sessions) > 25:
        L.append("- …%d older in `sessions/`" % (len(sessions) - 25))
    L += ["", "## Sessions by project", ""]
    for slug in sorted(by_project):
        L.append("- **%s**: %s" % (slug, ", ".join(
            "[%s](%s)" % (s["meta"].get("date", "?"), s["path"]) for s in by_project[slug])))
    open_items = [(d, t) for d in projects + others for t in d["open"]]
    if open_items:
        L += ["", "## Open threads (from project and topic notes)", ""]
        L += ["- [ ] %s — [%s](%s)" % (t, d["title"], d["path"]) for d, t in open_items]
    people = [d for d in others if d["path"].startswith("people/")]
    if people:
        L += ["", "## People", ""]
        L += ["- [%s](%s) — %s" % (d["meta"].get("name") or d["title"], d["path"], d["meta"].get("relation", ""))
              for d in sorted(people, key=lambda d: d["path"])]
    L += ["", "## About me and the rest", "",
          "- `me.md` profile · `now.md` cover story + upcoming · `nudges.md` reminders for me · "
          "`claude/habits.md` how Claude adapts · `ideas.md` · `inbox.md` captures to file"]
    L += ["- [%s](%s)" % (d["title"], d["path"]) for d in others if not d["path"].startswith("people/")]
    if folders:
        L += ["", "## ~/Projects folders with no notes yet", "",
              ", ".join("`%s`" % f["name"] for f in folders)]
    return "\n".join(L) + "\n"


def main():
    sync_school_assessments(NOTES, datetime.date.today().isoformat())
    docs = load_notes()
    known = [p for d in docs if d["kind"] == "project" for p in as_list(d["meta"].get("paths"))]
    folders = other_folders(known)

    with open(os.path.join(NOTES, "INDEX.md"), "w", encoding="utf-8") as f:
        f.write(build_index(docs, folders))

    n = {k: sum(d["kind"] == k for d in docs) for k in ("project", "session", "note")}
    print("Built INDEX.md: %(project)d projects, %(session)d sessions, %(note)d other notes" % n)


if __name__ == "__main__":
    main()
