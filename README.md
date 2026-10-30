# delphisci

This project was created for **Science Claw Hack @ MIT**.

## Goal

Our goal is to find the **fundamental theorems of biology**: the general laws that hold across organisms, scales, and systems, stated precisely enough to test.

To get there, we:

- extract candidate laws from the literature as claims, each traced back to its source papers and datasets;
- formalize them where possible, for example as Lean 4 theorems using the ontology's formal-verification terms;
- test them against real empirical data, and record the evidence and our assessments of it;
- publish each step as a nanopublication, so every candidate law, test, and assessment can be cited, queried, and challenged.

A machine-checked proof shows that a theorem follows from its stated assumptions. It does not show that living systems satisfy those assumptions, which is a question for evidence and experiment.

## Approach

This project builds on the Project Delphi ontology and uses [nanopublications](https://nanopub.net/) (nanopubs) as the format for publishing and querying small, citable, machine-readable scientific claims.

## Best practices

Before building, publishing, or querying nanopubs, read [BEST_PRACTICES.md](BEST_PRACTICES.md). It is adapted from the Project Delphi Ontology's publishing guide.

## Related projects

- **Project Delphi Ontology**: [fractastical/project-delphi-ontology](https://github.com/fractastical/project-delphi-ontology)
  - Open pull requests: [project-delphi-ontology/pulls](https://github.com/fractastical/project-delphi-ontology/pulls)

## Querying nanopubs

A nanopublication bundles a single assertion with its provenance and publication info as RDF named graphs. The following resources cover how to find and query them.

### Web interfaces

- [Nanodash](https://nanodash.knowledgepixels.com/): browse, search, and publish nanopubs in the browser.
- [Nanopub Query](https://query.knowledgepixels.com/): SPARQL endpoints over the nanopub network, including a full repository and per-type and per-pubkey repositories.

### SPARQL

You can send SPARQL queries to the Nanopub Query service. For example, this query lists recent nanopubs with their assertion graphs:

```sparql
PREFIX np: <http://www.nanopub.org/nschema#>
PREFIX dct: <http://purl.org/dc/terms/>

SELECT ?np ?assertion ?created WHERE {
  GRAPH ?head {
    ?np a np:Nanopublication ;
        np:hasAssertion ?assertion .
  }
  OPTIONAL { ?np dct:created ?created . }
}
ORDER BY DESC(?created)
LIMIT 20
```

See the [nanopub-query repository](https://github.com/knowledgepixels/nanopub-query) for available endpoints and usage details.

### Libraries and tooling

- [nanopub-py](https://github.com/fair-workflows/nanopub): Python library for searching, fetching, and publishing nanopubs.
- [nanopub-java](https://github.com/Nanopublication/nanopub-java): Java library and CLI.
- [Nanopub registry](https://github.com/knowledgepixels/nanopub-registry): the decentralized registry that stores and serves nanopubs.

### Background

- [nanopub.net](https://nanopub.net/): overview of the nanopublication model and ecosystem.
- [Nanopublication guidelines](https://nanopub.net/guidelines/working_draft/): the formal specification.
