# Zebrafish regulatory metadata coverage audit

Completed October 31, 2026, PDT. This is an executed **metadata audit**, not a
sequencing reanalysis, inference run or independent biological replication.
Protocol was committed at `dde2ea8` before retrieval; collector source was
committed at `ac487b0`. No site files, model services or provider-stopped work
were touched.

Checklist:

- [x] Freeze target accessions, metadata-only scope, resource/byte bounds and stops.
- [x] Retrieve and validate exact series/sample identities; pin raw response bytes.
- [x] Extract literal reference, assay, condition, time and replicate information.
- [x] Preserve ambiguous identities and unfetched files as explicit gaps.
- [x] Check response/artifact hashes, collector code pin and focused parser tests.
- [ ] Resolve cell barcodes, biological donor independence or assay pairing.
- [ ] Download processed sequencing matrices, cell annotations or raw reads.

## What was retrieved

128 successful public GEO text-export responses: six series and **122 unique GSM
records**. All requested SOFT headers and accession fields matched; no request
failed. The series are the three targets plus GSE126703's explicitly listed
children GSE126700/701/702. Root/child sample overlap was deduplicated; GSM count
does not equal independent biological replicate count.

| Target | Sample records and declared assays | Literal reference metadata | Important limits |
| --- | --- | --- | --- |
| [GSE261907](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE261907) | 20: 10 RNA-Seq, 10 ATAC-seq; caudal fin, 0/1/2/4/6 days after amputation | Sample processing says danRer11, Ensembl release104; series design says GRCz11. | Titles have rep1/rep2; no sample characteristic explicitly names a replicate. Series describes two biological replicates/time. RNA/ATAC barcode pairing and biological source identities remain unchecked; do not count20 independent replicates. |
| [GSE126703](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE126703) | 44: 8 ATAC-seq, 20 RNA-Seq, 16 Bisulfite-Seq; sorted sp7+/sp7− cells, fin/blastema and genotype conditions | GRCz10; RNA processing specifies Ensembl release85. | Includes fosl1a KO/WT comparisons; not one uniform baseline cohort. Some time-like values appear under `passages`. Assays/stages/conditions need stratification; no direct coordinate join to newer assemblies. |
| [GSE223922](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE223922) | 58 RNA-Seq; whole animal, single and multiplexed developmental-stage labels | GRCz11 release99 wording; Lawson Lab annotation4.3.2. | Explicit biological-replicate labels1/2/3 are metadata, not verified donor independence. Several records list multiple hpf stages. Per-cell stage/hash mapping and fin subtype coverage remain uninspected. |

Metadata list **84 unique supplementary-file URLs**, including processed signal,
count, archive and annotation references. All remain unfetched: bytes and hashes
are null. GSE223922 lists a separate `Sur2023_metadata.tsv.gz` alongside its
matrix and row/column files; this audit did not retrieve even that annotation
file. A listed resource is not verified availability or content.

The first extraction, `run/coverage.json`, counts only explicitly named time/age
and replicate characteristic fields. A separate read-only second pass,
`run/coverage-reviewed.json`, exposes literal time-unit strings and title
replicate labels, including `passages: 0 dpa`. Both outputs are retained; the
second does not relabel “passages,” infer donors or overwrite the first. All122
samples have some time and replicate literal in a characteristic or title;
**confirmed independent biological sample count remains unknown**.

## Stop points and next questions

Downstream cell-specific or replicate-pooled analysis stops here. Exact accession
identities are resolved; biological independence, cell labels and cross-assembly
compatibility are not.

1. Can source sample tables establish which RNA/ATAC libraries share the same
   tissue collection and barcodes, without treating paired modalities as new
   replicates? Preserve this dependence explicitly.
2. Which exact processed annotation files map each cell to sample, stage and
   cell type? A separately admitted metadata/annotation-only retrieval could
   inspect small files after a size/checksum gate; no sequencing matrix is
   authorized by this completed action.
3. Which GSE126703 genotype/assay/stage strata are genuinely comparable to the
   proposed contrast? Keep fosl1a KO/WT conditions separate from baseline and
   do not normalize ambiguous `passages` fields without source confirmation.
4. What exact gene/coordinate mapping and validation would support a GRCz10 to
   GRCz11 comparison? Assembly-name similarity and different annotation versions
   do not justify a direct peak–gene join. Adult caudal regeneration also remains
   separate from embryonic pectoral development or flying-fish transfer.

## Resource and provenance receipt

The collection ran locally under a systemd scope capped at one CPU, 2GiB RAM,
zero swap and128 tasks; numeric-library threads were set to one. Actual collector
receipt: **27.555s wall**, **0.446s process CPU**, **555,892KiB RUSAGE_SELF maximum
RSS**, **1,157,708 response bytes**. RSS is the process-reported high-water mark,
not a measured whole-host or cloud utilization statistic. No GPU/cloud job was
launched. Dollar cost is unknown (`null`), not estimated as zero.

`run/receipt.json` pins protocol, source commit/hash, Python/httpx versions,
request URL/time/status and every raw response SHA256/size. Raw responses are
under `run/raw/`. The reviewed coverage pins the original receipt and extraction
hashes separately. `artifact-manifest.json` covers the durable output files.
Four focused fixture tests passed in0.17s; Ruff and authored-code whitespace checks
passed. Raw responses retain upstream CRLF and trailing whitespace for exact
checksum preservation; local attributes disable text conversion/style checks
only for those source bytes.
Metadata retrieval and integrity checks do not independently validate the
authors' biological observations.
