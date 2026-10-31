"""Tests for the bioservices connectors and the Kir2.1 evaluation's fixed rules.

The tests that matter most here are the refusals. A connector that scores a
variant it should have rejected produces plausible numbers and no error, which
is the failure mode this package is built to prevent, so each refusal is tested
by asserting that it raises -- never by calling it and hoping.
"""

from __future__ import annotations

import io
import os
import zipfile

import pytest

from connectors.bioservices import proteingym, uniprot
from connectors.bioservices.receipts import RetrievalReceipt, sha256_text
from experiments.bioservices.baselines import BLOSUM62, blosum62
from experiments.bioservices.kir21_esm2_assay_agreement import common

REFERENCE = "MKTAYIAKQRQISFVKSHFSRQ"


def _assay_csv(rows: list[tuple[str, str, float]]) -> str:
    out = io.StringIO()
    out.write("mutant,mutated_sequence,DMS_score,DMS_score_bin\n")
    for mutant, seq, score in rows:
        out.write(f"{mutant},{seq},{score},{1 if score > 0 else 0}\n")
    return out.getvalue()


def _mutate(reference: str, pos: int, aa: str) -> str:
    return reference[: pos - 1] + aa + reference[pos:]


def _write_archive(tmp_path, assay_id: str, rows) -> str:
    path = os.path.join(tmp_path, "archive.zip")
    mode = "a" if os.path.exists(path) else "w"
    with zipfile.ZipFile(path, mode) as zf:
        zf.writestr(f"DMS_ProteinGym_substitutions/{assay_id}.csv", _assay_csv(rows))
    return path


def _simple_rows(reference=REFERENCE):
    """One substitution at every position, so the reference is over-determined."""
    rows = []
    for pos in range(1, len(reference) + 1):
        wt = reference[pos - 1]
        mut = "A" if wt != "A" else "G"
        rows.append((f"{wt}{pos}{mut}", _mutate(reference, pos, mut), float(pos) / 10))
    return rows


class TestReferenceReconstruction:
    def test_reference_is_recovered_from_the_rows_alone(self, tmp_path):
        archive = _write_archive(str(tmp_path), "TEST_ASSAY_a", _simple_rows())
        assay = proteingym.load_assay(archive, "TEST_ASSAY_a")
        assert assay.reference_sequence == REFERENCE
        assert len(assay.variants) == len(REFERENCE)

    def test_a_row_whose_sequence_contradicts_its_mutant_is_refused(self, tmp_path):
        rows = _simple_rows()
        bad_seq = _mutate(REFERENCE, 3, "W")  # row claims ->A at position 3
        rows[2] = (rows[2][0], bad_seq, 1.0)
        archive = _write_archive(str(tmp_path), "TEST_ASSAY_b", rows)
        with pytest.raises(proteingym.ReferenceMismatch, match="declares"):
            proteingym.load_assay(archive, "TEST_ASSAY_b")

    def test_rows_disagreeing_about_an_untouched_position_are_refused(self, tmp_path):
        rows = _simple_rows()
        # Corrupt position 10 in one row only: it is untouched by that variant,
        # so it must equal the reference and the disagreement must surface.
        seq = list(rows[0][1])
        seq[9] = "W" if seq[9] != "W" else "Y"
        rows[0] = (rows[0][0], "".join(seq), 1.0)
        archive = _write_archive(str(tmp_path), "TEST_ASSAY_c", rows)
        with pytest.raises(proteingym.ReferenceMismatch):
            proteingym.load_assay(archive, "TEST_ASSAY_c")

    def test_ragged_sequence_lengths_are_refused(self, tmp_path):
        rows = _simple_rows()
        rows[1] = (rows[1][0], rows[1][1] + "A", 1.0)
        archive = _write_archive(str(tmp_path), "TEST_ASSAY_d", rows)
        with pytest.raises(proteingym.ReferenceMismatch, match="ragged"):
            proteingym.load_assay(archive, "TEST_ASSAY_d")

    def test_a_missing_assay_names_itself(self, tmp_path):
        archive = _write_archive(str(tmp_path), "TEST_ASSAY_e", _simple_rows())
        with pytest.raises(KeyError, match="NOT_THERE"):
            proteingym.load_assay(archive, "NOT_THERE")


