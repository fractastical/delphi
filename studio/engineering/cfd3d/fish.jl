# Fixed rigid fish3d candidate in a uniform stream: 3-D incompressible Navier-Stokes (WaterLily BDIM).
# Usage: julia --project=engineering/cfd3d/env engineering/cfd3d/fish.jl CASE.json OUTDIR
# CASE.json: {"case_id", "L_cells", "Re", "t_end", "t_avg", "fins": bool, "slices_every", "geometry_dir"}
# Output contract: messages/cfd3d-to-coupled-mechanics.md (v0.1). Gates: gates_cpu.json "fish_gates".
using WaterLily, WaterLilyMeshBodies, StaticArrays, JSON, SHA, FileIO, LinearAlgebra
import GeometryBasics
const GPU = get(ENV, "CFD3D_GPU", "0") == "1"
GPU && @eval using CUDA
memtype() = GPU ? CUDA.CuArray : Array

const L_REF_M = 0.230699          # total length, snout to caudal tip (fish3d build.json bbox)
const SHELLS = ("pectoral_L", "pectoral_R", "pelvic_L", "pelvic_R", "dorsal", "anal", "caudal",
                "operculum_L", "operculum_R")      # thickness <= 0.5 mm: always sub-grid here
const CLOSED = ("body", "eye_L", "eye_R")
const HALF_THK = 1.866f0           # WaterLilyMeshBodies default shell half-thickness, cells

sha(path) = bytes2hex(open(sha256, path))

function load_components(gdir, fins)
    comp = JSON.parsefile(joinpath(gdir, "components.json"))
    names = fins ? (CLOSED..., SHELLS...) : CLOSED
    for k in names   # refuse any byte drift from the pinned fish3d candidate
        got = sha(joinpath(gdir, "$k.stl"))
        got == comp["components"][k]["stl_sha256"] || error("STL hash mismatch for $k: $got")
    end
    comp, names
end

function make_body(gdir, names, L, snout; mem=Array)
    scale = Float32(L / L_REF_M)              # mesh metres -> cells
    map = (x, t) -> x - snout                  # one closure object: SetBody requires equal maps
    bodies = [MeshBody(joinpath(gdir, "$k.stl"); scale, map, boundary=(k in CLOSED),
                       half_thk=HALF_THK, mem) for k in names]
    reduce(+, bodies)
end

"Trilinear sample of a cell-centred field at grid position x (WaterLily: centre of I is I - 1.5)."
function trilinear(p, x)
    f = x .+ 1.5
    i = floor.(Int, f); w = f .- i
    any(i .< 1) || any(i .+ 1 .> size(p)) && return NaN
    s = 0.0
    for c in CartesianIndices((0:1, 0:1, 0:1))
        o = c.I
        s += prod(ntuple(k -> o[k] == 1 ? w[k] : 1 - w[k], 3)) * p[(i .+ o)...]
    end
    s
end

function surface_rows(gdir, k, p, pref, U, L, snout, offset)
    mesh = load(joinpath(gdir, "$k.stl"))
    scale = L / L_REF_M
    rows = Matrix{Float32}(undef, 10, length(mesh))
    for (j, tri) in enumerate(mesh)
        a, b, c = (SVector{3,Float64}(v...) for v in tri)
        n = cross(b - a, c - a); A = norm(n) / 2; n = n / norm(n)
        cen = (a + b + c) / 3
        xg = snout .+ cen * scale
        cp(s) = (trilinear(p, xg + s * offset * n) - pref) / (0.5U^2)
        rows[:, j] = [cen..., n..., A, cp(1), k in CLOSED ? NaN : cp(-1), offset]
    end
    rows
end

writef32(path, a) = open(io -> write(io, htol.(Float32.(a))), path, "w")

