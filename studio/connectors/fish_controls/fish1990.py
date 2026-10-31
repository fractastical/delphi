"""Fish 1990 (J Zool 221:391-403) published statistics, transcribed from PAGE IMAGES of the scanned PDF (not from its OCR text, which is wrong in places).

The paper measured 199 preserved specimens (33 species, 6 genera of Exocoetidae; ANSP and USNM) and publishes only reduced-major-axis power-law fits
y = a * M^b (M in kg) and summary ranges. It does NOT publish the per-specimen measurements: raw data unavailable here.

Printed-versus-restored: the scan prints several `a` coefficients without a decimal point (e.g. `0460`). `a_printed` is exactly what is printed; `a` is the value with
the decimal restored. The restoration is checked in the tests by magnitude (standard length at 0.1 kg, wing area at 0.1 kg) and the P marks are checked against the CIs.
Units are not printed in the table headers; they are inferred from magnitude (length and span in m, areas in m^2, mass in kg) and labelled inferred.
"""

GENERA = ["Cypselurus", "Danichthyes", "Exocoetus", "Fodiator", "Hirundichthyes", "Parexocoetus"]   # spelled as printed (Hirundichthyes, Parexocoetus as in the table)
PREDICTED = {"Length": 0.33, "Wing span": 0.33, "Wing area": 0.67, "Hypocaudal area": 0.67}          # geometric scaling, stated in the text (p.395)
UNIT_INFERRED = {"Length": "m (standard length)", "Wing span": "m", "Wing area": "m^2", "Hypocaudal area": "m^2"}

# Table I (journal p.394, PDF p.4): genus -> dimension -> (N, r, a_printed, b, ci_low, ci_high, P_printed)
TABLE_I = {
    "Cypselurus": {"Length": (113, 0.993, "0460", 0.355, 0.347, 0.363, "0.001"), "Wing span": (113, 0.987, "0651", 0.375, 0.364, 0.387, "0.001"),
                   "Wing area": (113, 0.975, "0039", 0.642, 0.616, 0.671, "ns"), "Hypocaudal area": (90, 0.990, "0003", 0.650, 0.630, 0.670, "ns")},
    "Danichthyes": {"Length": (11, 0.996, "0442", 0.336, 0.314, 0.359, "ns"), "Wing span": (11, 0.998, "0.622", 0.310, 0.296, 0.325, "0.02"),
                    "Wing area": (11, 0.980, "0.038", 0.485, 0.416, 0.566, "0002"), "Hypocaudal area": (9, 0.995, "0002", 0.558, 0.510, 0.611, "0.005")},
    "Exocoetus": {"Length": (26, 0.990, "0.462", 0.347, 0.327, 0.369, "ns"), "Wing span": (26, 0.987, "0.774", 0.380, 0.355, 0.407, "0.005"),
                  "Wing area": (26, 0.958, "0.046", 0.741, 0.653, 0.842, "ns"), "Hypocaudal area": (18, 0.986, "0.004", 0.729, 0.665, 0.798, "ns")},
    "Fodiator": {"Length": (9, 0.992, "0.464", 0.333, 0.297, 0.373, "ns"), "Wing span": (9, 0.992, "0476", 0.332, 0.297, 0.373, "ns"),
                 "Wing area": (9, 0.959, "0026", 0.630, 0.481, 0.824, "ns"), "Hypocaudal area": (8, 0.972, "0003", 0.667, 0.522, 0.853, "ns")},
    "Hirundichthyes": {"Length": (21, 0.999, "0.429", 0.314, 0.307, 0.321, "0.001"), "Wing span": (21, 0.995, "0.566", 0.303, 0.290, 0.318, "0.001"),
                       "Wing area": (21, 0.994, "0.026", 0.479, 0.455, 0.505, "0.001"), "Hypocaudal area": (19, 0.995, "0.003", 0.594, 0.565, 0.624, "0.001")},
    "Parexocoetus": {"Length": (19, 0.959, "0.531", 0.366, 0.314, 0.426, "ns"), "Wing span": (19, 0.942, "0.573", 0.353, 0.293, 0.425, "ns"),
                     "Wing area": (19, 0.934, "0.040", 0.736, 0.604, 0.898, "ns"), "Hypocaudal area": (16, 0.926, "0.002", 0.595, 0.469, 0.755, "ns")},
}
# Table II (journal p.395, PDF p.5): wing loading (N/m^2) vs M: genus -> (N, range_min, range_max, r, a, b, ci_low, ci_high, P_printed vs b = 0.33)
TABLE_II = {
    "Cypselurus": (113, 16.1, 205.5, 0.935, 285.015, 0.400, 0.372, 0.430, "0.002"), "Danichthyes": (11, 14.1, 208.9, 0.983, 276.484, 0.533, 0.464, 0.614, "0.001"),
    "Exocoetus": (26, 40.3, 139.2, 0.808, 300.101, 0.360, 0.262, 0.495, "ns"), "Fodiator": (9, 54.4, 138.2, 0.913, 488.222, 0.434, 0.284, 0.663, "ns"),
    "Hirundichthyes": (21, 11.7, 141.9, 0.995, 390.069, 0.526, 0.502, 0.551, "0.001"), "Parexocoetus": (19, 52.3, 113.7, 0.764, 458.083, 0.408, 0.257, 0.649, "ns")}
