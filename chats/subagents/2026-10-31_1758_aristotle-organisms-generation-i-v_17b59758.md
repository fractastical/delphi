# Subagent: Aristotle organisms: Generation I–V

- **Parent chat:** [are we in a position (primarily using our own tests or other hard data tests) ho](../2026-10-31_1543_are-we-in-a-position-primarily-using-our-own-tests-or-other-.md)
- **Started:** 2026-10-31 17:58 EDT (UTC-4) through 2026-11-01 02:00, then EST (UTC-5)
- **Last activity:** 2026-10-31 19:22 EDT (UTC-4) through 2026-11-01 02:00, then EST (UTC-5)
- **Final status:** error
- **Transcript ID:** `17b59758-45a7-434b-acc3-380f05282c76`

---

### 2026-10-31 17:58 — Turn 1 (User)

> You are building organism reference records for the delphisci repository at /Users/jdietz/Documents/GitHub/dev/delphisci.
> 
> Read test-data/organisms/README.md fully and follow its rules exactly (animals only, real identifiers via the GBIF/NCBI/Wikidata APIs, only real datasets with checksums, no scoring, no files over 1 MB). Look at one existing slice (e.g. test-data/organisms/darwin-origin/ch05-06/) for the record shapes.
> 
> Your slice: project `aristotle-biology`, slice `ha01-04` = Aristotle's History of Animals Books I–IV, text claim-sources/aristotle-biology/inputs/ha.txt lines 6–659. Claims for this slice are the entries in claim-sources/aristotle-biology/claims.json whose id starts with aristotle-ha01- to aristotle-ha04- (read that file for claim ids and quotes; use claim_id sources for mentions inside claims, file/line sources for other mentions).
> 
> Write only under test-data/organisms/aristotle-biology/ha01-04/ (mentions.json, taxa/, datasets/, REPORT.md). Do not touch any other path, do not run state-changing git commands, never sign or publish. Aristotle's names are Greek kinds in a 1910 translation; map them via the translator's identifications where standard and note uncertainty. Prioritise taxa named in claims; for book-text-only mentions, cover the clearly identifiable ones. Per taxon, record at least a GBIF occurrence-count distribution; add genome assemblies (NCBI Datasets) and trait databases (AnAge, PanTHERIA, AVONET, FishBase etc.) where they apply.
> 
> When done, run `node test-data/organisms/validate.mjs aristotle-biology/ha01-04` and fix all errors. Report: counts of mentions, taxa, datasets, unresolved names, and validation result.

**Assistant:**

I should start by reading the README and looking at an existing slice to understand the structure.

Let me check the other datasets besides gbif-occ, along with a genome record and an anage record, by looking at the tail of the output.

I should check if there's a leftover build script in other slices or test-data directories, maybe under test-data/organisms, and see if any other aristotle slices or local AnAge caches exist that could help.

That's a lot of claims to process. I should check an existing script set for reuse and figure out where to put helper scripts, probably outside the repo in a temp location since I'm restricted to writing only within my slice.

I'll write my own pipeline script in /tmp instead, borrowing ideas from these. First I need to check the size of ha.txt lines 6–659 since those are likely long paragraph-per-line entries.

I should let that background find finish and kill it later, and use Python's urllib for fetching. With 266 KB of text to scan, reading it all for animal names would cost a lot of tokens, so instead I'm thinking of building a vocabulary list of known animal vernacular names and grepping the text against it for efficiency.

With 4176 words to handle, I'm deciding to just print them all out rather than trying to filter against a dictionary file, since the output size would still be manageable.

Now I'm compiling the full taxa list, drawing on D'Arcy Thompson's identifications to map names like "man," "woman," and "human" to Homo sapiens as a starting point.

I'm cataloging equids and ungulates next—horse to Equus caballus, ass to Equus asinus, mule as a hybrid noted under genus Equus, wild ass to Equus hemionus, and cattle terms (kine, ox, cow, bull, oxen) to Bos taurus, with bison and aurochs flagged for separate species checks, plus swine terms mapping to Sus scrofa. Given how frequently words like "man" appear, I'm deciding to cap text mentions per taxon at around five and note this limitation in the report rather than listing every occurrence exhaustively.

