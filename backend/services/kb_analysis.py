"""
Knowledge mining from ticket history.

This module analyses resolved (and historical) tickets to surface the signals
an IT knowledge manager cares about:

  * Frequently reported problems (category / sub-category clusters)
  * Common root causes & repeated troubleshooting steps (from notes)
  * Successful resolutions and likely-failed attempts
  * Common devices, applications, departments, and locations
  * Clusters that would benefit from a knowledge-base article

It is intentionally dependency-free and deterministic: it uses simple frequency
analysis over the existing data rather than an external AI service. The
"generate draft" step turns a cluster into a structured Markdown draft that is
stored as a DRAFT for human review — nothing here publishes anything.
"""
import re
from collections import Counter, defaultdict
from typing import Dict, List, Optional

import models
from sqlalchemy.orm import Session

# Phrases that suggest a step did not resolve the issue.
_FAILURE_HINTS = re.compile(
    r"\b(didn'?t work|did not work|no luck|still (not|broken|failing|failed)|"
    r"unsuccessful|not resolved|escalat|reopen)\b",
    re.IGNORECASE,
)

_STOPWORDS = {
    "the", "and", "for", "with", "was", "this", "that", "have", "has", "not",
    "you", "your", "are", "but", "from", "they", "will", "can", "not", "were",
    "issue", "ticket", "user", "please", "there", "when", "then", "after",
}


def _cluster_key(t: models.Ticket) -> str:
    sub = (t.sub_category or "").strip()
    return f"{t.category} / {sub}" if sub else t.category


def _keywords(text: str, limit: int = 8) -> List[str]:
    words = re.findall(r"[A-Za-z][A-Za-z0-9\-]{2,}", (text or "").lower())
    counts = Counter(w for w in words if w not in _STOPWORDS)
    return [w for w, _ in counts.most_common(limit)]


def analyze(db: Session, min_cluster_size: int = 2) -> Dict:
    """Return an analytics summary over ticket history."""
    tickets = db.query(models.Ticket).all()
    notes_by_ticket: Dict[str, List[models.Note]] = defaultdict(list)
    for n in db.query(models.Note).all():
        notes_by_ticket[n.ticket_id].append(n)

    total = len(tickets)
    resolved = [t for t in tickets if t.status == "resolved"]

    cat_counter = Counter()
    cluster_counter = Counter()
    dept_counter = Counter()
    loc_counter = Counter()
    device_counter = Counter()
    resolution_texts: Dict[str, List[str]] = defaultdict(list)
    step_texts: Dict[str, List[str]] = defaultdict(list)
    failed_texts: Dict[str, List[str]] = defaultdict(list)

    existing_kb_categories = {
        a.category for a in db.query(models.KBArticle).filter(
            models.KBArticle.workflow_status.in_(["approved", "published"])
        ).all() if a.category
    }

    for t in tickets:
        cat_counter[t.category] += 1
        key = _cluster_key(t)
        cluster_counter[key] += 1
        if t.department:
            dept_counter[t.department] += 1
        if t.location:
            loc_counter[t.location] += 1
        if t.device:
            device_counter[t.device] += 1
        if t.resolution_summary:
            resolution_texts[key].append(t.resolution_summary.strip())
        for n in notes_by_ticket.get(t.id, []):
            body = (n.content or "").strip()
            if not body:
                continue
            step_texts[key].append(body)
            if _FAILURE_HINTS.search(body):
                failed_texts[key].append(body)

    # KB candidates: sizeable clusters without an approved article yet.
    kb_candidates = []
    for key, count in cluster_counter.most_common():
        if count < min_cluster_size:
            continue
        category = key.split(" / ")[0]
        has_article = category in existing_kb_categories
        cluster_resolved = sum(
            1 for t in resolved if _cluster_key(t) == key
        )
        kb_candidates.append({
            "cluster": key,
            "category": category,
            "ticket_count": count,
            "resolved_count": cluster_resolved,
            "has_resolutions": bool(resolution_texts.get(key)),
            "already_documented": has_article,
            "recommended": count >= min_cluster_size and not has_article,
        })

    return {
        "total_tickets": total,
        "resolved_tickets": len(resolved),
        "resolution_rate": round(len(resolved) / total, 3) if total else 0,
        "frequent_problems": [
            {"cluster": k, "count": c} for k, c in cluster_counter.most_common(10)
        ],
        "top_categories": [
            {"category": k, "count": c} for k, c in cat_counter.most_common(10)
        ],
        "common_departments": [
            {"name": k, "count": c} for k, c in dept_counter.most_common(10)
        ],
        "common_locations": [
            {"name": k, "count": c} for k, c in loc_counter.most_common(10)
        ],
        "common_devices": [
            {"name": k, "count": c} for k, c in device_counter.most_common(10)
        ],
        "kb_candidates": kb_candidates,
    }


