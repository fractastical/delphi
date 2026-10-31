"""Curated list of animal taxa mentioned in Chapters VI-XI of D'Arcy Thompson,
*On Growth and Form* (1917), with the regexes used to find them in the text and
hints for resolving them against GBIF / WoRMS / PBDB / NCBI / Wikidata.

Each entry: slug, query name (sent to GBIF match), regex patterns matched against
the book text and the claim text, and keyword hints.  `group` is only used for
the report.  Protists that Thompson treats as animals (Foraminifera, Radiolaria,
testate amoebae, heliozoans) are included with their modern placement in `notes`.
"""

TAXA = []


def T(slug, query, patterns=None, **kw):
    kw.update(slug=slug, query=query, patterns=patterns or [r"\b" + query + r"\b"])
    TAXA.append(kw)


# ---------------------------------------------------------------- Protists treated as animals
RHIZ = "Thompson treats this as an animal (Protozoa); modern placement is in Rhizaria (SAR), not Animalia."
T("foraminifera", "Foraminifera", [r"\b[Ff]oraminifer\w*"], rank="phylum", kingdom="Chromista",
  ncbi_kw="Rhizaria", group="protist", notes=RHIZ, vern=["forams"])
T("globigerina", "Globigerina", kingdom="Chromista", ncbi_kw="Foraminifera", marine=True, fossil=True, group="protist", notes=RHIZ)
T("hastigerina", "Hastigerina", kingdom="Chromista", ncbi_kw="Foraminifera", marine=True, group="protist", notes=RHIZ)
T("nummulites", "Nummulites", [r"\b[Nn]ummulites?\b"], kingdom="Chromista", ncbi_kw="Foraminifera", marine=True, fossil=True,
  group="protist", notes=RHIZ + " Thompson writes 'the Nummulite'.")
T("nodosaria", "Nodosaria", kingdom="Chromista", ncbi_kw="Foraminifera", marine=True, fossil=True, group="protist", notes=RHIZ)
T("rotalia", "Rotalia", kingdom="Chromista", ncbi_kw="Foraminifera", marine=True, fossil=True, group="protist", notes=RHIZ)
T("pulvinulina", "Pulvinulina", kingdom="Chromista", ncbi_kw="Foraminifera", marine=True, fossil=True, group="protist",
  notes=RHIZ + " Pulvinulina is an obsolete genus (species now in Globorotalia / Eponides etc.).")
T("cristellaria", "Cristellaria", kingdom="Chromista", ncbi_kw="Foraminifera", marine=True, fossil=True, group="protist",
  notes=RHIZ + " Cristellaria is an obsolete name for Lenticulina.")
T("astrorhiza", "Astrorhiza", [r"\bAstrorhiza\b(?: limicola)?"], kingdom="Chromista", ncbi_kw="Foraminifera", marine=True,
  group="protist", notes=RHIZ)
T("entosolenia", "Entosolenia", [r"\bEntosolenia\b(?: aspera)?"], kingdom="Chromista", ncbi_kw="Foraminifera", marine=True,
  group="protist", notes=RHIZ + " Entosolenia is an obsolete name (species now in Fissurina / Oolina).")
T("radiolaria", "Radiolaria", [r"\b[Rr]adiolari\w*"], rank="class", kingdom="Chromista", ncbi_kw="Rhizaria", group="protist",
  notes=RHIZ + " 'Radiolaria' in Thompson covers Polycystinea, Acantharea and Phaeodarea (the last now in Cercozoa).")
T("nassellaria", "Nassellaria", [r"\b[Nn]assellari\w*"], rank="order", kingdom="Chromista", ncbi_kw="Polycystinea", group="protist", notes=RHIZ)
T("phaeodaria", "Phaeodaria", kingdom="Chromista", ncbi_kw="Rhizaria", group="protist", notes=RHIZ + " Phaeodaria are now placed in Cercozoa.")
T("acantharia", "Acantharia", [r"\bAcanthari\w*"], kingdom="Chromista", ncbi_kw="Rhizaria", group="protist", notes=RHIZ + " Modern class Acantharea.")
T("acanthometridae", "Acanthometridae", kingdom="Chromista", ncbi_kw="Rhizaria", group="protist", notes=RHIZ)
T("callimitra", "Callimitra", kingdom="Chromista", ncbi_kw="Rhizaria", marine=True, group="protist", notes=RHIZ)
T("collosphaera", "Collosphaera", kingdom="Chromista", ncbi_kw="Rhizaria", marine=True, group="protist", notes=RHIZ)
T("aulacantha", "Aulacantha", [r"\bAulacantha\b(?: scolymantha)?"], kingdom="Chromista", ncbi_kw="Rhizaria", marine=True, group="protist", notes=RHIZ)
T("aulonia", "Aulonia", [r"\bAulonia\b(?: hexagona)?"], kingdom="Chromista", ncbi_kw="Rhizaria", marine=True, group="protist", notes=RHIZ)
T("actinomma", "Actinomma", [r"\bActinomma\b(?: arcadophorum)?"], kingdom="Chromista", ncbi_kw="Rhizaria", marine=True, fossil=True, group="protist", notes=RHIZ)
T("ethmosphaera", "Ethmosphaera", [r"\bEthmosphaera\b(?: conosiphonia)?"], kingdom="Chromista", ncbi_kw="Rhizaria", marine=True, group="protist", notes=RHIZ)
T("cenosphaera", "Cenosphaera", [r"\bCenosphaera\b(?: favosa)?"], kingdom="Chromista", ncbi_kw="Rhizaria", marine=True, fossil=True, group="protist", notes=RHIZ)
T("aulastrum", "Aulastrum", [r"\bAulastrum\b(?: triceros)?"], kingdom="Chromista", ncbi_kw="Rhizaria", marine=True, group="protist", notes=RHIZ)
T("circoporus", "Circoporus", [r"\bCircoporus\b(?: sexfurcus)?"], kingdom="Chromista", ncbi_kw="Rhizaria", marine=True, group="protist", notes=RHIZ)
T("circospathis", "Circospathis", [r"\bCircospathis\b(?: novena)?"], kingdom="Chromista", ncbi_kw="Rhizaria", marine=True, group="protist", notes=RHIZ)
T("circorrhegma", "Circorrhegma", [r"\bCircorrhegma\b(?: dodecahedra)?"], kingdom="Chromista", ncbi_kw="Rhizaria", marine=True, group="protist", notes=RHIZ)
T("dorataspis", "Dorataspis", kingdom="Chromista", ncbi_kw="Rhizaria", marine=True, group="protist", notes=RHIZ)
T("phatnaspis", "Phatnaspis", [r"\bPhatnaspis\b(?: cristata)?"], kingdom="Chromista", ncbi_kw="Rhizaria", marine=True, group="protist", notes=RHIZ)
T("phractaspis", "Phractaspis", [r"\bPhractaspis\b(?: prototypus)?"], kingdom="Chromista", ncbi_kw="Rhizaria", marine=True, group="protist", notes=RHIZ)
AMOEB = "Thompson treats this rhizopod as an animal; modern placement is in Amoebozoa (Arcellinida), not Animalia."
T("difflugia", "Difflugia", [r"\bDifflugia\w*"], kingdom="Protozoa", ncbi_kw="Amoebozoa", group="protist", notes=AMOEB)
T("arcella", "Arcella", kingdom="Protozoa", ncbi_kw="Amoebozoa", group="protist", notes=AMOEB)
T("quadrula", "Quadrulella", [r"\bQuadrula\b"], kingdom="Protozoa", ncbi_kw="Amoebozoa", group="protist",
  notes=AMOEB + " Thompson's 'Quadrula' (after Rhumbler) is the testate amoeba now called Quadrulella, not the unionid mussel genus Quadrula.")