# Table III (journal p.396, PDF p.6): aspect ratio vs M (dimensionless): genus -> (N, range_min, range_max, r, r_significant, a, b, ci_low, ci_high)  (CI not computed where r is not significant)
TABLE_III = {
    "Cypselurus": (113, 3.0, 12.2, 0.723, True, 12.717, 0.163, 0.136, 0.195), "Danichthyes": (11, 4.6, 11.7, 0.793, True, 11.920, 0.182, 0.094, 0.352),
    "Exocoetus": (26, 8.9, 19.9, 0.211, False, 23.410, 0.195, None, None), "Fodiator": (9, 6.1, 8.9, 0.306, False, 15.991, 0.189, None, None),
    "Hirundichthyes": (21, 5.1, 10.7, 0.890, True, 13.344, 0.144, 0.112, 0.185), "Parexocoetus": (19, 7.1, 12.9, 0.065, False, 2.648, -0.293, None, None)}
# Percentage of wing area from the pectoral fins, mean +/- S.E., as STATED IN THE TEXT (journal pp.396-397, PDF pp.6-7); Table IV itself was not read.
PECTORAL_SHARE_PCT = {"Exocoetus": (91.8, 0.4), "Fodiator": (83.2, 0.7), "Parexocoetus": (81.5, 0.5), "Danichthyes": (77.4, 0.9), "Hirundichthyes": (76.6, 0.9), "Cypselurus": (76.0, 0.6)}
HYPOCAUDAL_SHARE_POOLED_PCT = (63.1, 0.5)
SPECIMENS = {"n": 199, "species": 33, "genera": 6, "mass_range_kg": [0.003, 0.53], "preserved": "70% ethanol", "collections": "Academy of Natural Sciences of Philadelphia; National Museum of Natural History, Washington D.C."}
# Internal inconsistencies in the paper, kept: (1) text says 11.7 N/m^2 is for 'a 0.001 kg Hirundichthyes' but the methods give 0.003 kg as the smallest mass;
# (2) text says individual pectoral-fin aspect ratios range 3.0 to 16.9, Table III lists a range up to 19.9 (Exocoetus).
INCONSISTENCIES = [
    "text: 'Wing loadings ... range from 11.7 N/m2 for a 0.001 kg Hirundichthyes to 208.9 N/m2 for a 0.53 kg Danichthyes' versus methods: specimens range in mass from 0.003 to 0.53 kg",
    "text: 'The aspect ratios (AR) of individual flying fish pectoral fins range from 3.0 to 16.9' versus Table III range up to 19.9 for Exocoetus",
]