class TestVariantRefusal:
    def test_wrong_declared_wild_type_is_refused(self):
        wrong = "W" if REFERENCE[4] != "W" else "Y"
        with pytest.raises(proteingym.ReferenceMismatch, match="reference holds"):
            proteingym.check_variant_against_reference(f"{wrong}5A", REFERENCE)

    def test_position_past_the_end_is_refused(self):
        with pytest.raises(proteingym.ReferenceMismatch, match="outside"):
            proteingym.check_variant_against_reference(f"A{len(REFERENCE) + 1}G", REFERENCE)

    def test_position_zero_is_refused(self):
        with pytest.raises(proteingym.ReferenceMismatch, match="outside"):
            proteingym.check_variant_against_reference("A0G", REFERENCE)

    def test_a_non_standard_residue_is_refused(self):
        with pytest.raises(proteingym.ReferenceMismatch, match="single substitution"):
            proteingym.check_variant_against_reference("M1X", REFERENCE)

    def test_a_correct_variant_is_accepted(self):
        v = proteingym.check_variant_against_reference(f"{REFERENCE[0]}1A", REFERENCE)
        assert (v.position, v.wt_aa, v.mut_aa) == (1, REFERENCE[0], "A")


class TestMatching:
    def test_assays_on_different_references_are_not_comparable(self, tmp_path):
        other = REFERENCE[:-1] + ("W" if REFERENCE[-1] != "W" else "Y")
        a_archive = _write_archive(str(tmp_path), "TEST_ASSAY_f", _simple_rows())
        b_dir = os.path.join(str(tmp_path), "b")
        os.makedirs(b_dir, exist_ok=True)
        b_archive = _write_archive(b_dir, "TEST_ASSAY_g", _simple_rows(other))
        a = proteingym.load_assay(a_archive, "TEST_ASSAY_f")
        b = proteingym.load_assay(b_archive, "TEST_ASSAY_g")
        with pytest.raises(proteingym.ReferenceMismatch, match="not comparable"):
            proteingym.matched_variants(a, b)

    def test_matching_is_the_intersection_in_deterministic_order(self, tmp_path):
        rows_a = _simple_rows()
        rows_b = rows_a[:-3]
        a_archive = _write_archive(str(tmp_path), "TEST_ASSAY_h", rows_a)
        b_dir = os.path.join(str(tmp_path), "b2")
        os.makedirs(b_dir, exist_ok=True)
        b_archive = _write_archive(b_dir, "TEST_ASSAY_i", rows_b)
        a = proteingym.load_assay(a_archive, "TEST_ASSAY_h")
        b = proteingym.load_assay(b_archive, "TEST_ASSAY_i")
        matched = proteingym.matched_variants(a, b)
        assert matched == sorted(set(a.variants) & set(b.variants))
        assert len(matched) == len(rows_b)


class TestSubsetSelection:
    SALT = "delphi-frontier/kir21-esm2-assay-agreement/v1"

    def test_selection_is_deterministic(self):
        names = [f"A{i}G" for i in range(1, 400)]
        assert common.select_subset(names, self.SALT, 50) == common.select_subset(names, self.SALT, 50)

    def test_selection_ignores_input_order(self):
        names = [f"A{i}G" for i in range(1, 400)]
        assert common.select_subset(names, self.SALT, 50) == common.select_subset(list(reversed(names)), self.SALT, 50)

    def test_selection_cannot_depend_on_a_measured_value(self):
        """The rule takes only names, so no measurement can reach it.

        This is the no-leakage guarantee of PROTOCOL.md §6 expressed as a test:
        the selector's signature has nowhere to put a score.
        """
        import inspect

        params = set(inspect.signature(common.select_subset).parameters)
        assert params == {"matched", "salt", "size"}

    def test_a_different_salt_gives_a_different_subset(self):
        names = [f"A{i}G" for i in range(1, 400)]
        assert common.select_subset(names, self.SALT, 50) != common.select_subset(names, "other", 50)