T("amoeba", "Amoeba", kingdom="Protozoa", ncbi_kw="Amoebozoa", group="protist", notes=AMOEB.replace("rhizopod", "amoeba").replace(" (Arcellinida)", ""))
T("actinosphaerium", "Actinosphaerium", kingdom="Protozoa", ncbi_kw="Heliozoa|Actinosphaerium", group="protist",
  notes="Thompson's heliozoan; modern placement Actinophryida (Stramenopiles), not Animalia.")
T("acanthocystis", "Acanthocystis", kingdom="Protozoa", ncbi_kw="Centroplasthelida|Acanthocystis", group="protist",
  notes="Thompson's heliozoan; modern placement Centroplasthelida (Haptista), not Animalia.")
T("clathrulina", "Clathrulina", kingdom="Protozoa", ncbi_kw="Cercozoa|Clathrulina", group="protist",
  notes="Thompson's heliozoan with a chitin-like lattice shell; modern placement Desmothoracida (Cercozoa), not Animalia.")
T("heliozoa", "Heliozoa", [r"\b[Hh]eliozoa\w*"], kingdom="Protozoa", ncbi_kw="Heliozoa", group="protist",
  notes="Polyphyletic protist grouping Thompson treats as animals; not Animalia.")
T("ciliophora", "Ciliophora", [r"\b[Cc]iliated? Infusoria\b", r"\b[Ii]nfusoria\b", r"\b[Cc]iliate(?:s|d)?\b(?= (?:or|and) flagellate)",
                                r"\bciliate or flagellate cells\b"],
  kingdom="Chromista", ncbi_kw="Ciliophora", group="protist",
  notes="Thompson's 'Infusoria' / ciliates; modern phylum Ciliophora (Alveolata), not Animalia.")
T("vorticella", "Vorticella", kingdom="Chromista", ncbi_kw="Ciliophora", group="protist",
  notes="Peritrich ciliate Thompson treats as an animal; modern placement Ciliophora, not Animalia.")

# ---------------------------------------------------------------- Porifera
T("porifera", "Porifera", [r"\b[Ss]ponges?\b", r"\bPorifera\b"], rank="phylum", kingdom="Animalia", group="sponge", vern=["sponges"])
T("calcarea", "Calcarea", [r"\bcalcareous sponges\b"], rank="class", phylum="Porifera", group="sponge", vern=["calcareous sponges"])
T("hexactinellida", "Hexactinellida", [r"\b[Hh]exactinellid\w*"], rank="class", phylum="Porifera", group="sponge", vern=["glass sponges"])
T("demospongiae", "Demospongiae", [r"\bMonaxonid sponges\b"], rank="class", phylum="Porifera", group="sponge",
  notes="Thompson's 'Monaxonid sponges' is an obsolete order (Monaxonida) of Demospongiae; resolved to the class.")
T("tetractinellida", "Tetractinellida", [r"\bTetractinellid(?:ae|a)\b", r"\btetractinellid sponges\b"], rank="order", phylum="Porifera", group="sponge")
T("grantia", "Grantia", phylum="Porifera", marine=True, group="sponge")
T("astrosclera", "Astrosclera", phylum="Porifera", marine=True, group="sponge")
T("hyalonema", "Hyalonema", phylum="Porifera", marine=True, group="sponge")
T("euplectella", "Euplectella", phylum="Porifera", marine=True, group="sponge")
T("farrea", "Farrea", phylum="Porifera", marine=True, group="sponge")

# ---------------------------------------------------------------- Cnidaria / Ctenophora
T("cnidaria", "Cnidaria", [r"\b[Cc]oelenterat\w*"], rank="phylum", kingdom="Animalia", group="cnidarian",
  notes="Thompson's 'Coelenterata' (which historically also embraced the Ctenophora); resolved to Cnidaria.")
T("anthozoa", "Anthozoa", [r"\b[Cc]orals?\b", r"\bcorallites?\b", r"\bcolonial corals\b"], rank="class", phylum="Cnidaria", group="cnidarian", vern=["corals"])
T("octocorallia", "Octocorallia", [r"\bAlcyonari\w*"], rank="subclass", phylum="Cnidaria", group="cnidarian",
  notes="Thompson's 'Alcyonaria' = modern Octocorallia.")
