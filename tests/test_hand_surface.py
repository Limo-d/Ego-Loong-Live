from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class HandSurfaceFrontendTests(unittest.TestCase):
    def test_surface_is_default_and_debug_is_optional(self):
        dashboard = (ROOT / "frontend/dashboard.html").read_text(encoding="utf-8")
        hand_view = (ROOT / "frontend/js/hand_view.js").read_text(encoding="utf-8")
        self.assertIn('<option value="surface">重建手</option>', dashboard)
        self.assertIn('<option value="skeleton">骨架</option>', dashboard)
        self.assertIn("this.displayMode = 'surface'", hand_view)
        self.assertIn("this.axes.visible = false", hand_view)
        self.assertIn("this.grid.visible = false", hand_view)
        self.assertIn("HAND_OFFSET = Object.freeze({left: -86, right: 86})", hand_view)
        self.assertIn("(point[1] - root[1]) * scale", hand_view)
        self.assertNotIn("-(point[1] - root[1]) * scale", hand_view)
        self.assertIn("hand back faces the front camera", hand_view)
        self.assertIn("positive finger flexion travels into the screen", hand_view)
        self.assertIn("hand.debug.update(points", hand_view)

    def test_procedural_surface_is_persistent_and_has_no_forearm_oval(self):
        model = (ROOT / "frontend/js/hand/hand_model_loader.js").read_text(encoding="utf-8")
        surface = (ROOT / "frontend/js/hand/hand_surface_geometry.js").read_text(encoding="utf-8")
        self.assertIn("createPalmGeometry", model)
        self.assertIn("SmoothFingerSurface", model)
        self.assertIn("PalmMcpBridgeSurface", model)
        self.assertIn("longitudinalSegments = 28", surface)
        self.assertIn("position.needsUpdate = true", surface)
        self.assertIn("const FINGER_SHAPES", surface)
        self.assertIn("thumbWidth:", surface)
        self.assertNotIn("const startCenter", surface)
        self.assertNotIn("const topCenter", surface)
        self.assertIn("MCP end deliberately remains open", surface)
        self.assertIn("this.mesh.castShadow = false", surface)
        self.assertIn("rootDepthFlare", surface)
        self.assertIn("palm-mcp-bridge-surface", surface)
        self.assertIn("rootExtension: finger === 'thumb' ? THUMB_VISUAL_MAPPING.geometry.rootExtension : 1.80", model)
        self.assertNotIn("new THREE.CylinderGeometry", model)
        self.assertEqual(surface.count("new THREE.CylinderGeometry"), 1)
        self.assertIn("const lengthScale = 0.74", model)
        self.assertIn("buildVisualThumbPoints", model)
        self.assertNotIn("wrist-surface", model)
        self.assertNotIn("new THREE", model.split("updateGeometry()", 1)[1])

    def test_thumb_surface_is_three_dof_bounded_and_collision_aware(self):
        mapping = (ROOT / "frontend/js/hand/hand_joint_mapping.js").read_text(encoding="utf-8")
        thumb = (ROOT / "frontend/js/hand/thumb_visual_mapping.js").read_text(encoding="utf-8")
        model = (ROOT / "frontend/js/hand/hand_model_loader.js").read_text(encoding="utf-8")
        surface = (ROOT / "frontend/js/hand/hand_surface_geometry.js").read_text(encoding="utf-8")
        self.assertIn("rawDof: 6", mapping)
        self.assertIn("['cmc_opposition', 'mcp_flex', 'ip_flex']", mapping)
        self.assertIn("cmc_axial_twist", mapping)
        self.assertIn("left: Object.freeze", mapping)
        self.assertIn("right: Object.freeze", mapping)
        self.assertIn("projectOutsidePalm", thumb)
        self.assertIn("separateFromIndex", thumb)
        self.assertIn("THREE.MathUtils.clamp", thumb)
        self.assertIn("const FINGER_WEBS", surface)
        self.assertIn("const thenarPad", surface)
        self.assertIn("const rootPad", surface)
        self.assertIn("if (side === 'left')", surface)
        self.assertIn("side === 'left' ? -1 : 1", surface)
        self.assertIn("palmNormal: -1", mapping)
        self.assertNotIn("thumb-web-transition", model)
        self.assertIn("rootExtension: finger === 'thumb' ? THUMB_VISUAL_MAPPING.geometry.rootExtension", model)

    def test_soft_candy_material_and_tactile_color_is_opt_in(self):
        material = (ROOT / "frontend/js/hand/hand_material.js").read_text(encoding="utf-8")
        model = (ROOT / "frontend/js/hand/hand_model_loader.js").read_text(encoding="utf-8")
        cute_style = (ROOT / "frontend/css/hand-cute.css").read_text(encoding="utf-8")
        self.assertIn("'#b9dcff'", material)
        self.assertIn("'#ffd1dc'", material)
        self.assertIn("new THREE.MeshLambertMaterial", material)
        self.assertIn("emissiveIntensity: 0.46", material)
        overlay = (ROOT / "frontend/js/hand/hand_tactile_overlay.js").read_text(encoding="utf-8")
        self.assertIn("material.emissive?.copy", overlay)
        self.assertIn("radial-gradient", cute_style)
        self.assertIn("{enabled: false}", model)

    def test_debug_skeleton_uses_origin_cylinders_glow_and_palm_arch(self):
        skeleton = (ROOT / "frontend/js/hand/hand_debug_skeleton.js").read_text(encoding="utf-8")
        material = (ROOT / "frontend/js/hand/hand_material.js").read_text(encoding="utf-8")
        hand_view = (ROOT / "frontend/js/hand_view.js").read_text(encoding="utf-8")
        self.assertIn("const ORIGIN_TO_SCENE = 0.82", skeleton)
        self.assertIn("new THREE.CylinderGeometry(1, 1, 1, 10)", skeleton)
        self.assertIn("new THREE.SphereGeometry(1, 14, 10)", skeleton)
        self.assertIn("const PALM_EDGES", skeleton)
        self.assertIn("this.forearmSegment", skeleton)
        self.assertNotIn("new THREE.LineSegments", skeleton)
        self.assertIn("bone: 0x76bdf0", material)
        self.assertIn("bone: 0xf2a7ba", material)
        self.assertIn("color: 0xffad72", material)
        self.assertIn("THREE.NormalBlending", material)
        self.assertIn("jointGlow", material)
        self.assertNotIn("0x04060a", hand_view)
        self.assertIn("this.renderer.setClearColor(0x000000, 0)", hand_view)

    def test_tactile_overlay_hook_remains_region_level(self):
        mapping = (ROOT / "frontend/js/hand/hand_joint_mapping.js").read_text(encoding="utf-8")
        app = (ROOT / "frontend/js/app.js").read_text(encoding="utf-8")
        self.assertIn("TACTILE_REGION_INDICES", mapping)
        self.assertIn("hand.updateTactile(side,m.data)", app)


if __name__ == "__main__":
    unittest.main()