class TestBaseline:
    def test_known_blosum62_values(self):
        assert blosum62("W", "W") == 11
        assert blosum62("A", "A") == 4
        assert blosum62("I", "V") == 3
        assert blosum62("G", "W") == -2

    def test_matrix_is_complete_and_symmetric(self):
        assert len(BLOSUM62) == 400
        for (a, b), v in BLOSUM62.items():
            assert BLOSUM62[(b, a)] == v

    def test_a_non_standard_residue_is_refused(self):
        with pytest.raises(ValueError, match="20 standard residues"):
            blosum62("A", "X")


class TestReceipts:
    def test_an_unknown_connector_state_is_refused(self):
        with pytest.raises(ValueError, match="unknown connector state"):
            RetrievalReceipt(source_id="s", url="u", state="validated-ish", retrieved_utc="now")

    def test_each_declared_state_is_accepted(self):
        for state in RetrievalReceipt.VALID_STATES:
            assert RetrievalReceipt(source_id="s", url="u", state=state, retrieved_utc="now").state == state


class TestUniProtComparison:
    def test_identical_sequences_report_identical(self):
        out = uniprot.compare(REFERENCE, REFERENCE)
        assert out["identical"] is True
        assert out["reference_sha256"] == sha256_text(REFERENCE)

    def test_a_single_substitution_is_located(self):
        other = REFERENCE[:4] + ("W" if REFERENCE[4] != "W" else "Y") + REFERENCE[5:]
        out = uniprot.compare(other, REFERENCE)
        assert out["identical"] is False
        assert out["n_substitutions"] == 1
        assert out["first_differences"][0]["position"] == 5

    def test_a_length_difference_is_reported_without_a_substitution_count(self):
        out = uniprot.compare(REFERENCE[:-2], REFERENCE)
        assert out["identical"] is False
        assert "n_substitutions" not in out


@pytest.fixture(scope="module")
def scorer():
    """A tiny ESM-2 for the guard tests; skips rather than passing silently."""
    torch = pytest.importorskip("torch")
    pytest.importorskip("transformers")
    from connectors.bioservices.esm2 import Esm2MaskedMarginalScorer, ScoringConfig

    cache = os.environ.get("BIOSERVICES_TEST_HF_CACHE")
    if not cache:
        pytest.skip("set BIOSERVICES_TEST_HF_CACHE to a cache holding esm2_t6_8M_UR50D")
    torch.set_num_threads(2)
    try:
        return Esm2MaskedMarginalScorer(
            REFERENCE, ScoringConfig("facebook/esm2_t6_8M_UR50D", threads=2, batch_positions=2),
            cache_dir=cache)
    except Exception as exc:  # pragma: no cover - environment-dependent
        pytest.skip(f"checkpoint unavailable: {exc}")