T("alcyonium", "Alcyonium", phylum="Cnidaria", marine=True, group="cnidarian")
T("siphonogorgia", "Siphonogorgia", phylum="Cnidaria", marine=True, group="cnidarian")
T("anthogorgia", "Anthogorgia", phylum="Cnidaria", marine=True, group="cnidarian")
T("eunicea", "Eunicea", phylum="Cnidaria", marine=True, group="cnidarian")
T("heliopora", "Heliopora", phylum="Cnidaria", marine=True, group="cnidarian")
T("podocoryna", "Podocoryna", [r"\bPodocoryne\b"], phylum="Cnidaria", marine=True, group="cnidarian", notes="Written 'Podocoryne'.")
T("hydractinia", "Hydractinia", phylum="Cnidaria", marine=True, group="cnidarian")
T("myxozoa", "Myxozoa", [r"\bActinomyxidia\b"], kingdom="Animalia", phylum="Cnidaria", ncbi_kw="Myxozoa", group="cnidarian",
  notes="Thompson's 'parasitic protozoa, the Actinomyxidia' are the actinospore stage of Myxozoa, now known to be cnidarian animals.")
T("rugosa", "Rugosa", [r"\bTetracoralla\b", r"\bRugosa\b"], kingdom="Animalia", phylum="Cnidaria", fossil=True, group="cnidarian",
  notes="Extinct Palaeozoic corals; Thompson's 'Tetracoralla'.")
T("heterophyllia", "Heterophyllia", [r"\bHeterophylli\w*(?: angulata)?"], phylum="Cnidaria", fossil=True, group="cnidarian")
T("zaphrentis", "Zaphrentis", phylum="Cnidaria", fossil=True, group="cnidarian")
T("cyathophyllum", "Cyathophyllum", [r"\bCyathophyllum\b(?: hexagonum)?"], phylum="Cnidaria", fossil=True, group="cnidarian")
T("cyathophyllidae", "Cyathophyllidae", phylum="Cnidaria", fossil=True, group="cnidarian")
T("streptelasma", "Streptelasma", [r"\bStreptoplasma\b"], phylum="Cnidaria", fossil=True, group="cnidarian",
  notes="Thompson writes 'Streptoplasma' (a misspelling of the rugose coral Streptelasma Hall, 1847).")
T("lithostrotion", "Lithostrotion", [r"\bLithostrotion\b(?: Martini)?"], phylum="Cnidaria", fossil=True, group="cnidarian")
T("arachnophyllum", "Arachnophyllum", [r"\bArachnophyllum\b(?: pentagonum)?"], phylum="Cnidaria", fossil=True, group="cnidarian")
T("heliolites", "Heliolites", phylum="Cnidaria", fossil=True, group="cnidarian")
T("synhelia", "Synhelia", phylum="Cnidaria", fossil=True, group="cnidarian")
T("oculinidae", "Oculinidae", phylum="Cnidaria", marine=True, group="cnidarian")
T("phillipsastrea", "Phillipsastrea", [r"\bPhillipsastraea\b"], phylum="Cnidaria", fossil=True, group="cnidarian", notes="Written 'Phillipsastraea'.")
T("thamnasteria", "Thamnasteria", [r"\bThamnastraea\b"], phylum="Cnidaria", fossil=True, group="cnidarian", notes="Written 'Thamnastraea'.")
T("comoseris", "Comoseris", phylum="Cnidaria", fossil=True, group="cnidarian")
T("fungiidae", "Fungiidae", [r"\bFungida\b"], phylum="Cnidaria", marine=True, group="cnidarian", notes="Thompson's '(Fungida)' for Thamnastraea; resolved to the family Fungiidae.")
T("monticulipora", "Monticulipora", [r"\bMonticulipor\w*"], phylum="Bryozoa", fossil=True, group="bryozoan",
  notes="Thompson lists 'Monticuliporae' among corals; Monticulipora is a Palaeozoic trepostome bryozoan.")
T("ctenophora", "Ctenophora", [r"\b[Cc]tenophores?\b"], rank="phylum", kingdom="Animalia", group="ctenophore")
T("leucothea", "Leucothea", [r"\bEucharis\b"], phylum="Ctenophora", marine=True, group="ctenophore",
  notes="Thompson's ctenophore 'Eucharis' (Eucharis multicornis) is now Leucothea multicornis.")

# ---------------------------------------------------------------- Echinodermata
T("echinodermata", "Echinodermata", [r"\b[Ee]chinoderms?\b"], rank="phylum", kingdom="Animalia", group="echinoderm")
T("echinoidea", "Echinoidea", [r"\bsea-urchins?\b", r"\bEchinids?\b"], rank="class", phylum="Echinodermata", group="echinoderm", vern=["sea urchins"])
T("echinus", "Echinus", phylum="Echinodermata", marine=True, group="echinoderm")
T("holothuroidea", "Holothuroidea", [r"\b[Hh]olothur\w*"], rank="class", phylum="Echinodermata", group="echinoderm", vern=["sea cucumbers"])
T("ophiuroidea", "Ophiuroidea", [r"\bOphiurids?\b"], rank="class", phylum="Echinodermata", group="echinoderm", vern=["brittle stars"])
T("ophiura", "Ophiura", phylum="Echinodermata", marine=True, group="echinoderm")
T("asterina", "Asterina", phylum="Echinodermata", marine=True, group="echinoderm")

