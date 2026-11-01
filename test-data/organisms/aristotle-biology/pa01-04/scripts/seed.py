"""Seed data for the aristotle-biology pa01-04 organism slice.

TAXA: animal kinds named in Aristotle, *Parts of Animals* I-IV (W. Ogle's 1912 translation,
claim-sources/aristotle-biology/inputs/pa.txt lines 6-481), each with the scientific name used to
query the authorities, the rank, and the regexes that find Ogle's English or Graeco-Latin forms.
Identifications follow Ogle's own glosses in the text ("Carabi (Prickly Lobsters)", "Cestreus
(mullet)", "Tethya (Ascidians)", "Scarus (Parrot-fish)") and, for the Greek names he leaves
untranslated, the standard identifications in D'Arcy Thompson's glossaries of Greek birds and
fishes and his History of Animals translation. Where commentators disagree the choice is stated
in `notes` and in REPORT.md.

Patterns are matched case-insensitively against each paragraph (one paragraph per line) and
against the `quote` and `claim` fields of every aristotle-pa claim.

UNRESOLVED: names deliberately not resolved to a taxon (listed in REPORT.md).
"""

BOOK = "claim-sources/aristotle-biology/inputs/pa.txt"
LINE_START, LINE_END = 6, 481

# Plain "fish"/"fishes", not parrot-fish, razor-fishes, cuttle-fishes, shell-fish, fish-spines, fishing-frog.
FISH = r"(?<![-\w])fish(?:es)?\b(?!-)"

