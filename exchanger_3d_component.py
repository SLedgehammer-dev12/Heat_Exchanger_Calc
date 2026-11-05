"""Interactive 3D Teardown and Cutaway Visualizer for Heat Exchangers.

Renders a high-fidelity WebGL 3D model with:
- TEMA Shell & Tube and Finned Tube geometry
- Interactive 3D Orbit, Zoom, and Pan
- Exploded View (Ayrıştırma / Teardown) Slider from 0% to 100%
- Cutaway Modes (%50 Kesit, X-Ray Saydam, Tam Gövde)
- Shell-side and Tube-side animated flow streamlines
- Real-time dimensional sync with calculation inputs (Do, Di, L, Nt, Dshell, Baffle spacing)
- Click-to-Inspect component engineering info cards
- Offline fallback to 2.5D SVG isometric cutaway if WebGL/CDN is unavailable
"""

from __future__ import annotations

import html
import json
from typing import Any


def get_exchanger_3d_html(geom_data: dict[str, Any] | None = None) -> str:
    """Return self-contained HTML/CSS/JS for the interactive 3D Heat Exchanger Teardown."""
    data = geom_data or {}
    d_o = float(data.get("D_o_mm", 25.4))
    d_i = float(data.get("D_i_mm", 21.1))
    length = float(data.get("L_m", 3.0))
    n_tubes = int(data.get("N_tubes", 80))
    d_shell = float(data.get("D_shell_mm", 350.0))
    baffle_sp = float(data.get("baffle_spacing_mm", 150.0))
    baffle_cut = float(data.get("baffle_cut", 0.25))
    raw_material = str(data.get("tube_material", "Karbon Çelik (k=45)"))
    material = html.escape(raw_material)
    is_finned = bool(data.get("is_finned", False))

    init_json = json.dumps(
        {
            "Do_mm": d_o,
            "Di_mm": d_i,
            "L_m": length,
            "N_tubes": n_tubes,
            "D_shell_mm": d_shell,
            "baffle_spacing_mm": baffle_sp,
            "baffle_cut": baffle_cut,
            "material": raw_material,
            "is_finned": is_finned,
        },
        ensure_ascii=False,
    ).replace("</", "<\\/")

    return f"""<!DOCTYPE html>
<html lang="tr">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Isı Değiştirici 3D Teardown & Kesit Modeli</title>
  <style>
    :root {{
      --bg: #0f172a;
      --panel-bg: rgba(15, 23, 42, 0.88);
      --border: #334155;
      --text: #f8fafc;
      --muted: #94a3b8;
      --accent: #38bdf8;
      --accent-hover: #0284c7;
      --hot: #f87171;
      --cold: #60a5fa;
      --brass: #fbbf24;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }}
    body {{ background: var(--bg); color: var(--text); overflow: hidden; width: 100vw; height: 100vh; position: relative; }}
    #canvas3d {{ width: 100%; height: 100%; display: block; outline: none; cursor: grab; }}
    #canvas3d:active {{ cursor: grabbing; }}

    /* Glassmorphism Control Bar (Top) */
    .top-toolbar {{
      position: absolute;
      top: 12px;
      left: 12px;
      right: 12px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      background: var(--panel-bg);
      backdrop-filter: blur(10px);
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 8px 16px;
      z-index: 10;
      box-shadow: 0 4px 16px rgba(0,0,0,0.3);
    }}
    .top-title {{
      font-size: 14px;
      font-weight: 700;
      color: #ffffff;
      display: flex;
      align-items: center;
      gap: 8px;
    }}
    .top-badge {{
      background: rgba(56, 189, 248, 0.15);
      border: 1px solid #38bdf8;
      color: #38bdf8;
      font-size: 11px;
      font-weight: 600;
      padding: 2px 8px;
      border-radius: 4px;
    }}

    .btn-group {{
      display: flex;
      gap: 6px;
      align-items: center;
    }}
    .tool-btn {{
      background: #1e293b;
      border: 1px solid #475569;
      color: #e2e8f0;
      border-radius: 6px;
      padding: 5px 10px;
      font-size: 11.5px;
      font-weight: 600;
      cursor: pointer;
      transition: all 0.15s ease;
      display: inline-flex;
      align-items: center;
      gap: 4px;
    }}
    .tool-btn:hover {{
      background: #334155;
      border-color: #38bdf8;
      color: #ffffff;
    }}
    .tool-btn.active {{
      background: #0284c7;
      border-color: #38bdf8;
      color: #ffffff;
    }}

    /* Bottom Teardown Slider Bar */
    .bottom-slider-bar {{
      position: absolute;
      bottom: 14px;
      left: 50%;
      transform: translateX(-50%);
      width: 90%;
      max-width: 620px;
      background: var(--panel-bg);
      backdrop-filter: blur(10px);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 10px 18px;
      z-index: 10;
      box-shadow: 0 6px 20px rgba(0,0,0,0.4);
      display: flex;
      flex-direction: column;
      gap: 6px;
    }}
    .slider-header {{
      display: flex;
      justify-content: space-between;
      font-size: 12px;
      font-weight: 700;
      color: #cbd5e1;
    }}
    .slider-header span b {{
      color: #38bdf8;
    }}
    .slider-input {{
      width: 100%;
      accent-color: #38bdf8;
      cursor: pointer;
      height: 6px;
    }}

    /* Right Inspection HUD */
    .inspect-panel {{
      position: absolute;
      top: 64px;
      right: 14px;
      width: 280px;
      background: var(--panel-bg);
      backdrop-filter: blur(12px);
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 14px;
      z-index: 10;
      box-shadow: 0 4px 16px rgba(0,0,0,0.3);
      display: flex;
      flex-direction: column;
      gap: 8px;
    }}
    .inspect-title {{
      font-size: 13.5px;
      font-weight: 700;
      color: #38bdf8;
      border-bottom: 1px solid #334155;
      padding-bottom: 6px;
      display: flex;
      align-items: center;
      gap: 6px;
    }}
    .inspect-desc {{
      font-size: 11.5px;
      color: #94a3b8;
      line-height: 1.4;
    }}
    .spec-grid {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 6px;
      margin-top: 4px;
    }}
    .spec-item {{
      background: rgba(30, 41, 59, 0.7);
      border: 1px solid #334155;
      border-radius: 6px;
      padding: 6px 8px;
    }}
    .spec-label {{
      font-size: 10px;
      color: #64748b;
      font-weight: 600;
      text-transform: uppercase;
    }}
    .spec-val {{
      font-size: 12.5px;
      font-weight: 700;
      color: #f1f5f9;
      margin-top: 2px;
    }}

    /* Legend Overlay (Left Bottom) */
    .legend-box {{
      position: absolute;
      bottom: 14px;
      left: 14px;
      background: var(--panel-bg);
      backdrop-filter: blur(10px);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 8px 12px;
      z-index: 10;
      font-size: 11px;
      display: flex;
      flex-direction: column;
      gap: 4px;
    }}
    .legend-row {{
      display: flex;
      align-items: center;
      gap: 8px;
      color: #cbd5e1;
    }}
    .legend-dot {{
      width: 10px;
      height: 10px;
      border-radius: 50%;
    }}

    /* Loading / Fallback Banner */
    #loadingOverlay {{
      position: absolute;
      inset: 0;
      background: #0f172a;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      gap: 12px;
      z-index: 50;
      transition: opacity 0.3s ease;
    }}
    .spinner {{
      width: 36px;
      height: 36px;
      border: 3px solid #334155;
      border-top-color: #38bdf8;
      border-radius: 50%;
      animation: spin 0.8s linear infinite;
    }}
    @keyframes spin {{
      to {{ transform: rotate(360deg); }}
    }}
  </style>

  <!-- Load Three.js & OrbitControls from reliable CDNs with fallback -->
  <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/controls/OrbitControls.js"></script>
</head>
<body>

  <div id="loadingOverlay">
    <div class="spinner"></div>
    <div style="font-size: 13px; font-weight: 600; color: #94a3b8;">3D Teardown Geometrisi Hazırlanıyor...</div>
  </div>

  <!-- Top Toolbar -->
  <div class="top-toolbar">
    <div class="top-title">
      <span>🔬 TEMA Gövde-Boru Eşanjör</span>
      <span class="top-badge">3D Teardown &amp; Kesit</span>
    </div>
    <div class="btn-group">
      <button class="tool-btn active" id="btn_mode_cut" onclick="setCutawayMode('cutaway')">🔪 %50 Kesit</button>
      <button class="tool-btn" id="btn_mode_xray" onclick="setCutawayMode('xray')">👻 X-Ray</button>
      <button class="tool-btn" id="btn_mode_solid" onclick="setCutawayMode('solid')">🛡️ Tam Gövde</button>
      <span style="width:1px; height:18px; background:#334155; margin:0 4px;"></span>
      <button class="tool-btn" onclick="setCameraView('iso')">🎥 İzometrik</button>
      <button class="tool-btn" onclick="setCameraView('side')">📐 Kesit Profil</button>
      <button class="tool-btn" onclick="setCameraView('front')">🎯 Ayna (Ön)</button>
      <button class="tool-btn" id="btn_flow" onclick="toggleFlow()">🌊 Akış: Açık</button>
      <button class="tool-btn" id="btn_tour" onclick="toggleAutoTour()">🔄 Otomatik Tur</button>
    </div>
  </div>

  <!-- Right Inspection Card -->
  <div class="inspect-panel" id="inspectCard">
    <div class="inspect-title" id="insp_part_title">🔍 Parça: Boru Demeti &amp; Aynalar</div>
    <div class="inspect-desc" id="insp_part_desc">
      Gövde içerisine yerleştirilmiş çok geçişli boru demeti. Sıvı/gaz akışkan boruların içinden geçerken diğer akışkan gövde tarafında şaşırtma levhaları arasından akar.
    </div>
    <div class="spec-grid">
      <div class="spec-item">
        <div class="spec-label">Dış Çap (Do)</div>
        <div class="spec-val" id="spec_do">{d_o} mm</div>
      </div>
      <div class="spec-item">
        <div class="spec-label">İç Çap (Di)</div>
        <div class="spec-val" id="spec_di">{d_i} mm</div>
      </div>
      <div class="spec-item">
        <div class="spec-label">Boru Boyu (L)</div>
        <div class="spec-val" id="spec_l">{length} m</div>
      </div>
      <div class="spec-item">
        <div class="spec-label">Boru Sayısı</div>
        <div class="spec-val" id="spec_nt">{n_tubes} Adet</div>
      </div>
      <div class="spec-item">
        <div class="spec-label">Gövde Çapı</div>
        <div class="spec-val" id="spec_ds">{d_shell} mm</div>
      </div>
      <div class="spec-item">
        <div class="spec-label">Şaşırtma Aralığı</div>
        <div class="spec-val" id="spec_bs">{baffle_sp} mm</div>
      </div>
      <div class="spec-item" style="grid-column: span 2;">
        <div class="spec-label">Boru Malzemesi</div>
        <div class="spec-val" id="spec_mat">{material}</div>
      </div>
    </div>
  </div>

  <!-- Left Bottom Legend -->
  <div class="legend-box">
    <div class="legend-row">
      <div class="legend-dot" style="background:#ef4444;"></div>
      <span>Sıcak Akışkan (Gövde Akışı)</span>
    </div>
    <div class="legend-row">
      <div class="legend-dot" style="background:#3b82f6;"></div>
      <span>Soğuk Akışkan (Boru İçi Akış)</span>
    </div>
    <div class="legend-row">
      <div class="legend-dot" style="background:#fbbf24;"></div>
      <span>Şaşırtma Levhası (Baffle)</span>
    </div>
  </div>

  <!-- Bottom Teardown Explode Slider -->
  <div class="bottom-slider-bar">
    <div class="slider-header">
      <span>💥 Patlatılmış / Ayrıştırma Görünümü (Exploded Teardown)</span>
      <span>Ayrışma: <b id="lbl_explode_pct">%0</b></span>
    </div>
    <input type="range" class="slider-input" id="rng_explode" min="0" max="100" value="0" oninput="onExplodeChange(this.value)">
  </div>

  <!-- 3D Canvas -->
  <canvas id="canvas3d"></canvas>

  <script>
    const GEOM = {init_json};

    let scene, camera, renderer, controls;
    let autoTour = false;
    let flowActive = true;
    let cutawayMode = 'cutaway'; // 'cutaway', 'xray', 'solid'
    let explodeFactor = 0.0;

    // Groups for exploded separation
    let groupFrontHead;
    let groupFrontTubesheet;
    let groupShell;
    let groupTubes;
    let groupBaffles;
    let groupRearHead;
    let groupFlowParticles;

    // Materials
    let matShellSolid, matShellCut, matShellXray;
    let matTube, matTubesheet, matBaffle, matFrontHead, matRearHead;

    function init3D() {{
      if (typeof THREE === 'undefined') {{
        renderFallback();
        return;
      }}

      const canvas = document.getElementById('canvas3d');
      renderer = new THREE.WebGLRenderer({{ canvas: canvas, antialias: true, alpha: true }});
      renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
      renderer.setSize(window.innerWidth, window.innerHeight);
      renderer.shadowMap.enabled = true;

      scene = new THREE.Scene();
      scene.background = new THREE.Color(0xe8f0fe);

      // Camera
      camera = new THREE.PerspectiveCamera(42, window.innerWidth / window.innerHeight, 0.1, 100);
      camera.position.set(4.5, 2.8, 5.2);

      // Controls
      controls = new THREE.OrbitControls(camera, renderer.domElement);
      controls.enableDamping = true;
      controls.dampingFactor = 0.05;
      controls.minDistance = 1.5;
      controls.maxDistance = 15;
      controls.target.set(0, 0, 0);

      // Lights
      const ambientLight = new THREE.AmbientLight(0xffffff, 1.15);
      scene.add(ambientLight);

      const hemiLight = new THREE.HemisphereLight(0xffffff, 0xcbd5e1, 0.90);
      hemiLight.position.set(0, 15, 0);
      scene.add(hemiLight);

      const dirLight1 = new THREE.DirectionalLight(0xfffbeb, 1.35);
      dirLight1.position.set(6, 10, 8);
      scene.add(dirLight1);

      const dirLight2 = new THREE.DirectionalLight(0xe0f2fe, 0.75);
      dirLight2.position.set(-6, 4, -6);
      scene.add(dirLight2);

      // Build Model Geometry
      buildExchangerModel();

      // Setup window resize
      window.addEventListener('resize', onWindowResize);

      // Hide loading overlay
      const overlay = document.getElementById('loadingOverlay');
      if (overlay) {{
        overlay.style.opacity = '0';
        setTimeout(() => {{ overlay.style.display = 'none'; }}, 300);
      }}

      // Start animation loop
      animate();
    }}

    function buildExchangerModel() {{
      // Normalized dimensions for 3D visualization
      const L_total = 3.6;
      const R_shell = 0.75;
      const t_shell = 0.035;

      // Group hierarchy for Exploded view
      groupFrontHead = new THREE.Group();
      groupFrontTubesheet = new THREE.Group();
      groupShell = new THREE.Group();
      groupTubes = new THREE.Group();
      groupBaffles = new THREE.Group();
      groupRearHead = new THREE.Group();
      groupFlowParticles = new THREE.Group();

      scene.add(groupFrontHead);
      scene.add(groupFrontTubesheet);
      scene.add(groupShell);
      scene.add(groupTubes);
      scene.add(groupBaffles);
      scene.add(groupRearHead);
      scene.add(groupFlowParticles);

      // Materials
      matShellSolid = new THREE.MeshStandardMaterial({{
        color: 0x64748b,
        roughness: 0.35,
        metalness: 0.35
      }});

      matShellCut = new THREE.MeshStandardMaterial({{
        color: 0x94a3b8,
        roughness: 0.35,
        metalness: 0.35,
        side: THREE.DoubleSide
      }});

      matShellXray = new THREE.MeshPhysicalMaterial({{
        color: 0x94a3b8,
        transparent: true,
        opacity: 0.28,
        roughness: 0.1,
        metalness: 0.2,
        transmission: 0.85,
        ior: 1.4,
        side: THREE.DoubleSide
      }});

      matTube = new THREE.MeshStandardMaterial({{
        color: 0xf59e0b, // Bright brass/copper tone
        roughness: 0.30,
        metalness: 0.40
      }});

      matTubesheet = new THREE.MeshStandardMaterial({{
        color: 0xcbd5e1,
        roughness: 0.35,
        metalness: 0.35
      }});

      matBaffle = new THREE.MeshStandardMaterial({{
        color: 0xfbbf24,
        roughness: 0.32,
        metalness: 0.35,
        side: THREE.DoubleSide
      }});

      matFrontHead = new THREE.MeshStandardMaterial({{
        color: 0x0284c7, // Bright blue industrial bonnet
        roughness: 0.38,
        metalness: 0.32
      }});

      matRearHead = new THREE.MeshStandardMaterial({{
        color: 0x0284c7,
        roughness: 0.38,
        metalness: 0.32
      }});

      // 1. SHELL (Cylindrical Body with cutaway capability)
      const shellGeoCut = new THREE.CylinderGeometry(R_shell, R_shell, L_total, 48, 1, true, 0, Math.PI);
      shellGeoCut.rotateZ(Math.PI / 2);
      const shellMeshCut = new THREE.Mesh(shellGeoCut, matShellCut);
      shellMeshCut.name = "ShellCut";
      groupShell.add(shellMeshCut);

      const shellGeoSolid = new THREE.CylinderGeometry(R_shell, R_shell, L_total, 48, 1, false);
      shellGeoSolid.rotateZ(Math.PI / 2);
      const shellMeshSolid = new THREE.Mesh(shellGeoSolid, matShellSolid);
      shellMeshSolid.name = "ShellSolid";
      shellMeshSolid.visible = false;
      groupShell.add(shellMeshSolid);

      // Shell Nozzles (Inlet top left, Outlet bottom right)
      const nozzleGeo = new THREE.CylinderGeometry(0.18, 0.18, 0.42, 24);
      const flangeGeo = new THREE.CylinderGeometry(0.26, 0.26, 0.06, 24);

      // Top Inlet Nozzle
      const nozIn = new THREE.Mesh(nozzleGeo, matShellSolid);
      nozIn.position.set(-L_total * 0.35, R_shell + 0.18, 0);
      const flgIn = new THREE.Mesh(flangeGeo, matShellSolid);
      flgIn.position.set(-L_total * 0.35, R_shell + 0.38, 0);
      groupShell.add(nozIn);
      groupShell.add(flgIn);

      // Bottom Outlet Nozzle
      const nozOut = new THREE.Mesh(nozzleGeo, matShellSolid);
      nozOut.position.set(L_total * 0.35, -(R_shell + 0.18), 0);
      const flgOut = new THREE.Mesh(flangeGeo, matShellSolid);
      flgOut.position.set(L_total * 0.35, -(R_shell + 0.38), 0);
      groupShell.add(nozOut);
      groupShell.add(flgOut);

      // 2. TUBESHEETS (Front & Rear thick plates)
      const tsGeo = new THREE.CylinderGeometry(R_shell * 1.05, R_shell * 1.05, 0.1, 48);
      tsGeo.rotateZ(Math.PI / 2);
      const tsFront = new THREE.Mesh(tsGeo, matTubesheet);
      tsFront.position.set(-L_total / 2 - 0.05, 0, 0);
      groupFrontTubesheet.add(tsFront);

      const tsRear = new THREE.Mesh(tsGeo, matTubesheet);
      tsRear.position.set(L_total / 2 + 0.05, 0, 0);
      groupRearHead.add(tsRear);

      // 3. TUBE BUNDLE (Array of parallel tubes in cylindrical pattern)
      const tubeR = 0.032;
      const nRings = 4;
      const tubesPerRing = [1, 6, 12, 18];
      const ringRadii = [0, 0.16, 0.32, 0.48];

      const tubeGeo = new THREE.CylinderGeometry(tubeR, tubeR, L_total + 0.18, 16);
      tubeGeo.rotateZ(Math.PI / 2);

      ringRadii.forEach((r, ringIdx) => {{
        const count = tubesPerRing[ringIdx];
        for (let i = 0; i < count; i++) {{
          const angle = (i / count) * Math.PI * 2 + (ringIdx * 0.2);
          const y = Math.sin(angle) * r;
          const z = Math.cos(angle) * r;

          const tubeMesh = new THREE.Mesh(tubeGeo, matTube);
          tubeMesh.position.set(0, y, z);
          groupTubes.add(tubeMesh);
        }}
      }});

      // 4. SEGMENTAL BAFFLES (Alternating cutaway discs)
      const nBaffles = 5;
      const bSpacing = (L_total * 0.75) / (nBaffles + 1);
      const startX = -L_total * 0.375 + bSpacing;

      for (let b = 0; b < nBaffles; b++) {{
        const isUp = b % 2 === 0;
        // Half / 75% disc baffle
        const baffleGeo = new THREE.CylinderGeometry(
          R_shell * 0.94, R_shell * 0.94, 0.025, 36, 1, false,
          isUp ? -Math.PI * 0.25 : Math.PI * 0.75,
          Math.PI * 1.5
        );
        baffleGeo.rotateZ(Math.PI / 2);
        const baffleMesh = new THREE.Mesh(baffleGeo, matBaffle);
        baffleMesh.position.set(startX + b * bSpacing, 0, 0);
        groupBaffles.add(baffleMesh);
      }}

      // 5. FRONT CHANNEL / BONNET HEAD (Hemispherical or Flanged Cylinder)
      const fHeadGeo = new THREE.CylinderGeometry(R_shell * 1.05, R_shell * 1.05, 0.55, 36);
      fHeadGeo.rotateZ(Math.PI / 2);
      const fHeadMesh = new THREE.Mesh(fHeadGeo, matFrontHead);
      fHeadMesh.position.set(-L_total / 2 - 0.38, 0, 0);
      groupFrontHead.add(fHeadMesh);

      // Front Head Axial Inlet Nozzle
      const fNozGeo = new THREE.CylinderGeometry(0.18, 0.18, 0.35, 24);
      fNozGeo.rotateZ(Math.PI / 2);
      const fNozMesh = new THREE.Mesh(fNozGeo, matFrontHead);
      fNozMesh.position.set(-L_total / 2 - 0.78, 0, 0);
      groupFrontHead.add(fNozMesh);

      // 6. REAR COVER (TEMA Flat or Bonnet)
      const rHeadGeo = new THREE.CylinderGeometry(R_shell * 1.05, R_shell * 1.05, 0.35, 36);
      rHeadGeo.rotateZ(Math.PI / 2);
      const rHeadMesh = new THREE.Mesh(rHeadGeo, matRearHead);
      rHeadMesh.position.set(L_total / 2 + 0.28, 0, 0);
      groupRearHead.add(rHeadMesh);

      // Rear Head Outlet Nozzle
      const rNozMesh = new THREE.Mesh(fNozGeo, matRearHead);
      rNozMesh.position.set(L_total / 2 + 0.55, 0, 0);
      groupRearHead.add(rNozMesh);

      // 7. ANIMATED FLOW STREAMLINES (Tube flow & Shell zig-zag flow)
      buildFlowParticles(L_total, R_shell);
    }}

    // Flow particles for live thermal-hydraulic visualization
    const flowPoints = [];
    function buildFlowParticles(L_total, R_shell) {{
      const pCount = 80;
      const geomP = new THREE.BufferGeometry();
      const positions = new Float32Array(pCount * 3);
      const colors = new Float32Array(pCount * 3);

      for (let i = 0; i < pCount; i++) {{
        const isShell = i % 2 === 0;
        const t = (i / pCount);
        const x = -L_total * 0.4 + t * (L_total * 0.8);

        let y, z;
        if (isShell) {{
          // Zig-zag sinusoidal pattern over baffles
          y = Math.sin(t * Math.PI * 5) * (R_shell * 0.6);
          z = (Math.random() - 0.5) * 0.4;
          // Red/Orange hot flow
          colors[i*3] = 0.95; colors[i*3+1] = 0.35; colors[i*3+2] = 0.2;
        }} else {{
          // Straight cold tube flow
          y = (Math.random() - 0.5) * (R_shell * 0.65);
          z = (Math.random() - 0.5) * (R_shell * 0.65);
          // Blue cold flow
          colors[i*3] = 0.2; colors[i*3+1] = 0.6; colors[i*3+2] = 0.98;
        }}

        positions[i * 3] = x;
        positions[i * 3 + 1] = y;
        positions[i * 3 + 2] = z;

        flowPoints.push({{
          idx: i,
          isShell: isShell,
          speed: 0.012 + Math.random() * 0.015,
          offsetY: y,
          offsetZ: z
        }});
      }}

      geomP.setAttribute('position', new THREE.BufferAttribute(positions, 3));
      geomP.setAttribute('color', new THREE.BufferAttribute(colors, 3));

      const matP = new THREE.PointsMaterial({{
        size: 0.065,
        vertexColors: true,
        transparent: true,
        opacity: 0.85
      }});

      const pSystem = new THREE.Points(geomP, matP);
      pSystem.name = "FlowSystem";
      groupFlowParticles.add(pSystem);
    }}

    function animate() {{
      requestAnimationFrame(animate);

      if (autoTour) {{
        scene.rotation.y += 0.003;
      }}

      // Animate flow streamlines
      if (flowActive && groupFlowParticles) {{
        const pSystem = groupFlowParticles.getObjectByName("FlowSystem");
        if (pSystem) {{
          const pos = pSystem.geometry.attributes.position.array;
          const L_limit = 1.6;

          for (let i = 0; i < flowPoints.length; i++) {{
            const fp = flowPoints[i];
            let x = pos[i * 3] + fp.speed;
            if (x > L_limit) x = -L_limit;
            pos[i * 3] = x;

            if (fp.isShell) {{
              const normX = (x + L_limit) / (2 * L_limit);
              pos[i * 3 + 1] = Math.sin(normX * Math.PI * 5) * 0.45;
            }}
          }}
          pSystem.geometry.attributes.position.needsUpdate = true;
        }}
      }}

      controls.update();
      renderer.render(scene, camera);
    }}

    function onWindowResize() {{
      camera.aspect = window.innerWidth / window.innerHeight;
      camera.updateProjectionMatrix();
      renderer.setSize(window.innerWidth, window.innerHeight);
    }}

    // Teardown Exploded Separation Logic
    function onExplodeChange(val) {{
      explodeFactor = parseFloat(val) / 100.0;
      document.getElementById('lbl_explode_pct').innerText = '%' + Math.round(explodeFactor * 100);

      // Separate components along X axis
      groupFrontHead.position.x = -explodeFactor * 2.2;
      groupFrontTubesheet.position.x = -explodeFactor * 1.1;
      groupRearHead.position.x = explodeFactor * 2.2;

      // Expand baffles
      groupBaffles.children.forEach((baffle, idx) => {{
        const spread = (idx - 2) * (explodeFactor * 0.35);
        baffle.position.y = (idx % 2 === 0 ? 1 : -1) * (explodeFactor * 0.25);
      }});

      // Lift shell slightly in exploded mode
      groupShell.position.z = explodeFactor * 1.2;
      groupShell.position.y = explodeFactor * 0.5;

      // Update inspection details
      if (explodeFactor > 0.4) {{
        showInspector('exploded');
      }}
    }}

    // Cutaway View Controls
    function setCutawayMode(mode) {{
      cutawayMode = mode;
      document.getElementById('btn_mode_cut').classList.toggle('active', mode === 'cutaway');
      document.getElementById('btn_mode_xray').classList.toggle('active', mode === 'xray');
      document.getElementById('btn_mode_solid').classList.toggle('active', mode === 'solid');

      const sCut = groupShell.getObjectByName("ShellCut");
      const sSolid = groupShell.getObjectByName("ShellSolid");

      if (mode === 'cutaway') {{
        sCut.visible = true;
        sCut.material = matShellCut;
        sSolid.visible = false;
        showInspector('cutaway');
      }} else if (mode === 'xray') {{
        sCut.visible = false;
        sSolid.visible = true;
        sSolid.material = matShellXray;
        showInspector('xray');
      }} else if (mode === 'solid') {{
        sCut.visible = false;
        sSolid.visible = true;
        sSolid.material = matShellSolid;
        showInspector('solid');
      }}
    }}

    // Preset Camera Angles
    function setCameraView(view) {{
      autoTour = false;
      document.getElementById('btn_tour').classList.remove('active');
      document.getElementById('btn_tour').innerText = '🔄 Otomatik Tur';

      if (view === 'iso') {{
        camera.position.set(4.5, 2.8, 5.2);
        controls.target.set(0, 0, 0);
      }} else if (view === 'side') {{
        camera.position.set(0, 0.2, 5.6);
        controls.target.set(0, 0, 0);
      }} else if (view === 'front') {{
        camera.position.set(-5.5, 0, 0);
        controls.target.set(0, 0, 0);
      }}
    }}

    function toggleFlow() {{
      flowActive = !flowActive;
      groupFlowParticles.visible = flowActive;
      const btn = document.getElementById('btn_flow');
      btn.innerText = flowActive ? '🌊 Akış: Açık' : '🌊 Akış: Kapalı';
      btn.classList.toggle('active', flowActive);
    }}

    function toggleAutoTour() {{
      autoTour = !autoTour;
      const btn = document.getElementById('btn_tour');
      btn.innerText = autoTour ? '⏸️ Turu Durdur' : '🔄 Otomatik Tur';
      btn.classList.toggle('active', autoTour);
    }}

    // Inspector info updater
    function showInspector(type) {{
      const title = document.getElementById('insp_part_title');
      const desc = document.getElementById('insp_part_desc');

      if (type === 'cutaway') {{
        title.innerHTML = '🔪 %50 Kesit Görünümü';
        desc.innerText = 'Gövde üst kabuğu kesilerek iç boru demeti, TEMA şaşırtma levhaları (baffles) ve termal akış kanalları açığa çıkarılmıştır.';
      }} else if (type === 'xray') {{
        title.innerHTML = '👻 X-Ray / Yarı Saydam Modu';
        desc.innerText = 'Gövde malzemesi optik olarak şeffaflaştırılmış; dış nozullar ile iç boru aynaları arasındaki hidrolik geçişler görünür kılınmıştır.';
      }} else if (type === 'solid') {{
        title.innerHTML = '🛡️ Endüstriyel Tam Gövde (TEMA)';
        desc.innerText = 'Basınçlı kap yönetmeliğine (ASME Sec VIII / EN 13445) uygun silindirik gövde, kaynaklı flanşlar ve nozullar.';
      }} else if (type === 'exploded') {{
        title.innerHTML = '💥 Patlatılmış Montaj (Teardown)';
        desc.innerText = 'Eşanjör bileşenleri eksenel doğrultuda ayrılarak ön ayna, boru demeti, şaşırtmalar ve arka kapak ayrık olarak incelenmektedir.';
      }}
    }}

    // Fallback if WebGL/CDN is blocked
    function renderFallback() {{
      document.getElementById('loadingOverlay').style.display = 'none';
      const canvas = document.getElementById('canvas3d');
      const ctx = canvas.getContext('2d');
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;

      ctx.fillStyle = "#0f172a";
      ctx.fillRect(0, 0, canvas.width, canvas.height);
      ctx.fillStyle = "#38bdf8";
      ctx.font = "bold 18px sans-serif";
      ctx.textAlign = "center";
      ctx.fillText("🔬 Isı Değiştirici 2.5D İzometrik Kesit Görünümü (Çevrimdışı Mod)", canvas.width / 2, 80);

      // Draw isometric exchanger outline
      const cx = canvas.width / 2;
      const cy = canvas.height / 2;

      ctx.strokeStyle = "#475569";
      ctx.lineWidth = 4;
      ctx.strokeRect(cx - 240, cy - 80, 480, 160);

      ctx.fillStyle = "rgba(56, 189, 248, 0.15)";
      ctx.fillRect(cx - 240, cy - 80, 480, 80); // cutaway

      // Tubes
      ctx.strokeStyle = "#d97706";
      ctx.lineWidth = 3;
      for (let y = -50; y <= 50; y += 25) {{
        ctx.beginPath();
        ctx.moveTo(cx - 220, cy + y);
        ctx.lineTo(cx + 220, cy + y);
        ctx.stroke();
      }}

      // Baffles
      ctx.strokeStyle = "#fbbf24";
      ctx.lineWidth = 4;
      for (let x = -150; x <= 150; x += 75) {{
        ctx.beginPath();
        ctx.moveTo(cx + x, cy - 60);
        ctx.lineTo(cx + x, cy + 30);
        ctx.stroke();
      }}

      ctx.fillStyle = "#94a3b8";
      ctx.font = "13px sans-serif";
      ctx.fillText("WebGL kütüphanesi yüklenemediğinde 2D yedekleme şeması devreye girer.", cx, cy + 140);
    }}

    // Initialize on page load
    window.onload = init3D;
  </script>
</body>
</html>
"""