Continuing through the species list, I'm mapping sheep terms to Ovis aries, goat to Capra hircus, dog and hound to Canis familiaris, wolf to Canis lupus, fox to Vulpes vulpes, and the big cats—lion to Panthera leo, leopard to Panthera pardus, lynx to Lynx lynx—along with bear to Ursus arctos. For trickier cases like marten and weasel I'm leaning toward genus-level mappings (Martes, Mustela) given uncertainty, while hedgehog goes to Erinaceus europaeus, porcupine to Hystrix cristata, and hare to Lepus europaeus.

Mouse resolves straightforwardly to Mus musculus, but the mole is trickier—Aristotle's blind "aspalax" could refer to either the mole-rat Spalax or true moles like Talpa caeca, since Talpa europaea doesn't actually occur in Greece, so I need to flag this identification as uncertain rather than commit to one species.

I'll settle on Spalacidae with a note on the Nannospalax leucodon ambiguity, then move through more animals: bat as Chiroptera, seal as Monachus monachus (Mediterranean monk seal), dolphin as Delphinus delphis, and porpoise as Phocoena phocoena.

For the baleen whale mapped from "phalaina," I'll go with Cetacea broadly since GBIF lacks a clean infraorder match, while the "mousewhale" (Thompson's term for a baleen whale) I'll assign to Mysticeti specifically. General "cetaceans" references map to Cetacea, and camel resolves cleanly to Camelus.

Bactrian camel becomes Camelus bactrianus and Arabian camel Camelus dromedarius, with generic camel milk references just using the genus Camelus. Elephant I'm mapping to Elephas maximus since Aristotle's knowledge came from Indian elephants, deer/stag/hart to Cervus elaphus, and roe to Capreolus capreolus — noting that "roe" is ambiguous since it also means fish eggs.

For antelope-type animals, gazelle maps to Gazella (Aristotle's dorkas), oryx stays as Oryx genus for the single-horned animal, and the hippelaphus ("horse-stag") is trickier since commentators debate whether it's the nilgai (Boselaphus tragocamelus) or the sambar deer — I'm leaning toward leaving it unresolved or tentatively using Boselaphus tragocamelus.

Continuing through the rest, hippopotamus clearly maps to Hippopotamus amphibius, while the primates are trickier: ape (pithekos) likely refers to the Barbary macaque, monkey (kebos) to Cercopithecidae generally, and baboon (cynocephalus) to Papio. Beaver goes to Castor fiber, otter to Lutra lutra, and I'm noting the manticore as a mythical creature that can't be mapped to a real species, along with starting to think through how to classify the jennet (a horse-ass hybrid).

I'm working through several more uncertain cases — the "Indian ass" might actually be a rhinoceros misidentified as a unicorn, and "aegocephalus" seems to be some gall-bladderless bird I can't pin down, so both stay unresolved. The dasypod/lagos terms both point to hare (Lepus europaeus), cats map straightforwardly to Felis catus, bison to Bison bonasus, and now I'm moving into reptiles and amphibians, starting with the river crocodile as Crocodylus niloticus.

For lizards I'm using Lacertidae as a generic placeholder since "saura" and "saurians" are too vague to pin to species. Tortoises go to Testudo, sea turtles to the loggerhead Caretta caretta, chameleons to Chamaeleo chamaeleon, and geckos to Gekkonidae broadly since Thompson's "askalabotes" could mean either Hemidactylus or Tarentola. I'm now moving into snakes, starting broad with Serpentes before trying to narrow down specific species.

Vipers map cleanly to Vipera ammodytes given the Greek context, and I'm treating water-snakes as Natrix generically. The sea-serpent is trickier — it might actually refer to a moray or snake-eel like Ophisurus serpens rather than a true serpent, so I'm leaving that one unresolved. For frogs, I'm defaulting to Anura generally, but trying to work out whether "bull-frog" should map specifically to Pelophylax ridibundus based on Thompson's description of the male's croak.

For toads I'm settling on Bufo bufo, and for newts I'm considering Salamandridae broadly since Aristotle's "kordylos" likely refers to Triturus or similar. The "fishing-frog" is actually a fish — Lophius piscatorius, the angler fish — which fits since "batrachos" was used for it.

Moving into birds now, I'm mapping eagle to Aquila and working through hawk and kestrel, trying to decide whether "hierax" should correspond to Accipiter broadly or something more specific like Falco tinnunculus for kestrel.

Continuing through the bird list, I'm assigning falcon to Falco, kite to Milvus milvus, owl to Strigiformes generally, and flagging "night-raven" (nyktikorax) as ambiguous between an owl species and the night heron. I'm settling raven as Corvus corax, treating crow and carrion-crow together under Corvus cornix with a note on the overlap, daw as Coloeus monedula, cuckoo as Cuculus canorus, swallow as Hirundo rustica, and swift as Apus apus since the Greek term directly parallels the modern genus name.

From there I'm working through sparrow (Passer domesticus), chaffinch (Fringilla coelebs), nightingale (Luscinia megarhynchos), partridge (Alectoris graeca based on Thompson's identification), quail (Coturnix coturnix), and the domestic fowl group (Gallus gallus). I'm also noting peacock as Pavo cristatus and pigeon-family terms — pigeon, ring-dove, and cushat all pointing to Columba species, with cushat specifically matching wood pigeon.

