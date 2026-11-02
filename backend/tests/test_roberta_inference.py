from concurrent.futures import ThreadPoolExecutor
from contextlib import nullcontext
from types import SimpleNamespace

import pytest
import app.dev_server as server
import ml.roberta_inference as roberta


@pytest.fixture(autouse=True)
def reset_model(monkeypatch):
    monkeypatch.setattr(roberta, '_model', None)


def test_model_cached_and_limit_never_truncated(monkeypatch):
    monkeypatch.setenv('CVDETECT_RESEARCH_ROBERTA', '1')
    loads, calls = [], []
    class Tokenizer:
        model_max_length = 512
        def num_special_tokens_to_add(self, pair=False): return 2
        def __call__(self, text, **kwargs):
            calls.append(kwargs)
            count = len(text) + (2 if kwargs.get('add_special_tokens', True) else 0)
            if kwargs.get('return_tensors'):
                return {'input_ids': SimpleNamespace(shape=(1, count))}
            result = {'input_ids': list(range(count))}
            if kwargs.get('return_offsets_mapping'): result['offset_mapping'] = [(i, i + 1) for i in range(len(text))]
            return result
    class Values:
        shape = (1, 2)
        def __getitem__(self, key): return [0.75, 0.25][key[1]]
    class Model:
        config = SimpleNamespace(max_position_embeddings=514, pad_token_id=1)
        def __call__(self, **kwargs): return SimpleNamespace(logits='logits')
    fake_torch = SimpleNamespace(inference_mode=nullcontext, softmax=lambda logits, dim: Values())
    def load():
        loads.append(1)
        return Tokenizer(), Model(), 0, fake_torch
    monkeypatch.setattr(roberta, '_load', load)
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(roberta.infer, ['fictional text sufficient'] * 4))
    assert len(loads) == 1
    assert all(result['chunks'][0]['ai_class_probability'] == 0.75 for result in results)
    long = roberta.infer('long content ' * 100)
    assert len(long['chunks']) > 1
    assert sum(c['characters'] for c in long['chunks']) == len('long content ' * 100)
    assert all(c['input_tokens'] <= 512 for c in long['chunks'])
    exact = roberta.infer('x' * 510)
    assert len(exact['chunks']) == 1 and exact['chunks'][0]['input_tokens'] == 512
    short_tail = roberta.infer('x' * 510 + ' hi')
    assert short_tail['chunks'][-1]['status'] == 'insufficient_text'
    assert short_tail['coverage']['assigned_characters'] == 513
    assert short_tail['coverage']['scored_characters'] < 513
    assert roberta.infer('x' * 9000) == {'status': 'chunk_limit', 'max_chunks': 16}
    assert all(call['truncation'] is False for call in calls)


def test_exact_character_partition_and_chunk_limit():
    class Tokenizer:
        def num_special_tokens_to_add(self, pair=False): return 2
        def __call__(self, text, **kwargs):
            result = {'input_ids': list(range(len(text) + (2 if kwargs.get('add_special_tokens', True) else 0)))}
            if kwargs.get('return_offsets_mapping'): result['offset_mapping'] = [(i, i + 1) for i in range(len(text))]
            return result
    tokenizer = Tokenizer()
    text = 'Section\n- bullet line here\n' + 'x' * 1200 + '\nTail — café 中文'
    chunks, source = roberta.chunk_text(text, tokenizer, 512)
    assert ''.join(c[0] for c in chunks) == text
    assert source == len(text)
    assert all(c[2] <= 512 for c in chunks)
    assert roberta.chunk_text('x' * 9000, tokenizer, 512)[0] is None


def test_missing_or_disabled_model(monkeypatch, tmp_path):
    monkeypatch.delenv('CVDETECT_RESEARCH_ROBERTA', raising=False)
    with pytest.raises(RuntimeError): roberta.infer('fictional')
    monkeypatch.setenv('CVDETECT_RESEARCH_ROBERTA', '1')
    monkeypatch.setattr(roberta, 'MODEL_DIR', tmp_path / 'missing')
    with pytest.raises(RuntimeError): roberta.infer('fictional')


def test_vite_endpoint_security_and_errors(browser, monkeypatch):
    monkeypatch.setenv('CVDETECT_RESEARCH_VITE', '1')
    origin = {'origin': server.VITE_ORIGIN}
    assert browser.post(server.VITE_ROBERTA, headers=origin, json={'text': 'fictional'}).status_code == 403
    token = browser.post(server.VITE_SESSION, headers={**origin, 'x-research-session': '1'}).json()['csrf_token']
    headers = {**origin, 'x-csrf-token': token}
    monkeypatch.setattr(roberta, 'infer', lambda text: {'status': 'too_long'})
    result = browser.post(server.VITE_ROBERTA, headers=headers, json={'text': 'fictional'})
    assert result.status_code == 200 and result.json() == {'status': 'too_long'}
    assert result.headers['cache-control'] == 'no-store'
    def fail(text): raise RuntimeError('private details')
    monkeypatch.setattr(roberta, 'infer', fail)
    result = browser.post(server.VITE_ROBERTA, headers=headers, json={'text': 'fictional'})
    assert result.status_code == 503 and 'private details' not in result.text
    assert browser.post(server.VITE_ROBERTA, headers={**headers, 'x-forwarded-for': '127.0.0.1'}, json={'text': 'fictional'}).status_code == 404


from test_research_upload import browser  # existing isolated development app fixture
