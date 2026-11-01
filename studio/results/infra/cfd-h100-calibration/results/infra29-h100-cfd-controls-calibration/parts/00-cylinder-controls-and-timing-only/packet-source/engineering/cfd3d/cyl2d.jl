# 2-D cylinder fidelity control, implementing cyl2d_contract.json (frozen before any run).
# Usage: julia --project=engineering/cfd3d/env engineering/cfd3d/cyl2d.jl OUT.json RUN_ID [TIMING nsteps]
#   RUN_ID in R1, R2, R3_domain, M1_mutant (parameters read from the contract, not from this file).
#   TIMING: step the run's exact domain nsteps times and record wall time and dt only. It never calls a
#   force or pressure routine, so a timing run cannot reveal the control's result before its band is frozen.
# Checkpoint/restart (environment; none of it changes the numerics):
#   CFD3D_CKPT=path        resume from path if it exists; write it every CFD3D_CKPT_EVERY_S (default 1800 s),
#                          at the end of a segment and at completion (atomic: write path.tmp, then rename)
#   CFD3D_SEGMENT_S=s      stop this process after s wall seconds: checkpoint, write no OUT, exit 75
#   CFD3D_SEGMENT_STEPS=n  the same after n steps (used by the bit-exact restart check)
#   CFD3D_SEGMENT_T=t      the same once the flow time reaches t (used by the CPU/CUDA same-state control)
#   A checkpoint is refused unless its run id, this script's sha256, the contract's sha256, Julia and
#   WaterLily versions all match. T_restart and T_same are tiny NON-contract runs for the restart check and
#   the CPU/CUDA same-state control only.
# Surface pressure is sampled from a host copy of p (same values on CPU; avoids device indexing of strided
# views on CUDA). Series are written as Float32 when that is lossless (they are Float32 quantities), which
# halves the output; the write checks the round trip and keeps Float64 otherwise. "series_dtype" says which,
# because the shortest Float32 decimal read as Float64 is not the Float32 value: a reader rounds it back.
using WaterLily, StaticArrays, JSON, SHA, Serialization
const GPU = get(ENV, "CFD3D_GPU", "0") == "1"
GPU && @eval using CUDA
memtype() = GPU ? CUDA.CuArray : Array
const CONTRACT_PATH = joinpath(@__DIR__, "cyl2d_contract.json")
const CONTRACT = JSON.parsefile(CONTRACT_PATH)
const IDENTITY = Dict("script_sha256" => bytes2hex(open(sha256, @__FILE__)),
                      "contract_sha256" => bytes2hex(open(sha256, CONTRACT_PATH)),
                      "julia" => string(VERSION), "waterlily" => string(pkgversion(WaterLily)))
const TEST_RUNS = Dict("T_restart" => Dict("n_D" => 4, "H" => 60, "Re" => 100, "t_end" => 30.0, "t0" => 8.0,
                                           "role" => "restart check only; not a contract run"),
                       "T_same" => Dict("n_D" => 8, "H" => 60, "Re" => 100, "t_end" => 130.0, "t0" => 100.0,
                                        "role" => "CPU/CUDA same-state control only; not a contract run"))
getrun(id) = haskey(CONTRACT["runs"], id) ? CONTRACT["runs"][id] : TEST_RUNS[id]

function build(run)
    nD, H, Re = run["n_D"], run["H"], run["Re"]
    D = Float32(nD); R = D / 2; U = 1f0
    @assert H == 60 || H == 120
    c = SA[(H / 2f0) * D, (H / 2f0) * D]               # square H, centred cylinder (30 D each side for H = 60)
    body = AutoBody((x, t) -> √sum(abs2, x .- c) - R)
    bump = c + SA[2D, 0f0]
    u0(i, x) = i == 1 ? U : 0.01f0 * U * exp(-sum(abs2, x .- bump) / D^2)
    sim = Simulation((H * nD, H * nD), (U, 0f0), D; ν=U * D / Re, body, u0, T=Float32, exitBC=true, mem=memtype())
    sim, D, R, U, c
