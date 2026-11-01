"""Offline tests for the BioModels connector: fail-closed SBML handling and bounded client rules.

The SBML strings below are parser inputs written for these tests, not model data.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from connectors.biomodels import client as cl  # noqa: E402
from connectors.biomodels.sbml import UnsupportedSBML, evaluate, inspect_sbml  # noqa: E402

NS = "http://www.sbml.org/sbml/level2/version4"
MATH = '<math xmlns="http://www.w3.org/1998/Math/MathML">{}</math>'


def sbml(extra="", law="<apply><times/><ci>k</ci><ci>x</ci></apply>", species_attrs='initialConcentration="2"', head=""):
    return f"""<?xml version="1.0"?>{head}
<sbml xmlns="{NS}" level="2" version="4"><model id="m" name="decay">
<listOfCompartments><compartment id="c" size="2" constant="true"/></listOfCompartments>
<listOfSpecies><species id="x" compartment="c" {species_attrs}/></listOfSpecies>
<listOfParameters><parameter id="k" value="0.5" constant="true"/></listOfParameters>
{extra}
<listOfReactions><reaction id="r"><listOfReactants><speciesReference species="x"/></listOfReactants>
<kineticLaw><math xmlns="http://www.w3.org/1998/Math/MathML">{law}</math></kineticLaw></reaction></listOfReactions>
</model></sbml>""".encode()


def test_supported_model_is_evaluated_per_unit_compartment():
    m = inspect_sbml(sbml())
    env = m.initial_env()
    # flux k*x = 1.0 in a compartment of size 2: d[x]/dt = -0.5
    assert m.rhs(m.initial_state(), env) == {"x": pytest.approx(-0.5)}
    assert m.unit_notes, "a model with no units declared must say so"


def test_initial_assignment_and_override_order():
    extra = '<listOfInitialAssignments><initialAssignment symbol="k"><math xmlns="http://www.w3.org/1998/Math/MathML"><ci>j</ci></math></initialAssignment></listOfInitialAssignments>'
    data = sbml(extra).replace(b'<parameter id="k"', b'<parameter id="j" value="3" constant="true"/><parameter id="k"')
    m = inspect_sbml(data)
    assert m.initial_env()["k"] == 3.0
    assert m.initial_env({"j": 4.0})["k"] == 4.0


@pytest.mark.parametrize(
    "data, fragment",
    [
        (sbml('<listOfEvents><event/></listOfEvents>'), "event"),
        (sbml('<listOfRules><algebraicRule/></listOfRules>'), "algebraicRule"),
        (sbml('<listOfRules><rateRule variable="k"/></listOfRules>'), "rateRule"),
        (sbml('<listOfConstraints><constraint/></listOfConstraints>'), "constraint"),
        (sbml(law="<csymbol definitionURL='http://www.sbml.org/sbml/symbols/time'>t</csymbol>"), "csymbol"),
        (sbml(law="<apply><sin/><ci>x</ci></apply>"), "sin"),
        (sbml(law="<apply><ci>undefined_fn</ci><ci>x</ci></apply>"), "undefined"),
        (sbml(species_attrs='initialAmount="2"'), "initialConcentration"),
        (sbml(species_attrs='initialConcentration="2" boundaryCondition="true"'), "boundary"),
        (sbml(head='<!DOCTYPE sbml [<!ENTITY e "x">]>'), "DOCTYPE"),
        (sbml().replace(b'level="2" version="4"', b'level="1" version="2"'), "Level 1"),
        (sbml().replace(b'level="2" version="4"', b'level="3" version="1" xmlns:q="urn:q" q:required="true"'), "required"),
        (b"<notxml", "well-formed"),
        (b"<other/>", "not <sbml>"),
    ],
)
def test_unsupported_constructs_are_refused_by_name(data, fragment):
    with pytest.raises(UnsupportedSBML) as exc:
        inspect_sbml(data)
    assert fragment.lower() in str(exc.value).lower()


def test_negative_control_the_valid_model_is_not_refused():
    inspect_sbml(sbml())


def test_evaluator_arithmetic_matches_known_values():
    node = ("op", "divide", [("num", 1.0), ("op", "plus", [("num", 1.0), ("op", "power", [("sym", "n"), ("num", 2.0)])])])
    assert evaluate(node, {"n": 3.0}, {}) == pytest.approx(0.1)
    with pytest.raises(UnsupportedSBML):
        evaluate(("sym", "missing"), {}, {})


# ---- client -----------------------------------------------------------------------------


def test_urls_outside_the_allow_list_are_refused():
    for url in ("http://www.biomodels.org/x", "https://evil.example/x", "https://www.biomodels.org.evil.example/x"):
        with pytest.raises(cl.ConnectorError):
            cl._check_url(url)
    cl._check_url("https://www.biomodels.org/BIOMD0000001047")


def test_accession_must_match_the_pattern():
    client = cl.BioModelsClient(min_interval=0)
    for bad in ("../etc/passwd", "BIOMD1", "biomd0000001047", "BIOMD0000001047?x=1"):
        with pytest.raises(cl.ConnectorError):
            client.metadata(bad)


class Stub(cl.BioModelsClient):
    def __init__(self, json_by_prefix, body=b""):
        super().__init__(min_interval=0)
        self.json_by_prefix, self.body, self.seen = json_by_prefix, body, []

    def _json(self, url):
        self.seen.append(url)
        for prefix, payload in self.json_by_prefix.items():
            if url.startswith(prefix):
                return payload
        raise AssertionError(url)

    def _get(self, url, cap):
        self.seen.append(url)
        return self.body


def test_search_uses_primary_when_it_reports_a_total():
    c = Stub({cl.BASE + "/search": {"matches": 1, "models": [{"id": "BIOMD0000001047", "name": "Collier"}]}})
    r = c.search("notch")
    assert (r.primary_status, r.total, r.hits[0].accession) == ("ok", 1, "BIOMD0000001047")
    assert all("ebisearch" not in u for u in c.seen)


def test_search_degraded_primary_is_reported_and_falls_back():
    # the observed 2026-10-31 response shape: HTTP 200, matches -1, no models
    c = Stub({
        cl.BASE + "/search": {"matches": -1, "models": []},
        cl.EBI_SEARCH: {"hitCount": 1, "entries": [{"id": "BIOMD0000001047", "fields": {"name": ["Collier1996"]}}]},
    })
    r = c.search("notch")
    assert r.primary_status.startswith("degraded") and "ebisearch" in r.source and r.hits[0].name == "Collier1996"


def _meta(body, **over):
    entry = {"name": "m.xml", "fileSize": str(len(body)), "sha256sum": cl.sha256_bytes(body)} | over
    return {"files": {"main": [entry]}, "history": {"revisions": [{"version": 3}]}, "format": {"name": "SBML", "version": "L2V4"}}


def test_fetch_keeps_a_file_whose_hash_and_size_match(tmp_path):
    body = b"<sbml/>"
    got = Stub({cl.BASE: _meta(body)}, body).fetch("BIOMD0000000001", tmp_path)
    assert Path(got.path).read_bytes() == body and got.sha256 == got.declared_sha256 and got.revision == 3


@pytest.mark.parametrize("tamper", [dict(sha256sum="0" * 64), dict(fileSize="3"), dict(name="../escape.xml"), dict(sha256sum=None)])
def test_fetch_refuses_mismatch_and_unsafe_names(tmp_path, tamper):
    body = b"<sbml/>"
    with pytest.raises(cl.ConnectorError):
        Stub({cl.BASE: _meta(body, **tamper)}, body).fetch("BIOMD0000000001", tmp_path)
    assert not list(tmp_path.iterdir()), "a refused download must leave nothing behind"


def test_licence_record_does_not_claim_the_terms_were_read():
    assert cl.LICENCE.spdx_claimed == "CC0-1.0" and cl.LICENCE.terms_page_read is False
    assert cl.LICENCE.per_model_licence_in_metadata is False
