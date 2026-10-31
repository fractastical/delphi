# Claim grounding

Links Project Delphi claims to the things they are about, as draft nanopublications, for
[#34](https://github.com/fractastical/delphi/issues/34).

`build/ground.py` reads each claim from the nanopublication network, sends its label, description
and quoted source text to [Gilda](https://grounding.indra.bio/) (the grounding service behind
INDRA), and keeps the matches from an allowed vocabulary (HGNC, UniProt, CHEBI, GO, UBERON, CL,
HP) with a score of at least 0.7. For every claim with at least one kept match it drafts a
nanopublication with the governed
[Project Delphi claim subject matter](https://w3id.org/np/RAUScXW9qrWeA-x8TUsvmHkqJJsHTHke8ev4eus4e61qQ)
template:

```turtle
<claim> schema:about <http://purl.obolibrary.org/obo/GO_0060361> .
<http://purl.obolibrary.org/obo/GO_0060361> rdfs:label "flight" .
```

Each entity gets its vocabulary's own IRI (OBO PURLs, UniProt IRIs; identifiers.org for HGNC,
which has none). The provenance names what made the link: the grounding agent, acting on behalf
of its operator, and the grounding activity, which used the claim's nanopublication and Gilda,
with this script at a pinned commit as its plan.

```
python3 claim-grounding/build/ground.py <claim-iri> [<claim-iri> ...]
```

| Path | Contents |
|---|---|
| `candidates/<claim>.json` | every match Gilda returned, kept or dropped, with score, matched text and reason, and a review block |
| `nanopubs/unsigned/<claim>.trig` | the unsigned draft, for review |

## Review before publishing

Nothing here is signed or published. Each draft is reviewed, by a person or by a second model,
against the claim it links, and the decision recorded in the `review` block of its candidates
file. A match on the words is not a match on the meaning: in `thompson1917-ch02-08`, Gilda links
"carbonic acid" to CHEBI:28976 (H₂CO₃), but in Thompson's 1917 usage the term means carbon
dioxide (CHEBI:16526).

## Limits

Gilda grounds molecular terms well and little else. Taxa and general concepts ground only to
MeSH, which is not an allowed vocabulary, so most claims from the historical texts get no link
yet. Lookups in EBI's Ontology Lookup Service (anatomy, processes, phenotypes) and the taxon IDs
in `organisms/` would cover them.
