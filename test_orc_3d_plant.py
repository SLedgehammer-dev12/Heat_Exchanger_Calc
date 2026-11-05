"""Unit tests for the 3D Industrial Plant / Digital Twin Component."""

import math
import re
import unittest

import orc_3d_plant_component
import orc_schematic_component


class TestOrc3DPlantComponent(unittest.TestCase):
    def test_3d_container_html(self):
        """Container HTML must include 3D mount point, toolbar, and telemetry HUD."""
        html = orc_3d_plant_component.get_orc_3d_plant_container_html()
        self.assertIn('id="container_3d"', html)
        self.assertIn('id="canvas_3d_mount"', html)
        self.assertIn("btn-3d-cam", html)
        self.assertIn('id="hud_3d_card"', html)
        self.assertIn("🎥 İzometrik", html)
        self.assertIn("📐 Üstten P&ID", html)
        self.assertIn("⚡ Türbin Odak", html)

    def test_3d_plant_js_structure(self):
        """JavaScript module must contain 3D scene builders, foundation, pipe racks, and animations."""
        js = orc_3d_plant_component.get_orc_3d_plant_js()
        # Foundation & Plinths
        self.assertIn("buildConcreteFoundation", js)
        self.assertIn("BoxGeometry(165, 1.2, 115)", js)  # Concrete slab
        self.assertIn("plinths3D", js)  # Equipment plinths

        # Pipe racks & supports
        self.assertIn("buildPipeRacksAndSupports", js)
        self.assertIn("pipe shoes", js.lower())

        # Equipment & Piping
        self.assertIn("buildPlantEquipment", js)
        self.assertIn("buildOrthogonalPipingNetwork", js)
        self.assertIn("addStraightSpool", js)
        self.assertIn("addElbow90", js)
        self.assertIn("addFlangePair", js)
        self.assertIn("buildOrthogonalRun", js)
        self.assertIn("U-TURN", js)  # Thermal expansion loop
        self.assertIn("buildParticleFlowStreams", js)
        self.assertIn("boilerRisers3D", js)

        # Interactivity & Sync
        self.assertIn("switchViewMode", js)
        self.assertIn("updatePlant3D", js)
        self.assertIn("on3DMouseClick", js)
        self.assertIn("show3DTelemetryHUD", js)

    def test_integrated_schematic_html(self):
        """Integrated schematic must provide seamless 2D and 3D views."""
        html = orc_schematic_component.get_orc_schematic_html({"n_boilers": 3})
        self.assertIn('id="btn_view_2d"', html)
        self.assertIn('id="btn_view_3d"', html)
        self.assertIn("switchViewMode", html)
        self.assertIn('id="container_3d"', html)
        self.assertIn('id="schematic_svg"', html)
        self.assertIn("three.min.js", html)
        self.assertIn("OrbitControls.js", html)
        self.assertIn("updatePlant3D", html)

    def test_standalone_3d_plant_html(self):
        """Standalone 3D plant HTML page must be self-contained."""
        html = orc_3d_plant_component.get_standalone_3d_plant_html({"n_boilers": 4})
        self.assertIn("<!DOCTYPE html>", html)
        self.assertIn('id="canvas_3d_mount"', html)
        self.assertIn("init3DPlant()", html)

    def test_latest_calc_result_caching_and_scoping(self):
        """updatePlant3D must cache latestCalcResult even before 3D is initialized."""
        js = orc_3d_plant_component.get_orc_3d_plant_js()
        # Verify caching occurs before is3DInitialized check
        idx_cache = js.find("window.latestCalcResult = calcResult;")
        idx_guard = js.find("if (!is3DInitialized) return;")
        self.assertGreater(idx_cache, 0)
        self.assertGreater(idx_guard, 0)
        self.assertLess(idx_cache, idx_guard)
        # Verify stainlessMat in buildOrthogonalPipingNetwork
        self.assertIn("const stainlessMat = new THREE.MeshStandardMaterial", js)

    def test_acc_and_cooling_tower_specialization_in_js(self):
        """3D plant JS must contain distinct models and dynamic toggling for ACC vs Cooling Tower."""
        js = orc_3d_plant_component.get_orc_3d_plant_js()

        # ACC Gantry, Bundles, and Forced-Draft Fans
        self.assertIn("accGroup = new THREE.Group()", js)
        self.assertIn("accFanRotors = []", js)
        self.assertIn("gantryMat", js)
        self.assertIn("fanDeck", js)
        self.assertIn("steamHeader", js)
        self.assertIn("accFanRotors.forEach", js)

        # Water Cooling Tower, Surface Condenser, and Induced-Draft Top Fan
        self.assertIn("waterCondenserGroup = new THREE.Group()", js)
        self.assertIn("towerFanRotor", js)
        self.assertIn("coolingTowerMist", js)
        self.assertIn("sShell", js)  # Surface condenser shell
        self.assertIn("sPlinth", js)  # Surface condenser plinth
        self.assertIn("towerBody", js)  # Cooling tower casing
        self.assertIn("towerStack", js)  # Top fan stack
        self.assertIn("cwSupplyPipe", js)  # Circulating water piping
        self.assertIn("cwReturnPipe", js)

        # Dynamic Condenser Toggle in updatePlant3D
        self.assertIn("accGroup.visible = isAir", js)
        self.assertIn("waterCondenserGroup.visible = !isAir", js)
        self.assertIn("accPipingGroup.visible = isAir", js)
        self.assertIn("waterPipingGroup.visible = !isAir", js)

    def test_condenser_camera_preset_and_toolbar(self):
        """Toolbar and camera presets must provide dedicated condenser focus."""
        html = orc_3d_plant_component.get_orc_3d_plant_container_html()
        js = orc_3d_plant_component.get_orc_3d_plant_js()
        self.assertIn("window.set3DCameraPreset('condenser')", html)
        self.assertIn('preset === "condenser"', js)

    def test_clash_free_orthogonal_piping_and_nozzles(self):
        """3D plant JS must verify clash-free routing, 3-way bypass, and equipment nozzles."""
        js = orc_3d_plant_component.get_orc_3d_plant_js()

        # PH Vapor Dome & Nozzles
        self.assertIn("phDome", js)
        self.assertIn("phDomeFlange", js)
        self.assertIn("phNozOilIn", js)
        self.assertIn("phNozOilOut", js)
        self.assertIn("phNozLiqIn", js)

        # SH Nozzles
        self.assertIn("shNozIn", js)
        self.assertIn("shNozOut", js)
        self.assertIn("shVapIn", js)
        self.assertIn("shVapOut", js)

        # 3-Way Valve Bypass Line
        self.assertIn("v101BypassWaypoints", js)
        self.assertIn("buildOrthogonalRun(v101BypassWaypoints", js)

        # Sleeper routing avoiding vessel clashes
        self.assertIn("-13.5", js)  # Sleeper corridor offset avoiding PH saddle
        self.assertIn("31.8", js)  # P-101 pump suction nozzle avoiding motor
        self.assertIn("38.5", js)  # Channel head liquid inlet avoiding shell mid-span
        self.assertIn("9.8", js)  # Overhead vapor bridge avoiding SH crown
        self.assertIn("-21.5", js)  # Dedicated north corridor for PH->SH vapor bridge

    def test_sh_pipe_separation_and_v101_upstream_pump_tie_in(self):
        """Verify SH oil/cyclopentane pipes do not overlap and V-101 3rd port ties upstream of P-101."""
        js = orc_3d_plant_component.get_orc_3d_plant_js()

        def extract_pts(name):
            match = re.search(rf"const\s+{name}\s*=\s*\[(.*?)\];", js, re.DOTALL)
            self.assertIsNotNone(match, f"Missing {name}")
            return [
                tuple(float(v) for v in m)
                for m in re.findall(
                    r"Vector3\(\s*([-\d.]+)\s*,\s*([-\d.]+)\s*,\s*([-\d.]+)\s*\)",
                    match.group(1),
                )
            ]

        bypass_pts = extract_pts("v101BypassWaypoints")
        ph_to_pump_pts = extract_pts("phToPumpWaypoints")
        pump_to_manifold_pts = extract_pts("pumpToManifoldWaypoints")

        # 1. V-101 bypass must terminate at a point on phToPumpWaypoints (upstream of P-101 suction)
        self.assertIn(bypass_pts[-1], ph_to_pump_pts)
        # And must NOT terminate on the downstream Cold Distribution Header (z = -24.0)
        self.assertNotEqual(bypass_pts[-1][2], -24.0)
        self.assertNotIn(bypass_pts[-1], pump_to_manifold_pts)

        # 2. SH Hot Oil lines (hotToSh, shToPh) and Cyclopentane lines (phToShVapor, shToTurb) must be separated
        hot_to_sh = extract_pts("hotToShWaypoints")
        sh_to_turb = extract_pts("shToTurbWaypoints")
        # hotToSh approaches from north (z = -21.0), shToTurb exits south (z = -6.0)
        self.assertTrue(any(p[2] == -21.0 for p in hot_to_sh))
        self.assertTrue(any(p[2] == -6.0 for p in sh_to_turb))

    def test_orc_loop_turbine_acc_pump_and_2d_3d_condenser_sync(self):
        """Verify turbine inlet/exhaust separation, ACC default priority, condensate manifold, and 2D/3D condenser sync."""
        js = orc_3d_plant_component.get_orc_3d_plant_js()
        html = orc_schematic_component.get_orc_schematic_html()

        def extract_pts(name):
            match = re.search(rf"const\s+{name}\s*=\s*\[(.*?)\];", js, re.DOTALL)
            self.assertIsNotNone(match, f"Missing {name}")
            return [
                tuple(float(v) for v in m)
                for m in re.findall(
                    r"Vector3\(\s*([-\d.]+)\s*,\s*([-\d.]+)\s*,\s*([-\d.]+)\s*\)",
                    match.group(1),
                )
            ]

        sh_to_turb = extract_pts("shToTurbWaypoints")
        turb_to_acc = extract_pts("turbToAccWaypoints")
        turb_to_water = extract_pts("turbToWaterCondWaypoints")
        cond_to_pump = extract_pts("condToPumpWaypoints")

        # 1. Turbine HP Inlet (x=34.5, y=5.6, z=32.0) and LP Exhaust Hood (x=32.5, y=6.2, z=32.0) are distinct and clash-free
        self.assertIn("turbInletNoz", js)
        self.assertIn("turbExhaustHood", js)
        self.assertIn("turbExhaustNoz", js)
        self.assertEqual(sh_to_turb[-1], (34.5, 5.6, 32.0))
        self.assertEqual(turb_to_acc[0], (32.5, 6.2, 32.0))
        self.assertEqual(turb_to_water[0], (32.5, 6.2, 32.0))
        # shToTurb approaches from north (z = 26.0 -> 32.0) at x = 34.5, never sharing z = 32.0 with turbToAcc (x <= 32.5)
        self.assertIn((34.5, 7.2, 26.0), sh_to_turb)
        self.assertEqual(turb_to_acc[-1], (7.0, 12.0, 32.0))  # ACC East Apex Steam Header Nozzle

        # 2. ACC Condensate Manifold collects both rear (z=37.8) and front (z=26.2) headers at x=-24.6 (clear of columns at x=-22, -8, 6)
        self.assertEqual(cond_to_pump[0], (-24.6, 5.3, 37.8))
        self.assertIn((-24.6, 5.3, 24.0), cond_to_pump)
        self.assertIn((-24.6, 1.5, 24.0), cond_to_pump)
        self.assertEqual(cond_to_pump[-1], (-15.8, 1.5, 13.5))  # P-102 suction nozzle

        # 3. ACC is prioritized as default condenser in 2D and 3D, with dynamic 2D/3D structure switching
        self.assertIn("condenser_type: 'air'", html)
        self.assertIn('id="svg_cond_acc"', html)
        self.assertIn('id="svg_cond_water"', html)
        self.assertIn("💨 KONDENSER (ACC)", html)
        self.assertIn("set3DCondenserType", js)

    def test_elbow_orientation_and_pipe_continuity_invariants(self):
        """Verify 90° elbows are C1-continuous (not inverted) and all segments are orthogonal with length > rBend."""
        js = orc_3d_plant_component.get_orc_3d_plant_js()

        # 1. Ensure double-negation bug in addElbow90 call is absent
        self.assertNotIn("segDir.clone().negate()", js)
        self.assertIn("addElbow90(pB, segDir, nextDir, cornerRadii[i + 1], pipeRadius, mat, parentGrp)", js)

        # 2. Extract all named waypoint arrays and verify orthogonality, non-collinearity, and segment lengths
        waypoint_names = [
            "hotToShWaypoints",
            "v101BypassWaypoints",
            "shToPhWaypoints",
            "phToPumpWaypoints",
            "pumpToManifoldWaypoints",
            "condToPumpWaypoints",
            "waterCondToPumpWaypoints",
            "pumpToPhWaypoints",
            "phToShVaporWaypoints",
            "shToTurbWaypoints",
            "turbToAccWaypoints",
            "turbToWaterCondWaypoints",
        ]
        for name in waypoint_names:
            pattern = rf"const\s+{name}\s*=\s*\[(.*?)\];"
            match = re.search(pattern, js, re.DOTALL)
            self.assertIsNotNone(match, f"Missing waypoint array {name}")
            pts = [
                tuple(float(v) for v in m)
                for m in re.findall(
                    r"Vector3\(\s*([-\d.]+)\s*,\s*([-\d.]+)\s*,\s*([-\d.]+)\s*\)",
                    match.group(1),
                )
            ]
            self.assertGreaterEqual(len(pts), 3, f"{name} must have at least 3 points")

            dirs = []
            for i in range(len(pts) - 1):
                dx = pts[i + 1][0] - pts[i][0]
                dy = pts[i + 1][1] - pts[i][1]
                dz = pts[i + 1][2] - pts[i][2]
                seg_len = math.sqrt(dx * dx + dy * dy + dz * dz)
                # Every segment must be >= 1.1m (> max rBend 0.8m) to prevent spool inversion
                self.assertGreaterEqual(seg_len, 1.05, f"Segment {i} in {name} is too short ({seg_len:.2f}m < 1.05m)")
                # Every segment must be strictly axis-aligned (only 1 non-zero component)
                non_zero_axes = sum(1 for c in (dx, dy, dz) if abs(c) > 1e-4)
                self.assertEqual(non_zero_axes, 1, f"Segment {i} in {name} is not orthogonal: {(dx, dy, dz)}")
                dirs.append((dx / seg_len, dy / seg_len, dz / seg_len))

            # Consecutive segments must make a clean 90-degree turn (dot product == 0)
            for i in range(len(dirs) - 1):
                dot = dirs[i][0] * dirs[i + 1][0] + dirs[i][1] * dirs[i + 1][1] + dirs[i][2] * dirs[i + 1][2]
                self.assertAlmostEqual(
                    dot, 0.0, places=4, msg=f"Corner {i + 1} in {name} is not a 90° turn (dot={dot})"
                )

    def test_whru_boiler_count_2d_3d_sync_and_bright_lighting(self):
        """Verify 2D/3D WHRU boiler count sync (1..5), ReferenceError-free recalculate, and bright 3D scene lighting."""
        html = orc_schematic_component.get_orc_schematic_html({"n_boilers": 3})
        js = orc_3d_plant_component.get_orc_3d_plant_js()
        container_html = orc_3d_plant_component.get_orc_3d_plant_container_html()

        # 1. Verify dp_static_bar and dp_hx_bar are defined before dp_bar in recalculate() so updatePlant3D is always reached
        idx_dp_hx_def = html.find("const dp_hx_bar =")
        idx_dp_bar_use = html.find("const dp_bar = dp_pipes_sum_bar + max_dp + dp_hx_bar;")
        idx_update_3d = html.find("window.updatePlant3D(plant3DTelemetry);")
        self.assertGreater(idx_dp_hx_def, 0)
        self.assertGreater(idx_dp_bar_use, idx_dp_hx_def)
        self.assertGreater(idx_update_3d, idx_dp_bar_use)

        # 2. Verify 2D <-> 3D WHRU boiler count & equipment ID synchronization hooks
        self.assertIn("window.currentBoilerCount = state.n_boilers;", html)
        self.assertIn("window.setBoilerCount = setBoilerCount;", html)
        self.assertIn("window.changeBoilerCount = changeBoilerCount;", html)
        self.assertIn("window.recalculate = recalculate;", html)
        self.assertIn("function normalizeEquipmentId(rawEq)", html)
        self.assertIn("window.sync3DBoilerCount = function(count)", js)
        self.assertIn("window.change3DBoilerCount = function(delta)", js)
        self.assertIn("window.sync3DSelectedEquipment = function(eqId)", js)
        self.assertIn("window.selected3DObject", js)
        self.assertIn('id: "node_valve"', js)
        self.assertIn("window.sync3DBoilerCount(initBoilerCount);", js)
        self.assertIn('id="lbl_3d_whru_count"', container_html)
        self.assertIn("isObjectVisibleInHierarchy", js)

        # 3. Verify bright daylight / studio lighting & non-dark PBR materials in 3D scene
        self.assertIn("new THREE.Color(0xe8f0fe)", js)
        self.assertIn("new THREE.HemisphereLight(0xffffff, 0xcbd5e1, 0.95)", js)
        self.assertIn("ACESFilmicToneMapping", js)
        # Ensure high metalness (>= 0.70) without envMap is eliminated in 3D plant
        metalness_vals = [float(v) for v in re.findall(r"metalness:\s*([0-9.]+)", js)]
        self.assertTrue(len(metalness_vals) > 0)
        for mv in metalness_vals:
            self.assertLessEqual(mv, 0.45, f"Material metalness {mv} is too high without envMap and darkens 3D scene")


if __name__ == "__main__":
    unittest.main()