class TestScorerGuards:
    """The scorer needs a checkpoint, so these skip rather than silently pass."""

    def test_a_wild_type_substitution_scores_exactly_zero(self, scorer):
        wt = REFERENCE[3]
        v = proteingym.Variant(f"{wt}4{wt}", wt, 4, wt, float("nan"))
        assert scorer.score_many([v])[v.mutant] == 0.0

    def test_scoring_refuses_a_variant_that_disagrees_with_the_reference(self, scorer):
        wrong = "W" if REFERENCE[3] != "W" else "Y"
        v = proteingym.Variant(f"{wrong}4A", wrong, 4, "A", float("nan"))
        with pytest.raises(ValueError, match="not the declared"):
            scorer.score_many([v])

    def test_scoring_refuses_an_out_of_range_position(self, scorer):
        bad = len(REFERENCE) + 5
        v = proteingym.Variant(f"A{bad}G", "A", bad, "G", float("nan"))
        with pytest.raises(ValueError, match="outside"):
            scorer.score_many([v])

    def test_each_batched_row_carries_exactly_one_mask(self, scorer):
        """Batching must be 4 copies with 1 mask each, not 1 copy with 4 masks.

        An independent critique raised the second reading as a defect that would
        silently replace single-mask marginals with a joint multi-mask quantity.
        It would still produce plausible numbers, so it is checked here against
        the tensor the model is actually given rather than argued about.
        """
        captured = {}
        real = scorer.model

        class Spy:
            def __call__(self, input_ids=None, attention_mask=None, **kw):
                captured["input_ids"] = input_ids.clone()
                return real(input_ids=input_ids, attention_mask=attention_mask, **kw)

            def __getattr__(self, name):
                return getattr(real, name)

        scorer.model = Spy()
        try:
            wt = REFERENCE[7]
            scorer.score_many([proteingym.Variant(f"{wt}8A", wt, 8, "A", float("nan"))])
        finally:
            scorer.model = real

        ids = captured["input_ids"]
        mask_id = scorer.tokenizer.mask_token_id
        per_row = (ids == mask_id).sum(dim=1).tolist()
        assert per_row and all(n == 1 for n in per_row), f"masks per row were {per_row}, expected all 1"

    def test_one_forward_pass_serves_every_variant_at_a_position(self, scorer):
        wt = REFERENCE[5]
        before = scorer.forward_passes
        variants = [proteingym.Variant(f"{wt}6{m}", wt, 6, m, float("nan")) for m in "ACDG" if m != wt]
        scores = scorer.score_many(variants)
        assert len(scores) == len(variants)
        assert scorer.forward_passes - before <= 1