Continuing, I'm mapping duck to Anas platyrhynchos, goose to Anser anser, swan to Cygnus olor, crane to Grus grus, and gull to the Laridae family. For grebe I'm leaning toward Aristotle's kolymbis matching the little grebe, Tachybaptus ruficollis, while diver needs more context to pin down. I'm also placing bustard as Otis tarda and hoopoe as Upupa epops.

Moving further, woodpecker fits Picidae and wryneck matches Jynx torquilla, but catarrhactes remains ambiguous between a gannet or tern. Porphyrio clearly corresponds to the purple swamphen, though balagrus and glaucus seem to be fish names I can't resolve yet, and I still need to work out what snipes and melancoryphus refer to in context.

Now I'm trying to pin down "sea-swallow" — it could mean the flying gurnard or a flying fish like Exocoetus, depending on how Thompson translates it. I'm also checking whether ostrich or ibis appear anywhere in this list, then shifting to fish classifications, where I'm working out that galeos likely refers to dogfish within the broader shark group, Selachii.

Continuing with eel → Anguilla anguilla, conger → Conger conger, muraena → Muraena helena, fishing-frog → Lophius piscatorius, tunny → Thunnus thynnus, bonito → Sarda sarda, pelamys → young Thunnus thynnus, mullet/cestreus → Mugilidae, carp → Cyprinus carpio, and now working through glanis/sheatfish.

I'm identifying glanis as Silurus aristotelis given the Achelous river reference, scarus as the parrotfish Sparisoma cretense, and psetta as likely turbot or brill (Scophthalmus), while channe maps to the comber Serranus cabrilla and I'm still working out erythrinus.

Erythrinus seems to match Pagellus erythrinus, and I'm noting Serranus's hermaphroditism fits the claim about fish always found with eggs. For psetta, I'm settling on Scophthalmus maximus given its synonym Psetta maxima, and I'm mapping the cuckoo-fish term to gurnards in the Triglidae family.

Continuing down the list: goby to Gobiidae, wrasse to Labridae, perch to Perca fluviatilis, basse to Dicentrarchus labrax, sciaena to Sciaena umbra. Chromis is trickier though — Thompson's Glossary suggests it could be Umbrina cirrosa or another sciaenid rather than the modern Chromis chromis, so I'm leaning toward classifying it within Sciaenidae given the genuine uncertainty here.

