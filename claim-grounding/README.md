# Claim grounding

Links Project Delphi claims to the things they are about, as draft nanopublications, for
[#34](https://github.com/fractastical/delphi/issues/34).

`build/ground.py` reads claims from the nanopublication network, or from a project's unsigned
nanopublication files in this repository (`--local`, through the delphisci CLI's local store, so
`npm ci` must have run). It grounds each claim's label, description, context and quoted source
text in two ways:

- [Gilda](https://grounding.indra.bio/) (the grounding service behind INDRA), strong on genes,
  proteins and chemicals;
- exact label or synonym lookups of one- to three-word phrases in GO, UBERON, CL and NCBITaxon
  through EBI's [Ontology Lookup Service](https://www.ebi.ac.uk/ols4/), which adds anatomy,
  processes and taxa.

For every claim with at least one kept match it drafts a nanopublication with the governed
[Project Delphi claim subject matter](https://w3id.org/np/RAUScXW9qrWeA-x8TUsvmHkqJJsHTHke8ev4eus4e61qQ)
template:

```turtle
<claim> schema:about <http://purl.obolibrary.org/obo/GO_0060361> .
<http://purl.obolibrary.org/obo/GO_0060361> rdfs:label "flight" .
```

Each entity gets its vocabulary's own IRI (OBO PURLs, UniProt IRIs; identifiers.org for HGNC,
which has none). The provenance names what made the link: the grounding agent, acting on behalf
of its operator, and the grounding activity, which used the claim's nanopublication, Gilda and
OLS, with this script at a pinned commit as its plan. A local claim's provenance cites the signed
copy of its nanopublication where the project has one.

```
python3 claim-grounding/build/ground.py <claim-iri> [<claim-iri> ...]
python3 claim-grounding/build/ground.py --local claim-sources/math-bio-claims
```

| Path | Contents |
|---|---|
| `candidates/<claim>.json` | every match found, kept or dropped, with score, source, matched text and reason, and a review block |
| `nanopubs/unsigned/<claim>.trig` | the unsigned draft, for review |

## What is kept

A term becomes a link if any of its mentions passes all of these:

- its vocabulary is allowed (HGNC, UniProt, CHEBI, GO, UBERON, CL, HP, NCBITaxon) and the match
  scores at least 0.7 (OLS: 1.0 for a label, 0.9 for a synonym);
- a gene or protein is matched on text written as a symbol (`KIT`, not `kit`);
- it is not a top-level chemical class (*chemical substance*, *mixture*, …), nor under the CHEBI
  *role* branch or the HPO clinical-modifier or frequency branches;
- an OLS synonym belongs to one term only, and is not capitalized in the text (*Fisher* the
  statistician is not *the fisher*, a mammal);
- a one-word OLS synonym is the common name of a taxon (*cattle*, *insects*), not a GO, UBERON or
  CL term;
- an NCBITaxon label is written as the scientific name (*Python*, not *python*).

## Review before publishing

Nothing here is signed or published. Each draft is reviewed, by a person or by a second model,
against the claim it links, and the decision recorded in the `review` block of its candidates
file. The rules remove most wrong matches but not those that hinge on meaning, which in the first
full run were about a third of the 34 links:

- a word in another sense: *membrane* of a bat wing linked to the cell membrane, *scale* as in
  size linked to the fish scale, the verb *bears* linked to Ursidae, image *segmentation*;
- a mention that negates or merely names: *without growth*, the book title *On Growth and Form*;
- a historical sense: in Thompson's 1917 usage *carbonic acid* means carbon dioxide
  (CHEBI:16526), not CHEBI:28976.
