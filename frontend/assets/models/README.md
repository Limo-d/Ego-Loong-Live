# Hand model assets

No third-party hand mesh is bundled at present.

The local reference scan found no reusable GLB/GLTF/FBX human-hand SkinnedMesh in
`/home/lenovo/Retarget`. MANO PKL files and static 778-vertex NPZ exports exist under the
post-processing repository, but the NPZ files contain only vertices/faces and no skeleton or skin
weights. The MANO license also restricts redistribution, so those files were not copied here.

The live viewer therefore uses the procedural FK-driven surface in
`frontend/js/hand/hand_model_loader.js` and `frontend/js/hand/hand_surface_geometry.js`: one asymmetric
palmar/dorsal surface with integrated thenar, hypothenar, first-web and finger-root shaping, plus
continuous open-root spline fingers. This directory is reserved for a future separately licensed
left/right GLB pair. Any future model must first have its complete bone hierarchy audited and mapped
explicitly to the verified Retarget state27 layout.
