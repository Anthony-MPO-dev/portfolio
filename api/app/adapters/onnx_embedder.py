"""Text to vectors on the server's CPU, with a small ONNX sentence model (no paid API, no GPU).

Responsibility: load the model and its tokenizer from a folder (model_quantized.onnx, tokenizer.json), turn texts
into L2-normalized vectors by mean pooling, with the model's own prefix for a query or a passage (the e5 family
wants "query: " and "passage: "). One thread, so a burst of searches can't starve the chat on the same machine.
Public API: OnnxEmbedder.
Used by: app.main (wires it into app.services.search), golden/search_eval.py.
Depends on: onnxruntime, tokenizers, numpy.
Tests: golden/search_eval.py runs it on the real model (dev only); the search service is unit-tested with a fake.
"""

from collections.abc import Sequence
from pathlib import Path
from typing import Literal

import numpy as np
import onnxruntime as ort
from tokenizers import Tokenizer

MAX_TOKENS = 256  # a passage of the fact base is far shorter; a visitor's question is capped at 200 characters


class OnnxEmbedder:
    def __init__(self, folder: Path, prefixes: dict[str, str] | None = None):
        self.tok = Tokenizer.from_file(str(folder / "tokenizer.json"))
        self.tok.enable_truncation(max_length=MAX_TOKENS)
        pad = self.tok.token_to_id("<pad>")
        self.tok.enable_padding(pad_id=pad if pad is not None else 0, pad_token="<pad>" if pad is not None else "[PAD]")
        opts = ort.SessionOptions()
        opts.intra_op_num_threads = opts.inter_op_num_threads = 1
        self.sess = ort.InferenceSession(str(folder / "model_quantized.onnx"), opts, providers=["CPUExecutionProvider"])
        self.inputs = {i.name for i in self.sess.get_inputs()}
        self.prefixes = prefixes or {}

    def embed(self, texts: Sequence[str], kind: Literal["query", "passage"]) -> list[list[float]]:
        enc = self.tok.encode_batch([self.prefixes.get(kind, "") + t for t in texts])
        ids = np.array([e.ids for e in enc], dtype=np.int64)
        mask = np.array([e.attention_mask for e in enc], dtype=np.int64)
        feed = {"input_ids": ids, "attention_mask": mask}
        if "token_type_ids" in self.inputs:
            feed["token_type_ids"] = np.zeros_like(ids)
        hidden = self.sess.run(None, feed)[0]
        m = mask[..., None].astype(np.float32)
        v = (hidden * m).sum(axis=1) / np.clip(m.sum(axis=1), 1e-9, None)
        v /= np.linalg.norm(v, axis=1, keepdims=True)
        return v.tolist()
