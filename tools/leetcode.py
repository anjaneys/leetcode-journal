"""Fetching problem metadata from LeetCode's public GraphQL endpoint.

No auth needed for public problem data. If the fetch fails for any reason
(offline, premium problem, LeetCode changed the schema) the caller still gets
a usable stub so scaffolding never hard-blocks on the network.
"""
from __future__ import annotations

import html
import re
from urllib.parse import urlparse

import requests

GRAPHQL = "https://leetcode.com/graphql"

_QUERY = """
query questionData($titleSlug: String!) {
  question(titleSlug: $titleSlug) {
    questionFrontendId
    title
    titleSlug
    content
    difficulty
    topicTags { name slug }
    codeSnippets { langSlug code }
  }
}
"""

_HEADERS = {
    "Content-Type": "application/json",
    "Referer": "https://leetcode.com",
    "User-Agent": "leetcode-journal/1.0",
}


def slugify(target: str) -> str:
    """Accept a full LeetCode URL, a slug, or a loose title and return a slug."""
    target = target.strip()
    if target.startswith("http"):
        parts = [p for p in urlparse(target).path.split("/") if p]
        if "problems" in parts:
            return parts[parts.index("problems") + 1]
        return parts[-1] if parts else target
    if re.fullmatch(r"[a-z0-9-]+", target):
        return target
    return re.sub(r"[^a-z0-9]+", "-", target.lower()).strip("-")


def html_to_markdown(content: str) -> str:
    """Good-enough conversion of LeetCode's problem HTML into readable markdown."""
    if not content:
        return "_Problem statement unavailable._"
    text = content
    text = re.sub(r"<sup>(.*?)</sup>", r"^\1", text, flags=re.S)
    text = re.sub(r"<sub>(.*?)</sub>", r"_\1", text, flags=re.S)
    text = re.sub(r"</?(strong|b)>", "**", text)
    text = re.sub(r"</?(em|i)>", "_", text)
    text = re.sub(r"<code>(.*?)</code>", r"`\1`", text, flags=re.S)
    text = re.sub(r"<li>", "\n- ", text)
    text = re.sub(r"</li>", "", text)
    text = re.sub(r"</?(ul|ol)>", "\n", text)
    text = re.sub(r"<br\s*/?>", "\n", text)
    text = re.sub(r"</p>", "\n\n", text)
    text = re.sub(r"<pre>(.*?)</pre>", lambda m: "\n```\n" + m.group(1) + "\n```\n", text, flags=re.S)
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text)
    text = text.replace(" ", " ").replace("​", "")
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


_DAILY_QUERY = """
query questionOfToday {
  activeDailyCodingChallengeQuestion { question { titleSlug } }
}
"""


def daily(timeout: int = 15) -> str | None:
    """Slug of today's LeetCode daily challenge, or None if unreachable."""
    try:
        resp = requests.post(GRAPHQL, json={"query": _DAILY_QUERY},
                             headers=_HEADERS, timeout=timeout)
        resp.raise_for_status()
        data = (resp.json().get("data") or {}).get("activeDailyCodingChallengeQuestion")
        return data["question"]["titleSlug"] if data else None
    except (requests.RequestException, ValueError, KeyError, TypeError):
        return None


def fetch(slug: str, timeout: int = 15) -> dict:
    """Return problem metadata. Always returns a dict; 'ok' says whether the
    network fetch actually succeeded."""
    stub = {
        "ok": False,
        "slug": slug,
        "id": "0000",
        "title": slug.replace("-", " ").title(),
        "difficulty": "Unknown",
        "tags": [],
        "statement": "_Could not fetch the problem statement. Fill this in manually._",
        "snippets": {},
        "url": f"https://leetcode.com/problems/{slug}/",
    }
    try:
        resp = requests.post(
            GRAPHQL,
            json={"query": _QUERY, "variables": {"titleSlug": slug}},
            headers=_HEADERS,
            timeout=timeout,
        )
        resp.raise_for_status()
        q = (resp.json().get("data") or {}).get("question")
        if not q:
            return stub
    except (requests.RequestException, ValueError) as exc:
        stub["error"] = str(exc)
        return stub

    return {
        "ok": True,
        "slug": q["titleSlug"],
        "id": str(q["questionFrontendId"]).zfill(4),
        "title": q["title"],
        "difficulty": q["difficulty"] or "Unknown",
        "tags": [t["name"] for t in (q.get("topicTags") or [])],
        "statement": html_to_markdown(q.get("content") or ""),
        "snippets": {s["langSlug"]: s["code"] for s in (q.get("codeSnippets") or [])},
        "url": f"https://leetcode.com/problems/{q['titleSlug']}/",
    }
