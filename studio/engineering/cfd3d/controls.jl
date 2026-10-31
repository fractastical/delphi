# CPU feasibility controls for cfd3d (gates in gates_cpu.json, frozen before the first run).
# Usage: julia --project=engineering/cfd3d/env engineering/cfd3d/controls.jl OUT.json [C0|C1|C2|all]
using WaterLily, StaticArrays, JSON, LinearAlgebra

const t_wall0 = time()

"Empty box with a uniform stream: anything but U everywhere is a solver defect."
function c0(; n=32, steps=200)
    sim = Simulation((n, n, n), (1.0, 0.0, 0.0), n; ν=1e-3, T=Float64)
    t = @elapsed for _ in 1:steps
        sim_step!(sim)
    end
    u = sim.flow.u
    I = CartesianIndices((2:n+1, 2:n+1, 2:n+1))
    du = maximum(abs, @view(u[I, 1]) .- 1.0)
    dvw = max(maximum(abs, @view u[I, 2]), maximum(abs, @view u[I, 3]))
    div = maximum(I) do i
        abs(sum(u[i+δ(k, i), k] - u[i, k] for k in 1:3))
    end
    Dict("n" => n, "steps" => steps, "max_abs_u_minus_U" => du, "max_abs_v_w" => dvw,
         "max_abs_div" => div, "wall_s" => t)
end

δ(k, ::CartesianIndex{N}) where N = CartesianIndex(ntuple(j -> j == k ? 1 : 0, N))

"Fixed sphere, Re = U D / nu; Cd from WaterLily's total (pressure + viscous) force."
function sphere(D; Re=100, t_end=12.0, t_avg=8.0, U=1.0f0)
    centre = SA[1.5f0D, 2f0D, 2f0D]
    body = AutoBody((x, t) -> √sum(abs2, x .- centre) - D / 2)
    sim = Simulation((6D, 4D, 4D), (U, 0, 0), D; ν=U * D / Re, body, T=Float32)
    area = π * D^2 / 4
    ts, cd, cl = Float64[], Float64[], Float64[]
    nsteps = 0
    wall = @elapsed while sim_time(sim) < t_end
        sim_step!(sim)
        nsteps += 1
        f = WaterLily.total_force(sim)
        push!(ts, sim_time(sim)); push!(cd, 2f[1] / (U^2 * area)); push!(cl, 2hypot(f[2], f[3]) / (U^2 * area))
        isfinite(cd[end]) || break
    end
    w = ts .>= t_avg
    Dict("D_cells" => D, "Re" => Re, "grid" => collect(size(sim.flow.p)), "steps" => nsteps,
         "t_end" => ts[end], "Cd_mean" => sum(cd[w]) / count(w),
         "Cl_rms" => sqrt(sum(abs2, cl[w]) / count(w)), "finite" => all(isfinite, cd),
         "wall_s" => wall, "cells" => prod(size(sim.flow.p)),
         "ns_per_cell_step" => 1e9wall / (nsteps * prod(size(sim.flow.p))),
         "Cd_trace_every_10" => cd[1:10:end])
end

function main(out, which)
    gates = JSON.parsefile(joinpath(@__DIR__, "gates_cpu.json"))["controls"]
    r = Dict{String,Any}("julia" => string(VERSION), "threads" => Threads.nthreads(),
        "waterlily" => string(pkgversion(WaterLily)))
    if which in ("C0", "all")
        c = c0(); g = gates["C0_uniform_no_body"]["pass"]
        c["pass"] = c["max_abs_u_minus_U"] <= g["max_abs_u_minus_U"] && c["max_abs_v_w"] <= g["max_abs_v_w"] &&
                    c["max_abs_div"] <= g["max_abs_div"]
        r["C0"] = c
    end
    if which in ("C1", "all")
        g = gates["C1_sphere_Re100"]["pass"]
        s8, s16 = sphere(8), sphere(16)
        lo, hi = g["Cd_D16_in"]
        rel = abs(s8["Cd_mean"] - s16["Cd_mean"]) / s16["Cd_mean"]
        r["C1"] = Dict("D8" => s8, "D16" => s16, "rel_diff_D8_D16" => rel,
            "pass_band" => lo <= s16["Cd_mean"] <= hi, "pass_grid" => rel <= g["abs_rel_diff_D8_D16_max"],
            "pass_steady" => s16["Cl_rms"] <= g["wake_steady_Cl_rms_max"])
        r["C1"]["pass"] = r["C1"]["pass_band"] && r["C1"]["pass_grid"] && r["C1"]["pass_steady"]
    end
    if which in ("C2", "all")
        lo, hi = gates["C1_sphere_Re100"]["pass"]["Cd_D16_in"]
        m = sphere(16; Re=25)
        m["pass"] = !(lo <= m["Cd_mean"] <= hi)
        r["C2"] = m
    end
    r["wall_total_s"] = time() - t_wall0
    tmp = out * ".tmp"
    open(io -> JSON.print(io, r, 1), tmp, "w"); mv(tmp, out; force=true)
    println(JSON.json(Dict(k => (v isa Dict ? get(v, "pass", "") : v) for (k, v) in r)))
end

main(ARGS[1], length(ARGS) > 1 ? ARGS[2] : "all")