Gilt-head maps cleanly to Sparus aurata, but sparus itself and synagris remain ambiguous, possibly Diplodus annularis or a Pagellus/Dentex species respectively — I'll leave those unresolved rather than force a match. Scorpion fish goes to Scorpaena scrofa, callionymus fits Uranoscopus scaber given Aristotle's description of its large gall bladder, citharus matches Citharus linguatula, cottus is Cottus gobio, and dorado points to Coryphaena hippurus, while elops remains uncertain — possibly a sturgeon.

Echeneis likely corresponds to Echeneis naucrates or the Mediterranean Remora remora within family Echeneidae, though hepatus stays unresolved (perhaps Lichia or Serranus), and phycis isn't addressed here. Saupe is Sarpa salpa, sword-fish is clearly Xiphias gladius, and angel-fish is Squatina squatina. The boar-fish reference is trickier — it could tie to Capros aper or Aristotle's river kapros of the Achelous, but I'm leaving that as an open note, along with pipe-fish pointing to Syngnathidae and ribbon-fish still needing identification.

Continuing down the list, ribbon-fish matches Cepola macrophthalma, flying-fish aligns with Exocoetidae, and I need to verify whether sea-swallow refers to Dactylopterus volitans. Trygon is the sting-ray and the shark entry is straightforward, but sea-scolopendras likely points to a polychaete worm like Eunice rather than a true fish. Rhine seems to be another name for the angel shark, so I'm folding that into the Squatina squatina entry alongside batos as skate, while thoon and a few other terms remain unidentified for now.

Moving further, I'm linking cestreus to the mullet family Mugilidae, tettix and its relatives to cicadas (Cicadidae), achetes to the male cicada, and dayfly to mayflies (Ephemeroptera). Cantharis likely refers to a beetle, possibly a blister beetle in Meloidae, though the exact species depends on context. The carabus entry is the interesting one -- Thompson translates Aristotle's karabos as "crawfish," which actually refers to the spiny lobster Palinurus elephas, distinct from the true lobster.

Continuing through crustaceans, astakos corresponds to Homarus gammarus, while crayfish maps to the river crawfish genus Astacus. For carid, crangon, and the shrimps/prawns, I'm sorting these into Caridea generally, with crangon likely being Crangon crangon and squilla possibly referring to the mantis shrimp Squilla mantis, since both genus names trace back to Aristotle's terminology. Maia clearly corresponds to the spider crab Maja squinado, though cyllarus remains uncertain, and heracleotis seems to reference the so-called "Heracleotic crab."

Pagarus likely points to Cancer pagurus, the edible crab. I'm also noting the hermit crab reference even though the text doesn't name it directly, just describes the shell-dwelling behavior typical of Paguroidea. I'm settling crab as Brachyura broadly, lobster as Homarus gammarus, and crawfish as Palinurus elephas, while double-checking whether crayfish should instead be confirmed as Astacus astacus based on context.

Moving on to arachnids and insects, I'm mapping phalangium to Araneae, noting Thompson's identification as a venomous spider like Latrodectus, and treating scorpion as Scorpiones while distinguishing it from the sea scorpion fish. I'm assigning centipede/scolopendra to Chilopoda, iulus to Diplopoda, bee to Apis mellifera, wasp to Vespidae, and starting to work out ant as Formicidae.

Now I'm continuing through the beetles: dung-beetle to Scarabaeus, stag-beetle to Lucanus cervus, cockchafer to Melolontha melolontha, glow-worm to Lampyridae, and blister-beetle to Meloidae, with butterfly going to Lepidoptera. I'm puzzling over the fly-related terms, trying to pin down whether gadfly maps to Tabanidae or to Thompson's oestrus/empis, especially given a tricky claim about river worms developing into gadflies.

I'm deciding to map gadfly to Tabanidae with a caveat, myops similarly to horsefly, and conops/gnat to Culicidae. Then fleas go to Siphonaptera, lice to Phthiraptera, grasshopper to Orthoptera, and cicada to Cicadidae, with locust not appearing in my list.

For the stags' head maggots, I recognize these as Cephenemyia deer nose bot fly larvae based on commentator identification. River worms and generic worms I'm inclined to skip since they're too ambiguous, and leeches don't apply here. For cephalopods, I'm mapping cuttlefish to Sepia officinalis, calamary to Loligo vulgaris, teuthus to a larger squid like Ommastrephidae with a note on the uncertainty, and starting to work out octopus/poulpe/polypus as Octopus vulgaris.