def build_cluster_context(db: Session, cluster: str) -> Optional[Dict]:
    """Collect the raw material for a specific cluster (category / sub-category)."""
    tickets = [t for t in db.query(models.Ticket).all() if _cluster_key(t) == cluster]
    if not tickets:
        return None
    notes_by_ticket: Dict[str, List[str]] = defaultdict(list)
    for n in db.query(models.Note).all():
        if any(t.id == n.ticket_id for t in tickets) and n.content:
            notes_by_ticket[n.ticket_id].append(n.content.strip())

    resolutions, steps, failures, descriptions = [], [], [], []
    for t in tickets:
        if t.description:
            descriptions.append(t.description.strip())
        if t.resolution_summary:
            resolutions.append(t.resolution_summary.strip())
        for body in notes_by_ticket.get(t.id, []):
            steps.append(body)
            if _FAILURE_HINTS.search(body):
                failures.append(body)

    category = cluster.split(" / ")[0]
    all_text = " ".join(descriptions + resolutions + steps)
    return {
        "cluster": cluster,
        "category": category,
        "ticket_count": len(tickets),
        "resolved_count": sum(1 for t in tickets if t.status == "resolved"),
        "descriptions": descriptions,
        "resolutions": resolutions,
        "steps": steps,
        "failures": failures,
        "keywords": _keywords(all_text),
        "departments": [d for d in {t.department for t in tickets} if d],
        "devices": [d for d in {t.device for t in tickets} if d],
        "locations": [d for d in {t.location for t in tickets} if d],
    }


def _dedupe(items: List[str], limit: int = 8) -> List[str]:
    seen, out = set(), []
    for it in items:
        norm = it.strip()
        low = norm.lower()
        if norm and low not in seen:
            seen.add(low)
            out.append(norm)
        if len(out) >= limit:
            break
    return out


def generate_draft(context: Dict) -> Dict:
    """Turn a cluster context into a structured draft article + playbook.

    Returns a dict with title/problem_summary/content ready to persist as a
    DRAFT KB article (source='ai_generated', workflow_status='draft').
    """
    cluster = context["cluster"]
    resolutions = _dedupe(context["resolutions"])
    steps = _dedupe(context["steps"], limit=12)
    failures = _dedupe(context["failures"], limit=6)
    keywords = context["keywords"]

    lines: List[str] = []
    lines.append("> **Draft — AI-assisted. Requires review and approval before publishing.**")
    lines.append("")
    lines.append(f"_Generated from {context['ticket_count']} related ticket(s), "
                 f"{context['resolved_count']} resolved._")
    lines.append("")
    lines.append("## Problem")
    lines.append(f"Recurring **{cluster}** issues reported by end users.")
    if keywords:
        lines.append("")
        lines.append(f"**Common terms:** {', '.join(keywords)}")
    lines.append("")

    lines.append("## Troubleshooting Playbook")
    if steps:
        for i, s in enumerate(steps, 1):
            lines.append(f"{i}. {s}")
    else:
        lines.append("_No troubleshooting notes were recorded for these tickets yet._")
    lines.append("")

    if resolutions:
        lines.append("## Known Successful Resolutions")
        for r in resolutions:
            lines.append(f"- {r}")
        lines.append("")

    if failures:
        lines.append("## Approaches That Did Not Work")
        for f in failures:
            lines.append(f"- {f}")
        lines.append("")

    context_bits = []
    if context["devices"]:
        context_bits.append(f"**Devices:** {', '.join(context['devices'][:6])}")
    if context["departments"]:
        context_bits.append(f"**Departments:** {', '.join(context['departments'][:6])}")
    if context["locations"]:
        context_bits.append(f"**Locations:** {', '.join(context['locations'][:6])}")
    if context_bits:
        lines.append("## Commonly Involved")
        lines.extend(context_bits)
        lines.append("")

    lines.append("---")
    lines.append("_This draft was assembled automatically from resolved-ticket history. "
                 "An authorized IT professional must verify accuracy before approval._")

    return {
        "title": f"{cluster} — Troubleshooting Guide",
        "category": context["category"],
        "problem_summary": f"Recurring {cluster} issues ({context['ticket_count']} tickets).",
        "content": "\n".join(lines),
        "tags": ", ".join(keywords[:6]),
    }
