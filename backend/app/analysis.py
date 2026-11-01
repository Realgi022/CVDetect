"""Transparent, text-only CV presentation heuristics; no claims about suitability."""
import re

HEADINGS = {
    "education": {"education", "academic background", "qualifications", "academic qualifications"},
    "experience": {"experience", "work experience", "professional experience", "employment", "employment history", "work history", "internships", "volunteer experience"},
    "projects": {"projects", "personal projects", "academic projects", "selected projects"},
    "skills": {"skills", "technical skills", "key skills", "core skills", "competencies"},
    "summary": {"summary", "professional summary", "profile", "personal profile", "objective", "career objective"},
}
VERBS = set("built created developed designed implemented improved led managed organized organised delivered researched analyzed analysed tested wrote collaborated coordinated supported automated maintained deployed investigated planned produced contributed assisted presented".split())
BULLET = re.compile(r"^\s*(?:[•●▪◦‣]|[-*–—])\s*")
WORDS = re.compile(r"\b[\w+#.-]+\b")
CONTACT = re.compile(r"(?:\b[\w.+-]+@[\w.-]+\.[a-z]{2,}\b|https?://|www\.|\b(?:linkedin\.com|github\.com)/|(?<!\w)\+?\d[\d ()-]{7,}\d(?!\w))", re.I)


def sections_from_text(text: str) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {}
    current = None
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        # A heading may also have its contents after a colon.
        heading, sep, content = line.partition(":")
        candidate = heading.strip().lower() if sep else line.rstrip(": ").lower()
        found = next((key for key, names in HEADINGS.items() if candidate in names), None)
        if found:
            current = found
            sections.setdefault(found, [])
            if sep and content.strip():
                sections[found].append(content.strip())
        elif current and not CONTACT.search(line):
            sections[current].append(line)
    return sections


def analyze_text(text: str) -> dict:
    sections = sections_from_text(text)
    strengths, weaknesses, recommendations = [], [], []
    categories = {}

    def category(key, score, explanation):
        categories[key] = {"score": max(0, min(100, round(score))), "explanation": explanation}

    # Neither work experience nor every optional section is mandatory.
    academic = "education" in sections
    practical = bool({"experience", "projects"} & sections.keys())
    skills = "skills" in sections
    optional = "summary" in sections
    structure = 30 * academic + 40 * practical + 20 * skills + 10 * optional
    found = ", ".join(sections) or "none"
    category("structure", structure, f"Recognized sections: {found}. Education contributes 30 points; experience OR projects 40; skills 20; summary 10. Projects count equally with experience; the summary is optional.")
    if practical:
        strengths.append("A recognizable experience or projects section provides a place for practical work.")
    else:
        weaknesses.append("No experience or projects heading was recognized.")
        recommendations.append("If applicable, add an experience or projects section; coursework, volunteering or personal projects can provide context.")
    if not academic:
        weaknesses.append("No education heading was recognized.")
        recommendations.append("Consider a clearly labeled education section if relevant.")
    if not optional:
        recommendations.append("Optionally add a short summary or objective tailored to your goals.")

    entries = [line for name in ("experience", "projects") for line in sections.get(name, []) if BULLET.match(line)]
    cleaned = [BULLET.sub("", line).strip() for line in entries]
    action = sum(bool(WORDS.findall(line)) and WORDS.findall(line)[0].lower() in VERBS for line in cleaned)
    specific = sum(len(WORDS.findall(line)) >= 6 for line in cleaned)
    measurable = sum(bool(re.search(r"\b\d+(?:[.,]\d+)?\s*(?:%|percent\b|users?\b|customers?\b|hours?\b|days?\b|weeks?\b|projects?\b|clients?\b|requests?\b|people\b)", line, re.I)) for line in cleaned)
    count = len(cleaned)
    # Metrics are reported, never scored: numerical outcomes are not always available.
    exp_score = (20 + 40 * action / count + 40 * specific / count) if count else 0
    category("experience", exp_score, f"Found {count} explicit bullet(s) under experience/projects: {action} begin with a listed action verb, {specific} contain at least 6 words, and {measurable} include a recognizable numerical outcome. With bullets: 20 points for having bullets, up to 40 for the action-verb fraction and 40 for the 6-word fraction. Numerical outcomes do not affect the score and are not verified.")
    if count:
        strengths.append(f"Found {count} experience/project bullet(s); {action} start with a recognized action verb and {specific} have at least 6 words.")
        if action < count or specific < count:
            recommendations.append("Where accurate, start bullets with action verbs and explain what you did and its context or outcome.")
    else:
        weaknesses.append("No explicit experience/project bullets were recognized; extraction may have merged or removed bullet formatting.")
        recommendations.append("Where applicable, use clear bullets to describe projects, coursework, volunteering or work; check the extracted preview for formatting loss.")
    recommendations.append("Include measurable outcomes only when accurate and meaningful; qualitative outcomes are useful too. Never invent numbers.")

    skill_lines = sections.get("skills", [])
    skill_text = " ".join(skill_lines).strip()
    separated = bool(re.search(r"[,;|•]", skill_text) or len(skill_lines) > 1)
    skill_score = 40 * skills + 40 * bool(skill_text) + 20 * separated
    category("skills", skill_score, f"Skills heading: {'yes' if skills else 'no'} (40 points); content beneath it: {'yes' if skill_text else 'no'} (40); separated items or multiple lines: {'yes' if separated else 'no'} (20). No particular skill is required or verified.")
    if skill_text:
        strengths.append("A recognized skills section contains text.")
    else:
        weaknesses.append("No populated skills section was recognized.")
        recommendations.append("If relevant, list skills you actually have under a clear Skills heading.")
    if skill_text and not separated:
        recommendations.append("Consider separating skills into readable items or groups without adding skills you do not have.")

    # Evaluate only recognized section content, excluding unclassified contact/personal details.
    lines = [line for content in sections.values() for line in content]
    word_counts = [len(WORDS.findall(line)) for line in lines]
    concise = sum(1 for n in word_counts if 1 <= n <= 40)
    read_score = 100 * concise / len(lines) if lines else 0
    category("readability", read_score, f"Of {len(lines)} non-empty lines in recognized sections, {concise} have 1–40 words. Score is their percentage; no recognized content scores 0. Contact and unclassified lines are excluded. Extraction can merge lines, and this does not measure grammar or meaning.")
    if lines and concise == len(lines):
        strengths.append(f"All {len(lines)} recognized content line(s) are within the 40-word guideline.")
    else:
        weaknesses.append(f"Readability: {len(lines)} recognized content line(s) assessed; {len(lines) - concise} exceed the guideline or have no countable words.")
        recommendations.append("Review long or unrecognized content in the preview; use concise lines and clear headings where appropriate.")

    overall = round(sum(categories[k]["score"] * weight for k, weight in (("structure", .3), ("experience", .3), ("skills", .2), ("readability", .2))))
    return {"overall_score": overall, "categories": categories, "strengths": strengths, "weaknesses": weaknesses, "recommendations": recommendations, "method": "Heuristic guidance only, not hiring suitability or ATS certification. Overall = 30% structure + 30% experience/projects + 20% skills + 20% readability. Scores assess recognized text presentation, not truth or ability; extraction and heading recognition can miss content."}
