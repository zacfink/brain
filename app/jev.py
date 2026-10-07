#!/usr/bin/env python3
"""Jev (TypeSafe's System One model, https://docs.typesafe.ai) over plain HTTP. Optional: with no
TYPESAFE_API_KEY every call returns None and Brain behaves exactly as before.

Used for two things:
  - filing phone captures (phone.py): Jev picks the project or person a capture belongs to, code files it.
  - the bet check:  brain jev-bet "<what Claude is about to recommend>" [kind]
    prints how likely Zac is to go along, judged from claude/predictions.md. Claude logs it as "· jev: NN%".
"""
import json
import os
import sys
import urllib.request

URL = "https://api.typesafe.ai/v1/systemone"


def ask(state, questions, timeout=30):
    """One request, many questions. Returns {question id: answer} or None when Jev is off."""
    if os.environ.get("BRAIN_JEV_FAKE"):  # tests: canned answers, no network
        return json.loads(os.environ["BRAIN_JEV_FAKE"])
    key = os.environ.get("TYPESAFE_API_KEY")
    if not key:
        return None
    req = urllib.request.Request(URL, json.dumps({"state": state, "model": "jev-latest", "questions": questions}).encode(),
                                 {"Authorization": "Bearer " + key, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)["answers"]


def bet(notes, text, kind="recommend"):
    """Chance (0-1) that Claude's bet turns out right, from how Zac answered the logged bets before it."""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import predictions
    path = os.path.join(notes, "claude", "predictions.md")
    past = predictions.parse(open(path, encoding="utf-8").read()) if os.path.exists(path) else []
    state = {
        "past_bets": [{"kind": e["kind"], "claude_bet": e["bet"], "what_he_said": e["got"], "claude_was_right": e["hit"]}
                      for e in past[-60:]],
        "new_bet": {"kind": kind, "claude_bet": text},
    }
    answers = ask(state, {"right": {
        "type": "noul",
        "instructions": "`past_bets` are Claude's earlier guesses about what Zac would want, with what he actually said. "
                        "Judging from how he answered those, will Zac go along with `new_bet`?",
        "criteria": {"true": "He accepts it as Claude put it (picks it, keeps the draft, agrees with the guess).",
                     "false": "He rejects it, rewrites it, or wants something different."},
    }})
    return None if answers is None else answers["right"]["noul"]


if __name__ == "__main__":
    if len(sys.argv) < 3 or sys.argv[1] != "bet":
        sys.exit('usage: jev.py bet "<bet>" [recommend|guess|draft|habit]')
    notes = os.environ.get("BRAIN_NOTES") or os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    p = bet(notes, sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "recommend")
    if p is None:
        sys.exit("Jev is off: set TYPESAFE_API_KEY.")
    print("jev: %d%%" % round(100 * p))  # log it at the end of the prediction line: "· jev: NN%"
