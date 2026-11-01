# Bioelectric (Hodgkin-Huxley chain) and mechanobiology (motor-clutch) bundles, imported 2026-10-31 20:35:33Z (13:35 PDT)
33 records into `node-a` (7 Claims, 13 Actions, 13 Evidence): 0 forks, 33/33 `imported_unreviewed`, graph gates passed, no warnings.
Bioelectric pinned to root tip 42cbd81 (all 63 manifest files + code hashes recomputed); mechanobio pinned to `work/mechanobio` 76a93e7 (artifacts are not on root's tip).
Compute and render are separate Actions; every render Evidence is `context_only`; 0 Evidence with `supports`; pointers `urn:sha256`/`referenced`.
Conditions, source context (Hodgkin-Huxley 1952 DOI 10.1113/jphysiol.1952.sp004764; Gong et al. PNAS 2018 DOI 10.1073/pnas.1716620115), open questions and the producers' limitations are kept in the records.
Finding kept visible: mechanobio's simulation manifest lists `render.py` as c8934056..., the pinned file (and the render manifest) say a662afe1... ; render.py takes no part in the simulation.
Also fixed: `artifacts.to_artifact_ref` typed every PNG/MP4/STL as application/octet-stream; media types are now video/mp4, image/png, model/stl, model/gltf-binary, so a media resolver can tell them apart.
Single-reader (corpus), not Codex-reviewed, not independently reviewed; neither model is calibrated to any fish or tissue.
