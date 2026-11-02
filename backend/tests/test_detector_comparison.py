import pytest

from ml.detector_comparison import TooLong, compare
from ml.manifest_audit import text_hash


def records():
    samples = [
        ('train', 'human', 'Volunteered at the observatory and catalogued antique astronomical instruments for the local museum collection.'),
        ('validation', 'human', 'Skills: Python, SQL, Docker.'),
        ('validation', 'ai', 'Experience\n- Built reporting tools for local charities and maintained dashboards for twenty volunteers across three regional community events and annual workshops.'),
        ('validation', 'human', 'Summary: Research analyst with practical experience translating survey results into clear presentations for teams and supporting cross functional collaboration with external partners.'),
        ('validation', 'mixed', 'Professional profile: A carefully edited fictional AI draft combining personal experience and generated wording about imaginary logistics work in a regional archive.'),
        ('test', 'ai', 'Projects: Created an imaginary gardening program for schools that measured water use and documented seasonal changes over multiple years.'),
    ]
    return [{'dataset_id': 'fictional-day24', 'source_url': 'https://example.org/fictional', 'license_status': 'unverified',
             'original_record_id': str(i), 'provenance_group': str(i), 'related_groups': [], 'source_domain': 'cv',
             'model_id': None, 'label': label, 'text': text, 'text_hash': text_hash(text), 'split': split, 'transformations': []}
            for i, (split, label, text) in enumerate(samples)]


def test_metrics_abstention_and_mixed_labels():
    rows = records()
    result = compare(rows, split='validation', evidence='synthetic', models={'model': lambda text: 0.8 if text.startswith('Experience') else 0.1})
    model = result['models']['model']
    assert model['classification']['confusion_matrix']['counts'] == [[1, 0], [0, 1]]
    assert model['classification']['non_binary_prediction_distribution']['mixed']['human'] == 1
    assert model['abstention_reasons_all_labels']['insufficient_text'] == 1
    assert model['scored_binary_count'] == 2 and model['roc_auc'] == 1
    assert model['brier_score'] == pytest.approx(0.025)
    assert model['latency_ms']['count'] == 3
    assert 'Professional profile' not in str(result)


def test_token_limit_and_missing_class():
    def reject(text): raise TooLong()
    result = compare(records(), split='validation', evidence='synthetic', models={'candidate': reject})['models']['candidate']
    assert result['abstention_reasons_all_labels']['candidate_token_limit'] == 3
    assert result['roc_auc'] is None and result['brier_score'] is None
    assert result['classification']['coverage_eligible'] == 0


@pytest.mark.parametrize('score', [float('nan'), float('inf'), -0.1, 1.1, True])
def test_invalid_score_rejected(score):
    with pytest.raises(ValueError):
        compare(records(), split='validation', evidence='synthetic', models={'broken': lambda _: score})


def test_reject_unapproved_or_unsafe_provenance():
    with pytest.raises(ValueError):
        compare(records(), split='test', evidence='unvalidated_research', models={'x': lambda _: 0.5})
    rows = records()
    rows[-1]['provenance_group'] = rows[0]['provenance_group']
    with pytest.raises(ValueError):
        compare(rows, split='test', evidence='synthetic', models={'x': lambda _: 0.5})


def test_oversized_text_abstains():
    rows = records()
    rows[2]['text'] = 'Long fictional details ' * 1000
    rows[2]['text_hash'] = text_hash(rows[2]['text'])
    result = compare(rows, split='validation', evidence='synthetic', models={'x': lambda _: 0.5})
    assert result['models']['x']['abstention_reasons_all_labels']['character_limit'] == 1