# ---------------------------------------------------------------- Mollusca: higher groups
T("mollusca", "Mollusca", [r"\b[Mm]ollusca\b", r"\b[Mm]olluscs?\b", r"\bmolluscan\b"], rank="phylum", kingdom="Animalia", group="mollusc")
T("gastropoda", "Gastropoda", [r"\b[Gg]astropods?\b", r"\bGastropoda\b", r"\b[Ss]nails?\b", r"\bsnail-shell\b"], rank="class", phylum="Mollusca", group="mollusc", vern=["snails"])
T("bivalvia", "Bivalvia", [r"\b[Ll]amellibranch\w*", r"\b[Bb]ivalves?\b(?! carapace| shell of)", r"\bbivalve shells?\b"], rank="class", phylum="Mollusca", group="mollusc", vern=["bivalves", "lamellibranchs"])
T("cephalopoda", "Cephalopoda", [r"\b[Cc]ephalopods?\b", r"\bCephalopoda\b", r"\bcuttle-?fish(?:es)?\b"], rank="class", phylum="Mollusca", group="mollusc")
T("pteropoda", "Pteropoda", [r"\b[Pp]teropods?\b"], kingdom="Animalia", phylum="Mollusca", group="mollusc", notes="Pelagic sea-butterflies; modern order Pteropoda.")
T("dentalium", "Dentalium", [r"\bDentalium\b"], phylum="Mollusca", marine=True, group="mollusc", vern=["tusk shells"])
T("patellogastropoda", "Patellogastropoda", [r"\b[Ll]impets?\b"], kingdom="Animalia", phylum="Mollusca", group="mollusc", vern=["limpets"],
  notes="'the Limpet' resolved to the true limpets.")

# Cephalopods
T("nautilus", "Nautilus", [r"\bNautilus\b(?! pompilius| umbilicatus)", r"\b[Nn]autiloid\w*"], phylum="Mollusca", marine=True, fossil=True, group="mollusc")
T("nautilus-pompilius", "Nautilus pompilius", [r"\bNautilus pompilius\b", r"\bN\. pompilius\b"], phylum="Mollusca", marine=True, group="mollusc")
T("nautilus-umbilicatus", "Nautilus umbilicatus", [r"\bNautilus umbilicatus\b", r"\bN\. umbilicatus\b"], phylum="Mollusca", marine=True, group="mollusc",
  notes="Nautilus umbilicatus (Lister / Lamarck) is an unaccepted name; WoRMS gives the accepted name.")
T("ammonoidea", "Ammonoidea", [r"\b[Aa]mmonites?\b(?! \(| \_)", r"\bAmmonitoid\w*", r"\bammonitoid\b", r"\bAmmonoidea\b", r"\bAptych\w*", r"\bAnaptychus\b"],
  rank="subclass", phylum="Mollusca", fossil=True, group="mollusc",
  notes="Thompson's 'Ammonites' (as a genus) and 'Ammonitoid shells'; resolved to the extinct subclass Ammonoidea. The aptychus is an ammonoid structure.")
T("arcestes", "Arcestes", [r"\bArcestes\b(?: tornatus)?"], phylum="Mollusca", fossil=True, group="mollusc")
T("oecotraustes", "Oecotraustes", [r"\bOekotraustes\b"], phylum="Mollusca", fossil=True, group="mollusc", notes="Written 'Oekotraustes'.")
T("scaphites", "Scaphites", phylum="Mollusca", fossil=True, group="mollusc")
T("macroscaphites", "Macroscaphites", phylum="Mollusca", fossil=True, group="mollusc")
T("ancyloceras", "Ancyloceras", phylum="Mollusca", fossil=True, group="mollusc")
T("lituites", "Lituites", phylum="Mollusca", fossil=True, group="mollusc")
T("orthoceras", "Orthoceras", [r"\bOrthocera\w*"], phylum="Mollusca", fossil=True, group="mollusc", notes="'Orthocerata' = orthoconic nautiloids; resolved to Orthoceras.")
T("goniatites", "Goniatites", phylum="Mollusca", fossil=True, group="mollusc")
T("sonninia", "Sonninia", [r"\bSonninia\b"], phylum="Mollusca", fossil=True, group="mollusc")
T("pinacoceras", "Pinacoceras", phylum="Mollusca", fossil=True, group="mollusc")
T("belemnitida", "Belemnitida", [r"\bBelemnites\b"], phylum="Mollusca", fossil=True, group="mollusc", notes="'the Belemnites' resolved to the order.")
T("argonauta", "Argonauta", [r"\bArgonauta?\b"], phylum="Mollusca", marine=True, group="mollusc")
T("spirula", "Spirula", phylum="Mollusca", marine=True, group="mollusc")
T("sepia", "Sepia", phylum="Mollusca", marine=True, group="mollusc")
T("loligo", "Loligo", phylum="Mollusca", marine=True, group="mollusc")
T("illex", "Illex", phylum="Mollusca", marine=True, group="mollusc")
T("todarodes", "Todarodes", phylum="Mollusca", marine=True, group="mollusc")

# Gastropods
T("haliotis", "Haliotis", [r"\bHaliotis\b(?: excavatus| parvus| rugoso-plicata| viridis)?"], phylum="Mollusca", marine=True, group="mollusc")
T("turritella", "Turritella", [r"\bTurritella\b(?: terebellata| imbricata| duplicata| carinata)?"], phylum="Mollusca", marine=True, group="mollusc")
T("turbo", "Turbo", [r"\bTurbo\b(?: duplicatus| phasianus)?"], phylum="Mollusca", marine=True, group="mollusc")
T("tonna", "Tonna", [r"\bDolium\b(?: perdix| zonatum)?"], phylum="Mollusca", marine=True, group="mollusc", worms_name="Dolium", notes="Thompson's 'Dolium' = Tonna.")
T("nerita", "Nerita", phylum="Mollusca", marine=True, group="mollusc")
T("trochus", "Trochus", [r"\bTroch(?:us|i)\b(?: niloticus)?", r"\bT\. niloticus\b", r"\bT\. zizyphinus\b"], phylum="Mollusca", marine=True, group="mollusc")
T("harpa", "Harpa", phylum="Mollusca", marine=True, group="mollusc")
T("cypraea", "Cypraea", [r"\bCypraeae?\b"], phylum="Mollusca", marine=True, group="mollusc")
T("natica", "Natica", [r"\bNatica\b(?: aperta| glaucina)?"], phylum="Mollusca", marine=True, group="mollusc")
T("architectonica", "Architectonica", [r"\bSolarium\b(?: perspectivum| trochleare| magnificum)?"], phylum="Mollusca", marine=True, group="mollusc",
  worms_name="Solarium", notes="Thompson's 'Solarium' (Lamarck, 1799) = Architectonica (sundial shells).")
