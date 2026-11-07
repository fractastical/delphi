/-
Axiom audit. `#print axioms` lists every axiom a theorem depends on. Mathlib proofs use only
Lean's three standard axioms (`propext`, `Classical.choice`, `Quot.sound`). A `sorry` would
show up here as `sorryAx`. `lean/report.mjs` runs this file and records the output.
-/
import Biolib.PopulationGenetics.Kimura
import Biolib.PopulationGenetics.Fisher
import Biolib.PopulationGenetics.MaynardSmith
import Biolib.PopulationGenetics.FavoredFixation
import Biolib.Meta.Blueprint
import Biolib.Allometry.CubeLaw
import BiolibAlpha.Morphogenesis.Turing
import BiolibAlpha.Morphogenesis.CellGeometry
import BiolibAlpha.Certificates.AFlyingFish
import Biolib.Meta.Constraints
/-!
## Biolib · Meta: anatomy graphs, constraint forms and informal results awaiting formalization

Origin: `lean/Delphi/Audit.lean` in fractastical/delphi_private at `ffdc528e4f95`, copied by
`biolib/scripts/sync-from-delphi.py`. Edit it there; this copy is regenerated.
Registry laws: none.
Lean-checked claims: none.
-/


#print axioms Delphi.NeutralChain.fixedBy_tendsto
#print axioms Delphi.NeutralChain.fixedBy_sub_le
#print axioms Delphi.wrightFisher_fixation_one
#print axioms Delphi.neutral_substitution_rate
#print axioms Delphi.neutral_substitution_rate_diploid
#print axioms Delphi.neutral_substitution_rate_tendsto
#print axioms Delphi.fisher_fundamental_theorem
#print axioms Delphi.fisher_fundamental_theorem'
#print axioms Delphi.mean_fitness_nondecreasing
#print axioms Delphi.twofold_cost_of_sex
#print axioms Delphi.twofold_cost_of_sex_n
#print axioms Delphi.FavoredChain.fixationProbability_ge
#print axioms Delphi.FavoredChain.fixationProbability_le_one
#print axioms Delphi.wrightFisherSelection_fixation_one_ge
#print axioms Delphi.neutral_expectedSubstitutions
#print axioms Delphi.favored_expectedSubstitutions_ge
#print axioms Delphi.expectedSubstitutions_le
#print axioms Delphi.wrightFisherSelection_substitutions_bounds
#print axioms Delphi.Blueprint.Graph.acyclic_of_levelsDown
#print axioms Delphi.Blueprint.Graph.transGen_trans
#print axioms Delphi.Blueprint.Graph.transGen_level_lt
#print axioms Delphi.Blueprint.Graph.rooted_of
#print axioms Delphi.Blueprint.wellFormed_of_check
#print axioms Delphi.Blueprint.Certificates.aFlyingFish_check
#print axioms Delphi.Blueprint.Certificates.aFlyingFish_wellFormed
#print axioms Delphi.Blueprint.Certificates.aFlyingFish_nodup
#print axioms Delphi.Blueprint.Certificates.aFlyingFish_counts
#print axioms Delphi.Blueprint.Certificates.aFlyingFish_size
#print axioms Delphi.cubeLaw_ratio
#print axioms Delphi.cubeLaw_loglog_exponent
#print axioms Delphi.not_cubeLaw_of_exponent_ne_three
#print axioms Delphi.CellGeometry.tripleJunction_120
#print axioms Delphi.CellGeometry.hexagon_of_120
#print axioms Delphi.CellGeometry.average_sides
#print axioms Delphi.CellGeometry.pentagons_eq_twelve
#print axioms Delphi.CellGeometry.beeCellArea_min
#print axioms Delphi.CellGeometry.beeCell_rhombus_angle
#print axioms Delphi.CellGeometry.tetrahedralJunction_angle
#print axioms Delphi.CellGeometry.hex_denser_than_square
#print axioms Delphi.Constraints.kimura_rate_rules_out
#print axioms Delphi.Constraints.neutral_fixation_rules_out
#print axioms Delphi.Constraints.favored_fixation_rules_out
#print axioms Delphi.Constraints.supply_rules_out
#print axioms Delphi.Constraints.supply_rules_out'
#print axioms Delphi.Constraints.fisher_rules_out
#print axioms Delphi.Constraints.fisher_decline_rules_out
#print axioms Delphi.Constraints.twofold_rules_out
#print axioms Delphi.Constraints.cubeLaw_rules_out
#print axioms Delphi.Constraints.cubeLaw_rules_out'
#print axioms Delphi.Constraints.exponent_rules_out
#print axioms Delphi.Constraints.kimura_rate_ratio_rules_out
#print axioms Delphi.Constraints.fisher_zero_variance_rules_out
#print axioms Delphi.Constraints.twofold_factor_rules_out
#print axioms Delphi.Turing.turing_instability_iff
#print axioms Delphi.Turing.no_instability_of_equal_diffusivity
#print axioms Delphi.Turing.witness
