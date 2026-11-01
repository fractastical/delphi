# The three reported browser-test failures, compared on root 506f97a

| Test (as I had reported it) | On 506f97a before | Cause | Result |
|---|---|---|---|
| `test_home_offers_the_v3_display_props_with_hash_exact_stl_downloads` | no longer exists | root 92abf15 replaced it with `test_home_offers_print_revisions_with_hash_exact_stl_downloads` | replacement passes; nothing to fix |
| `test_recovery_inputs_are_published_exactly_and_the_failed_run_is_not_called_complete` | FAILED | stale assertions: root 89726ac now publishes a separate evaluation of the retained checkpoint (diffusion pilot, strict secondary audit failed), so "no evaluation and no generated examples exist" is retired page text | page is correct; assertions updated to the current text and still require "primary run: failed", "The primary timeout remains a failure", "strict secondary audit failed", "not evaluated performance or validated biology", and that the retired sentence is absent |
| `test_stale_sentences_are_gone_and_cost_cites_the_dated_google_receipt` | FAILED | stale assertions: the Cost counter now cites the dated Google Cloud allocation snapshot (reservations, not usage) instead of the older "dated readiness receipt" wording | assertions updated: still no "terms-of-service", the dated snapshot is cited, "No dollar estimate or zero spend inferred from credits", "spend remains unknown" |

No genuine product regression was found: both failing pages say the right thing; only the tests lagged. The builder is current (`scripts/build_site.py --check` -> stale: []).
Focused check (this worktree, base 506f97a): the two updated tests plus the print-revisions test pass. The full suite was not run.