class TestAnalysisStatistics:
    """Positive controls on the statistics, using data whose answer is known.

    The evaluation's conclusion rests on these functions, so each is checked
    against a case where the right answer is fixed in advance -- and, for the
    difference tests, against a null case they must NOT call significant.
    """

    @staticmethod
    def _rng():
        import numpy as np

        return np.random.default_rng(12345)

    def test_spearman_matches_scipy_including_ties(self):
        np = pytest.importorskip("numpy")
        from scipy.stats import spearmanr

        from experiments.bioservices.kir21_esm2_assay_agreement import analyze

        rng = self._rng()
        a = rng.normal(size=200)
        b = 0.6 * a + rng.normal(size=200)
        assert analyze._spearman(a, b) == pytest.approx(spearmanr(a, b).statistic, abs=1e-10)
        # Heavy ties: rounding collapses many values onto the same rank.
        at, bt = np.round(a), np.round(b)
        assert analyze._spearman(at, bt) == pytest.approx(spearmanr(at, bt).statistic, abs=1e-10)

    def test_bootstrap_interval_brackets_a_known_difference(self):
        """pred is built to track `strong` better than `weak`; delta must be > 0."""
        pytest.importorskip("numpy")
        from experiments.bioservices.kir21_esm2_assay_agreement import analyze

        rng = self._rng()
        n = 400
        pred = rng.normal(size=n)
        strong = 0.9 * pred + 0.3 * rng.normal(size=n)
        weak = 0.2 * pred + 1.0 * rng.normal(size=n)
        bs, bf, bd, _ = analyze._paired_bootstrap(pred, strong, weak, 600, 0, 0.95)
        assert bs["bootstrap_mean"] > bf["bootstrap_mean"]
        assert bd["ci_low"] > 0, "a real difference must not produce an interval spanning zero"

    def test_bootstrap_interval_spans_zero_when_there_is_no_difference(self):
        """The null case. A test that only ever fires is not a test."""
        pytest.importorskip("numpy")
        from experiments.bioservices.kir21_esm2_assay_agreement import analyze

        rng = self._rng()
        n = 400
        pred = rng.normal(size=n)
        a = 0.5 * pred + rng.normal(size=n)
        b = 0.5 * pred + rng.normal(size=n)
        _, _, bd, _ = analyze._paired_bootstrap(pred, a, b, 600, 0, 0.95)
        assert bd["ci_low"] < 0 < bd["ci_high"]

    def test_williams_and_paired_permutation_agree_on_a_real_difference(self):
        pytest.importorskip("numpy")
        from experiments.bioservices.kir21_esm2_assay_agreement import analyze

        rng = self._rng()
        n = 400
        pred = rng.normal(size=n)
        strong = 0.9 * pred + 0.3 * rng.normal(size=n)
        weak = 0.2 * pred + 1.0 * rng.normal(size=n)
        delta = analyze._spearman(pred, strong) - analyze._spearman(pred, weak)
        w = analyze._williams_test(pred, strong, weak)
        p = analyze._paired_permutation_delta(pred, strong, weak, 600, 0, delta)
        assert w["applicable"] and w["p_two_sided"] < 0.01
        assert p["p_two_sided"] < 0.01

    def test_paired_permutation_does_not_fire_on_the_null(self):
        pytest.importorskip("numpy")
        from experiments.bioservices.kir21_esm2_assay_agreement import analyze

        rng = self._rng()
        n = 400
        pred = rng.normal(size=n)
        a = 0.5 * pred + rng.normal(size=n)
        b = 0.5 * pred + rng.normal(size=n)
        delta = analyze._spearman(pred, a) - analyze._spearman(pred, b)
        assert analyze._paired_permutation_delta(pred, a, b, 600, 0, delta)["p_two_sided"] > 0.05

    def test_clustering_widens_the_interval_under_full_intra_cluster_dependence(self):
        """With variants at a position perfectly dependent, effective n is the
        number of POSITIONS. A variant-level bootstrap then badly understates the
        variance of delta_rho and the clustered one must be wider.

        Measured caveat, kept because the first version of this test asserted the
        stronger claim and failed: clustering is **not** universally wider. With
        substantial independent within-position noise (0.3 and 0.9 on the two
        outcomes, 10 variants per position, seed 12345) the clustered interval
        came out *narrower* -- 0.143 against 0.171 -- because drawing whole
        clusters keeps the design balanced while variant-level resampling lets
        per-position counts vary and adds variance of its own. So the clustered
        interval is the APPROPRIATE one when clusters are dependent, not the
        automatically conservative one, and both are reported.
        """
        pytest.importorskip("numpy")
        import numpy as np

        from experiments.bioservices.kir21_esm2_assay_agreement import analyze

        rng = self._rng()
        n_pos, per_pos = 40, 10
        positions, pred, a, b = [], [], [], []
        for p in range(n_pos):
            x = rng.normal()
            ya = 0.8 * x + 0.3 * rng.normal()
            yb = 0.3 * x + 0.9 * rng.normal()
            for _ in range(per_pos):  # identical within a position: perfect dependence
                positions.append(p)
                pred.append(x)
                a.append(ya)
                b.append(yb)
        pred, a, b = np.array(pred), np.array(a), np.array(b)
        _, _, bd, _ = analyze._paired_bootstrap(pred, a, b, 400, 0, 0.95)
        cb = analyze._cluster_bootstrap(pred, a, b, positions, 400, 0, 0.95)
        assert cb["n_clusters"] == n_pos
        assert (cb["delta_ci_high"] - cb["delta_ci_low"]) > (bd["ci_high"] - bd["ci_low"])

    def test_the_verdict_rule_reads_the_interval_not_the_point(self):
        from experiments.bioservices.kir21_esm2_assay_agreement import analyze

        assert analyze._verdict({"ci_low": 0.1, "ci_high": 0.3})[0] == "supported"
        assert analyze._verdict({"ci_low": -0.3, "ci_high": -0.1})[0] == "falsified"
        assert analyze._verdict({"ci_low": -0.3, "ci_high": 0.0})[0] == "falsified"
        assert analyze._verdict({"ci_low": -0.05, "ci_high": 0.3})[0] == "undetermined"
