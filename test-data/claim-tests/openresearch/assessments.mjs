#!/usr/bin/env node
// Hand-written literature assessments for the OpenResearch runs (issue #16). Every identifier cited below is one that
// `orx discover` returned in the corresponding openresearch.json; the script refuses to write a citation it cannot
// find in that file's runs. Written 2026-10-31 by the claims thread after reading the returned titles and abstracts.
//   node claim-tests/openresearch/assessments.mjs
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { QUERIES } from './run.mjs';

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, '../..');

const A = {
  'kimura-heterozygosity': {
    status: 'done',
    what_the_literature_says: 'The weak scaling of nucleotide diversity with census population size is a named, long-studied problem (Lewontin\'s paradox). Corbett-Detig et al. 2015 test linked selection as its cause across 40 sexual eukaryotes and find the impact of selection on neutral diversity rises with census size; Charlesworth and Jensen 2022 review the candidate forces (direct selection, hitchhiking, population size change) and argue no single one suffices; a 2024 preprint reports that reference-free diversity metrics scale faster with population size proxies in 112 plant species, so part of the paradox may be measurement.',
    already_answered_by_prior_work: true,
    citation: ['10.1371/journal.pbio.1002112', '10.1093/gbe/evac096', '10.1101/2024.05.17.594778'],
    implication_for_this_test: 'The pattern this test refutes (diversity tracking census size with slope near 1) is already established as absent; the test is a reproduction on Buffalo\'s compiled table and should be cited as such, not presented as new. What remains open in the literature is the cause, which the test does not address.',
  },
  'thompson1917-ch03-07': {
    status: 'done',
    what_the_literature_says: 'Two different exponents exist in the literature and must not be confused. Within an age or in adults, weight scales roughly as height squared (Quetelet\'s rule, the basis of BMI: Heymsfield et al. 2024 overview; Heymsfield et al. 2007 on body composition scaling; adult weight-height scaling 2014). Across childhood growth, Kato and Yamashita 2024 fit weight-for-height centile curves in children and adolescents as power laws and show the exponent changes with age ("allometric multi-scaling"), which is the quantity Thompson\'s claim concerns. No returned paper reports a single across-growth exponent for ages 2 to 19 on NHANES means.',
    already_answered_by_prior_work: 'partly',
    citation: ['10.1371/journal.pone.0307238', '10.1111/obr.13842', '10.1093/ajcn/86.1.82', '10.3945/ajcn.114.088831'],
    implication_for_this_test: 'The test measures the across-growth exponent, not the within-age one, and the literature confirms the exponent depends on the age window, which is exactly why the two-swarm cross-check found 2.74 for ages 2-19 and 2.41 when infancy is included. The record should cite the 2024 multi-scaling paper and state which exponent it tests.',
  },
  'maynardsmith-hitchhiking': {
    status: 'done',
    what_the_literature_says: 'A positive association between recombination rate and nucleotide diversity in humans is established: Nachman 1998 at X-linked loci, Nachman 2002 with gene density, Spencer et al. 2006 across an entire chromosome with fine-scale maps. The open question is attribution: Cai et al. 2009 argue for pervasive hitchhiking in humans, Innan and Stephan 2003 show how to distinguish hitchhiking from background selection, and Comeron 2014 treats background selection as the baseline in Drosophila. Braverman et al. 1995 give the hitchhiking effect on the site frequency spectrum.',
    already_answered_by_prior_work: true,
    citation: ['10.1371/journal.pgen.0020148', '10.1093/oxfordjournals.molbev.a004086', '10.1093/genetics/150.3.1133', '10.1371/journal.pgen.1000336', '10.1093/genetics/165.4.2307', '10.1371/journal.pgen.1004434'],
    implication_for_this_test: 'The correlation the test finds on chromosome 22 is a reproduction of a settled result and should be cited as such; the test\'s own caveat that it cannot separate sweeps from background selection matches where the literature stands. A new experiment would only be warranted for the attribution question, which needs site-frequency or sweep-scan methods, not a correlation.',
  },
  'darwin1859-ch09-03': {
    status: 'done',
    what_the_literature_says: 'The age of the end of the Cretaceous is a settled measurement: the returned geochronology and Cretaceous-Paleogene boundary literature (Hull et al. 2020; Berggren et al. 1988) works with a boundary at about 66 Ma, the same figure the ICS chart gives and the test used. The query on Darwin\'s Weald denudation estimate itself returned only the Origin of Species and unrelated nineteenth-century books, so this search found no modern paper on the history of that calculation; the test\'s note that Darwin withdrew it after Phillips\'s criticism is not supported by a citation from this run.',
    already_answered_by_prior_work: true,
    citation: ['10.1126/science.aay5055', '10.1029/pa003i006p00707', '10.5962/bhl.title.68064'],
    implication_for_this_test: 'This is a comparison against a settled number, not an experiment; the record is a citation-level refutation. A history-of-science citation for the Phillips episode is still wanted and was not found by this search.',
  },
  'thompson1917-ch04-13': {
    status: 'done',
    what_the_literature_says: 'Chromosome number distributions are compiled and analysed: the Chromosome Counts Database (Rice et al. 2015) is the plant compilation the test used; Roman-Palacios et al. 2021 compile animal counts and report a similar range of chromosome numbers to plants but less polyploidy in animals; reviews of polyploidy (Alix et al. 2017; Van de Peer et al. 2022 in Annals of Botany) and the ancestral angiosperm chromosome number (Carta et al. 2020) establish that polyploidy, unknown to Thompson, puts a large share of plant species above his range.',
    already_answered_by_prior_work: true,
    citation: ['10.1111/nph.13191', '10.1111/jeb.13884', '10.1093/aob/mcx079', '10.1093/aob/mcac132', '10.1111/nph.16668'],
    implication_for_this_test: 'The plant refutation is a fact that can be read off the existing compilation; the untested animal half of Thompson\'s claim is addressed by the 2021 animal compilation and needs that dataset rather than a new experiment.',
  },
  'darwin1859-ch11-13': {
    status: 'done',
    what_the_literature_says: 'Repeated long glacial cycles registered in the global benthic oxygen-isotope stack and in Antarctic ice are textbook: the LR04 stack data (returned as its PANGAEA appendix), the AICC2012 Antarctic ice core chronology, the Mid-Pleistocene Transition review (Berends et al. 2021), Pleistocene sea-surface temperature evolution (McClymont et al. 2013), Heinrich events (Hemming 2004) and sub-orbital Asian monsoon and Antarctic coupling (2016) all describe glacial states lasting tens of thousands of years with signals in both hemispheres.',
    already_answered_by_prior_work: true,
    citation: ['10.1594/pangaea.701576', '10.5194/cp-9-1733-2013', '10.1029/2020rg000727', '10.1016/j.earscirev.2013.04.006', '10.1029/2003rg000128', '10.1038/srep32995'],
    implication_for_this_test: 'The supported verdict confirms a settled picture; where the literature departs from Darwin is that there were dozens of cycles, not one long Glacial period, which the test already records as a reading of the claim. No new experiment is needed; the record should cite the chronology papers.',
  },
};

for (const [claim_id, a] of Object.entries(A)) {
  const f = path.join(root, 'claim-tests', QUERIES[claim_id].dir, 'openresearch.json');
  const j = JSON.parse(fs.readFileSync(f, 'utf8'));
  const returned = new Set(j.runs.flatMap(r => r.results.map(x => String(x.id))));
  for (const c of a.citation) if (!returned.has(c)) throw new Error(`${claim_id}: citation ${c} was not returned by any run; refusing to write it`);
  j.assessment = { ...a, written_by: 'claims thread (Claude Fable 5.1), from the returned records only', date: '2026-10-31' };
  fs.writeFileSync(f, JSON.stringify(j, null, 1) + '\n');
  console.log(`${claim_id}: assessment written (${a.citation.length} citations, all returned by the runs)`);
}
