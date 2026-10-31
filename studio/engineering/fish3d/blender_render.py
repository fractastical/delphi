"""Blender (Cycles) render of the exact fish.glb a build wrote.  Runs INSIDE Blender:

    blender -b --factory-startup --python engineering/fish3d/blender_render.py -- \
        --glb artifacts/fish3d/<id>/fish.glb --out DIR --mode still|turntable [--samples N] [--res W H] [--frames N]

Refuses to render unless the GLB's sha256 equals build.json's.  Writes PNG frames and blender_report.json
(Blender version, GLB sha256, object names and triangle counts as imported, every render setting).
A beauty render: it shows the mesh, it measures nothing.
"""
import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

import bpy

SETTINGS = {
    "engine": "CYCLES", "device": "CPU", "threads": 4, "denoise": "OpenImageDenoise",
    "view_transform": "AgX", "look": "AgX - Medium High Contrast",
    "sky": {"type": "NISHITA", "sun_elevation_deg": 38.0, "sun_rotation_deg": 140.0, "strength": 0.22},
    "sun": {"strength": 2.6, "angle_deg": 1.5, "rotation_deg": [52.0, 0.0, 128.0]},
    "camera": {"lens_mm": 70.0, "elevation_deg": 24.0, "azimuth_deg": -48.0,
               "framing": {"still": 0.78, "turntable": 1.02}},  # x bounding-sphere fit
    "film_transparent": True,
    "materials": {
        "body": {"metallic": 0.55, "roughness": 0.32, "thin_film_nm": 320.0},
        "scales": {"metallic": 0.78, "roughness": 0.2, "thin_film_nm": 380.0},
        "operculum": {"metallic": 0.85, "roughness": 0.22, "thin_film_nm": 300.0},
        "fin": {"base": [0.11, 0.14, 0.19], "transmission": 0.35, "roughness": 0.38, "alpha": 0.93},
        "eye": {"base": [0.012, 0.012, 0.015], "roughness": 0.04, "coat": 1.0},
        "dorsal_colour": [0.018, 0.05, 0.13], "ventral_colour": [0.78, 0.8, 0.84],
    },
}


def args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--glb", required=True); ap.add_argument("--out", required=True)
    ap.add_argument("--mode", choices=("still", "turntable"), default="still")
    ap.add_argument("--samples", type=int, default=256)
    ap.add_argument("--res", type=int, nargs=2, default=[1920, 1080])
    ap.add_argument("--frames", type=int, default=48)
    return ap.parse_args(argv)


def gradient_material(name, m, cfg, z_lo, z_hi):
    mat = bpy.data.materials.new(name); mat.use_nodes = True
    nt = mat.node_tree; bsdf = nt.nodes["Principled BSDF"]
    tc = nt.nodes.new("ShaderNodeTexCoord"); sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    mr = nt.nodes.new("ShaderNodeMapRange"); ramp = nt.nodes.new("ShaderNodeValToRGB")
    mr.inputs["From Min"].default_value = z_lo; mr.inputs["From Max"].default_value = z_hi
    ramp.color_ramp.elements[0].position = 0.35; ramp.color_ramp.elements[1].position = 0.62
    ramp.color_ramp.elements[0].color = (*cfg["ventral_colour"], 1); ramp.color_ramp.elements[1].color = (*cfg["dorsal_colour"], 1)
    nt.links.new(tc.outputs["Object"], sep.inputs["Vector"]); nt.links.new(sep.outputs["Z"], mr.inputs["Value"])
    nt.links.new(mr.outputs["Result"], ramp.inputs["Fac"]); nt.links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Metallic"].default_value = m["metallic"]; bsdf.inputs["Roughness"].default_value = m["roughness"]
    if "Thin Film Thickness" in bsdf.inputs:
        bsdf.inputs["Thin Film Thickness"].default_value = m["thin_film_nm"]
    return mat


def plain_material(name, base, roughness, metallic=0.0, transmission=0.0, alpha=1.0, coat=0.0):
    mat = bpy.data.materials.new(name); mat.use_nodes = True
    b = mat.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*base, 1); b.inputs["Roughness"].default_value = roughness
    b.inputs["Metallic"].default_value = metallic; b.inputs["Transmission Weight"].default_value = transmission
    b.inputs["Alpha"].default_value = alpha; b.inputs["Coat Weight"].default_value = coat
    return mat


