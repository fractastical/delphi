"""Pressure field -> fin-ray traction -> distributed line load -> beam deflection (one-way, static).

Schemas:
    frontier.coupled.member-pressure/2  the INPUT contract a flow model must publish (contract.py):
                                        one tributary width per station, with geometry provenance
    frontier.coupled.member-pressure/1  the same with one constant width per member; still read, for
                                        members whose width really is constant (an extrusion strip, a
                                        declared uniform rod), never for a fan
    frontier.coupled.member-target/1    the structural member the load is applied to
    frontier.coupled.result/1           one-way coupling result (couple.py)

Every number is SIMULATED or ANALYTIC; nothing here is observed, and a passing unit or
conservation check establishes arithmetic, never biological transfer.
"""
SCHEMA_PRESSURE = "frontier.coupled.member-pressure/1"
SCHEMA_PRESSURE_V2 = "frontier.coupled.member-pressure/2"
SCHEMA_TARGET = "frontier.coupled.member-target/1"
SCHEMA_RESULT = "frontier.coupled.result/1"
MODEL_VERSION = "coupled-pressure-to-eb-ray-one-way-static/1"
