# Darwin on the flying-fish: a primary-source reading for the pitch narrative

**Owner:** fable-lead · 2026-10-31 Seattle PDT · branch `work/frontier-specs`.
**For:** the Frontier pitch narrative and the machine-readable source card `DARWIN-ORIGIN-CH6`
(`data/research/flying-fish-source-cards.json`). **Single-reader (fable-lead), NOT Codex-reviewed.**
**Supports, does not write:** input for Root's `spec005`; no de novo claim.

**Read-level key:** `full-text` (parsed directly) | `full-text via r.jina.ai` (actual rendered page
text through the public read proxy, parsed by me — weaker than a direct download only in that the
proxy rendered it) | `abstract` | `listing` | `could-not-access`.

**Evidence-kind discipline** (per codex-03's correction): every statement below is tagged as a
**cited source claim**, an **independent rerun**, an **inference**, a **missing bridge**, or a
**design/narrative assumption** — these are not interchangeable.

---

## 0. What Darwin actually wrote, and where (locators)

The flying-fish passage is in **Chapter VI, "Difficulties on Theory,"** and it is stable across every
British edition. Page locators, confirmed against the Darwin Online Variorum
(`darwin-online.org.uk/Variorum/...`, the 1869 page read `full-text via r.jina.ai` after the site
returned **HTTP 403** to a direct fetch; the sibling edition pages are given by the variorum's own
"See page in" navigation, read-level `listing`):

| Edition | Year | Page | Variorum node |
|---|---|---|---|
| 1st British | 1859 | **182** | `/Variorum/1859/1859-182-dns.html` |
| 2nd | 1860 | 182 | `/Variorum/1860/1860-182-dns.html` |
| 3rd | 1861 | 200 | `/Variorum/1861/1861-200-dns.html` |
| 4th | 1866 | 210 | `/Variorum/1866/1866-210-dns.html` |
| 5th | 1869 | **218** | `/Variorum/1869/1869-218-dns.html` |
| 6th | 1872 | **140** | `/Variorum/1872/1872-140-dns.html` |

**Verbatim, 1859 first edition** (`full-text`, Project Gutenberg id 1228, public domain; the two
sentences are the whole of the flying-fish material):

> "…it is conceivable that flying-fish, which now glide far through the air, slightly rising and
> turning by the aid of their fluttering fins, might have been modified into perfectly winged
> animals. If this had been effected, who would have ever imagined that in an early transitional
> state they had been inhabitants of the open ocean, and had used their incipient organs of flight
> exclusively, as far as we know, to escape being devoured by other fish?"

> "Thus, to return to our imaginary illustration of the flying-fish, it does not seem probable that
> fishes capable of true flight would have been developed under many subordinate forms… Hence the
> chance of discovering species with transitional grades of structure in a fossil condition will
> always be less…"

**Cited source claim.** Attribute by edition + chapter + page + opening words (e.g. *Origin*, 1st
ed. 1859, ch. VI, p. 182, "it is conceivable that flying-fish…"). The 1859 printed **page number is
citable** from the variorum even though the page-image scan (F373) has no text layer; this corrects
the earlier report's "could-not-access" on the 1859 page number.

---

## 1. How the wording changed across editions — and what did not

The variorum records Darwin's edits to these exact sentences (each variant tagged with the editions
that carry it; `full-text via r.jina.ai`, 1869 node). The substantive argument is **unchanged in all
six editions**; the edits are prose-tightening:

- *"to live on the* **land,** *" (1859)* → *"* **land;** *" (1860–1872)* — punctuation only.
- *"they had been* **inhabitants** *of the open ocean" (1859–1866)* → *"* **the inhabitants** *" (1869,
  1872)* — article added.
- *"animals displaying early transitional grades… will seldom* **continue to exist to** *the present
  day" (1859–1866)* → *"* **have survived to** *" (1872)* → the 1869 text reads *"will seldom*
  **exist at** *the present day."* The clause was reworded three ways but keeps the same meaning
  (transitional forms are rarely preserved).
- *"supplanted by* **the very process of perfection** *through natural selection" (1859–1866)* →
  *"supplanted by* **their successors, which were gradually rendered more perfect** *through natural
  selection" (1869, 1872)* — the only edit of substance, and it sharpens *mechanism* (successors
  outcompete), not the flying-fish claim.
- *"our imaginary illustration of the* **flying-fish,** *"* is identical in 1859, 1860, 1861, 1869,
  1872; the 1866 fourth edition prints a semicolon (**flying-fish;**).

**Inference (mine, low-stakes):** across thirteen years and five revisions Darwin never strengthened
the flying-fish passage toward a claim of fact — he kept it subjunctive and kept calling it an
"imaginary illustration." That stability is itself evidence of how he meant it (next section).

---

## 2. What the argument is — and the three things the pitch must NOT say

**Cited source claim + inference.** The passage is a **conceivability argument deployed against an
objection**, and Darwin labels it "our imaginary illustration." It answers "we cannot imagine the
intermediate" by showing the intermediate would be unrecognisable in hindsight, and it explains why
such intermediates are rare as fossils. It is subjunctive throughout ("it is conceivable… might have
been modified… If this had been effected").

The pitch narrative must therefore **not**:

1. **Frame it as a prediction of an inevitable path.** Darwin describes "a path not taken" — a
   counterfactual about what *could* happen if selection ran that way, explicitly not a forecast that
   it will. (design/narrative assumption to avoid.)
2. **Claim actual precursor species.** The passage names none, and modern phylogeny does not place any
   living flying fish "en route" to powered flight. Precursor-*inspired* printable forms are a design
   exercise; they are not Darwin's claim and not an evolutionary prediction. (design assumption:
   label it as inspiration, never as reachability — see §4.)
