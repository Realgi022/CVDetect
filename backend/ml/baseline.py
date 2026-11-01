"""Reproducible in-memory baseline. Never fit vocabulary on held-out texts."""
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

from .dataset import check_split


def create_pipeline():
    return Pipeline([("tfidf", TfidfVectorizer()), ("classifier", LogisticRegression(random_state=42, max_iter=1000))])


def train(train_records, test_records):
    check_split(train_records, test_records)
    model = create_pipeline()
    model.fit([r["text"] for r in train_records], [r["label"] for r in train_records])
    return model