TAXA = [
    # --- higher groups Aristotle treats as "great kinds" -----------------------------------
    dict(slug="vertebrata", name="Vertebrata", rank="subphylum", vernacular=["vertebrates"],
         patterns=[r"(?<!non-)\bsanguineous animals?\b", r"(?<!non-)\bsanguineous (?:and viviparous )?(?:kinds|creatures?|quadrupeds)\b",
                   r"\banimals with blood\b", r"(?<!non-)\bsanguineous\b(?= and viviparous)"],
         notes="Aristotle's 'sanguineous animals' (enaima, animals with red blood) coincide with the vertebrates; "
               "his 'bloodless animals' (anaima) are not a taxon and are not resolved."),
    dict(slug="mammalia", name="Mammalia", rank="class", vernacular=["mammals"],
         patterns=[r"\bviviparous quadrupeds?\b", r"\bVivipara\b", r"\bviviparous animals?\b"],
         notes="'Vivipara' / 'viviparous quadrupeds' (zootoka): animals viviparous internally, which with the Cetacea "
               "and man are the mammals."),
    dict(slug="aves", name="Aves", rank="class", vernacular=["birds"],
         patterns=[r"\bbirds?\b", r"\bfeathered animals\b"],
         notes="Ogle's 'Birds' (ornithes) = class Aves."),
    dict(slug="reptilia", name="Reptilia", rank="class", vernacular=["reptiles"],
         patterns=[r"\boviparous quadrupeds?\b", r"\banimals with scaly plates\b", r"\banimals with scale-like plates\b"],
         notes="'Oviparous quadrupeds' (tetrapoda ootoka: lizards, tortoises, crocodiles) and 'animals with scaly plates' "
               "(pholidota) are the non-serpent reptiles; Aristotle also counts frogs among the oviparous quadrupeds, so "
               "Reptilia is the closest single taxon, not an exact match."),
    dict(slug="actinopterygii", name="Actinopterygii", rank="class", vernacular=["ray-finned fishes"],
         patterns=[FISH],
         notes="Ogle's 'fishes' (ichthues). Aristotle's fishes include the Selachia, which are resolved separately to "
               "Elasmobranchii; the bony fishes he contrasts them with are ray-finned fishes, so Actinopterygii is used "
               "as the best matching taxon for the generic word. 'Fish' itself is paraphyletic."),
    dict(slug="elasmobranchii", name="Elasmobranchii", rank="subclass", vernacular=["sharks and rays"],
         patterns=[r"\bSelachia\b", r"\bselachians?\b", r"\bsharks and rays\b"],
         notes="'Selachia' (selache, cartilaginous fishes): Ogle's own gloss is cartilaginous fishes; his examples "
               "(Torpedo, Trygon, Batos, Rhine) are all sharks and rays."),
    dict(slug="cetacea", name="Cetacea", rank="order", vernacular=["cetaceans", "whales"],
         patterns=[r"\bCetacea\b", r"\bwhales?\b", r"\bcetaceans?\b"],
         notes="'Cetacea' and 'whale' (phalaina); the dolphin is resolved separately."),
    dict(slug="insecta", name="Insecta", rank="class", vernacular=["insects"],
         patterns=[r"\binsects?\b"],
         notes="'Insects' (entoma, 'insected' animals). Aristotle's entoma also include spiders, scorpions and "
               "millipedes; Insecta is the best matching taxon for the group word."),
    dict(slug="crustacea", name="Crustacea", rank="subphylum", vernacular=["crustaceans"],
         patterns=[r"\bCrustacea\b", r"\bcrustaceans?\b"],
         notes="'Crustacea' (malakostraka, 'soft-shelled'). All of Aristotle's examples (Carabi, Astaci, Carides, Carcini) "
               "are decapods; the translator's group word is kept at subphylum rank."),
    dict(slug="mollusca", name="Mollusca", rank="phylum", vernacular=["molluscs", "shell-fish"],
         patterns=[r"\bTestacea\b", r"\btestaceans?\b", r"\bshell-fish\b"],
         notes="'Testacea' (ostrakoderma, 'potsherd-skinned'): shelled molluscs, but Aristotle also places the sea-urchins "
               "and the Tethya (ascidians) here. Mollusca is the best matching single taxon."),
    dict(slug="gastropoda", name="Gastropoda", rank="class", vernacular=["gastropods", "sea-snails"],
         patterns=[r"\bTurbinata\b", r"\bCochli\b", r"\bsea-snails?\b", r"\bturbinate shells\b", r"\bspiral snails\b",
                   r"\bunivalves\b", r"\bsnails\b"],
         notes="'Turbinata' (strombode, spiral-shelled Testacea), 'Cochli (Sea-snails)' and 'univalves' are gastropods."),
    dict(slug="bivalvia", name="Bivalvia", rank="class", vernacular=["bivalves"],
         patterns=[r"\bbivalves\b"],
         notes="'bivalves' (dithura)."),
    dict(slug="cephalopoda", name="Cephalopoda", rank="class", vernacular=["cephalopods"],
         patterns=[r"\bCephalopoda\b", r"\bCephalopods?\b"],
         notes="Ogle's 'Cephalopoda' for Aristotle's malakia ('softies')."),
    dict(slug="serpentes", name="Serpentes", rank="suborder", vernacular=["snakes", "serpents"],
         patterns=[r"\bserpents?\b", r"\bsnakes?\b"],
         notes="'serpents' (opheis)."),

    # --- mammals ---------------------------------------------------------------------------
    dict(slug="homo-sapiens", name="Homo sapiens", rank="species", vernacular=["human"],
         patterns=[r"\bman\b", r"\bmen\b", r"\bwomen\b", r"\bwoman\b", r"\bmankind\b"],
         notes="'man', 'men', 'women'. Book I also uses 'man' in methodological asides; all refer to humans."),
    dict(slug="equus-caballus", name="Equus caballus", rank="species", vernacular=["horse"],
         patterns=[r"\bhorses?\b", r"\bcolts?\b", r"\bfoals?\b", r"\bmares?\b"],
         notes="'horse', 'colts' (hippos). The domestic horse."),
    dict(slug="equus-asinus", name="Equus asinus", rank="species", vernacular=["donkey", "ass"],
         patterns=[r"(?<!Indian )\bass\b", r"\basses\b"],
         notes="'ass' (onos), the domestic donkey. The 'so-called Indian ass' is not resolved (see REPORT.md)."),
    dict(slug="equus", name="Equus", rank="genus", vernacular=["mule"],
         patterns=[r"\bmules?\b"],
         notes="'mule' (oreus), the hybrid of horse and ass; hybrids have no backbone name, so the common genus is used."),
    dict(slug="bos-taurus", name="Bos taurus", rank="species", vernacular=["cattle", "ox"],
         patterns=[r"\boxen\b", r"\box\b", r"\bbulls?\b", r"\bcows?\b"],
         notes="'ox', 'oxen', 'bull', 'cows' (bous), domestic cattle. The 'certain kind of ox' with a bone in the heart "
               "(pa03-15) is the same species."),
    dict(slug="ovis-aries", name="Ovis aries", rank="species", vernacular=["sheep"],
         patterns=[r"\bsheep\b", r"\brams?\b", r"\bewes?\b"],
         notes="'sheep', 'rams', 'ewes' (probaton), domestic sheep."),
    dict(slug="capra-hircus", name="Capra hircus", rank="species", vernacular=["goat"],
         patterns=[r"\bgoats?\b"],
         notes="'goat' (aix), the domestic goat."),
    dict(slug="sus-scrofa", name="Sus scrofa", rank="species", vernacular=["pig", "wild boar"],
         patterns=[r"\bpigs?\b", r"\bswine\b", r"\bboars?\b", r"\bsows?\b"],
         notes="'pig', 'swine', 'boar', 'sow' (hys); domestic pigs and wild boar are both Sus scrofa."),
    dict(slug="canis-familiaris", name="Canis familiaris", rank="species", vernacular=["dog"],
         patterns=[r"\bdogs?\b(?!-teeth)", r"\bhounds?\b"],
         notes="'dog' (kyon), the domestic dog; 'Dogs in India' (pa01-07) are dogs too."),
    dict(slug="canis-lupus", name="Canis lupus", rank="species", vernacular=["wolf"],
         patterns=[r"\bwolf\b", r"\bwolves\b"],
         notes="'wolves' (lykos), the grey wolf."),
    dict(slug="panthera-leo", name="Panthera leo", rank="species", vernacular=["lion"],
         patterns=[r"\blions?\b", r"\blioness\b"],
         notes="'lion' (leon). Lions survived in Thrace and Macedonia in Aristotle's time."),
    dict(slug="panthera-pardus", name="Panthera pardus", rank="species", vernacular=["leopard"],
         patterns=[r"\bleopards?\b"],
         notes="'leopard' (pardalis)."),
    dict(slug="lynx-lynx", name="Lynx lynx", rank="species", vernacular=["Eurasian lynx"],
         patterns=[r"\blynx\b"],
         notes="'lynx' (lynx); the Eurasian lynx is the species of Greece and Asia Minor."),
    dict(slug="hyaena-hyaena", name="Hyaena hyaena", rank="species", vernacular=["striped hyena"],
         patterns=[r"\bhyenas?\b"],
         notes="'hyena' (hyaina); the striped hyena is the hyena of Asia Minor and the standard identification."),
    dict(slug="martes", name="Martes", rank="genus", vernacular=["martens"],
         patterns=[r"\bmartens?\b"],
         notes="'marten' (iktis). Ogle translates marten; Thompson suggests the beech marten (Martes foina) but the word "
               "is also read as polecat or weasel, so the genus is used."),
    dict(slug="ursus-arctos", name="Ursus arctos", rank="species", vernacular=["brown bear"],
         patterns=[r"(?<=case with )bears\b"],
         notes="'bears' (arktos), the brown bear of Greece."),
    dict(slug="cervus-elaphus", name="Cervus elaphus", rank="species", vernacular=["red deer"],
         patterns=[r"\bdeer\b", r"\bstags?\b", r"\bdoes\b(?= have none)"],
         notes="'deer', 'stags', 'does' (elaphos). The elaphos of Greece is the red deer; Aristotle's statements about deer "
               "in general (solid shed horns, no gall-bladder) are also mapped here. The roe is resolved separately."),
    dict(slug="capreolus-capreolus", name="Capreolus capreolus", rank="species", vernacular=["roe deer"],
         patterns=[r"\broes?\b"],
         notes="'roe' (prox / dorkas in this sense), the European roe deer."),
    dict(slug="bison-bonasus", name="Bison bonasus", rank="species", vernacular=["European bison", "wisent"],
         patterns=[r"\bBonasus\b"],
         notes="'Bonasus' (bonasos) of Paeonia, which defends itself by ejecting dung, is identified with the European "
               "bison by the commentators (Thompson); some older readings suggested the aurochs."),
    dict(slug="alcelaphus-buselaphus", name="Alcelaphus buselaphus", rank="species", vernacular=["hartebeest", "bubal"],
         patterns=[r"\bBubalus\b"],
         notes="'Bubalus' (boubalis), an African antelope with inward-curving horns: the bubal hartebeest in Thompson. "
               "Not the water buffalo, which took the name Bubalus later."),
    dict(slug="gazella-dorcas", name="Gazella dorcas", rank="species", vernacular=["dorcas gazelle"],
         patterns=[r"\bgazelles?\b"],
         notes="'gazelle' (dorkas), the smallest horned animal Aristotle knew; the dorcas gazelle of North Africa and the "
               "Levant is the usual identification."),
    dict(slug="oryx", name="Oryx", rank="genus", vernacular=["oryxes"],
         patterns=[r"\bOryx\b"],
         notes="'Oryx', reported one-horned and cloven-hoofed. Known to the Greeks from Africa/Arabia; the species is not "
               "determinable (O. beisa, O. dammah, O. leucoryx), so the genus is used."),
    dict(slug="camelus", name="Camelus", rank="genus", vernacular=["camels"],
         patterns=[r"\bcamels?\b"],
         notes="'camel' (kamelos). History of Animals distinguishes Bactrian and Arabian camels; Parts of Animals does not, "
               "so the genus is used."),
    dict(slug="elephantidae", name="Elephantidae", rank="family", vernacular=["elephants"],
         patterns=[r"\belephants?\b"],
         notes="'elephant' (elephas). Aristotle's information came mainly from Indian elephants (Elephas maximus) but the "
               "text does not distinguish, so the family is used."),
    dict(slug="monachus-monachus", name="Monachus monachus", rank="species", vernacular=["Mediterranean monk seal"],
         patterns=[r"\bseals?\b"],
         notes="'seal' (phoke); the only seal of the Aegean is the Mediterranean monk seal, the standard identification."),
    dict(slug="delphinus-delphis", name="Delphinus delphis", rank="species", vernacular=["common dolphin"],
         patterns=[r"\bdolphins?\b"],
         notes="'dolphin' (delphis); the common dolphin is the standard identification for the Aegean, though bottlenose "
               "dolphins also occur there."),
    dict(slug="lepus-europaeus", name="Lepus europaeus", rank="species", vernacular=["European hare"],
         patterns=[r"\bhares?\b"],
         notes="'hare' (lagos); the brown hare is the hare of Greece."),
    dict(slug="mus-musculus", name="Mus musculus", rank="species", vernacular=["house mouse"],
         patterns=[r"\bmouse\b", r"\bmice\b"],
         notes="'mouse', 'mice' (mys). The word covers mice and small rodents generally; the house mouse is the default "
               "identification."),
    dict(slug="macaca-sylvanus", name="Macaca sylvanus", rank="species", vernacular=["Barbary macaque"],
         patterns=[r"\bapes?\b"],
         notes="'ape' (pithekos), tailless and intermediate between man and quadrupeds: the Barbary macaque, the standard "
               "identification of Aristotle's pithekos."),
    dict(slug="chiroptera", name="Chiroptera", rank="order", vernacular=["bats"],
         patterns=[r"\bbats?\b"],
         notes="'bats' (nykteris)."),

    # --- birds -----------------------------------------------------------------------------
    dict(slug="struthio-camelus", name="Struthio camelus", rank="species", vernacular=["ostrich"],
         patterns=[r"\bostrich\b"],
         notes="'Ostrich', 'Libyan ostrich' (strouthos ho Libykos)."),
    dict(slug="grus-grus", name="Grus grus", rank="species", vernacular=["common crane"],
         patterns=[r"\bcranes?\b"],
         notes="'Crane' (geranos), the common crane."),
    dict(slug="crex-crex", name="Crex crex", rank="species", vernacular=["corncrake"],
         patterns=[r"\bCrex\b"],
         notes="'Crex' (krex), a long-legged bird with a short hind toe. Identification uncertain: Thompson's Glossary of "
               "Greek Birds discusses the corncrake and, alternatively, a wader such as the black-winged stilt; the "
               "corncrake (which bears the Greek name) is used."),
    dict(slug="jynx-torquilla", name="Jynx torquilla", rank="species", vernacular=["Eurasian wryneck"],
         patterns=[r"\bwrynecks?\b"],
         notes="'wryneck' (iynx), the only bird with two toes forward and two back in the text."),
    dict(slug="columba", name="Columba", rank="genus", vernacular=["pigeons"],
         patterns=[r"\bpigeons?\b"],
         notes="'pigeon' (peristera). Aristotle distinguishes several pigeon kinds elsewhere; the genus is used."),
    dict(slug="accipitridae", name="Accipitridae", rank="family", vernacular=["hawks"],
         patterns=[r"\bhawks?\b"],
         notes="'hawk' (hierax), a collective name for small diurnal raptors (hawks and falcons); Accipitridae is used, "
               "with the caveat that falcons belong to Falconidae."),
    dict(slug="milvus", name="Milvus", rank="genus", vernacular=["kites"],
         patterns=[r"\bkites?\b"],
         notes="'kite' (iktinos): the red or black kite."),
    dict(slug="corvus", name="Corvus", rank="genus", vernacular=["crows"],
         patterns=[r"\bcrows?\b"],
         notes="'crows and birds of crowlike habit' (korone, the hooded crow, and allies)."),
    dict(slug="picidae", name="Picidae", rank="family", vernacular=["woodpeckers"],
         patterns=[r"\bwoodpeckers?\b"],
         notes="'woodpeckers' (dryokolaptes)."),
    dict(slug="gallus-gallus", name="Gallus gallus", rank="species", vernacular=["chicken", "domestic fowl"],
         patterns=[r"\bfowls?\b", r"\bcocks?\b", r"\bhens?\b"],
         notes="'common fowls' (alektoris / alektryon), the domestic fowl."),

    # --- reptiles and amphibians -------------------------------------------------------------
    dict(slug="crocodylus-niloticus", name="Crocodylus niloticus", rank="species", vernacular=["Nile crocodile"],
         patterns=[r"\bcrocodiles?\b"],
         notes="'river crocodile' (krokodeilos ho potamios), the Nile crocodile."),
    dict(slug="testudines", name="Testudines", rank="order", vernacular=["tortoises and turtles"],
         patterns=[r"(?<!sea-)(?<!land-)\btortoises?\b", r"\bturtles?\b"],
         notes="'Tortoises' as a group, including the Chelone and the Emys; land-tortoises are resolved to Testudo, "
               "sea-tortoises to Cheloniidae."),
    dict(slug="testudo", name="Testudo", rank="genus", vernacular=["Mediterranean tortoises"],
         patterns=[r"\bland-tortoises?\b"],
         notes="'land-tortoises' (chelone chersaia): Testudo graeca / T. hermanni / T. marginata in Greece; genus used."),
    dict(slug="cheloniidae", name="Cheloniidae", rank="family", vernacular=["sea turtles"],
         patterns=[r"\bsea-tortoises?\b", r"\bChelone\b"],
         notes="'sea-tortoise' and 'Chelone' (chelone thalattia): the Mediterranean sea turtles (loggerhead Caretta caretta "
               "and green turtle Chelonia mydas); the family is used."),
    dict(slug="emys", name="Emys", rank="genus", vernacular=["pond turtles"],
         patterns=[r"\bEmys\b"],
         notes="'Emys' (emys), the freshwater terrapin; in Greece the European pond turtle (Emys orbicularis) or the "
               "Balkan terrapin (Mauremys rivulata), so the genus named by Ogle is used."),
    dict(slug="lacertilia", name="Lacertilia", rank="suborder", vernacular=["lizards"],
         patterns=[r"\blizards?\b"],
         notes="'lizards' (sauroi). Lizards are paraphyletic with respect to snakes; Lacertilia is the conventional name."),
    dict(slug="chamaeleo-chamaeleon", name="Chamaeleo chamaeleon", rank="species", vernacular=["common chameleon"],
         patterns=[r"\bChamaeleons?\b", r"\bchameleons?\b"],
         notes="'Chamaeleon', the common chameleon of the eastern Mediterranean."),
    dict(slug="viperidae", name="Viperidae", rank="family", vernacular=["vipers"],
         patterns=[r"\bvipers?\b"],
         notes="'vipers' (echis), viviparous serpents; in Greece mainly Vipera ammodytes, family used."),
    dict(slug="bufo", name="Bufo", rank="genus", vernacular=["toads"],
         patterns=[r"\btoads?\b"],
         notes="'toad' (phrynos)."),
    dict(slug="caudata", name="Caudata", rank="order", vernacular=["salamanders and newts"],
         patterns=[r"\bCordylus\b"],
         notes="'Cordylus' (kordylos), an animal with gills and feet and a flattened tail: identified as a newt or its "
               "gilled larva (Thompson, Ogle). Uncertain; the order is used."),

    # --- fishes ------------------------------------------------------------------------------
    dict(slug="sparisoma-cretense", name="Sparisoma cretense", rank="species", vernacular=["Mediterranean parrotfish"],
         patterns=[r"\bScarus\b", r"\bparrot-fish\b"],
         notes="'Scarus (Parrot-fish)' (skaros), the Mediterranean parrotfish, the only parrotfish of the Aegean."),
    dict(slug="mugilidae", name="Mugilidae", rank="family", vernacular=["grey mullets"],
         patterns=[r"\bCestreus\b", r"\bmullets?\b"],
         notes="'Cestreus (mullet)' (kestreus), the grey mullets. The 'certain kind of Cestreus' in the lake at Siphae is "
               "not identified to species."),
    dict(slug="anguilla-anguilla", name="Anguilla anguilla", rank="species", vernacular=["European eel"],
         patterns=[r"\beels?\b"],
         notes="'eel' (enchelys)."),
    dict(slug="conger-conger", name="Conger conger", rank="species", vernacular=["European conger"],
         patterns=[r"\bcongers?\b"],
         notes="'conger' (gongros)."),
    dict(slug="muraena-helena", name="Muraena helena", rank="species", vernacular=["Mediterranean moray"],
         patterns=[r"\bSmuraena\b", r"\bmuraena\b"],
         notes="'Smuraena' (smyraina / myraina), the Mediterranean moray."),
    dict(slug="sarda-sarda", name="Sarda sarda", rank="species", vernacular=["Atlantic bonito"],
         patterns=[r"\bAmia\b"],
         notes="'Amia' (amia): Thompson's Glossary of Greek Fishes identifies it with the bonito (Pelamys sarda = Sarda "
               "sarda). Uncertain; not the North American bowfin Amia calva."),
    dict(slug="cyprinus-carpio", name="Cyprinus carpio", rank="species", vernacular=["common carp"],
         patterns=[r"\bCyprini\b", r"\bCyprinus\b"],
         notes="'Cyprini' (kyprinos), river fishes with a fleshy palate: the carp (Thompson)."),
    dict(slug="lophius-piscatorius", name="Lophius piscatorius", rank="species", vernacular=["angler", "monkfish"],
         patterns=[r"\bFishing-frog\b"],
         notes="'Fishing-frog' (batrachos ho halieus), the angler fish."),
    dict(slug="torpedo", name="Torpedo", rank="genus", vernacular=["electric rays"],
         patterns=[r"\bTorpedos?\b"],
         notes="'Torpedo' (narke): T. torpedo and T. marmorata in the Aegean; genus used."),
    dict(slug="dasyatis-pastinaca", name="Dasyatis pastinaca", rank="species", vernacular=["common stingray"],
         patterns=[r"\bTrygons?\b"],
         notes="'Trygon' (trygon), the common stingray."),
    dict(slug="raja", name="Raja", rank="genus", vernacular=["skates"],
         patterns=[r"\bBatos\b", r"\bBati\b"],
         notes="'Batos', 'Bati' (batos), the skates/rays of the genus Raja (Thompson)."),
    dict(slug="squatina-squatina", name="Squatina squatina", rank="species", vernacular=["angelshark"],
         patterns=[r"\bRhine\b"],
         notes="'Rhine' (rhine), the angel shark, whose rough skin was used as a rasp."),

    # --- arthropods --------------------------------------------------------------------------
    dict(slug="formicidae", name="Formicidae", rank="family", vernacular=["ants"],
         patterns=[r"\bants?\b"],
         notes="'ants' (myrmex); winged and wingless ants (pa01-06) are the sexual and worker castes."),
    dict(slug="apis-mellifera", name="Apis mellifera", rank="species", vernacular=["western honey bee"],
         patterns=[r"\bbees?\b"],
         notes="'bees' (melitta), the honey bee; 'all the various kinds of bees' also takes in wild bees."),
    dict(slug="vespidae", name="Vespidae", rank="family", vernacular=["wasps"],
         patterns=[r"\bwasps?\b"],
         notes="'wasps' (sphex)."),
    dict(slug="diptera", name="Diptera", rank="order", vernacular=["flies"],
         patterns=[r"(?<!gad-)(?<!cattle-)\bflies\b"],
         notes="'flies' (myia), two-winged with a proboscis: the house fly and its allies; order used."),
    dict(slug="tabanidae", name="Tabanidae", rank="family", vernacular=["horse-flies", "gadflies"],
         patterns=[r"\bgad-flies\b"],
         notes="'gad-flies' (myops) that pierce the skin of man and beasts: the horse-flies."),
    dict(slug="cicadidae", name="Cicadidae", rank="family", vernacular=["cicadas"],
         patterns=[r"\bCicadae\b", r"\bcicadas?\b"],
         notes="'Cicadae' (tettix)."),
    dict(slug="ephemeroptera", name="Ephemeroptera", rank="order", vernacular=["mayflies"],
         patterns=[r"\bEphemera\b"],
         notes="'Ephemera' living a single day about the Black Sea (the ephemeron of the Hypanis): a mayfly."),
    dict(slug="acrididae", name="Acrididae", rank="family", vernacular=["grasshoppers", "locusts"],
         patterns=[r"\blocusts?\b"],
         notes="'locusts' (akris), leaping insects with steering hind legs: short-horned grasshoppers."),
    dict(slug="siphonaptera", name="Siphonaptera", rank="order", vernacular=["fleas"],
         patterns=[r"\bfleas?\b"],
         notes="'the various kinds of fleas' (psylla)."),
    dict(slug="melolontha", name="Melolontha", rank="genus", vernacular=["cockchafers"],
         patterns=[r"\bMelolonthae\b"],
         notes="'Melolonthae' (melolonthe), sheath-winged beetles: cockchafers (Thompson); 'and the like' covers "
               "other chafers."),
    dict(slug="scarabaeidae", name="Scarabaeidae", rank="family", vernacular=["scarab beetles"],
         patterns=[r"\bCanthari\b"],
         notes="'Canthari' (kantharos), beetles that freeze when touched. Usually the dung beetle / scarab; uncertain, "
               "family used."),
    dict(slug="lampyridae", name="Lampyridae", rank="family", vernacular=["fireflies", "glow-worms"],
         patterns=[r"\bglow-worms?\b"],
         notes="'glow-worm' (lampyris), winged males and wingless females."),
    dict(slug="scorpiones", name="Scorpiones", rank="order", vernacular=["scorpions"],
         patterns=[r"\bscorpions?\b"],
         notes="'scorpions' (skorpios)."),
    dict(slug="diplopoda", name="Diplopoda", rank="class", vernacular=["millipedes"],
         patterns=[r"\bJuli\b", r"\bMillipedes?\b"],
         notes="'Juli (Millipedes)' (ioulos)."),
    dict(slug="palinurus-elephas", name="Palinurus elephas", rank="species", vernacular=["European spiny lobster"],
         patterns=[r"\bCarabi\b", r"\bCaraboids?\b", r"\bPrickly Lobsters\b", r"\bspiny lobsters?\b"],
         notes="'Carabi (Prickly Lobsters)' (karabos), the spiny lobster of the Mediterranean."),
    dict(slug="homarus-gammarus", name="Homarus gammarus", rank="species", vernacular=["European lobster"],
         patterns=[r"\bAstaci\b", r"(?<!Prickly )\bLobsters?\b"],
         notes="'Astaci' and 'Lobsters' (astakos), the clawed European lobster."),
    dict(slug="caridea", name="Caridea", rank="infraorder", vernacular=["shrimps", "prawns"],
         patterns=[r"\bCarides\b"],
         notes="'Carides' (karis), shrimps and prawns, distinguished by a tail from crabs and by the absence of claws "
               "from the Carabi."),
    dict(slug="brachyura", name="Brachyura", rank="infraorder", vernacular=["crabs"],
         patterns=[r"\bCarcini\b", r"\bCarcinoid\b", r"\bcrabs?\b"],
         notes="'Carcini (Crabs)' (karkinos)."),
    dict(slug="maja-squinado", name="Maja squinado", rank="species", vernacular=["European spider crab"],
         patterns=[r"\bMaiae\b"],
         notes="'Maiae' (maia), thin-legged spider crabs: the Mediterranean spider crab (Ogle, Thompson)."),

    # --- molluscs ----------------------------------------------------------------------------
    dict(slug="sepia-officinalis", name="Sepia officinalis", rank="species", vernacular=["common cuttlefish"],
         patterns=[r"\bSepias?\b(?! officinalis)", r"\bCuttle-fish(?:es)?\b", r"\bcuttlefish(?:es)?\b"],
         notes="'Sepia', 'Cuttle-fishes' (sepia), the common cuttlefish."),
    dict(slug="octopus-vulgaris", name="Octopus vulgaris", rank="species", vernacular=["common octopus"],
         patterns=[r"\bPoulps?\b", r"\boctopus(?:es)?\b"],
         notes="'Poulp' (polypous), the common octopus."),
    dict(slug="loligo-vulgaris", name="Loligo vulgaris", rank="species", vernacular=["European squid"],
         patterns=[r"\bCalamar(?:y|ies)\b", r"\bTeuthides\b", r"\bsquids?\b"],
         notes="'Calamary' / 'Teuthides' (teuthis), the smaller calamary: the European squid. The larger 'Teuthi' are "
               "resolved separately."),
    dict(slug="ommastrephidae", name="Ommastrephidae", rank="family", vernacular=["flying squids"],
         patterns=[r"\bTeuthi\b"],
         notes="'the larger calamaries known as Teuthi' (teuthos): flying squids such as Todarodes sagittatus "
               "(Thompson); family used."),
    dict(slug="muricidae", name="Muricidae", rank="family", vernacular=["murex snails", "purple snails"],
         patterns=[r"\bPurpurae\b", r"\bPurpuras\b", r"\bpurple snails?\b"],
         notes="'Purpurae' (porphyra), the purple-dye snails (Bolinus brandaris, Hexaplex trunculus)."),
    dict(slug="buccinidae", name="Buccinidae", rank="family", vernacular=["whelks"],
         patterns=[r"\bwhelks?\b"],
         notes="'Whelks' (keryx). Ogle translates whelk; Thompson takes keryx for the trumpet shell Charonia, so the "
               "identification is uncertain."),
    dict(slug="neritidae", name="Neritidae", rank="family", vernacular=["nerites"],
         patterns=[r"\bNerites\b"],
         notes="'Nerites' (nerites), an operculate sea-snail; commonly taken for a nerite, though some read a top-shell "
               "(Trochidae). Uncertain."),
    dict(slug="patella", name="Patella", rank="genus", vernacular=["limpets"],
         patterns=[r"\blimpets?\b"],
         notes="'Limpets' (lepas)."),
    dict(slug="pectinidae", name="Pectinidae", rank="family", vernacular=["scallops"],
         patterns=[r"\bscallops?\b"],
         notes="'scallops' (kteis)."),
    dict(slug="mytilus", name="Mytilus", rank="genus", vernacular=["mussels"],
         patterns=[r"\bmussels?\b"],
         notes="'mussels' (mys); in the Aegean Mytilus galloprovincialis."),
    dict(slug="ostreidae", name="Ostreidae", rank="family", vernacular=["oysters"],
         patterns=[r"\boysters?\b"],
         notes="'oysters' (ostreon). Aristotle's ostreon can mean any testacean ('the several species known by the general "
               "name of oysters'); the true oysters are used."),
    dict(slug="solen", name="Solen", rank="genus", vernacular=["razor clams"],
         patterns=[r"\bSolens\b", r"\brazor-fish(?:es)?\b"],
         notes="'Solens (razor-fishes)' (solen)."),

    # --- echinoderms, tunicates, cnidarians, sponges ----------------------------------------
    dict(slug="echinoidea", name="Echinoidea", rank="class", vernacular=["sea urchins"],
         patterns=[r"\bsea-urchins?\b", r"\bsea urchins?\b"],
         notes="'sea-urchins' (echinos); the edible Aegean species is Paracentrotus lividus, but Aristotle speaks of several "
               "kinds."),
    dict(slug="asteroidea", name="Asteroidea", rank="class", vernacular=["starfish"],
         patterns=[r"\bStarfish(?:es)?\b"],
         notes="'Starfishes' (aster)."),
    dict(slug="holothuroidea", name="Holothuroidea", rank="class", vernacular=["sea cucumbers"],
         patterns=[r"\bHolothurias?\b"],
         notes="'Holothurias' (holothourion). Whether Aristotle's holothouria are sea cucumbers is debated (Thompson "
               "considered pelagic animals possible); the conventional identification is used."),
    dict(slug="ascidiacea", name="Ascidiacea", rank="class", vernacular=["sea squirts"],
         patterns=[r"\bAscidians?\b", r"\bTethya\b"],
         notes="'Tethya (Ascidians)' (tethyon), sea squirts."),
    dict(slug="actiniaria", name="Actiniaria", rank="order", vernacular=["sea anemones"],
         patterns=[r"\bAcalephae\b", r"\bSea-nettles?\b"],
         notes="'Acalephae, or Sea-nettles' (akalephe / knide), which attach to rocks and also detach: sea anemones in the "
               "standard reading (Ogle, Thompson), not jellyfish."),
    dict(slug="porifera", name="Porifera", rank="phylum", vernacular=["sponges"],
         patterns=[r"\bsponges?\b"],
         notes="'sponges' (spongos), which Aristotle treats as virtually plants; they are animals (Porifera)."),
]

TAXA_BY_SLUG = {t["slug"]: t for t in TAXA}

UNRESOLVED = [
    dict(name="Indian ass", line=211, reason="one-horned, solid-hoofed animal known only by report (Ctesias); variously "
         "read as the Indian rhinoceros, the kiang/onager or a fable. No identification is agreed."),
    dict(name="crabs known as Heracleotic", line=394, reason="short-legged crab (karkinos herakleotikos); proposed "
         "identifications (e.g. Calappa, Dromia, Eriphia) disagree."),
    dict(name="sea-lungs", line=370, reason="pleumon, free-floating sea animal; read as a ctenophore, a jellyfish such as "
         "Rhizostoma, or a salp. No agreed identification."),
    dict(name="cattle-flies", line=190, reason="oistros, the gadfly/botfly of cattle (Hypoderma or Tabanus); Ogle's 'gad-flies' "
         "and 'cattle-flies' are two Greek words whose referents overlap, so only 'gad-flies' is resolved (Tabanidae)."),
    dict(name="Cestreus found in the lake at Siphae", line=467, reason="a grey mullet of a Boeotian lake; species unknown, "
         "mapped to Mugilidae with the other Cestreus mentions."),
]