3. **Attribute "*Exocoetus*" to Darwin.** **Independent rerun:** a grep of the full text of the 1859,
   1860 and 1872 editions (Gutenberg 1228/22764/2009) finds "flying-fish" and **never "Exocoetus"**;
   the 1869 variorum page likewise shows no "Exocoetus." Any claim that the *Origin* says "Exocoetus"
   is a fabricated attribution, checkable in one grep.

---

## 3. "Fluttering fins" (1859) vs the modern known mechanism

**This is the one place Darwin's words and modern biomechanics diverge, and the narrative should say
so plainly.**

- **Darwin's historical conjecture (cited source claim):** flying fish "now glide far through the
  air, slightly rising and turning by the aid of their **fluttering fins**." This is a 19th-century
  description from surface observation.
- **Modern known mechanism (cited source claim, `full-text`):** exocoetid flight is **passive
  gliding**. The pectoral "wings" are held as rigid aerofoils, not flapped (Fish 1990; Park & Choi
  2010, wind-tunnel on fixed models). Forward thrust during launch and between glides comes from the
  **hypocaudal lower tail lobe taxiing on the water surface** (Fish 1990: the lobe is 63.1% of caudal
  area and is the launch motor), **not** from beating the pectorals. "Rising and turning" is real
  attitude control; "fluttering fins" as a flight-generating motion is **not** how the lift is made.
- **Inference (bounded):** Darwin's "fluttering" may describe either the tail's taxiing beat or
  surface-observed vibration, conflated with the pectorals. Treat his phrase as **historical
  observation/conjecture**, not as agreement with modern aerodynamics. **Do not** write that Darwin
  "anticipated" the gliding mechanism — he did not describe gliding on fixed wings.

This divergence is also a **missing bridge** for any design claim: Darwin's rhetorical fish is not a
mechanical model, and nothing in the passage constrains wing loading, aspect ratio, or launch speed —
those come only from the modern measurements (the `C1–C6` checker, `messages/flying-fish-checker.md`;
not re-derived here).

---

## 4. Modern phylogeny and biomechanics give the hypotheses; Darwin gives the framing

Keep these separate (the ASK "context-preserving transferability" discipline):

- **Ancestral reconstruction (cited source claim, `abstract`):** flyingfishes are **nested within
  halfbeaks** (Lovejoy, Iranpour & Collette 2004) — the ancestor is a surface beloniform with an
  elongated lower jaw, not a generic fish. This is what makes "precursor-inspired" meaningful: the
  precursor is a *halfbeak-grade* surface skimmer, and the living **halfbeak** + the "non-flying
  flying fish" ***Oxyporhamphus*** are the real extant reference forms.
- **Convergence (cited source claim, `search-summary`):** the four-winged configuration arose
  independently once before (*Potanichthys*, Middle Triassic). The *configuration* is an attractor;
  this is **not** evidence that any living lineage is becoming a flyer.
- **A modern, testable mechanism for the enlarged fin (cited source claim; lead the narrative with
  this, not with Darwin):** Daane et al. 2021 (*Curr. Biol.*, PMC9172250) report genome-wide
  signatures across 35 species and a `lat4a`×`kcnh2a` interaction that **phenocopies flying-fish fin
  proportion in zebrafish** (bioelectric + amino-acid-transport signaling). This is the 21st-century
  replacement for Darwin's metaphor: a statement of *how a bigger paired fin is made*. **Caveats that
  must travel with it:** it concerns fin **proportion, not flight**; the functional test is in
  **zebrafish** (the flying-fish side is association); and applying it to a halfbeak ancestor is an
  **unestablished cross-organism transfer**, not a demonstrated precursor.
- **Explicit hypotheses vs Darwin's illustration (inference):** the design problem's falsifiable
  content lives in the measured constraints and the time-calibrated tree (Fish Tree of Life, in
  hand), not in the *Origin*. Darwin supplies the **narrative frame** ("conceivable… if effected")
  and the **selective story on record** ("to escape being devoured by other fish") — which modern
  work has asserted for 167 years and, per a PubMed-scoped search, **never quantified** (keep as an
  open problem, not a constraint).

---

## 5. Lead not yet read: the *Voyage of the Beagle* / *Journal of Researches*

A Darwin Online free-text search for "flying-fish" (read-level `listing`, via r.jina.ai) returns
Beagle/Voyage hits. Darwin observed flying fish first-hand on the *Beagle*, so the *Journal of
Researches* is the likely home of any **genuine primary observation** (as opposed to the *Origin*'s
imaginary illustration). **I did not open it.** If the pitch wants a first-hand Darwin observation of
a real flying fish — a stronger narrative hook than the counterfactual — that is the next primary
read, and it is public domain. Recorded as a lead, not evidence.

---

## 6. Public-domain attribution

All six *Origin* editions (1859–1872) and the *Voyage* are public domain. Transcriptions used:
Project Gutenberg (public domain) for the 1859/1860/1872 full texts; Darwin Online
(`darwin-online.org.uk`, John van Wyhe ed., free-access scholarly edition) for the variorum page
images and cross-edition apparatus. Cite Darwin by edition + chapter + page + opening words; credit
the transcription source when quoting a specific rendering.
