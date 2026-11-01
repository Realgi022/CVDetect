"""Descriptive CV writing measurements; not an authorship detector or quality score."""
from collections import Counter, defaultdict
import re
import statistics
import unicodedata

from .analysis import BULLET, CONTACT, HEADINGS, OTHER_HEADING, PERSONAL_FIELD, VERBS, WORDS, YEAR_RANGE
from .writing_insights import GENERIC_PHRASES

MIN_WORDS = 20
MIN_UNITS = 3
MAX_ANALYZED_CHARS = 100_000
MEASURABLE = re.compile(r"\b\d+(?:[.,]\d+)?\s*(?:%|percent\b|users?\b|customers?\b|hours?\b|days?\b|weeks?\b|projects?\b|clients?\b|requests?\b|people\b)", re.I)
NUMBER = re.compile(r"\b\d+(?:[.,]\d+)?\b")


def writing_patterns(text: str) -> dict:
    """Count line/sentence fragments; never return arbitrary source snippets.

    Each nonempty non-contact line is a boundary; terminal punctuation followed
    by whitespace creates additional boundaries. This is not linguistic parsing.
    """
    analyzed = text[:MAX_ANALYZED_CHARS]
    lines = [line.strip() for line in analyzed.splitlines() if line.strip()]
    heading_names = set().union(*HEADINGS.values())
    eligible = []
    for line in lines:
        if CONTACT.search(YEAR_RANGE.sub("", line)) or PERSONAL_FIELD.match(line):
            continue
        heading, separator, content = line.partition(":")
        candidate = re.sub(r"\s+", " ", (heading if separator else line).strip().strip("|–— ").casefold())
        if candidate in heading_names:
            line = content.strip() if separator else ""
        elif OTHER_HEADING.fullmatch(line):
            line = ""
        if line:
            eligible.append(line)

    units = []
    for line in eligible:
        line = BULLET.sub("", line).strip()
        for part in re.split(r"(?<=[.!?。！？])\s+", line):
            normalized = unicodedata.normalize("NFKC", part).casefold()
            words = WORDS.findall(normalized)
            if words:
                units.append((part, words))
    lengths = [len(words) for _, words in units]
    unit_count, word_count = len(units), sum(lengths)
    distribution = [{"label": label, "count": sum(lower <= n <= upper for n in lengths)} for label, lower, upper in
                    (("1–5 words", 1, 5), ("6–10 words", 6, 10), ("11–20 words", 11, 20), ("21+ words", 21, float("inf")))]
    openings = Counter(tuple(words[:2]) for _, words in units if len(words) >= 2)
    bigram_units = defaultdict(set)
    for i, (_, words) in enumerate(units):
        for pair in set(zip(words, words[1:])):
            bigram_units[pair].add(i)
    generic = []
    generic_unit_indices = set()
    for _, phrase in GENERIC_PHRASES:
        needle = WORDS.findall(phrase)
        matches = {index for index, (_, words) in enumerate(units)
                   if any(words[i:i + len(needle)] == needle for i in range(len(words) - len(needle) + 1))}
        if matches:
            generic.append({"phrase": phrase, "unit_count": len(matches)})
            generic_unit_indices.update(matches)
    return {
        "status": "sufficient" if word_count >= MIN_WORDS and unit_count >= MIN_UNITS else "insufficient",
        "coverage": {"total_characters": len(text), "analyzed_characters": len(analyzed), "truncated": len(analyzed) < len(text),
                     "nonempty_lines": len(lines), "included_lines": len(eligible), "units": unit_count,
                     "words": word_count, "minimum_words": MIN_WORDS, "minimum_units": MIN_UNITS},
        "sentence_length": {"distribution": distribution, "mean_words": round(statistics.mean(lengths), 2) if lengths else None,
                            "population_stddev_words": round(statistics.pstdev(lengths), 2) if len(lengths) >= 2 else None},
        "repetition": {"repeated_two_word_phrases": sum(len(indices) >= 2 for indices in bigram_units.values()),
                       "repeated_opening_groups": sum(count >= 2 for count in openings.values()),
                       "units_with_repeated_opening": sum(count for count in openings.values() if count >= 2),
                       "units_with_two_word_opening": sum(openings.values())},
        "generic_phrases": {"matched": generic, "units_with_match": len(generic_unit_indices)},
        "specificity": {"units_with_number": sum(bool(NUMBER.search(part)) for part, _ in units),
                        "units_with_measurable_pattern": sum(bool(MEASURABLE.search(part)) for part, _ in units),
                        "units_starting_action_verb": sum(words[0] in VERBS for _, words in units)},
        "limitations": "Counts describe recognized text only, not AI authorship, truth, writing quality or hiring suitability. Sentence boundaries, extraction and English-oriented lists are imperfect; numbers and outcomes are not verified.",
    }