T("cerithium", "Cerithium", [r"\bCerithium\b(?: nodulosum| nodosum| palustre| lignitarum| sulcatum)?"], phylum="Mollusca", marine=True, group="mollusc")
T("planorbis", "Planorbis", [r"\bPlanorbis\b(?: corneus| corneas)?"], phylum="Mollusca", group="mollusc", notes="Freshwater ramshorn snails; 'Planorbis corneas' is a misprint for P. corneus.")
T("helix", "Helix", [r"(?<!cylindrical )\bHelix\b(?: nemoralis)?"], phylum="Mollusca", group="mollusc", notes="'Helix nemoralis' is now Cepaea nemoralis.")
T("epitonium", "Epitonium", [r"\bScalaria\b(?: pretiosa)?", r"\bScalaria$"], phylum="Mollusca", marine=True, group="mollusc", worms_name="Scalaria",
  notes="Thompson's 'Scalaria' = Epitonium (wentletraps).")
T("pupa", "Pupa", [r"\bPupae?\b(?! stage)"], phylum="Mollusca", group="mollusc", worms_name="Pupa",
  notes="Land snails 'Pupa' (Draparnaud) in Thompson's sense are now Pupilla / Pupillidae; the marine genus Pupa Röding is a different animal. See report.")
T("clausilia", "Clausilia", phylum="Mollusca", group="mollusc")
T("patella", "Patella", phylum="Mollusca", marine=True, group="mollusc")
T("bulimus", "Bulimus", [r"\bBulimi\b"], phylum="Mollusca", group="mollusc", notes="Thompson's 'Bulimi' (Bulimus, land snails); an obsolete genus.")
T("conus", "Conus", [r"\bConus\b(?: virgo| litteratus| betulina| gloria-maris)?", r"\bCones\b"], phylum="Mollusca", marine=True, group="mollusc")
T("lamellaria", "Lamellaria", [r"\bLamellaria\b(?: perspicua)?"], phylum="Mollusca", marine=True, group="mollusc")
T("cassis", "Cassis", phylum="Mollusca", marine=True, group="mollusc")
T("littorina", "Littorina", [r"\bLittorina\b", r"\b[Pp]eriwinkles?\b"], phylum="Mollusca", marine=True, group="mollusc", vern=["periwinkle"])
T("babylonia", "Babylonia", [r"\bEburnea\b"], phylum="Mollusca", marine=True, group="mollusc", worms_name="Eburna",
  notes="Thompson's 'Eburnea' (Eburna Lamarck) = Babylonia.")
T("trophon", "Trophon", phylum="Mollusca", marine=True, group="mollusc")
T("fusus", "Fusus", [r"\bFusus\b(?: longissimus| antiquus| colosseus)?"], phylum="Mollusca", marine=True, group="mollusc")
T("buccinum", "Buccinum", [r"\bBuccinum\b", r"\b[Ww]helks?\b"], phylum="Mollusca", marine=True, group="mollusc", vern=["whelk"])
T("cyclostoma", "Cyclostoma", phylum="Mollusca", group="mollusc", notes="Land operculate snail; Cyclostoma Lamarck = Pomatias in current usage.")
T("potamides", "Potamides", phylum="Mollusca", marine=True, group="mollusc")
T("oliva", "Oliva", phylum="Mollusca", marine=True, group="mollusc")
T("stomatella", "Stomatella", phylum="Mollusca", marine=True, group="mollusc")
T("capulus", "Capulus", [r"\bPileopsis\b"], phylum="Mollusca", marine=True, group="mollusc", worms_name="Pileopsis", notes="Thompson's 'Pileopsis' = Capulus.")
T("sinum", "Sinum", [r"\bSigaretus\b(?: haliotoideus)?"], phylum="Mollusca", marine=True, group="mollusc", worms_name="Sigaretus", notes="Thompson's 'Sigaretus' = Sinum.")
T("fissurella", "Fissurella", phylum="Mollusca", marine=True, group="mollusc")
T("emarginula", "Emarginula", phylum="Mollusca", marine=True, group="mollusc")
T("calyptraea", "Calyptraea", phylum="Mollusca", marine=True, group="mollusc")
T("succinea", "Succinea", phylum="Mollusca", group="mollusc")
T("cymba", "Cymba", phylum="Mollusca", marine=True, group="mollusc", notes="Cymba Broderip (volutes) is now treated as a synonym of Cymbium / Melo.")
T("melo", "Melo", [r"\bMelo\b(?: ethiopicus)?"], phylum="Mollusca", marine=True, group="mollusc")
T("eulima", "Eulima", phylum="Mollusca", marine=True, group="mollusc")
T("ampullaria", "Pomacea", [r"\bAmpullaria\b", r"\bApple-snails\b"], phylum="Mollusca", group="mollusc", worms_name="Ampullaria",
  notes="Thompson's 'Ampullaria, or Apple-snails'; Ampullaria Lamarck is an unavailable/suppressed name, apple snails are Ampullariidae (Pomacea, Pila).")
T("phasianella", "Phasianella", [r"\bPhasianella\b(?: bulloides)?"], phylum="Mollusca", marine=True, group="mollusc")
T("crepidula", "Crepidula", phylum="Mollusca", marine=True, group="mollusc")
T("telescopium", "Telescopium", [r"\bTelescopium\b(?: fuscum)?"], phylum="Mollusca", marine=True, group="mollusc")
T("terebra", "Terebra", [r"\bTerebra\b(?: maculata| dimidiata)?", r"\bAcus\b(?: subulatus| crenulatus| dimidiatus)?"], phylum="Mollusca", marine=True, group="mollusc",
  notes="'Acus' (Humphrey) is an old name for auger shells now in Terebra / Oxymeris.")
