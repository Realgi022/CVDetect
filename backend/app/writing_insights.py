"""Conservative, non-scoring wording suggestions; never return source text.

These English-oriented patterns flag only a few explicit cases. Absence of a
match does not mean the writing is complete or that its claims are verified.
"""
from collections import Counter
import re
import unicodedata

from .analysis import BULLET, sections_from_text

MAX_INSIGHTS = 5

# Whole-description matching avoids flagging a phrase that is followed by
# useful context, and fixed IDs do not depend on document text or positions.
GENERIC_PHRASES = (
    ("generic_various_tasks", "responsible for various tasks"),
    ("generic_team_player", "hardworking team player"),
    ("generic_work_well_under_pressure", "works well under pressure"),
    ("generic_excellent_communication", "excellent communication skills"),
)
VAGUE_DESCRIPTIONS = {
    "responsible for tasks", "handled various duties", "helped with various tasks",
    "worked on various projects", "performed various duties", "assisted with various tasks",
}
OPENING = re.compile(r"^([^\W\d_]{3,})\s+([^\W\d_]{3,})(?:\s|$)", re.UNICODE)


def normalized_description(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).casefold()
    return " ".join(text.strip().strip(".!,;: \t\u3002").split())


def practical_bullets(sections: dict[str, list[str]]) -> dict[str, list[str]]:
    """Recognize explicit bullets and conservative lowercase wrapped lines."""
    result: dict[str, list[str]] = {}
    for section in ("experience", "projects"):
        bullets: list[str] = []
        continuing = False
        for line in sections.get(section, []):
            if BULLET.match(line):
                bullets.append(BULLET.sub("", line).strip())
                continuing = True
            elif continuing and not re.search(r"[.!?:]$", bullets[-1]) and line[:1].islower():
                bullets[-1] += " " + line
            else:
                continuing = False
        result[section] = bullets
    return result


def writing_insights(text: str) -> list[dict[str, str]]:
    sections = sections_from_text(text)
    bullets = practical_bullets(sections)
    descriptions = [normalized_description(line) for line in sections.get("summary", [])]
    descriptions.extend(normalized_description(line) for lines in bullets.values() for line in lines)
    insights: list[dict[str, str]] = []

    for insight_id, phrase in GENERIC_PHRASES:
        if phrase in descriptions:
            insights.append({
                "id": insight_id, "type": "generic_phrase", "priority": "low",
                "explanation": "A standalone familiar phrase gives little context about your contribution.",
                "recommendation": "If relevant, replace it with a specific task or example you can accurately describe.",
            })

    if any(normalized_description(line) in VAGUE_DESCRIPTIONS for lines in bullets.values() for line in lines):
        insights.append({
            "id": "vague_contribution", "type": "vague_description", "priority": "medium",
            "explanation": "An experience or project bullet mentions general duties without naming a task.",
            "recommendation": "Where accurate, name a task you performed and add useful context or a qualitative outcome; numbers are optional.",
        })

    for section, lines in bullets.items():
        # At least three distinct bullets with the same two-word opening within
        # one section. Never echo an opening, which could contain a name.
        unique_lines = {normalized_description(line) for line in lines}
        openings = Counter(match.group(0).strip() for line in unique_lines if (match := OPENING.match(line)))
        if any(count >= 3 for count in openings.values()):
            insights.append({
                "id": f"repeated_opening_{section}", "type": "repeated_opening", "priority": "low",
                "explanation": f"At least three distinct {section} bullets begin with the same two words.",
                "recommendation": "Review those openings and vary them only where a different wording accurately describes your contribution.",
            })
    return insights[:MAX_INSIGHTS]
