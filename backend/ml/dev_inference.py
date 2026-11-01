"""Unvalidated, in-memory fictional-baseline inference for local research only."""
from functools import lru_cache
from pathlib import Path

from .baseline import train
from .dataset import load_dataset, split_records

MAX_TEXT_CHARS = 20_000
SMOKE = Path(__file__).parent / "fixtures" / "synthetic_smoke.json"


@lru_cache(maxsize=1)
def _fictional_model():
    records = load_dataset(SMOKE)
    # Never permit the fallback random split for this prototype.
    if any("split" not in record for record in records):
        raise ValueError("The fixed smoke split is required.")
    training, test = split_records(records)
    if len(training) != 8 or len(test) != 4:
        raise ValueError("Unexpected smoke dataset partition sizes.")
    return train(training, test)


def infer(text: str) -> dict:
    if not isinstance(text, str) or not text.strip() or not any(char.isalnum() for char in text):
        raise ValueError("Text must contain at least one letter or number.")
    if len(text) > MAX_TEXT_CHARS:
        raise ValueError("Text exceeds the local research limit.")
    if any(0xD800 <= ord(char) <= 0xDFFF for char in text):
        raise ValueError("Text contains invalid Unicode.")
    model = _fictional_model()
    score = float(model.decision_function([text])[0])
    positive = str(model.named_steps["classifier"].classes_[1])
    return {
        "status": "unvalidated_research_model",
        "authorship_conclusion": "inconclusive",
        "model_diagnostic": {
            "raw_uncalibrated_decision_score": score,
            "positive_direction": f"toward the illustrative {positive} training label",
        },
        "limitations": [
            "Local research only: trained on eight fictional examples with illustrative, unverified labels; real-world accuracy and fairness are not established.",
            "The raw decision score is not a probability of authorship and is not a reliable AI/human verdict.",
            "The conclusion is always inconclusive; abstention does not establish safety or accuracy.",
        ],
    }