end

function timing(run, nsteps)
    sim, D, _, _, _ = build(run)
    sim_step!(sim); sim_step!(sim)                     # compile outside the timed loop
    dts = Float64[]
    wall = @elapsed for _ in 1:nsteps
        sim_step!(sim); push!(dts, sim.flow.Δt[end])
    end
    cells = prod(size(sim.flow.p))
    Dict("mode" => "TIMING", "cells" => cells, "steps" => nsteps, "wall_s" => wall,
         "ns_per_cell_step" => 1e9wall / (nsteps * cells), "dt_grid_mean" => sum(dts) / length(dts),
         "dt_grid_last" => dts[end], "steps_per_D_over_U_at_this_dt" => D / dts[end],
         "note" => "start-up dt; the developed wake has a higher peak speed, so later dt is smaller (estimate only)")
end

"Wall points and the three off-wall sample points per angle, in grid coordinates."
function stations(R, c, n=720)
    θ = range(0, 2π; length=n + 1)[1:end-1]
    nrm = [SA[Float32(cos(t)), Float32(sin(t))] for t in θ]
    pts = [[c + (R + k) * nn for nn in nrm] for k in (1.5f0, 2.5f0, 3.5f0)]
    nrm, pts
end

"Every array a WaterLily step reads before it writes it. V, mu0 and mu1 (and the Poisson L, D, iD) are
rebuilt by measure! at the start of every step, so they are not stored."
function state_arrays(sim)
    f = sim.flow
    a = Any[f.u, f.u⁰, f.f, f.p, f.σ]
    for l in sim.pois.levels
        append!(a, (l.x, l.ϵ, l.r, l.z))
    end
    a
end

function save_ckpt(path, sim, id, rec)
    st = merge(IDENTITY, Dict("run_id" => id, "arrays" => [Array(x) for x in state_arrays(sim)],
                              "dt" => copy(sim.flow.Δt), "rec" => rec))
    tmp = path * ".tmp"
    open(io -> serialize(io, st), tmp, "w")
    mv(tmp, path; force=true)
end

function load_ckpt!(path, sim, id)
    st = open(deserialize, path)
    for (k, v) in merge(IDENTITY, Dict("run_id" => id))
        st[k] == v || error("checkpoint refused: $k is $(st[k]), this process has $v")
    end
    dst = state_arrays(sim)
    length(dst) == length(st["arrays"]) || error("checkpoint refused: array count differs")
    for (d, s) in zip(dst, st["arrays"])
        size(d) == size(s) || error("checkpoint refused: array size differs")
        copyto!(d, s)
    end
    empty!(sim.flow.Δt); append!(sim.flow.Δt, st["dt"])
    st["rec"]
end

"Float32 copy when the round trip is exact (the series are Float32 quantities), else the Float64 original."
f32(x) = (y = Float32.(x); Float64.(y) == x ? y : x)

