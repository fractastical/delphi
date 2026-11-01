# turing-capable-network-topologies--grok-4-7--3

Outcome: completed computation; the open classification problem remains unsettled.

No n=3 census was present in `problems/approaches/*.json` outputs or
`test-data/claim-tests`, so this run implemented the required same-method baseline first.
The baseline exhausts all 3^9 = 19,683 sign patterns and all seven non-empty diffusion
supports, but samples the continuous parameters and therefore is not an exact census.

Pre-registered seed: 470003.
Nonzero reaction rates and positive diffusion coefficients: log-uniform [0.01, 100].
Wave-number sweep: 121 log-spaced k values on [0.001, 1000].
Capability test: J is strictly Hurwitz by Routh-Hurwitz, while J-k²D is non-Hurwitz
for at least one tested k > 0.

n=3 baseline (200 draws per pattern/support):
- 3,782/19,683 patterns detected capable (0.192146).
- 3,782/19,574 cyclic patterns detected capable (0.193215).

n=4 pre-registered sample (2,000 distinct cyclic patterns, 100 draws each):
- 392/2,000 detected capable (0.196).
- Exact two-sided Clopper-Pearson 95% interval: [0.178808, 0.214088].
- The interval is entirely below 0.9, so the operational claim is refuted.

This sample can refute the fixed detection-rate claim but cannot prove “almost all.”
Because finite parameter search can miss existential witnesses, it does not rigorously
refute the underlying mathematical capability conjecture or solve the classification.