function main(case_path, out)
    case = JSON.parsefile(case_path)
    L = case["L_cells"]; Re = case["Re"]; U = 1.0f0
    gdir = case["geometry_dir"]; fins = case["fins"]
    Re <= 2000 || error("REFUSED: Re_L $Re > 2000 is outside what these grids resolve (fish_gates.Re_rule)")
    comp, names = load_components(gdir, fins)
    dims = (4L, 3L ÷ 2, L)
    snout = SA[Float32(L), Float32(3L / 4), Float32(L / 2)]   # snout grid position; y = 0, z = 0 plane
    mkpath(joinpath(out, "fields")); mkpath(joinpath(out, "surface")); mkpath(joinpath(out, "slices"))
    mem = memtype()
    t_build = @elapsed body = make_body(gdir, names, L, snout; mem)
    sim = Simulation(dims, (U, 0, 0), L; ν=U * L / Re, body, T=Float32, exitBC=true, mem)
    stride = get(case, "slice_stride", 1); f16 = get(case, "slice_f16", false)
    # stride 1: ghost-inclusive planes (CPU contract v0.1); stride > 1: interior cells 1:stride:n only
    sub(a) = stride == 1 ? a : a[2:stride:end-1, 2:stride:end-1, :]
    wslice(path, a) = f16 ? open(io -> write(io, htol.(Float16.(sub(a)))), path, "w") : writef32(path, sub(a))
    h_m = L_REF_M / L
    ts = Float64[]; F = Vector{Float64}[]; Fp = Vector{Float64}[]
    nslice = 0; every = get(case, "slices_every", 0.1); next_slice = 0.0
    zc = round(Int, snout[3] + 1.5); yc = round(Int, snout[2] + 1.5)
    wall = @elapsed while sim_time(sim) < case["t_end"]
        sim_step!(sim; remeasure=false)
        f = WaterLily.total_force(sim); fp = WaterLily.pressure_force(sim)
        push!(ts, sim_time(sim)); push!(F, collect(Float64, f)); push!(Fp, collect(Float64, fp))
        all(isfinite, f) || break
        if sim_time(sim) >= next_slice   # mid-planes for the video: u-magnitude and p at z = fish axis, y = 0
            u = Array(sim.flow.u); p = Array(sim.flow.p)
            wslice(joinpath(out, "slices", "z$(lpad(nslice, 4, '0')).f32"),
                     cat(u[:, :, zc, 1], u[:, :, zc, 2], u[:, :, zc, 3], p[:, :, zc]; dims=3))
            wslice(joinpath(out, "slices", "y$(lpad(nslice, 4, '0')).f32"),
                     cat(u[:, yc, :, 1], u[:, yc, :, 2], u[:, yc, :, 3], p[:, yc, :]; dims=3))
            nslice += 1; next_slice += every
        end
    end
    p = Array(sim.flow.p); u = Array(sim.flow.u)
    pref = sum(@view p[2, 2:end-1, 2:end-1]) / ((size(p, 2) - 2) * (size(p, 3) - 2))
    I = (2:size(p, 1)-1, 2:size(p, 2)-1, 2:size(p, 3)-1)
    if get(case, "write_fields", true)
        writef32(joinpath(out, "fields", "final.p.f32"), p[I...])
        writef32(joinpath(out, "fields", "final.u.f32"), u[I..., :])
    end
    σ = sim.flow.σ    # scratch: fill with the body SDF for the renderer
    # exact within 4 cells, +-4 beyond (the default fastd2 = 0 writes +-0 outside the band: the whole box reads as body)
    WaterLily.measure_sdf!(σ, sim.body, WaterLily.time(sim); fastd²=16f0)
    sdf = Array(σ)
    sdfI = sdf[I...]
    if stride == 1
        writef32(joinpath(out, "fields", "sdf.f32"), sdfI)
    else   # the two slice planes only, at the slice stride
        writef32(joinpath(out, "fields", "sdf_z.f32"), sdfI[1:stride:end, 1:stride:end, zc-1])
        writef32(joinpath(out, "fields", "sdf_y.f32"), sdfI[1:stride:end, yc-1, 1:stride:end])
    end
    surf = Dict{String,Any}()
    for k in names
        off = k in CLOSED ? 2.0 : HALF_THK + 1.0
        rows = surface_rows(gdir, k, p, pref, U, L, snout, off)
        writef32(joinpath(out, "surface", "$k.f32"), rows)
        surf[k] = Dict("rows" => size(rows, 2), "offset_cells" => off, "resolved" => k in CLOSED,
                       "thickness_mm" => get(get(comp["components"][k]["params"], "thickness_mm", Dict()), "value", nothing),
                       "stl_sha256" => comp["components"][k]["stl_sha256"])
    end
    w = ts .>= case["t_avg"]; q = 0.5U^2 * L^2       # coefficients on L_ref^2
    mean(v) = sum(v) / length(v)
    # WaterLily returns +sum(p n ds) with outward n (Metrics.jl:148), the force ON THE FLUID; body force = -F
    coeffs = Dict("Cd_total" => -mean([f[1] for f in F[w]]) / q, "Cd_pressure" => -mean([f[1] for f in Fp[w]]) / q,
                  "Cy_total" => -mean([f[2] for f in F[w]]) / q, "Cz_total" => -mean([f[3] for f in F[w]]) / q,
                  "sign" => "coefficients are forces on the body (= -WaterLily total_force)",
                  "avg_window_tUL" => [case["t_avg"], ts[end]], "reference_area" => "L_ref^2")
    open(joinpath(out, "forces.json"), "w") do io
        JSON.print(io, Dict("t" => ts, "F_total_grid" => F, "F_pressure_grid" => Fp, "coefficients" => coeffs), 1)
    end
    thin = [k for k in names if !(k in CLOSED)]
    hdr = Dict(
        "schema" => "cfd3d-case-0.1", "case" => case, "solver" => Dict("julia" => string(VERSION),
            "WaterLily" => string(pkgversion(WaterLily)), "WaterLilyMeshBodies" => string(pkgversion(WaterLilyMeshBodies)),
            "threads" => Threads.nthreads(), "device" => GPU ? string(CUDA.name(CUDA.device())) : "cpu", "T" => "Float32", "exitBC" => true, "body" => "fixed, remeasure=false"),
        "candidate_sha256" => comp["candidate_sha256"], "components" => surf,
        "grid" => Dict("dims" => collect(dims), "L_cells" => L, "h_m" => h_m, "snout_grid" => collect(snout),
            "p_location" => "x_grid = I - 1.5 (ghost at I=1); files hold interior I=2..n+1",
            "u_location" => "component i at x_grid = I - 1.5 - 0.5 e_i", "frame" => "x snout->tail, y left, z dorsal; stream +x",
            "file_order" => "little-endian Float32, column-major (numpy order='F')",
            "p_shape" => collect(size(p[I...])), "u_shape" => collect(size(u[I..., :])),
            "surface_columns" => ["cx_m", "cy_m", "cz_m", "nx", "ny", "nz", "area_m2", "Cp_plus", "Cp_minus", "offset_cells"],
            "slices" => Dict("count" => nslice, "every_tUL" => every, "z_index" => zc, "y_index" => yc,
                             "layout" => "[n1, n2, 4] = u, v, w, p incl. ghosts", "stride" => stride, "dtype" => f16 ? "float16" : "float32")),
        "nondim" => Dict("U_grid" => U, "nu_grid" => U * L / Re, "Re_L" => Re, "L_ref_m" => L_REF_M,
            "p" => "kinematic, grid units; use Cp = (p - p_ref)/(0.5 U^2)", "p_ref" => pref,
            "p_ref_def" => "mean p over inlet plane interior at final time"),
        "medium" => "none (non-dimensional); see contract for the water_20C conversion",
        "steps" => length(ts), "t_end_reached" => ts[end], "wall_s" => wall, "body_build_s" => t_build,
        "cells" => prod(dims), "ns_per_cell_step" => 1e9wall / (length(ts) * prod(dims)), "coefficients" => coeffs,
        "resolution" => Dict("fin_thickness_cells" => 0.5e-3 / h_m, "min_cells_rule" => 2,
            "fins_resolved" => false, "sub_grid_components" => thin,
            "shell_simulated_thickness_mm" => 2HALF_THK * h_m * 1e3),
        "refusals" => ["fin forces and fin pressure jumps are smeared sub-grid shell values, not fin loads",
                       "not swimming, taxiing or gliding; flight Re (air ~1e5) and free surface not simulated",
                       "no grid-convergence claim from a single case; see the paired comparison"],
        "finite" => all(f -> all(isfinite, f), F))
    open(io -> JSON.print(io, hdr, 1), joinpath(out, "case.json"), "w")
    println(JSON.json(Dict("case" => case["case_id"], "steps" => length(ts), "wall_s" => wall, "coeffs" => coeffs,
                           "finite" => hdr["finite"])))
end

main(ARGS[1], ARGS[2])