T("melanopsis", "Melanopsis", [r"\bMelanopsis\b(?: terebralis)?"], phylum="Mollusca", group="mollusc")
T("mitra", "Mitra", [r"\bMitra\b(?: episcopalis)?"], phylum="Mollusca", marine=True, group="mollusc")
T("pleurotomaria", "Pleurotomaria", [r"\bPleurotomaria\b(?: conoidea)?"], phylum="Mollusca", fossil=True, group="mollusc")
T("helicostyla", "Helicostyla", [r"\bHelicostyla\b(?: polychroa)?"], phylum="Mollusca", group="mollusc")
T("euomphalus", "Euomphalus", [r"\bEuomphalus\b(?: pentangulatus)?"], phylum="Mollusca", fossil=True, group="mollusc")
T("solaropsis", "Solaropsis", [r"\bSolaropsis\b(?: pellis-serpentis)?"], phylum="Mollusca", group="mollusc")
T("angaria", "Angaria", [r"\bDelphinula\b(?: atrata)?"], phylum="Mollusca", marine=True, group="mollusc", worms_name="Delphinula",
  notes="Thompson's 'Delphinula' = Angaria.")
T("bellerophon", "Bellerophon", [r"\bBellerophon\b(?: expansus)?"], phylum="Mollusca", fossil=True, group="mollusc")
T("charonia", "Charonia", [r"\bTriton corrugatus\b"], phylum="Mollusca", marine=True, group="mollusc", worms_name="Triton",
  notes="'Triton corrugatus Lam.' is a triton shell now placed in Charonia (Triton Montfort is a preoccupied name).")
# Pteropods
T("cavolinia", "Cavolinia", [r"\bHyalaea\b(?: trispinosa| longirostris)?", r"\bH\. (?:globulosa|trispinosa)\b", r"\bCavolinia\b", r"\bPleuropus\b(?: longifilis)?"],
  phylum="Mollusca", marine=True, group="mollusc", notes="Thompson's 'Hyalaea' = Cavolinia; 'Pleuropus longifilis' is a juvenile stage of Cavolinia tridentata.")
T("cleodora", "Clio", [r"\bCleodora\b(?: cuspidata| chierchiae| australis)?", r"\bClio\b"], phylum="Mollusca", marine=True, group="mollusc", worms_name="Cleodora",
  notes="Thompson's 'Cleodora' (Péron & Lesueur) is a synonym of Clio.")
T("cuvierina", "Cuvierina", [r"\bCuvierina\b(?: columnella)?"], phylum="Mollusca", marine=True, group="mollusc")
T("creseis", "Creseis", phylum="Mollusca", marine=True, group="mollusc")
T("limacina", "Limacina", phylum="Mollusca", marine=True, group="mollusc")
T("peraclis", "Peracle", [r"\bPeraclis\b"], phylum="Mollusca", marine=True, group="mollusc", worms_name="Peraclis", notes="Written 'Peraclis'; accepted genus Peracle.")

# Bivalves
T("anomia", "Anomia", phylum="Mollusca", marine=True, group="mollusc")
T("lima", "Lima", phylum="Mollusca", marine=True, family="Limidae", group="mollusc")
T("solen", "Solen", [r"\bSolen\b(?: pellucidus)?"], phylum="Mollusca", marine=True, group="mollusc")
T("gryphaea", "Gryphaea", phylum="Mollusca", fossil=True, group="mollusc")
T("caprinula", "Caprinula", [r"\bCaprinella\b(?: adversa)?"], phylum="Mollusca", fossil=True, group="mollusc", pbdb_name="Caprinula",
  notes="Thompson's rudist 'Caprinella adversa' (d'Orbigny) is Caprinula adversa; Caprinella is a junior name.")
T("glossus", "Glossus", [r"\bIsocardia\b(?: cor)?"], phylum="Mollusca", marine=True, group="mollusc", worms_name="Isocardia", notes="Thompson's 'Isocardia cor' = Glossus humanus.")
T("diceras", "Diceras", phylum="Mollusca", fossil=True, group="mollusc")
T("hippopus", "Hippopus", phylum="Mollusca", marine=True, group="mollusc")
T("tridacna", "Tridacna", phylum="Mollusca", marine=True, group="mollusc")
T("cardiidae", "Cardiidae", [r"\b[Cc]ockles?\b"], rank="family", phylum="Mollusca", group="mollusc", vern=["cockles"])
T("pholas", "Pholas", phylum="Mollusca", marine=True, group="mollusc")
T("mya", "Mya", [r"\bMya\b"], phylum="Mollusca", marine=True, group="mollusc")
T("sphaerium", "Sphaerium", [r"\bCyclas\b"], phylum="Mollusca", group="mollusc", notes="Thompson's 'Cyclas' (freshwater pea clams) = Sphaerium.")
T("dosinia", "Dosinia", [r"\bArtemis\b"], phylum="Mollusca", marine=True, group="mollusc", worms_name="Artemis", notes="Thompson's 'Artemis' (Poli) = Dosinia.")
T("anodonta", "Anodonta", [r"\bAnodon\b"], phylum="Mollusca", group="mollusc", notes="Written 'Anodon'.")
T("lithocardium", "Lithocardium", phylum="Mollusca", fossil=True, group="mollusc")
T("mactra", "Mactra", phylum="Mollusca", marine=True, group="mollusc")
T("gervillia", "Gervillia", [r"\bGervillea\b"], phylum="Mollusca", fossil=True, group="mollusc", notes="Written 'Gervillea'.")
T("perna", "Perna", phylum="Mollusca", marine=True, group="mollusc")
T("pteria", "Pteria", [r"\bAvicula\b"], phylum="Mollusca", marine=True, group="mollusc", worms_name="Avicula", notes="Thompson's 'Avicula' = Pteria.")
T("modiolus", "Modiolus", [r"\bModiola\b"], phylum="Mollusca", marine=True, group="mollusc", worms_name="Modiola", notes="Written 'Modiola'.")
T("mytilus", "Mytilus", phylum="Mollusca", marine=True, group="mollusc")
T("pecten", "Pecten", phylum="Mollusca", marine=True, group="mollusc")
T("solecurtus", "Solecurtus", phylum="Mollusca", marine=True, group="mollusc")
T("cultellus", "Cultellus", phylum="Mollusca", marine=True, group="mollusc")
T("gari", "Gari", [r"\bPsammobia\b"], phylum="Mollusca", marine=True, group="mollusc", worms_name="Psammobia", notes="Thompson's 'Psammobia' = Gari.")
T("ostreidae", "Ostreidae", [r"\bOstreidae\b", r"\b[Oo]ysters?\b"], rank="family", phylum="Mollusca", group="mollusc", vern=["oysters"])
T("tellina", "Tellina", phylum="Mollusca", marine=True, group="mollusc")
T("unio", "Unio", phylum="Mollusca", group="mollusc")

