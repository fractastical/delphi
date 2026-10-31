"""The bounded gene set. Roles are this connector's grouping, not a source's classification."""

GENES = {
    # bioelectric / amino-acid-transport candidates for fin proportion (Daane 2021 abstract names kcnh2a and "lat4a")
    "kcnh2a": "bioelectric_proportion", "kcnk5b": "bioelectric_proportion", "kcnj13": "bioelectric_proportion", "ppp3ca": "bioelectric_proportion",
    # candidates for the paper's "lat4a": NOT confirmed (see data/genomics/lat4a_resolution.json)
    "slc43a2a": "lat4a_candidate_unconfirmed", "slc43a2b": "lat4a_candidate_unconfirmed",
    "fgf10a": "fin_development", "fgf20a": "fin_development", "fgf24": "fin_development", "shha": "fin_development", "tbx5a": "fin_development",
    "lef1": "fin_development", "wnt5b": "fin_development", "msx1b": "fin_development", "hoxd13a": "fin_development", "runx2b": "fin_development",
    "sp7": "fin_development", "and1": "fin_development",
    "piezo1": "mechanosensation", "piezo2a": "mechanosensation", "tmc2b": "mechanosensation", "pkd2": "mechanosensation",
}