Now I'm working through the single-row-sucker octopus (heledone, bolitaina, ozolis) as the genus Eledone, with ozolis likely Eledone moschata and heledone likely Eledone cirrhosa. I'm mapping nautilus polypus to Argonauta argo as the paper nautilus, and identifying Aristotle's "molluscs" (malakia) as actually referring to Cephalopoda as a whole group, which resolves the claim about all molluscs having eight feet. I'm about to move into testaceans next.

Mapping entoma to Insecta despite Aristotle including spiders and myriapods under that term. For echinoderms, I'm sorting the sea-urchin terms: generic references to Echinoidea, spatangus to Spatangus purpureus, edible urchin to Paracentrotus lividus. Sea-nettle and sea-anemone terms map to Actiniaria, sponges to Porifera, and now I'm working through the tethya terms.

Tethyum and ascidian map to Ascidiacea, while Aristotle's holothuria is uncertain since it may refer to salps or hydroids rather than true sea cucumbers. I'm also checking whether any star-fish terms appear in my lists, noting limpet maps to Patella and sea-ear to Haliotis, and leaving nerites as an uncertain case possibly tied to Neritidae or Nerita.

Since true Nerita species aren't Mediterranean, except Smaragdia, I'm leaving that mapping unresolved, treating Theodoxus fluviatilis as a separate consideration. I'm mapping trumpet-shell/kerux to Charonia, purple-fish and murex to Muricidae species like Bolinus brandaris and Hexaplex trunculus, and continuing to sort out whelk, snail, cockle, and scallop into their respective families.

Now I'm working through mussel as Mytilus galloprovincialis, oyster as Ostrea edulis, and trying to pin down pool-oyster, clam, razor-fish/solen, Pinna nobilis, chama, and tellina, while leaving strombus as a generic turbinate shell reference and noting the ambiguity around lyra (possibly the gurnard Trigla lyra) and chalcis (possibly a sardine species).

I'm also sorting out several animal identifications: kynokephalos as the dog-headed baboon matches Papio hamadryas, kebos likely refers to a tailed monkey mapping to Cercopithecidae, pithekos to Macaca sylvanus, and bonasus probably corresponds to bison, while still checking terms like "sea-lung" and camel references.

Continuing down the list, I'm checking more entries - hyaena, dog-fish, fox-shark, swan, pelican, ostrich, bear, hippopotamus, porcupine, beaver, otter, lynx, wolf, plus some uncertain ones like martichoras (mythical), glow-worm, silkworm, salpe, and obscure terms like epitragias that remain unresolved.

Then I move to mecon (cephalopod anatomy), scolopendra (sea version), carcinium which maps to hermit crab, cocalia which might be Trochus or Nassa shells, cyphae/siphae referring to shrimps, achainae identified as a deer species related to Cervus elaphus, and drepanis which Thompson suggests could be a sand martin - still working through chrem...

There are several more unresolved terms to track down: caprus as a possible fish, localus and colenes of uncertain identity, epomis possibly anatomical, phasis as a place name, plus mentions of sea-snail, kites, vultures, geese, pelagic creatures, goby, lyra, and thori as anatomy. I'm also noting the plant list separately - fig, vetch, beans, lucerne, cytisus, poppy, origanum, fleabane, onion, barley, grapes, styrax, and various trees - before planning to search for remaining candidates like star, ostrich, vulture, pelican, sea-lung, and hyena.

I'm clarifying that carabus refers to the stag-beetle here, while karabos elsewhere means crayfish or spiny lobster. I'm adding the fresh-water crab (Potamon fluviatile) and confirming chamaeleon, then checking whether pinna refers to the ear's anatomy or the mollusk before continuing through crawfish, lobster, and crayfish.

