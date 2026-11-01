"""Refusal gates.  A refusal is a result: it says what was NOT formalized and what would be needed.

These are conservative lexical gates over the claim text and the proposal's free text.  They exist because the
grammar has no vocabulary for biological mechanism: a causal genotype -> phenotype statement cannot be turned
into constraints by renaming it into symbols.  The gate is a heuristic (it can miss paraphrases); a miss is
not a licence -- 'checked' never means the English claim was formalized faithfully.
"""
from __future__ import annotations

import re

CAUSAL = re.compile(r"\b(explain|explains|explained|cause|causes|caused|causal|responsible for|underlie|underlies|"
                    r"underlying|leads? to|results? in|due to|accounts? for|determines?|drives?|is why|because of|"
                    r"sufficient|necessary for)\b", re.I)
GENOTYPE = re.compile(r"\b(gene|genes|exon|intron|allele|alleles|mutation|mutations|variant|variants|deletion|"
                      r"insertion|knock-?out|loss of|loss-of-function|snp|locus|loci|genotype|oca2|mc1r|crispr|talen)\b", re.I)
PHENOTYPE = re.compile(r"\b(albinism|albino|pigment\w*|phenotype|trait|traits|disease|syndrome|blindness|eye loss|"
                       r"melanin|depigment\w*|behaviou?r|morpholog\w*|fitness|survival|viab\w*)\b", re.I)
FUNCTION = re.compile(r"\b(will (express|produce|function|work|be functional)|guarantees?|ensures? (expression|function|viability)|"
                      r"functional (organism|genome|protein)|viable organism|therapeutic|safe for)\b", re.I)


def _texts(ctx: dict) -> str:
    p = ctx["proposal"]
    parts = [ctx["claim"].get("text", "")]
    parts += [a.get("text", "") for a in p.get("assumptions", [])]
    parts += [u.get("question", "") for u in p.get("unresolved", [])]
    return "\n".join(parts)


def gate(ctx: dict) -> list:
    text = _texts(ctx)
    out = []
    if CAUSAL.search(text) and GENOTYPE.search(text) and PHENOTYPE.search(text):
        out.append({
            "code": "CAUSAL_GENOTYPE_PHENOTYPE_NO_MECHANISM",
            "reason": "The claim asserts that a genotype lesion causes or explains a phenotype. The bounded grammar contains "
                      "no mechanism (no pathway, no quantitative gene-to-trait map), so turning the sentence into symbols and "
                      "constraints would only restate the assertion, not check it. Association, mapping or perturbation evidence "
                      "in a source supports the claim biologically; it is not a formalization.",
            "what_would_be_needed": [
                "a mechanistic map from the lesion to the trait stated with declared symbols, units and domains (e.g. molecular "
                "consequence of the lesion on transcript/protein and the downstream quantity that defines the phenotype)",
                "the source's evidence class for each link (observed association, perturbation/rescue, prediction) kept separate",
                "scope: which population, background and conditions the mapping holds in",
                "separately, only sequence-level facts (lengths, counts, coordinates) are checkable by counting; these are "
                "reported apart from the causal claim and say nothing about function"]})
    if FUNCTION.search(text):
        out.append({
            "code": "BIOLOGICAL_FUNCTION_NOT_FORMALIZABLE",
            "reason": "The text asserts function, viability or safety of a designed biological object. Sequence or constraint "
                      "checks here do not establish biological function.",
            "what_would_be_needed": ["a predictive or experimental assay for the function, kept as observed/predicted, "
                                     "not as a result of constraint satisfaction"]})
    return out