# ---------------------------------------------------------------- Brachiopoda
T("brachiopoda", "Brachiopoda", [r"\b[Bb]rachiopods?\b", r"\bBrachiopoda\b"], rank="phylum", kingdom="Animalia", group="brachiopod")
T("spirifer", "Spirifer", phylum="Brachiopoda", fossil=True, group="brachiopod")
T("spiriferidae", "Spiriferidae", phylum="Brachiopoda", fossil=True, group="brachiopod")
T("atrypa", "Atrypa", [r"\bAtrypas?\b"], phylum="Brachiopoda", fossil=True, group="brachiopod")
T("atrypidae", "Atrypidae", phylum="Brachiopoda", fossil=True, group="brachiopod")
T("athyridae", "Athyrididae", [r"\bAthyridae\b"], phylum="Brachiopoda", fossil=True, group="brachiopod", notes="Written 'Athyridae'; the family is Athyrididae.")
T("orthis", "Orthis", phylum="Brachiopoda", fossil=True, group="brachiopod")
T("lingula", "Lingula", phylum="Brachiopoda", marine=True, fossil=True, group="brachiopod")
T("pentamerus", "Pentamerus", [r"\bPentameri\b"], phylum="Brachiopoda", fossil=True, group="brachiopod", notes="Written 'the Pentameri'.")
T("productus", "Productus", phylum="Brachiopoda", fossil=True, group="brachiopod")
T("strophomena", "Strophomena", phylum="Brachiopoda", fossil=True, group="brachiopod")
T("terebratula", "Terebratula", [r"\bTerebratulae?\b"], phylum="Brachiopoda", marine=True, fossil=True, group="brachiopod")
T("rhynchonella", "Rhynchonella", phylum="Brachiopoda", fossil=True, group="brachiopod")
T("megathiris", "Megathiris", [r"\bArgiope\b"], phylum="Brachiopoda", marine=True, group="brachiopod", worms_name="Argiope",
  notes="Thompson's brachiopod 'Argiope' (Deslongchamps) is Megathiris; Argiope Audouin is the orb-weaver spider.")
T("cyrtina", "Cyrtina", phylum="Brachiopoda", fossil=True, group="brachiopod")
T("reticularia", "Reticularia", phylum="Brachiopoda", fossil=True, group="brachiopod", pbdb_name="Reticularia",
  notes="The brachiopod Reticularia M'Coy, 1844 (not the slime mould Reticularia Bulliard).")
T("koninckina", "Koninckina", phylum="Brachiopoda", fossil=True, group="brachiopod")
T("thecidium", "Thecidellina", [r"\bThecidium\b"], phylum="Brachiopoda", marine=True, fossil=True, group="brachiopod", worms_name="Thecidium", pbdb_name="Thecidium",
  notes="Thompson's 'Thecidium' (Thecidea / Thecidium) is an old name for recent thecideide brachiopods (Thecidellina, Lacazella).")

# ---------------------------------------------------------------- Annelida and other worms
T("annelida", "Annelida", [r"\b[Aa]nnelids?\b", r"\btube worms\b"], rank="phylum", kingdom="Animalia", group="worm")
T("nereis", "Nereis", phylum="Annelida", marine=True, group="worm")
T("spirorbis", "Spirorbis", phylum="Annelida", marine=True, group="worm")
T("sabella", "Sabella", [r"\bSpirographis\b"], phylum="Annelida", marine=True, group="worm", worms_name="Spirographis",
  notes="Thompson's 'Spirographis' (Spirographis spallanzanii) = Sabella spallanzanii.")
T("ditrupa", "Ditrupa", phylum="Annelida", marine=True, group="worm")
T("lumbricidae", "Lumbricidae", [r"\bearthworm\b"], rank="family", phylum="Annelida", group="worm", vern=["earthworm"],
  notes="'earthworm' resolved to the family of common earthworms.")
T("trematoda", "Trematoda", [r"\btrematode\b"], rank="class", phylum="Platyhelminthes", group="worm")
T("cestoda", "Cestoda", [r"\bcestode\b"], rank="class", phylum="Platyhelminthes", group="worm")
T("rotifera", "Rotifera", [r"\bRotifers?\b"], rank="phylum", kingdom="Animalia", group="worm")

# ---------------------------------------------------------------- Arthropoda
T("insecta", "Insecta", [r"\b[Ii]nsects?\b"], rank="class", phylum="Arthropoda", group="arthropod")
T("apis-mellifera", "Apis mellifera", [r"\bhive-bee\b", r"\b[Bb]ees?\b"], phylum="Arthropoda", group="arthropod",
  vern=["honey bee", "hive-bee"], notes="Thompson's 'hive-bee' / 'the bee'.")
T("melipona", "Melipona", [r"\bMelipona\b(?: domestica)?"], phylum="Arthropoda", group="arthropod",
  notes="'Melipona domestica' is Darwin's name for a stingless bee; GBIF has no accepted species of that name, resolved to the genus.")
T("vespidae", "Vespidae", [r"\b[Ww]asps?\b"], rank="family", phylum="Arthropoda", group="arthropod", vern=["wasps"])
T("odonata", "Odonata", [r"\bdragon-flies\b"], rank="order", phylum="Arthropoda", group="arthropod", vern=["dragonflies"])
T("trichoptera", "Trichoptera", [r"\bcaddis-worms\b"], rank="order", phylum="Arthropoda", group="arthropod", vern=["caddis flies"])
T("cossus-cossus", "Cossus cossus", [r"\bGoatmoth\b", r"\bCossus ligniperda\b"], phylum="Arthropoda", group="arthropod", vern=["goat moth"],
  notes="'Cossus ligniperda' is a synonym of Cossus cossus.")