Rather than manually verify each remaining creature term—whale, purple, limpet, sea-ear, scallop, cockle, mussel, oyster, sponge, and the many others—I'm planning to build a seed list with regex patterns and then print sample contexts for each taxon to sanity check. I'm designing a pipeline in a working directory using Python's urllib: first a seed file listing each taxon's slug, query name, rank, patterns, notes, vernacular name, and flags like marine or fossil status, plus any contexts to skip; then a mention-scanning step that searches the text lines for each pattern, records the full sentence as a quote for each match, and separately checks claims against those quotes—making sure to avoid double-counting any text occurrence that falls within a claim's own quoted span.

I'm deciding to cap text mentions per taxon at around 8 occurrences (keeping first occurrences) while still logging the total occurrence count in the notes, since some terms like "man," "fish," or "bird" appear far more frequently than others. Quotes will be verbatim substrings trimmed to roughly 300 characters around the match. For resolving each taxon to authoritative records, I'm planning to use GBIF species matching restricted to Animalia with verbose output to check rank and match type, NCBI esearch, and Wikidata—preferably via a SPARQL query linking GBIF taxon keys (P846) to QIDs, falling back to name-based P225 search, and consulting WoRMS for marine species. Then for datasets, I'll pull GBIF occurrence counts per taxon with recorded byte size and hash, NCBI reference genome reports for species-level taxa, and supplementary trait datasets like AnAge, PanTHERIA for mammals, and AVONET for birds.

I'm trying to track down a reliable AVONET download link on figshare and verifying it against what prior slices used, and I want to check how other slices handled FishBase/SeaLifeBase access—possibly through a fetch script or an rfishbase parquet mirror—along with sourcing PBDB, IUCN (via GBIF), and WoRMS records, plus the standard GBIF backbone, NCBI taxonomy, and Wikidata lookups as the reference example does.

Let me grab exact metadata from existing AVONET, PanTHERIA, FishBase and AMNIOTE records so I reuse verified URLs.

I should check what Python libraries are available, like pyarrow or openpyxl, and verify whether network access is possible.

I should check a few more terms like whale, crawfish, lobster, and hermit before finalizing the seed list, inspecting their contexts via the mention scanner. Then I'll write a seed.py file in /tmp/ha0104/ with entries containing slug, scientific name query, rank, and pattern fields.

Writing seed patterns...

I'm checking whether "gnat" could falsely match inside other words like "designate," so I should use word boundaries in the matching logic. Now I'm ready to write out the seed carefully.

I should clean up the "antilopinae" notes. Boubalis likely refers to the hartebeest, Alcelaphus buselaphus, under subfamily Alcelaphinae rather than antelope generically — I'll go with Alcelaphus as the resolution.

I'm also fixing several other slug mismatches: "stylommatophora" with Helix should become "helix", "errantia" with Annelida becomes "annelida", "erinaceus-europaeus" becomes "erinaceus", and "scorpaena-scrofa" becomes "scorpaena".

I need to tighten up some regex word patterns too, since verbs like "flies" and "bears" create noise when matching animal terms. I'll restrict the Diptera pattern to require "the fly/flies" plus terms like "dipterous," "diptera," and "two-winged insects," and similarly limit "bear" matches to phrases like "the bear(s)," "she-bear," or "bear's" to avoid catching verb usages. Other simple terms like "ass," "ram," "hart," "kite," "crane," and "swallow" should be fine as-is without special restrictions.

For "roe" I'm narrowing the match to cases like "the roe," followed by punctuation, matching the specific claim text. Generic "fish" and "bird" terms need a cap since they're too common, and I'm leaving the "river worms" case unresolved for now while I tally up total mentions per taxon.

I'll set the mention cap at 8, extract quotes by truncating to sentence boundaries around 250 characters centered on the match while keeping it a verbatim substring, and skip text matches that fall inside a claim's already-recorded quote span to avoid double-counting. Now I'm moving on to building the mentions list and fixing the seed logic.

That edit didn't go through, so I'll try using StrReplace instead.

I'm now building a mentions script that writes results to a JSON file along with summary stats, then I'll review some sample outputs.

