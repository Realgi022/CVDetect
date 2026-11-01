import numpy as np
import pytest

from ml import artifact_inference
from test_research_upload import artifact, trust


@pytest.mark.parametrize('classes,values,expected', [(['ai', 'human'], [0.8, 0.2], 0.8), (['human', 'ai'], [0.8, 0.2], 0.2)])
def test_class_orientation(monkeypatch, artifact, classes, values, expected):
    trust(monkeypatch, artifact)
    class Model:
        named_steps = {'classifier': type('Classifier', (), {'classes_': classes})()}
        def decision_function(self, texts): return [0.1]
        def predict_proba(self, texts): return np.array([values])
    monkeypatch.setattr(artifact_inference.pickle, 'loads', lambda data: Model())
    assert artifact_inference.infer_trusted('Fictional text')['model_diagnostic']['ai_class_probability'] == expected


def test_no_probability_is_not_converted(monkeypatch, artifact):
    trust(monkeypatch, artifact)
    class Model:
        named_steps = {'classifier': type('Classifier', (), {'classes_': ['ai', 'human']})()}
        def decision_function(self, texts): return [0.1]
    monkeypatch.setattr(artifact_inference.pickle, 'loads', lambda data: Model())
    assert artifact_inference.infer_trusted('Fictional text')['model_diagnostic']['ai_class_probability'] is None


@pytest.mark.parametrize('values', [[float('nan'), 0.5], [1.1, -0.1], [0.2, 0.2]])
def test_invalid_probabilities_rejected(monkeypatch, artifact, values):
    trust(monkeypatch, artifact)
    class Model:
        named_steps = {'classifier': type('Classifier', (), {'classes_': ['ai', 'human']})()}
        def decision_function(self, texts): return [0.1]
        def predict_proba(self, texts): return np.array([values])
    monkeypatch.setattr(artifact_inference.pickle, 'loads', lambda data: Model())
    with pytest.raises(RuntimeError): artifact_inference.infer_trusted('Fictional text')
