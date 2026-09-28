#!/usr/bin/env python3
"""Apply the phone's queued actions to the notes, then write phone/state.json for the phone to read.

Run by the notes repo's GitHub Action (see docs/specs/2026-09-27-phone-app.md):
    python3 .brain/app/phone.py <notes folder>

The phone never edits notes. It drops one JSON file per action into phone/queue/, and this applies each with
the same functions the Mac app uses, so both write notes identically. A bad action is moved to phone/failed/
with its error instead of blocking the rest. Captures don't run agents here: they're parked in
agents/pending/ for the Mac.
"""
import datetime
import glob
import json
import os
import sys

NOTES = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else ".")
os.environ["BRAIN_NOTES"] = NOTES
os.environ["BRAIN_AGENTS"] = "pending"
sys.argv = sys.argv[:1]  # server.py reads its own flags from argv
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import server  # noqa: E402
import jev  # noqa: E402

SURE = 0.7  # ponytail: one threshold, untuned; raise it if Jev files things in the wrong place


def section_add(text, heading, line):
    """Put `line` first under `## heading`, adding the section at the end if the page doesn't have it."""
    lines = text.rstrip("\n").split("\n")
    i = next((n for n, l in enumerate(lines) if l.strip().lower() == "## " + heading.lower()), None)
    if i is None:
        return "\n".join(lines) + "\n\n## %s\n%s\n" % (heading, line)
    return "\n".join(lines[:i + 1] + [line] + lines[i + 1:]) + "\n"


def jev_file(body):
    """File an idea, todo or person capture straight into its note when Jev is sure where it goes.
    Returns False (and the capture goes to the inbox for Claude, as before) when Jev is off or unsure."""
    kind, text = body.get("kind"), " ".join(str(body.get("text") or "").split())[:2000]
    if kind not in ("idea", "todo", "person") or not text:
        return False
    s = server.state()
    if kind == "person":
        options = {os.path.basename(p["path"])[:-3]: "%s. %s" % (p["title"], p["tldr"] or "") for p in s["people"]}
        none, what = "Someone not in this list, or not about one specific person.", "Which person is this note about?"
    else:
        options = {p["slug"]: "%s. %s" % (p["title"], p["meta"].get("summary") or p["tldr"] or "")
                   for p in s["projects"] if not p["archived"]}
        none, what = "It doesn't clearly belong to any one of these projects.", "Which project does this %s belong to?" % kind
    if not options:
        return False
    try:
        a = jev.ask({"capture": text}, {"where": {"type": "choice", "instructions": what + " (`capture`)",
                                                   "criteria": {**options, "none": none}}})
    except Exception:  # noqa: BLE001  Jev down or slow: Claude files it later, like before
        return False
    if not a or a["where"]["choice"] == "none" or a["where"]["probabilities"][a["where"]["choice"]] < SURE:
        return False
    slug, day = a["where"]["choice"], server.today()
    if kind == "idea":
        ideas = server.idea_sections(server.read("ideas.md"))
        ideas["open"].append("%s · %s (project: %s)" % (day, text, slug))
        server.write("ideas.md", server.render_ideas(ideas))
    elif kind == "todo":
        rel = "projects/%s.md" % slug
        server.write(rel, section_add(server.read(rel), "Open threads", "- [ ] %s (from phone, %s)" % (text, day)))
    else:
        rel = "people/%s.md" % slug
        server.write(rel, section_add(server.read(rel), "History", "- %s · %s" % (day, text)))
    return True


def capture(body):
    if not jev_file(body):
        server.act_capture(body)


ACTIONS = {
    "capture": capture,
    "nudge": server.act_nudge,
    "idea": server.act_idea,
    "habit": server.act_habit,
    "habit-new": server.act_habit_new,
}
# What the phone shows. Sessions, people and the note list stay on the Mac.
KEEP = ("today", "issue", "streak", "now", "me", "nudges", "habits", "projects", "ideas", "ideas_closed", "inbox", "agents", "predictions")


def apply_queue():
    applied, failed = [], []
    for path in sorted(glob.glob(os.path.join(NOTES, "phone", "queue", "*.json"))):
        name = os.path.basename(path)
        try:
            with open(path, encoding="utf-8") as f:
                job = json.load(f)
            ACTIONS[job["action"]](job.get("body") or {})
            applied.append(name[:-5])
        except Exception as e:  # noqa: BLE001  one bad action mustn't block the rest
            failed.append({"id": name[:-5], "error": "%s: %s" % (type(e).__name__, e)})
            os.makedirs(os.path.join(NOTES, "phone", "failed"), exist_ok=True)
            with open(os.path.join(NOTES, "phone", "failed", name), "w", encoding="utf-8") as f:
                json.dump({"error": failed[-1]["error"], "job": open(path, encoding="utf-8").read()}, f)
        os.remove(path)
    return applied, failed


def main():
    applied, failed = apply_queue()
    server.rebuild_index()
    full = server.state()
    state = {k: full[k] for k in KEEP if k in full}
    for p in state.get("projects", []):  # Mac-only details: resume commands and local folder paths
        p.pop("resume", None)
        p.pop("folders", None)
    state["built"] = datetime.datetime.now().isoformat(timespec="seconds")
    state["applied"], state["failed"] = applied, failed
    with open(os.path.join(NOTES, "phone", "state.json"), "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False)
    print("applied %d, failed %d" % (len(applied), len(failed)))


if __name__ == "__main__":
    main()