def main():
    a = args()
    glb = Path(a.glb).resolve(); out = Path(a.out).resolve(); out.mkdir(parents=True, exist_ok=True)
    build = json.loads((glb.parent / "build.json").read_text())
    glb_sha = hashlib.sha256(glb.read_bytes()).hexdigest()
    if glb_sha != build["files"]["fish.glb"]:
        raise SystemExit(f"fish.glb sha256 {glb_sha} != build.json {build['files']['fish.glb']}: refusing to render")
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(glb))
    objs = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    sl = max(max(v.co.x for v in o.data.vertices) for o in objs if o.name.startswith("body"))
    zs = [v.co.z for o in objs if o.name.startswith("body") for v in o.data.vertices]
    cfg = SETTINGS["materials"]
    mats = {"body": gradient_material("body", cfg["body"], cfg, min(zs), max(zs)),
            "scales": gradient_material("scales", cfg["scales"], cfg, min(zs), max(zs)),
            "operculum": gradient_material("operculum", cfg["operculum"], cfg, min(zs), max(zs)),
            "fin": plain_material("fin", cfg["fin"]["base"], cfg["fin"]["roughness"], transmission=cfg["fin"]["transmission"],
                                  alpha=cfg["fin"]["alpha"]),
            "eye": plain_material("eye", cfg["eye"]["base"], cfg["eye"]["roughness"], coat=cfg["eye"]["coat"])}
    imported = {}
    pivot = bpy.data.objects.new("pivot", None); bpy.context.scene.collection.objects.link(pivot)
    allv = [o.matrix_world @ v.co for o in objs for v in o.data.vertices]
    lo = [min(q[i] for q in allv) for i in range(3)]; hi = [max(q[i] for q in allv) for i in range(3)]
    centre = [(lo[i] + hi[i]) / 2 for i in range(3)]
    radius = max(math.dist(q, centre) for q in allv)
    pivot.location = centre
    bpy.context.view_layer.update()  # else the children are re-parented against a stale identity matrix
    for o in objs:
        key = o.name.split(".")[0]
        kind = ("body" if key == "body" else "scales" if key == "scales" else "operculum" if key.startswith("operculum")
                else "eye" if key.startswith("eye") else "fin")
        o.data.materials.clear(); o.data.materials.append(mats[kind])
        for p in o.data.polygons:
            p.use_smooth = kind in ("body", "eye", "operculum")
        o.data.calc_loop_triangles()
        imported[key] = {"triangles": len(o.data.loop_triangles), "vertices": len(o.data.vertices), "material": kind}
        mw = o.matrix_world.copy(); o.parent = pivot; o.matrix_world = mw
    sc = bpy.context.scene; st = SETTINGS
    sc.render.engine = "CYCLES"; sc.cycles.device = "CPU"; sc.cycles.samples = a.samples
    sc.cycles.use_denoising = True; sc.cycles.denoiser = "OPENIMAGEDENOISE"; sc.cycles.seed = 0
    sc.render.threads_mode = "FIXED"; sc.render.threads = st["threads"]
    sc.render.resolution_x, sc.render.resolution_y = a.res; sc.render.resolution_percentage = 100
    sc.view_settings.view_transform = st["view_transform"]; sc.view_settings.look = st["look"]
    sc.render.image_settings.file_format = "PNG"; sc.render.image_settings.color_depth = "8"
    sc.render.film_transparent = st["film_transparent"]; sc.render.image_settings.color_mode = "RGBA"
    world = bpy.data.worlds.new("sky"); sc.world = world; world.use_nodes = True
    sky = world.node_tree.nodes.new("ShaderNodeTexSky"); sky.sky_type = st["sky"]["type"]
    sky.sun_elevation = math.radians(st["sky"]["sun_elevation_deg"]); sky.sun_rotation = math.radians(st["sky"]["sun_rotation_deg"])
    bg = world.node_tree.nodes["Background"]; bg.inputs["Strength"].default_value = st["sky"]["strength"]
    world.node_tree.links.new(sky.outputs["Color"], bg.inputs["Color"])
    sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun", "SUN")); sc.collection.objects.link(sun)
    sun.data.energy = st["sun"]["strength"]; sun.data.angle = math.radians(st["sun"]["angle_deg"])
    sun.rotation_euler = [math.radians(q) for q in st["sun"]["rotation_deg"]]
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam")); sc.collection.objects.link(cam); sc.camera = cam
    c = st["camera"]; cam.data.lens = c["lens_mm"]
    fov_v = 2 * math.atan(0.5 * cam.data.sensor_width * a.res[1] / a.res[0] / c["lens_mm"])
    d = c["framing"][a.mode] * radius / math.sin(fov_v / 2)
    el, az = math.radians(c["elevation_deg"]), math.radians(c["azimuth_deg"])
    cam.location = (centre[0] + d * math.cos(el) * math.cos(az), centre[1] - d * math.cos(el) * math.sin(az),
                    centre[2] + d * math.sin(el))
    tr = cam.constraints.new("TRACK_TO"); tr.target = pivot; tr.track_axis = "TRACK_NEGATIVE_Z"; tr.up_axis = "UP_Y"
    frames = []
    n = 1 if a.mode == "still" else a.frames
    for i in range(n):
        pivot.rotation_euler = (0, 0, 2 * math.pi * i / n)
        sc.render.filepath = str(out / f"frame_{i:03d}.png")
        bpy.ops.render.render(write_still=True)
        frames.append(sc.render.filepath)
    rep = {"blender": bpy.app.version_string, "glb": str(glb), "glb_sha256": glb_sha,
           "candidate_sha256": build["candidate_sha256"], "mode": a.mode, "samples": a.samples, "resolution": a.res,
           "frames": len(frames), "settings": SETTINGS,
           "framing": {"centre_m": centre, "bounding_radius_m": radius, "camera_distance_m": d}, "imported": imported,
           "evidence_kind": "path-traced rendering of the candidate mesh; not a measurement, not aerodynamics"}
    (out / "blender_report.json").write_text(json.dumps(rep, indent=1, sort_keys=True) + "\n")
    print("BLENDER-DONE", len(frames))


main()