I'm spotting a few false positives to exclude: "flying fox" is a bat not a vulpes reference, "echinus" refers to a ruminant stomach not the echinoid, and "fishing frog" without a hyphen shouldn't match the fox pattern either.

Looking further, I need to add a fishing-frog variant to the lophius pattern, drop "chicks" from gallus since "swallow chicks" is unrelated, skip "or crow" since it's used as a verb, and flag the "lice/fleas" line as ambiguous since it likely refers to fish parasites like sea lice rather than true lice or fleas — I'll note that as unresolved rather than matching phthiraptera or siphonaptera.

I also realize "pardion" is actually an unidentified maned animal in Thompson's text, not a leopard, so I should remove that pattern and mark it unresolved too. For camels, I need separate patterns distinguishing "the Arabian" for dromedary and "the Bactrian" for the bactrian camel, since the text refers to them without using the full species names directly. Once these fixes are in, I'll rerun the matching and check the totals again, including unresolved items like the dog-fish reference.

The heredoc approach to running python seems to be failing intermittently, so instead I'll write the patch script to a file first and then execute it separately.

I'm double-checking the taxa count against my seed list—it's a bit fuzzy but roughly in the 150-190 range, so I'll just trust the actual list length rather than recounting. Now moving on to writing resolve.py.

This script caches raw HTTP responses via urllib, recording byte size and sha256 for each lookup, and handles each taxon across three sources. For GBIF, it attempts species/match for standard ranks, falling back to backbone search for odd ranks like subclass or infraorder, accepting a hit only if the canonical name matches and kingdom is Animalia. For NCBI it uses esearch/esummary against the scientific name, and for Wikidata it queries by GBIF key via SPARQL or falls back to searching haswbstatement for the NCBI taxid property, then resolves the QID with wbgetentities.

For marine species I'm adding a WoRMS lookup via AphiaRecordsByName, and skipping ITIS since its service is too slow — recording it as null. Every raw response gets written to a local cache directory keyed by hash, along with metadata like the source URL, retrieval timestamp, byte count, and checksum.

Next I'm working on resolve.py, which will produce resolved.json for each taxon containing identifiers, lineage, GBIF info, and provenance metadata from GBIF, NCBI, Wikidata, and WoRMS. I need to map GBIF ranks, handling both standard ranks like species through phylum and non-standard ones like subclass, infraorder, superfamily, and suborder for specific taxa.

For GBIF matching, I'll try species/match with verbose output, accepting exact canonical name matches, falling back to checking alternatives, and finally trying species/search filtered to the backbone dataset and accepted Animalia status if nothing else works. I also need to handle synonym cases where GBIF's accepted name differs (like Coloeus monedula → Corvus monedula) and note those substitutions, plus set up Wikidata SPARQL queries to find entities with P846 or P685 identifiers via P225 name lookups, recording the SPARQL responses themselves as provenance.

For cross-referencing, I want to pull NCBI taxon IDs (P685) alongside GBIF keys (P846) from Wikidata, preferring GBIF key matches first and falling back to name matches only when NCBI IDs confirm them or no ambiguity exists — flagging homonym-prone genera for manual review. Then I'll run NCBI esearch queries by scientific name, handling cases where multiple taxon IDs come back.

For sorting out homonyms, I'll check the NCBI esummary "division" field to confirm I've picked the animal record rather than a plant or other kingdom, and for marine species I'll cross-check against WoRMS AphiaRecordsByName.

For compiling datasets, I'm mapping out sources: GBIF occurrence counts by taxon key, NCBI genome reports filtered to reference genomes, IUCN Red List categories via GBIF's species endpoint, PBDB occurrence counts, and supplementary datasets like AnAge, PanTHERIA, AVONET (which will need zip/XML parsing since it's an Excel file), FishBase parquet files, and the Amniote database.

I have enough sources identified now, so I'll start writing a resolve.py script to pull these together.

_Tools used: Read ×4, Shell ×26, StrReplace ×10, UpdateCurrentStep ×2, Write ×5_

_Turn ended: error (Connection failed repeatedly)_
