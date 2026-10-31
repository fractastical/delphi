"""Equations copied semantically from the actual pinned implementations, not new biology."""


def registry(sources):
    entries = []

    def add(identifier, model, scale, latex, variables, path, symbol, assumptions, controls, inputs, outputs, couplings=(), regions=(), citation=None):
        entries.append({"id": identifier, "model_id": model, "studio_anchor": "flying-fish:" + scale,
                        "scale": scale, "region_ids": list(regions), "latex": latex,
                        "variables": [{"symbol": key, "unit": unit, "role": role} for key, unit, role in variables],
                        "sources": [sources.pin(path, "symbol:" + symbol)], "citation": citation,
                        "domain": "Published/scoped computational model; no target-fish calibration or biological correspondence established",
                        "assumptions": assumptions, "check_evidence": [sources.pin(path, selector) for path, selector in controls],
                        "input_ports": list(inputs), "output_ports": list(outputs), "coupling_ids": list(couplings),
                        "scope": "An executable model equation/checked mathematical formula, not a demonstrated developmental mechanism"})

    add("eq-wing-loading", "flying_fish_constraints", "organism", r"W_L=\frac{mg}{S}",
        [("m", "kg", "input"), ("g", "m/s^2", "parameter"), ("S", "m^2", "input"), ("W_L", "N/m^2", "output")],
        "engineering/formal/GeometricSimilarity.lean", "FlyingFish.wingLoading", ["S>0", "source envelope differs from a viability region"],
        [("engineering/formal/RECEIPT.json", "/lean_checks")], ["flying_fish_constraints.m", "flying_fish_constraints.S"], ["wing_loading"], ["c01_mass", "c02_area"], ["body"])
    add("eq-similarity", "flying_fish_constraints", "organism", r"m'=k^3m,\quad S'=k^2S\Rightarrow W_L'=kW_L,\quad V_s'=\sqrt{k}V_s",
        [("m", "kg", "input"), ("S", "m^2", "input"), ("k", "1", "assumed-scale-factor"), ("V_s", "m/s", "output"), ("W_L", "N/m^2", "output")],
        "engineering/formal/GeometricSimilarity.lean", "FlyingFish.scaling_laws", ["geometric similarity", "unchanged body density, rho, C and gravity", "positivity hypotheses"],
        [("engineering/formal/RECEIPT.json", "/lean_checks")], ["m", "S", "k"], ["scaled-wing-loading", "scaled-level-flight-speed"], regions=["body"])
    add("eq-level-lift", "flying_fish_constraints", "organism", r"\frac12\rho V^2SC_L\ge mg",
        [("rho", "kg/m^3", "assumed-parameter"), ("V", "m/s", "input"), ("S", "m^2", "input"), ("C_L", "1", "assumed-parameter"), ("m", "kg", "input"), ("g", "m/s^2", "parameter")],
        "engineering/constraints.py", "flying_fish_model", ["level-flight lift proxy, not gliding feasibility", "rho and CL are design assumptions"],
        [("engineering/formal/RECEIPT.json", "/solver_result"), ("engineering/formal/RECEIPT.json", "/lean_checks")], ["m", "S", "V", "rho", "CL"], ["declared-constraint-verdict"], ["c01_mass", "c02_area", "c03_span", "c04_speed"], ["body"])
    add("eq-glide-dynamics", "glide_pointmass", "organism", r"\dot x=V\cos\gamma,\quad\dot h=V\sin\gamma,\quad m\dot V=-D-mg\sin\gamma,\quad mV\dot\gamma=L-mg\cos\gamma",
        [("x", "m", "state"), ("h", "m", "state"), ("V", "m/s", "state"), ("gamma", "rad", "state"), ("m", "kg", "input"), ("g", "m/s^2", "parameter"), ("L", "N", "input"), ("D", "N", "input")],
        "engineering/simulation/glide.py", "_rhs", ["point mass, vertical plane", "constant commanded lift coefficient", "no fin-deformation feedback or active control"],
        [("engineering/simulation/results/controls.json", ""), ("engineering/simulation/results_controlled/summary.json", "/n_unconverged")], ["glide_pointmass.m", "glide_pointmass.release_speed"], ["trajectory", "range", "sink"], ["c01_mass", "c02_area", "c03_span", "c04_speed", "c08_fin_deflection_to_glide_speed"], ["body"])
    add("eq-aero-polar", "glide_pointmass", "organism", r"L=\frac12\rho V^2SC_L,\quad D=\frac12\rho V^2SC_D,\quad C_D=C_{D0}+\frac{C_L^2}{\pi e AR},\quad AR=b^2/S",
        [("rho", "kg/m^3", "assumed-parameter"), ("V", "m/s", "input"), ("S", "m^2", "input"), ("b", "m", "input"), ("C_L", "1", "assumed-parameter"), ("C_D", "1", "model-output"), ("C_D0", "1", "assumed-parameter"), ("e", "1", "assumed-parameter"), ("AR", "1", "derived"), ("L", "N", "output"), ("D", "N", "output")],
        "engineering/simulation/glide.py", "drag_coeff,_rhs", ["assumed parabolic polar", "no sourced target-species aerodynamic calibration"],
        [("engineering/simulation/results_controlled/summary.json", "/claim")], ["glide_pointmass.S", "glide_pointmass.b", "CL", "CD0", "e"], ["lift", "drag"], ["c02_area", "c03_span"], ["body"])
    add("eq-fin-beam", "finbeam_euler_bernoulli", "organ", r"\frac{d^2}{dx^2}\left(EI\frac{d^2w}{dx^2}\right)=q,\quad w(0)=w'(0)=0;\quad w_{uniform}(L)=\frac{qL^4}{8EI}",
        [("x", "m", "coordinate"), ("L", "m", "assumed-geometry"), ("w", "m", "state-output"), ("EI", "N m^2", "assumed-material"), ("q", "N/m", "assumed-load")],
        "engineering/fin_mechanics/beam.py", "solve_cantilever,w_uniform", ["clamped-free Euler-Bernoulli beam", "linear elastic small deflection", "uniform loading closed form requires constant EI"],
        [("engineering/fin_mechanics/artifacts/result.json", "/controls"), ("engineering/fin_mechanics/artifacts/result.json", "/convergence")], ["finbeam_euler_bernoulli.flexural_rigidity", "finbeam_euler_bernoulli.q_line", "fin_load_bridge.L_ray"], ["finbeam_euler_bernoulli.tip_deflection"], ["c11_load_proxy_to_beam", "c12_ray_length_to_beam"], ["pectoral-left", "pectoral-right"])
    add("eq-hh-voltage", "hh1952_gap_chain", "cellular", r"C_m\dot V_i=I_i-g_{Na}m_i^3h_i(V_i-E_{Na})-g_Kn_i^4(V_i-E_K)-g_L(V_i-E_L)+\sum_jg_{ij}(V_j-V_i)",
        [("V_i", "mV", "state"), ("C_m", "uF/cm^2", "parameter"), ("I_i", "uA/cm^2", "input"), ("g_Na", "mS/cm^2", "parameter"), ("g_K", "mS/cm^2", "parameter"), ("g_L", "mS/cm^2", "parameter"), ("g_ij", "mS/cm^2", "assumed-network"), ("E_Na,E_K,E_L", "mV", "fixed-reservoir-parameters"), ("m_i,h_i,n_i", "1", "gating-states")],
        "engineering/bioelectric/model.py", "rhs,currents,gap_current", ["squid source membrane", "assumed equal-area sealed gap chain", "fixed ion reservoirs, no pumps/depletion"],
        [("artifacts/bioelectric/controls_baseline.json", "/checks"), ("artifacts/bioelectric/mutation_receipt.json", "")], ["gap_conductance", "stimulus"], ["hh1952_gap_chain.voltage"], citation="10.1113/jphysiol.1952.sp004764 Eq26, pp518–520")
    add("eq-hh-gates", "hh1952_gap_chain", "cellular", r"\dot q=\alpha_q(V)(1-q)-\beta_q(V)q,\quad q\in\{m,h,n\};\quad \phi_T=3^{(T-6.3)/10},\quad Q_{10}=3",
        [("q", "1", "gating-state"), ("V", "mV", "input"), ("alpha_q,beta_q", "1/ms", "voltage-dependent-rates"), ("T", "degC", "scenario-parameter")],
        "engineering/bioelectric/model.py", "rates", ["published voltage-dependent empirical rate functions", "source temperature scaling"],
        [("artifacts/bioelectric/controls_baseline.json", "/checks/2")], ["voltage", "temperature"], ["m", "h", "n"], citation="10.1113/jphysiol.1952.sp004764 Eqs7,12–16,20–24,p519")
    add("eq-motor-clutch", "motor_clutch_ecm", "cellular", r"F=\sum_{bound} k_c(a-r_i-x_s)=k_lx_s+k_a(x_s-z),\quad\dot z=k_a(x_s-z)/\eta,\quad\dot a=v_u(1-F/(N_mF_m))",
        [("F,F_m", "pN", "force-state/parameter"), ("a,r_i,x_s,z", "nm", "states/reference"), ("k_c,k_l,k_a", "pN/nm", "parameters"), ("eta", "pN s/nm", "parameter"), ("v_u", "nm/s", "parameter"), ("N_m", "1", "parameter")],
        "engineering/mechanobio/model.py", "_propagators,simulate", ["quasi-static linear force balance", "shared actin displacement", "standard-linear-solid contact, no whole-cell shape"],
        [("artifacts/mechanobio/controls.json", "/independent_viscoelastic_integration"), ("artifacts/mechanobio/controls.json", "/force_balance")], ["contact-stiffness", "viscosity", "motor-parameters"], ["traction", "substrate-displacement"], citation="10.1073/pnas.1716620115 Model Description,Eqs1–6")
    add("eq-clutch-rupture", "motor_clutch_ecm", "cellular", r"p_{off}=1-\exp[-k_{off}\exp(\max(f_i,0)/F_b)\Delta t],\quad p_{on}=1-\exp(-k_{on}\Delta t)",
        [("p_on,p_off", "1", "frozen-rate-transition-probabilities"), ("k_on,k_off", "1/s", "parameters"), ("f_i,F_b", "pN", "force-state/parameter"), ("Delta t", "s", "numerical-step")],
        "engineering/mechanobio/model.py", "simulate", ["slip bonds with Bell rupture", "frozen-rate stochastic splitting; compression uses unloaded rate"],
        [("artifacts/mechanobio/controls.json", "/bell_law_mutant"), ("artifacts/mechanobio/controls.json", "/timestep_screen")], ["clutch-force", "rates", "seed"], ["clutch-state"], citation="10.1073/pnas.1716620115 Eqs5–6; implementation clips exponent to60 after probabilities saturate")
    add("eq-rd-schnakenberg", "rdfield_nonlinear_sweep", "tissue", r"\partial_\tau u=\nabla^2u+a-u+u^2v,\quad\partial_\tau v=D_v\nabla^2v+b-u^2v",
        [("u,v", "model units", "states"), ("tau", "dimensionless model time", "coordinate"), ("a,b,D_v", "model units", "parameters")],
        "engineering/simulation/rd_frames.py", "react,run_cell", ["Schnakenberg branch only", "1-D no-flux boundaries", "no SI tissue length/time or fin mapping"],
        [("engineering/simulation/rd/receipt.json", "/cells/1")], ["kinetics", "diffusivity", "initial-field"], ["dominant-mode", "field-amplitude"], ["c07_rd_wavelength_to_wing_span"])
    add("eq-pressure-line-load", "fin_load_bridge", "organ", r"p=\frac12\rho V^2C_L,\quad q=pw_t,\quad L_{ray}=f_{ray}\,b/2",
        [("p", "Pa", "mean-pressure-proxy"), ("rho", "kg/m^3", "assumed-parameter"), ("V", "m/s", "input"), ("C_L", "1", "assumed-parameter"), ("w_t", "m", "assumed-width"), ("q", "N/m", "output"), ("f_ray", "1", "assumed-length-fraction"), ("b", "m", "input"), ("L_ray", "m", "output")],
        "engineering/fin_mechanics/load_bridge.py", "bridge", ["fixed mean lift-pressure proxy", "declared tributary width and ray fraction", "no deformation-dependent aerodynamic feedback"],
        [("engineering/fin_mechanics/artifacts/result.json", "/load_bridge"), ("engineering/COUPLING_MANIFEST.json", "/couplings")], ["fin_load_bridge.V", "fin_load_bridge.b"], ["fin_load_bridge.q_line", "fin_load_bridge.L_ray"],
        ["c09_span_to_fin_bridge", "c10_speed_to_fin_bridge", "c11_load_proxy_to_beam", "c12_ray_length_to_beam", "c13_pressure_to_line_load_dimension_only"], ["pectoral-left", "pectoral-right"])
    gaps = [{"id": identifier, "status": "missing_mechanism", "scales": scales, "summary": text,
             "evidence": [sources.pin("projects/flying-fish.draft.json", "/draft/payload/limitations")],
             "latex": None} for identifier, scales, text in [
                 ("gene-to-fin-program", ["molecular", "developmental", "organ"], "No calibrated gene-to-channel-to-pattern-to-fin equation stack is established"),
                 ("tissue-to-EI", ["cellular", "tissue", "organ"], "No calibrated cell/contact/pattern-to-ray material/geometry map exists"),
                 ("deformed-fin-to-polar", ["organ", "organism"], "No two-way fluid-structure transfer or measured deformed-fin aerodynamic polar"),
                 ("neural-caudal-control", ["neural", "organism"], "No executable propulsion, active fin control or caudal swimming dynamics linked here"),
                 ("whole-life-history", ["developmental", "ecological", "evolutionary"], "No growth, ecological fitness or evolutionary reachability equations established")]]
    return entries, gaps
