"""Opt-in, local-only research inference; never imported by the public app."""
import math
import os
import re
from pathlib import Path
from threading import Lock

from .dev_inference import validate_text

MODEL_DIR = Path(r"C:\Users\realg\AppData\Local\Temp\opencode\day24-fakespot")
MAX_TOKENS = 512
MAX_CHUNKS = 16
MIN_CONTENT_TOKENS = 10
_model = None
_lock = Lock()


def _load():
    if not MODEL_DIR.is_absolute() or MODEL_DIR.is_symlink() or not MODEL_DIR.is_dir():
        raise RuntimeError("Local model directory unavailable.")
    for name in ("config.json", "model.safetensors", "tokenizer.json", "tokenizer_config.json"):
        file = MODEL_DIR / name
        if file.is_symlink() or not file.is_file():
            raise RuntimeError("Local model files unavailable.")
    from transformers import AutoModelForSequenceClassification, AutoTokenizer
    import torch
    tokenizer = AutoTokenizer.from_pretrained(str(MODEL_DIR), local_files_only=True, trust_remote_code=False)
    model = AutoModelForSequenceClassification.from_pretrained(str(MODEL_DIR), local_files_only=True, trust_remote_code=False, use_safetensors=True)
    model.to("cpu").eval()
    labels = {int(k): str(v).casefold() for k, v in model.config.id2label.items()}
    if model.config.model_type != "roberta" or set(labels.values()) != {"human", "ai"} or set(labels) != {0, 1}:
        raise RuntimeError("Unsupported model class labels.")
    return tokenizer, model, next(i for i, label in labels.items() if label == "ai"), torch


def chunk_text(text, tokenizer, model_limit):
    """Partition source characters without overlap; tokenize each final chunk again.

    Prefer line boundaries, then whitespace, then tokenizer offsets for a long
    unbroken fragment. Counts exclude special tokens unless otherwise noted.
    """
    special = tokenizer.num_special_tokens_to_add(pair=False)
    budget = model_limit - special
    if budget < 1:
        raise RuntimeError("Invalid model token limit.")
    source_tokens = len(tokenizer(text, add_special_tokens=False, truncation=False, verbose=False)['input_ids'])
    chunks = []
    start = 0
    while start < len(text):
        remainder = text[start:]
        encoded = tokenizer(remainder, add_special_tokens=False, return_offsets_mapping=True, truncation=False, verbose=False)
        ids, offsets = encoded['input_ids'], encoded['offset_mapping']
        if len(ids) <= budget:
            end = len(text)
        else:
            cut = offsets[budget - 1][1]
            if cut <= 0:
                raise RuntimeError("Unable to split tokenizer offsets safely.")
            prefix = remainder[:cut]
            newline = max(prefix.rfind('\n'), prefix.rfind('\r'))
            whitespace = list(re.finditer(r'\s+', prefix))
            # Do not create an extremely short chunk just to preserve a line.
            if newline >= cut // 2:
                cut = newline + 1
            elif whitespace and whitespace[-1].end() >= cut // 2:
                cut = whitespace[-1].end()
            end = start + cut
        piece = text[start:end]
        # Retokenizing at a boundary can alter byte-level BPE tokens. Validate
        # the actual model input rather than trusting offsets alone.
        count = len(tokenizer(piece, add_special_tokens=True, truncation=False, verbose=False)['input_ids'])
        while count > model_limit and end > start + 1:
            end -= 1
            piece = text[start:end]
            count = len(tokenizer(piece, add_special_tokens=True, truncation=False, verbose=False)['input_ids'])
        if count > model_limit or end <= start:
            raise RuntimeError("Unable to split text within model limit.")
        content = len(tokenizer(piece, add_special_tokens=False, truncation=False, verbose=False)['input_ids'])
        chunks.append((piece, content, count))
        if len(chunks) > MAX_CHUNKS:
            return None, source_tokens
        start = end
    return chunks, source_tokens


def infer(text):
    validate_text(text)
    if os.environ.get("CVDETECT_RESEARCH_ROBERTA") != "1":
        raise RuntimeError("Local RoBERTa opt-in not enabled.")
    global _model
    # Serialize initialization and inference to prevent duplicate loads and
    # unbounded concurrent CPU/memory usage on the local research service.
    with _lock:
        if _model is None:
            _model = _load()
        tokenizer, model, ai_index, torch = _model
        limit = min(MAX_TOKENS, tokenizer.model_max_length,
                    model.config.max_position_embeddings - model.config.pad_token_id - 1)
        chunks, source_tokens = chunk_text(text, tokenizer, limit)
        if chunks is None:
            return {"status": "chunk_limit", "max_chunks": MAX_CHUNKS}
        results = []
        for piece, content_count, input_count in chunks:
            result = {"content_tokens": content_count, "input_tokens": input_count,
                      "characters": len(piece), "status": "insufficient_text"}
            if content_count >= MIN_CONTENT_TOKENS:
                tokens = tokenizer(piece, return_tensors="pt", truncation=False, verbose=False)
                if tokens['input_ids'].shape[1] != input_count or input_count > limit:
                    raise RuntimeError("Invalid token count.")
                with torch.inference_mode():
                    values = torch.softmax(model(**tokens).logits, dim=-1)
                    if tuple(values.shape) != (1, 2):
                        raise RuntimeError("Invalid model output shape.")
                    score = float(values[0, ai_index])
                if not math.isfinite(score) or not 0 <= score <= 1:
                    raise RuntimeError("Invalid model output.")
                result.update(status="scored", ai_class_probability=score)
            results.append(result)
        return {"status": "unvalidated_research_model", "authorship_conclusion": "inconclusive",
                "chunks": results, "coverage": {"source_characters": len(text),
                "assigned_characters": sum(c["characters"] for c in results),
                "scored_characters": sum(c["characters"] for c in results if c["status"] == "scored"),
                "source_content_tokens": source_tokens, "chunk_content_tokens": sum(c["content_tokens"] for c in results),
                "model_input_limit": limit, "minimum_content_tokens": MIN_CONTENT_TOKENS}}