function run_case(run, id)
    sim, D, R, U, c = build(run)
    t_end = get(run, "t_end", CONTRACT["time"]["t_end"])
    t0 = get(run, "t0", CONTRACT["time"]["transient_discarded_before"])
    nrm, pts = stations(R, c)
    ny = size(sim.flow.p, 2)
    ck = get(ENV, "CFD3D_CKPT", "")
    rec = !isempty(ck) && isfile(ck) ? load_ckpt!(ck, sim, id) :
        Dict{String,Any}("t" => Float64[], "Cd" => Float64[], "Cd_p" => Float64[], "Cl" => Float64[],
                         "cp_sum" => zeros(Float64, length(nrm)), "cp_t" => Float64[], "steps" => 0,
                         "wall_s" => 0.0, "segments" => 0)
    rec["segments"] += 1
    ts, cd, cdp, cl, cp_sum, cp_t = rec["t"], rec["Cd"], rec["Cd_p"], rec["Cl"], rec["cp_sum"], rec["cp_t"]
    seg_s = parse(Float64, get(ENV, "CFD3D_SEGMENT_S", "Inf"))
    seg_steps = parse(Int, get(ENV, "CFD3D_SEGMENT_STEPS", string(typemax(Int))))
    seg_t = parse(Float64, get(ENV, "CFD3D_SEGMENT_T", "Inf"))
    every = parse(Float64, get(ENV, "CFD3D_CKPT_EVERY_S", "1800"))
    t_seg = t_mark = t_ck = Base.time(); n_seg = 0
    tick!() = (now = Base.time(); rec["wall_s"] += now - t_mark; t_mark = now)
    while sim_time(sim) < t_end
        if n_seg >= seg_steps || Base.time() - t_seg >= seg_s || sim_time(sim) >= seg_t
            tick!(); isempty(ck) || save_ckpt(ck, sim, id, rec)
            return nothing                                       # segment over, not finished: resumable
        end
        sim_step!(sim); n_seg += 1; rec["steps"] += 1
        ft = WaterLily.total_force(sim); fp = WaterLily.pressure_force(sim)
        push!(ts, sim_time(sim)); push!(cd, -2ft[1] / (U^2 * D)); push!(cl, -2ft[2] / (U^2 * D))
        push!(cdp, -2fp[1] / (U^2 * D))
        isfinite(cd[end]) || break
        if ts[end] >= t0 && rec["steps"] % 10 == 0
            p = Array(sim.flow.p)                                        # host copy (see header)
            pref = sum(Array(@view p[2, 2:ny-1])) / (ny - 2)
            s = [WaterLily.interp.(pt, Ref(p)) for pt in pts]            # samples at R + 1.5, 2.5, 3.5 h
            # quadratic through (1.5, s1), (2.5, s2), (3.5, s3), evaluated at 0 (the wall)
            pw = @. (35 * s[1] - 42 * s[2] + 15 * s[3]) / 8
            cp_sum .+= (pw .- pref) ./ (0.5U^2); push!(cp_t, ts[end])
        end
        if !isempty(ck) && Base.time() - t_ck >= every
            tick!(); save_ckpt(ck, sim, id, rec); t_ck = Base.time()
        end
    end
    tick!(); isempty(ck) || save_ckpt(ck, sim, id, rec)         # final state, so a re-invocation is idempotent
    Dict("mode" => "RUN", "contract_run" => haskey(CONTRACT["runs"], id), "n_D" => run["n_D"], "H" => run["H"],
         "Re" => run["Re"], "t_end_contract" => t_end, "grid" => collect(size(sim.flow.p)),
         "steps" => rec["steps"], "segments" => rec["segments"], "t_end_reached" => ts[end],
         "finite" => all(isfinite, cd), "wall_s" => rec["wall_s"],
         "ns_per_cell_step" => 1e9rec["wall_s"] / (rec["steps"] * prod(size(sim.flow.p))),
         "t" => f32(ts), "Cd" => f32(cd), "Cd_p" => f32(cdp), "Cl" => f32(cl),
         "series_dtype" => Dict(k => string(eltype(f32(v))) for (k, v) in ("t" => ts, "Cd" => cd, "Cd_p" => cdp, "Cl" => cl)),
         "surface" => Dict("angles" => length(nrm), "samples" => length(cp_t),
                           "Cp_wall_mean" => cp_sum ./ max(length(cp_t), 1), "t_first" => isempty(cp_t) ? nothing : cp_t[1]))
end

function main(out, id, mode="RUN", nsteps="200")
    run = getrun(id)
    r = mode == "TIMING" ? timing(run, parse(Int, nsteps)) : run_case(run, id)
    r === nothing && exit(75)                                    # EX_TEMPFAIL: resume with the same CFD3D_CKPT
    r["run_id"] = id; r["gpu"] = GPU; r["threads"] = Threads.nthreads()
    merge!(r, IDENTITY)
    open(out * ".tmp", "w") do io; JSON.print(io, r); end
    mv(out * ".tmp", out; force=true)
end

main(ARGS...)
