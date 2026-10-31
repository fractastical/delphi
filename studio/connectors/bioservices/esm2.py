"""ESM-2 masked-marginal variant scoring.

The masked-marginal score of a substitution (Meier et al. 2021) is

    score(wt -> mut at position i) = log p(mut | x_\\i) - log p(wt | x_\\i)

where ``x_\\i`` is the reference sequence with position ``i`` replaced by the
mask token. It needs one forward pass per *distinct position*, not per variant,
so variants sharing a position are scored from one pass.

This is zero-shot: the checkpoint is frozen, no measurement is ever shown to the
model, and nothing here is fitted. The scorer does not accept assay values at
all, which is the structural form of that guarantee.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class ScoringConfig:
    checkpoint: str
    threads: int = 2
    batch_positions: int = 4


class Esm2MaskedMarginalScorer:
    """Scores substitutions against one reference sequence.

    The reference is fixed at construction so a caller cannot accidentally score
    a variant against a sequence it was not measured on.
    """

    def __init__(self, reference: str, config: ScoringConfig, cache_dir: str | None = None):
        import torch
        from transformers import AutoModelForMaskedLM, AutoTokenizer

        torch.set_grad_enabled(False)
        torch.set_num_threads(config.threads)
        torch.manual_seed(0)
        os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

        self.reference = reference
        self.config = config
        self._torch = torch
        self.tokenizer = AutoTokenizer.from_pretrained(config.checkpoint, cache_dir=cache_dir)
        self.model = AutoModelForMaskedLM.from_pretrained(config.checkpoint, cache_dir=cache_dir)
        self.model.eval()

        enc = self.tokenizer(reference, return_tensors="pt")
        self._input_ids = enc["input_ids"]
        self._attention_mask = enc["attention_mask"]
        # ESM tokenizers prepend <cls>, so residue position p (1-based) is token p.
        expected = len(reference) + 2  # <cls> ... <eos>
        if self._input_ids.shape[1] != expected:
            raise ValueError(
                f"tokenizer produced {self._input_ids.shape[1]} tokens for a {len(reference)}-residue "
                f"sequence; expected {expected}. Position mapping would be wrong."
            )
        self._verify_position_mapping()
        self._log_probs: dict[int, "object"] = {}
        self.forward_passes = 0

    def _verify_position_mapping(self) -> None:
        """Assert that token index p holds the residue at 1-based position p.

        A silent off-by-one here would score the wrong residue and still produce
        plausible numbers, so it is checked rather than trusted.
        """
        ids = self._input_ids[0].tolist()
        for pos in (1, len(self.reference) // 2, len(self.reference)):
            token = self.tokenizer.convert_ids_to_tokens(ids[pos])
            if token != self.reference[pos - 1]:
                raise ValueError(
                    f"token {pos} is {token!r} but reference position {pos} is "
                    f"{self.reference[pos - 1]!r}: position mapping is wrong"
                )

    def _masked_log_probs(self, positions: list[int]):
        """Log-softmax over the vocabulary at each masked position."""
        torch = self._torch
        todo = [p for p in positions if p not in self._log_probs]
        for start in range(0, len(todo), self.config.batch_positions):
            chunk = todo[start : start + self.config.batch_positions]
            batch = self._input_ids.repeat(len(chunk), 1).clone()
            for row, pos in enumerate(chunk):
                batch[row, pos] = self.tokenizer.mask_token_id
            out = self.model(
                input_ids=batch,
                attention_mask=self._attention_mask.repeat(len(chunk), 1),
            )
            self.forward_passes += 1
            logits = out.logits
            for row, pos in enumerate(chunk):
                self._log_probs[pos] = torch.log_softmax(logits[row, pos], dim=-1)
        return self._log_probs

    def score_many(self, variants) -> dict[str, float]:
        """Score an iterable of :class:`Variant`-like objects.

        Each must carry ``mutant``, ``wt_aa``, ``position`` and ``mut_aa``. A
        variant disagreeing with the reference raises; it is never scored.
        """
        variants = list(variants)
        for v in variants:
            if not 1 <= v.position <= len(self.reference):
                raise ValueError(f"{v.mutant}: position {v.position} outside 1..{len(self.reference)}")
            if self.reference[v.position - 1] != v.wt_aa:
                raise ValueError(
                    f"{v.mutant}: reference holds {self.reference[v.position - 1]} at {v.position}, "
                    f"not the declared {v.wt_aa}"
                )
        log_probs = self._masked_log_probs(sorted({v.position for v in variants}))
        scores: dict[str, float] = {}
        for v in variants:
            lp = log_probs[v.position]
            mut_id = self.tokenizer.convert_tokens_to_ids(v.mut_aa)
            wt_id = self.tokenizer.convert_tokens_to_ids(v.wt_aa)
            scores[v.mutant] = float(lp[mut_id] - lp[wt_id])
        return scores

    def position_log_probs(self, positions: list[int]) -> dict[int, dict]:
        """Per-position log-probabilities over the 20 standard residues.

        Exposed so a run can *persist* what the in-process cache holds. The 256
        -variant run saved only per-variant scores, which cannot be inverted back
        into a position's full distribution, so extending it to more variants at
        the same positions cost a full recomputation. Saving this makes any later
        extension free.

        Each entry carries a sha256 of the exact masked input row, so a later run
        can show it fed the model the same thing rather than assuming it did.
        """
        import hashlib

        self._masked_log_probs(sorted(set(positions)))
        out: dict[int, dict] = {}
        for pos in sorted(set(positions)):
            lp = self._log_probs[pos]
            masked = self._input_ids.clone()
            masked[0, pos] = self.tokenizer.mask_token_id
            row = ",".join(str(int(v)) for v in masked[0].tolist())
            out[pos] = {
                "wt_aa": self.reference[pos - 1],
                "log_probs": {
                    aa: float(lp[self.tokenizer.convert_tokens_to_ids(aa)])
                    for aa in "ACDEFGHIKLMNPQRSTVWY"
                },
                "input_ids_sha256": hashlib.sha256(row.encode()).hexdigest(),
            }
        return out