T("saturnia-pavonia", "Saturnia pavonia", [r"\bEmperor moth\b"], phylum="Arthropoda", group="arthropod", vern=["emperor moth"],
  notes="'the Emperor moth' of British usage is Saturnia pavonia.")
T("iphiclides-podalirius", "Iphiclides podalirius", [r"\bPapilio podalirius\b"], phylum="Arthropoda", group="arthropod")
T("synanthedon-spheciformis", "Synanthedon spheciformis", [r"\bSesia spheciformis\b"], phylum="Arthropoda", group="arthropod")
T("crustacea", "Crustacea", [r"\b[Cc]rustacea\b", r"\bcrustacean\b"], kingdom="Animalia", phylum="Arthropoda", group="arthropod")
T("brachyura", "Brachyura", [r"\bcrab\b"], phylum="Arthropoda", group="arthropod", vern=["crabs"])
T("branchipus", "Branchipus", phylum="Arthropoda", group="arthropod")
T("estheria", "Estheria", phylum="Arthropoda", cls="Branchiopoda", fossil=True, group="arthropod",
  notes="Thompson's clam shrimp 'Estheria' (Rüppell, 1837); the living species are now in Cyzicus and allies, the name persists for fossils. Not the tachinid fly genus Estheria Robineau-Desvoidy.")

# ---------------------------------------------------------------- Chordata
T("tunicata", "Tunicata", [r"\b[Aa]scidians?\b", r"\bascidian\b"], kingdom="Animalia", phylum="Chordata", group="chordate",
  notes="'Ascidians' resolved to the subphylum Tunicata (class Ascidiacea in older usage).")
T("pyrosoma", "Pyrosoma", phylum="Chordata", marine=True, group="chordate")
T("styela", "Styela", [r"\bCynthia\b(?: partita)?"], phylum="Chordata", marine=True, group="chordate", worms_name="Cynthia",
  notes="Conklin's ascidian 'Cynthia partita' is Styela partita.")
T("vertebrata", "Vertebrata", [r"\b[Vv]ertebrates?\b"], kingdom="Animalia", phylum="Chordata", group="chordate")
T("elasmobranchii", "Elasmobranchii", [r"\belasmobranch fishes\b"], rank="class", phylum="Chordata", group="chordate")
T("actinopterygii", "Actinopterygii", [r"(?<![-\w])\b(?:bony )?fish(?:es)?\b"], rank="class", phylum="Chordata", group="chordate",
  notes="Thompson's 'fish' / 'bony fish' (otoliths, scales, body contour); resolved to the ray-finned fishes, which cover his examples (plaice, cod).")
T("pleuronectes-platessa", "Pleuronectes platessa", [r"\bPlaice\b"], phylum="Chordata", marine=True, group="chordate", vern=["plaice"])
T("gadus-morhua", "Gadus morhua", [r"\bcod\b"], phylum="Chordata", marine=True, group="chordate", vern=["cod"])
T("chaetodontidae", "Chaetodontidae", [r"\bChaetodonts\b"], rank="family", phylum="Chordata", group="chordate", vern=["butterflyfishes"])
T("anura", "Anura", [r"\b[Ff]rogs?\b"], rank="order", phylum="Chordata", group="chordate", vern=["frogs"],
  notes="'the frog' of Rauber's and Roux's egg-segmentation studies is Rana (R. temporaria / R. esculenta); resolved to the order.")
T("pelophylax-esculentus", "Pelophylax esculentus", [r"\bRana esculenta\b"], phylum="Chordata", group="chordate", notes="'Rana esculenta' = Pelophylax kl. esculentus.")
T("reptilia", "Reptilia", [r"\breptiles?\b"], rank="class", phylum="Chordata", group="chordate")
T("serpentes", "Serpentes", [r"\bsnake\b"], phylum="Chordata", group="chordate", vern=["snakes"])
T("chamaeleonidae", "Chamaeleonidae", [r"\bchameleon(?:['’]s)?\b"], rank="family", phylum="Chordata", group="chordate", vern=["chameleons"])
T("aves", "Aves", [r"\bbirds?\b"], rank="class", phylum="Chordata", group="chordate", vern=["birds"])
T("argusianus-argus", "Argusianus argus", [r"\bArgus\b(?:\s+Pheasant)?"], phylum="Chordata", group="chordate", vern=["great argus"])
T("mammalia", "Mammalia", [r"\b[Mm]ammal(?:s|ian)?\b"], rank="class", phylum="Chordata", group="chordate")
T("ruminantia", "Ruminantia", [r"\bruminants?\b"], phylum="Chordata", group="chordate", vern=["ruminants"])
T("ovis-aries", "Ovis aries", [r"\bram's horn\b", r"\bram\b"], phylum="Chordata", group="chordate", vern=["sheep", "ram"], notes="'the ram's horn'.")
T("elephantidae", "Elephantidae", [r"\belephant(?:['’]s)?\b"], rank="family", phylum="Chordata", group="chordate", vern=["elephants"])
T("simiiformes", "Simiiformes", [r"\bmonkey['’]s\b"], phylum="Chordata", group="chordate", vern=["monkeys"], notes="'a monkey's tail'; resolved to the anthropoid primates.")
T("equus-caballus", "Equus caballus", [r"\bhorse\b"], phylum="Chordata", group="chordate", vern=["horse"])
T("homo-sapiens", "Homo sapiens", [r"\ba man\b"], phylum="Chordata", group="chordate", vern=["human"])
T("oryctolagus-cuniculus", "Oryctolagus cuniculus", [r"\brabbit\b"], phylum="Chordata", group="chordate", vern=["rabbit"])
T("rattus", "Rattus", [r"\ba rat\b"], phylum="Chordata", group="chordate", vern=["rats"])
T("felis-catus", "Felis catus", [r"\bcat['’]s\b"], phylum="Chordata", group="chordate", vern=["domestic cat"])

SLUGS = {t["slug"] for t in TAXA}
assert len(SLUGS) == len(TAXA), "duplicate slug"
