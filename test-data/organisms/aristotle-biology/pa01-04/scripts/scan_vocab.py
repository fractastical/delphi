#!/usr/bin/env python3
"""Exploration helper: counts of common English animal words in Parts of Animals I-IV."""
import collections
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[5]
lines = (REPO / "claim-sources/aristotle-biology/inputs/pa.txt").read_text(encoding="utf-8").split("\n")[5:481]
text = "\n".join(lines).lower()
words = collections.Counter(re.findall(r"[a-z][a-z\-]+", text))
VOCAB = """ant bee wasp hornet fly flies gnat midge mosquito locust grasshopper cicada beetle scarab moth butterfly flea louse lice
spider scorpion crab lobster crayfish prawn shrimp crawfish oyster mussel cockle scallop snail whelk limpet purple sponge anemone
nettle jellyfish urchin starfish holothuria ascidian octopus poulp cuttle squid calamary nautilus worm earthworm leech centipede
millipede fish eel shark ray skate dogfish torpedo tunny mullet carp sargue sea-perch perch pike frog toad newt salamander lizard
gecko chameleon crocodile tortoise turtle serpent snake viper adder bird hawk eagle kite vulture owl raven crow jackdaw jay magpie
pigeon dove partridge quail fowl cock hen goose duck swan crane heron stork pelican ostrich parrot swallow swift sparrow lark
wryneck woodpecker nightingale cuckoo kingfisher halcyon horse mare colt foal ass mule camel ox oxen bull cow calf sheep ram goat
deer stag hind roe pig swine boar sow dog hound wolf fox jackal lion lioness leopard panther lynx bear hyena weasel marten
ferret badger otter beaver mole mouse mice rat hare rabbit hedgehog porcupine bat ape apes monkey baboon elephant seal dolphin
porpoise whale man men woman women child bison wild-ox antelope oryx gazelle buffalo hippopotamus rhinoceros hippo ichneumon
squirrel dormouse cat bonasus cetacea insects testacea crustacea selachia caterpillar larva grub chrysalis silkworm drone
spider tick mite gadfly horse-fly dung-beetle glow-worm firefly sea-urchin sea-anemone sea-nettle sea-cucumber razor-fish
solen tethya acalephe acalephae sea-lung lamprey sturgeon bream gudgeon scarus glanis sprat anchovy herring mackerel""".split()
for w in sorted(set(VOCAB)):
    for form in (w, w + "s", w + "es"):
        if words.get(form):
            print(f"{form}:{words[form]}", end=" ")
print()
hy = collections.Counter(w for w in words.elements() if "-" in w)
print(" ".join(f"{w}:{n}" for w, n in sorted(hy.items()) if n >= 1 and any(k in w for k in ("sea", "fish", "bird", "fly", "worm", "beetle", "hog", "ox", "dog", "footed", "hoofed"))))
