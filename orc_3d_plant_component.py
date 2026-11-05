"""Interactive 3D Digital Twin & Industrial Plant Visualizer for ORC & WHRU Systems.

Renders a high-fidelity WebGL 3D industrial plant scene with:
- Concrete plant slab foundation with expansion joints and safety walkways
- Individual elevated concrete pedestals/plinths under all equipment
- Structural steel pipe racks (H-beam / I-beam columns & cross-beams) and pipe shoes
- Parametric 3D equipment models:
  * 1 to 5 Dynamic WHRU Boilers with flue gas inlet ducts, flanged exhaust stacks, and rising smoke
  * Cold distribution and hot collection manifolds with vertical support columns
  * TEMA Shell & Tube Superheater (SH) with insulation cladding, elliptical heads, and saddle supports
  * TEMA Shell & Tube Preheater/Evaporator (PH) with saddles and nozzles
  * ORC Turbo-expander with spiral volute casing driving a ribbed alternator on a structural skid
  * Air-Cooled Condenser (ACC) A-frame structure with rotating 4-blade fans
  * Thermal Oil & Cyclopentane centrifugal pumps with electric motors on vibration plinths
  * 3-Way proportional bypass valve with pneumatic/electric actuator
- Traditional orthogonal industrial plant piping routes (North-South, East-West, Vertical drops/risers):
  * Composed of discrete piping elements: straight pipe spools, standard 90° elbows, flanges, and U-turn expansion loops
  * Rigorously traced from equipment outlet to destination equipment inlet
- Animated 3D fluid particle flow streams color-coded by temperature & fluid phase following the orthogonal routes
- Interactive Raycaster (Hover highlight + Click to Inspect live telemetry HUD)
- Camera navigation (Orbit, Pan, Zoom) and preset angles (Isometric, Top P&ID, Front, Turbine close-up)
- Full client-side synchronization with the 2D P&ID flowsheet and thermodynamic solver
"""

from __future__ import annotations

import json
from typing import Any


def get_orc_3d_plant_container_html() -> str:
    """Return the container HTML element and toolbar for the 3D plant digital twin."""
    return """
      <!-- 3D Digital Twin Container (Toggled via View Switcher) -->
      <div id="container_3d" style="display: none; position: relative; width: 100%; height: 620px; background: linear-gradient(180deg, #dbeafe 0%, #eff6ff 55%, #e2e8f0 100%); border-radius: 10px; overflow: hidden; border: 1px solid #cbd5e1; box-shadow: inset 0 2px 8px rgba(15,23,42,0.08);">
        <!-- 3D Canvas Mount Point -->
        <div id="canvas_3d_mount" style="width: 100%; height: 100%; cursor: grab;"></div>

        <!-- 3D Camera & View Controls Toolbar -->
        <div class="toolbar-3d" style="position: absolute; top: 12px; left: 12px; display: flex; gap: 6px; flex-wrap: wrap; z-index: 20; background: rgba(15, 23, 42, 0.88); backdrop-filter: blur(8px); padding: 6px 10px; border-radius: 8px; border: 1px solid rgba(51, 65, 85, 0.7);">
          <button type="button" class="btn-3d-cam" onclick="window.set3DCameraPreset && window.set3DCameraPreset('iso')" title="İzometrik Genel Görünüm">🎥 İzometrik</button>
          <button type="button" class="btn-3d-cam" onclick="window.set3DCameraPreset && window.set3DCameraPreset('top')" title="Üstten P&ID Plan Açısı">📐 Üstten P&ID</button>
          <button type="button" class="btn-3d-cam" onclick="window.set3DCameraPreset && window.set3DCameraPreset('front')" title="Ön Cephe (Elevation)">🏢 Ön Cephe</button>
          <button type="button" class="btn-3d-cam" onclick="window.set3DCameraPreset && window.set3DCameraPreset('turbine')" title="ORC Türbin & Jeneratör">⚡ Türbin Odak</button>
          <button type="button" class="btn-3d-cam" onclick="window.set3DCameraPreset && window.set3DCameraPreset('condenser')" title="Kondenser & Soğutma Kulesi Odak">❄️ Kondenser Odak</button>
          <button type="button" class="btn-3d-cam" onclick="window.reset3DCamera && window.reset3DCamera()" title="Kamerayı Varsayılana Sıfırla">🔄 Sıfırla</button>
          <span style="color:#475569; margin:0 2px;">|</span>
          <button type="button" class="btn-3d-cam" onclick="window.change3DBoilerCount && window.change3DBoilerCount(-1)" title="Atık Isı Baca Kazanı Eksilt">➖</button>
          <span id="lbl_3d_whru_count" style="display:inline-flex; align-items:center; font-size:11.5px; font-weight:700; color:#f8fafc; padding:0 4px;">🏭 WHRU: 2 Kazan</span>
          <button type="button" class="btn-3d-cam" onclick="window.change3DBoilerCount && window.change3DBoilerCount(1)" title="Atık Isı Baca Kazanı Ekle">➕</button>
          <span style="color:#475569; margin:0 2px;">|</span>
          <button type="button" id="btn_3d_cond_air" class="btn-3d-cam" style="border-color:#38bdf8;" onclick="window.set3DCondenserType && window.set3DCondenserType('air')" title="Hava Soğutmalı Kondenser (A-Frame ACC)">💨 ACC (Hava)</button>
          <button type="button" id="btn_3d_cond_water" class="btn-3d-cam" onclick="window.set3DCondenserType && window.set3DCondenserType('water')" title="Su Soğutmalı Yüzey Kondenseri & Soğutma Kulesi">💧 Kule (Su)</button>
          <span style="display: inline-flex; align-items: center; font-size: 11px; color: #cbd5e1; margin-left: 6px; font-weight: 500;">
            🖱️ Sol Tık: Döndür | Sağ Tık: Kaydır | Tekerlek: Zoom
          </span>
        </div>

        <!-- Legend Overlay in 3D Viewport -->
        <div style="position: absolute; bottom: 12px; left: 12px; z-index: 20; background: rgba(15, 23, 42, 0.88); backdrop-filter: blur(6px); padding: 6px 12px; border-radius: 6px; border: 1px solid rgba(51, 65, 85, 0.6); display: flex; gap: 12px; font-size: 11px; font-weight: 600; color: #e2e8f0; pointer-events: none; flex-wrap: wrap;">
          <span style="display: flex; align-items: center; gap: 5px;"><span style="width: 10px; height: 10px; border-radius: 50%; background: #ef4444; box-shadow: 0 0 6px #ef4444;"></span> Sıcak Yağ İletim (295°C)</span>
          <span style="display: flex; align-items: center; gap: 5px;"><span style="width: 10px; height: 10px; border-radius: 50%; background: #eab308; box-shadow: 0 0 6px #eab308;"></span> Dönüş Yağ (205°C)</span>
          <span style="display: flex; align-items: center; gap: 5px;"><span style="width: 10px; height: 10px; border-radius: 50%; background: #c084fc; box-shadow: 0 0 6px #c084fc;"></span> Kızgın Buhar (225°C)</span>
          <span style="display: flex; align-items: center; gap: 5px;"><span style="width: 10px; height: 10px; border-radius: 50%; background: #06b6d4; box-shadow: 0 0 6px #06b6d4;"></span> Sıvı Siklopentan (38°C)</span>
          <span style="display: flex; align-items: center; gap: 5px;"><span style="width: 10px; height: 10px; border-radius: 50%; background: #3b82f6; box-shadow: 0 0 6px #3b82f6;"></span> Soğutma Suyu (25°C)</span>
          <span style="display: flex; align-items: center; gap: 5px;"><span style="width: 10px; height: 10px; border-radius: 50%; background: #64748b;"></span> Flanş, Dirsek & Gantry</span>
        </div>

        <!-- Interactive 3D Equipment Telemetry HUD Card -->
        <div id="hud_3d_card" style="display: none; position: absolute; top: 12px; right: 12px; z-index: 25; width: 270px; background: rgba(15, 23, 42, 0.94); backdrop-filter: blur(10px); border: 1px solid rgba(59, 130, 246, 0.55); border-radius: 8px; padding: 12px; box-shadow: 0 8px 24px rgba(0,0,0,0.65); color: #f8fafc; font-family: -apple-system, BlinkMacSystemFont, sans-serif;">
          <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid rgba(51, 65, 85, 0.6); padding-bottom: 6px; margin-bottom: 8px;">
            <div id="hud_3d_title" style="font-size: 13px; font-weight: 800; color: #60a5fa;">Ekipman Telemetrisi</div>
            <button type="button" onclick="document.getElementById('hud_3d_card').style.display='none'" style="background: none; border: none; color: #94a3b8; cursor: pointer; font-size: 14px;">✕</button>
          </div>
          <div id="hud_3d_content" style="font-size: 11.5px; line-height: 1.6; color: #cbd5e1;"></div>
        </div>
      </div>
    """


def get_orc_3d_plant_js() -> str:
    """Return the client-side JavaScript for building, animating, and interacting with the 3D plant."""
    return """
  /* =========================================================================
   * 3D DIGITAL TWIN & INDUSTRIAL PLANT VISUALIZER (Three.js WebGL Engine)
   * ========================================================================= */
  let scene3D, camera3D, renderer3D, controls3D;
  let is3DInitialized = false;
  let plant3DGroup = null;
  let boilers3D = [];
  let plinths3D = [];
  let boilerRisers3D = [];
  let animatedParticles = [];
  let accGroup = null;
  let waterCondenserGroup = null;
  let accFanRotors = [];
  let towerFanRotor = null;
  let coolingTowerMist = null;
  let accPipingGroup = null;
  let waterPipingGroup = null;
  let accParticles = [];
  let waterParticles = [];
  let raycaster3D, mouse3D;
  let interactiveObjects = [];
  let hoveredObject = null;

  function init3DPlant() {
    if (is3DInitialized) return;
    const container = document.getElementById("canvas_3d_mount");
    if (!container) return;

    if (typeof THREE === "undefined") {
      console.warn("Three.js kütüphanesi yüklenemedi; 3D görünüm pasif.");
      container.innerHTML = '<div style="display:flex;align-items:center;justify-content:center;height:100%;color:#94a3b8;font-size:13px;">⚠️ 3D WebGL motoru başlatılamadı. Lütfen internet bağlantınızı kontrol ediniz.</div>';
      return;
    }

    const width = container.clientWidth || 800;
    const height = container.clientHeight || 600;

    // 1. Scene & Camera Setup (Bright Daylight / Engineering Studio Atmosphere)
    scene3D = new THREE.Scene();
    scene3D.background = new THREE.Color(0xe8f0fe);
    scene3D.fog = new THREE.FogExp2(0xe8f0fe, 0.0015);

    camera3D = new THREE.PerspectiveCamera(45, width / height, 0.5, 600);
    camera3D.position.set(0, 52, 90);

    // 2. WebGL Renderer
    try {
      renderer3D = new THREE.WebGLRenderer({ antialias: true, alpha: true, powerPreference: "high-performance" });
    } catch (e) {
      console.warn("WebGL renderer hatası:", e);
      container.innerHTML = '<div style="display:flex;align-items:center;justify-content:center;height:100%;color:#ef4444;font-size:13px;font-weight:600;">⚠️ Tarayıcınızda WebGL donanım hızlandırması başlatılamadı.</div>';
      return;
    }
    renderer3D.setSize(width, height);
    renderer3D.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer3D.shadowMap.enabled = true;
    renderer3D.shadowMap.type = THREE.PCFSoftShadowMap;
    if (typeof THREE.ACESFilmicToneMapping !== "undefined") {
      renderer3D.toneMapping = THREE.ACESFilmicToneMapping;
      renderer3D.toneMappingExposure = 1.25;
    }
    container.innerHTML = "";
    container.appendChild(renderer3D.domElement);

    // 3. OrbitControls
    if (typeof THREE.OrbitControls !== "undefined") {
      controls3D = new THREE.OrbitControls(camera3D, renderer3D.domElement);
      controls3D.enableDamping = true;
      controls3D.dampingFactor = 0.08;
      controls3D.maxPolarAngle = Math.PI / 2 - 0.03; // Don't go below ground
      controls3D.minDistance = 15;
      controls3D.maxDistance = 240;
      controls3D.target.set(0, 10, 0);
    }

    // 4. High-Brightness Industrial Daylight & Studio Lighting Rig
    const ambientLight = new THREE.AmbientLight(0xffffff, 1.15);
    scene3D.add(ambientLight);

    const hemiLight = new THREE.HemisphereLight(0xffffff, 0xcbd5e1, 0.95);
    hemiLight.position.set(0, 120, 0);
    scene3D.add(hemiLight);

    const sunLight = new THREE.DirectionalLight(0xfffbeb, 1.45);
    sunLight.position.set(55, 85, 50);
    sunLight.castShadow = true;
    sunLight.shadow.mapSize.width = 1024;
    sunLight.shadow.mapSize.height = 1024;
    sunLight.shadow.camera.near = 10;
    sunLight.shadow.camera.far = 220;
    sunLight.shadow.camera.left = -70;
    sunLight.shadow.camera.right = 70;
    sunLight.shadow.camera.top = 70;
    sunLight.shadow.camera.bottom = -70;
    scene3D.add(sunLight);

    const blueFillLight = new THREE.DirectionalLight(0xe0f2fe, 0.85);
    blueFillLight.position.set(-55, 60, -45);
    scene3D.add(blueFillLight);

    const frontFillLight = new THREE.DirectionalLight(0xffffff, 0.65);
    frontFillLight.position.set(0, 45, 90);
    scene3D.add(frontFillLight);

    // 5. Build Plant Hierarchy
    boilers3D = [];
    plinths3D = [];
    boilerRisers3D = [];
    interactiveObjects = [];
    animatedParticles = [];
    plant3DGroup = new THREE.Group();
    scene3D.add(plant3DGroup);

    buildConcreteFoundation();
    buildPipeRacksAndSupports();
    buildPlantEquipment();
    buildOrthogonalPipingNetwork();
    buildParticleFlowStreams();

    // Sync initial WHRU boiler count with 2D schematic / initialData
    const initBoilerCount = (window.latestCalcResult && window.latestCalcResult.boilers && window.latestCalcResult.boilers.length)
      ? window.latestCalcResult.boilers.length
      : ((window.latestCalcResult && typeof window.latestCalcResult.n_boilers === "number")
        ? window.latestCalcResult.n_boilers
        : ((typeof window.currentBoilerCount === "number" && window.currentBoilerCount >= 1)
          ? window.currentBoilerCount
          : ((typeof initialData !== "undefined" && initialData && initialData.n_boilers)
            ? parseInt(initialData.n_boilers)
            : ((typeof initData !== "undefined" && initData && initData.n_boilers)
              ? parseInt(initData.n_boilers)
              : 2))));
    if (typeof window.sync3DBoilerCount === "function") {
      window.sync3DBoilerCount(initBoilerCount);
    }

    // 6. Raycaster & Mouse Interactivity
    raycaster3D = new THREE.Raycaster();
    mouse3D = new THREE.Vector2();

    renderer3D.domElement.addEventListener("mousemove", on3DMouseMove, false);
    renderer3D.domElement.addEventListener("click", on3DMouseClick, false);
    window.addEventListener("resize", on3DWindowResize, false);
    if (window.ResizeObserver && container) {
      try {
        const ro = new ResizeObserver(() => on3DWindowResize());
        ro.observe(container);
      } catch (e) { /* fallback to window resize */ }
    }

    is3DInitialized = true;
    start3DAnimation();
  }

  /* -------------------------------------------------------------------------
   * 1. Concrete Plant Slab & Equipment Foundation Plinths (Beton Kaideler)
   * ------------------------------------------------------------------------- */
  function buildConcreteFoundation() {
    // Ana Endüstriyel Zemin Plakası (Bright Light-Gray Industrial Concrete Slab)
    const slabGeo = new THREE.BoxGeometry(165, 1.2, 115);
    const slabMat = new THREE.MeshStandardMaterial({
      color: 0xcbd5e1,
      roughness: 0.80,
      metalness: 0.08,
    });
    const mainSlab = new THREE.Mesh(slabGeo, slabMat);
    mainSlab.position.y = -0.6;
    mainSlab.receiveShadow = true;
    plant3DGroup.add(mainSlab);

    // Zemin Genleşme Derzleri / Grid
    const grid = new THREE.GridHelper(155, 31, 0x64748b, 0x94a3b8);
    grid.position.y = 0.02;
    plant3DGroup.add(grid);

    // Güvenlik Yürüme Yolları (Yellow Safety Walkway Stripes)
    const walkwayGeo = new THREE.PlaneGeometry(145, 2.8);
    const walkwayMat = new THREE.MeshBasicMaterial({ color: 0xfacc15, depthWrite: false });
    const walkway = new THREE.Mesh(walkwayGeo, walkwayMat);
    walkway.rotation.x = -Math.PI / 2;
    walkway.position.set(0, 0.04, 18);
    plant3DGroup.add(walkway);

    // Ekipman Beton Kaideleri (Elevated Plinths / Pedestals)
    const plinthMat = new THREE.MeshStandardMaterial({
      color: 0x94a3b8,
      roughness: 0.78,
      metalness: 0.08,
    });

    // WHRU Kazan Kaideleri (1..5) - Dairesel/Pahlı Yükseltilmiş Beton Pabuçlar
    const whruXCoords = [-52, -37, -22, -7, 8];
    whruXCoords.forEach((x, idx) => {
      const plinthGeo = new THREE.CylinderGeometry(4.8, 5.2, 0.8, 24);
      const plinth = new THREE.Mesh(plinthGeo, plinthMat);
      plinth.position.set(x, 0.4, -18);
      plinth.receiveShadow = true;
      plinth.castShadow = true;
      plinth.userData = { boilerIndex: idx + 1 };
      plant3DGroup.add(plinth);
      plinths3D.push(plinth);
    });

    // E-101 Superheater İkiz Semer Beton Kaideleri
    [-2, 6].forEach(dx => {
      const shPad = new THREE.Mesh(new THREE.BoxGeometry(2.4, 0.9, 5.5), plinthMat);
      shPad.position.set(24 + dx, 0.45, -18);
      shPad.receiveShadow = true;
      shPad.castShadow = true;
      plant3DGroup.add(shPad);
    });

    // E-102 Evaporator / Ön Isıtıcı İkiz Kaideleri
    [-3, 5].forEach(dx => {
      const phPad = new THREE.Mesh(new THREE.BoxGeometry(2.8, 0.9, 6.5), plinthMat);
      phPad.position.set(44 + dx, 0.45, -18);
      phPad.receiveShadow = true;
      phPad.castShadow = true;
      plant3DGroup.add(phPad);
    });

    // Pompa ve Motor Ortak Titreşim Kaideleri
    const pumpPad1 = new THREE.Mesh(new THREE.BoxGeometry(5.0, 0.7, 4.0), plinthMat);
    pumpPad1.position.set(34, 0.35, -2);
    pumpPad1.receiveShadow = true;
    plant3DGroup.add(pumpPad1);

    const pumpPad2 = new THREE.Mesh(new THREE.BoxGeometry(4.5, 0.7, 3.5), plinthMat);
    pumpPad2.position.set(-15, 0.35, 12);
    pumpPad2.receiveShadow = true;
    plant3DGroup.add(pumpPad2);

    // ORC Türbin & Jeneratör Ağır Beton Temeli (Turbine Table Plinth)
    const turbPlinth = new THREE.Mesh(new THREE.BoxGeometry(16, 1.4, 9.5), plinthMat);
    turbPlinth.position.set(38, 0.7, 32);
    turbPlinth.receiveShadow = true;
    turbPlinth.castShadow = true;
    plant3DGroup.add(turbPlinth);
  }

  /* -------------------------------------------------------------------------
   * 2. Structural Steel Pipe Racks & Supports (Boru Köprüleri ve Mesnetler)
   * ------------------------------------------------------------------------- */
  function buildPipeRacksAndSupports() {
    const steelMat = new THREE.MeshStandardMaterial({
      color: 0x475569,
      metalness: 0.35,
      roughness: 0.40,
    });

    // Pipe Rack 1: WHRU Kazanları Önünde Boylu Boyunca Uzanan Çelik Boru Köprüsü (x = -55 .. +13)
    const rackXPositions = [-55, -40, -25, -10, 2, 13];
    rackXPositions.forEach(rx => {
      // Dikey H-Kolonlar (Vertical Columns)
      [-26, -10].forEach(rz => {
        const col = new THREE.Mesh(new THREE.BoxGeometry(0.5, 12.0, 0.5), steelMat);
        col.position.set(rx, 6.0, rz);
        col.castShadow = true;
        plant3DGroup.add(col);
      });

      // Yatay I-Kiriş Taşıyıcı Traversler (Horizontal Transom Beams)
      const beamLow = new THREE.Mesh(new THREE.BoxGeometry(0.4, 0.5, 16.5), steelMat);
      beamLow.position.set(rx, 4.2, -18);
      plant3DGroup.add(beamLow);

      const beamHigh = new THREE.Mesh(new THREE.BoxGeometry(0.4, 0.5, 16.5), steelMat);
      beamHigh.position.set(rx, 11.2, -18);
      plant3DGroup.add(beamHigh);

      // Boru Pabuçları (Pipe Shoes)
      const shoe1 = new THREE.Mesh(new THREE.BoxGeometry(0.6, 0.25, 0.7), steelMat);
      shoe1.position.set(rx, 4.45, -24);
      plant3DGroup.add(shoe1);

      const shoe2 = new THREE.Mesh(new THREE.BoxGeometry(0.6, 0.25, 0.7), steelMat);
      shoe2.position.set(rx, 11.45, -12);
      plant3DGroup.add(shoe2);
    });

    // Boyuna Bağlantı Kirişleri (Longitudinal Stringers)
    [-26, -10].forEach(rz => {
      const longBeam = new THREE.Mesh(new THREE.BoxGeometry(70, 0.45, 0.45), steelMat);
      longBeam.position.set(-21.0, 11.2, rz);
      plant3DGroup.add(longBeam);
    });

    // Intermediate Pipe Rack: Kuzey-Güney Ana Buhar Köprüsü (x = 26.0 hattını iki yandan destekleyen portal)
    [0, 10, 22].forEach(pz => {
      [24.0, 28.0].forEach(px => {
        const midCol = new THREE.Mesh(new THREE.BoxGeometry(0.45, 11.4, 0.45), steelMat);
        midCol.position.set(px, 5.7, pz);
        plant3DGroup.add(midCol);
      });
      // Transverse Portal Beam supporting x = 26.0, y = 11.8 vapor line from underneath
      const crossBeam = new THREE.Mesh(new THREE.BoxGeometry(4.6, 0.45, 0.45), steelMat);
      crossBeam.position.set(26.0, 11.15, pz);
      plant3DGroup.add(crossBeam);

      const vapShoe = new THREE.Mesh(new THREE.BoxGeometry(0.6, 0.22, 0.6), steelMat);
      vapShoe.position.set(26.0, 11.38, pz);
      plant3DGroup.add(vapShoe);
    });
  }

  /* -------------------------------------------------------------------------
   * 3. Industrial Plant Equipment Models (Gerçekçi 3D Ekipmanlar)
   * ------------------------------------------------------------------------- */
  function buildPlantEquipment() {
    const steelShellMat = new THREE.MeshStandardMaterial({ color: 0x64748b, metalness: 0.35, roughness: 0.38 });
    const stainlessMat = new THREE.MeshStandardMaterial({ color: 0xf1f5f9, metalness: 0.35, roughness: 0.28 });
    const motorBlueMat = new THREE.MeshStandardMaterial({ color: 0x0284c7, metalness: 0.30, roughness: 0.38 });
    const darkExhaustMat = new THREE.MeshStandardMaterial({ color: 0x475569, metalness: 0.30, roughness: 0.45 });
    const turbineGoldMat = new THREE.MeshStandardMaterial({ color: 0xf59e0b, metalness: 0.40, roughness: 0.30 });

    // A. WHRU Atık Isı Kazanları (1..5 Dynamic WHRU Boilers)
    const whruXCoords = [-52, -37, -22, -7, 8];
    whruXCoords.forEach((x, idx) => {
      const boilerGrp = new THREE.Group();
      boilerGrp.position.set(x, 0, -18);

      // Ana Dikey Kazan Gövdesi
      const body = new THREE.Mesh(new THREE.CylinderGeometry(3.6, 3.6, 11.0, 24), steelShellMat);
      body.position.y = 6.3;
      body.castShadow = true;
      body.receiveShadow = true;
      boilerGrp.add(body);

      // Alt Baca Gazı Giriş Kanalı & Brülör Kutusu
      const ductIn = new THREE.Mesh(new THREE.BoxGeometry(3.2, 2.4, 2.0), darkExhaustMat);
      ductIn.position.set(0, 2.0, 3.8);
      boilerGrp.add(ductIn);

      // Üst Baca Borusu & Çıkış Flanş Ringi
      const stack = new THREE.Mesh(new THREE.CylinderGeometry(1.4, 1.6, 7.0, 20), darkExhaustMat);
      stack.position.y = 15.3;
      stack.castShadow = true;
      boilerGrp.add(stack);

      const stackRing = new THREE.Mesh(new THREE.TorusGeometry(1.6, 0.18, 12, 24), steelShellMat);
      stackRing.rotation.x = Math.PI / 2;
      stackRing.position.y = 18.6;
      boilerGrp.add(stackRing);

      // Flanşlı Nozullar
      const nozOut = new THREE.Mesh(new THREE.CylinderGeometry(0.45, 0.45, 1.2, 16), stainlessMat);
      nozOut.rotation.z = Math.PI / 2;
      nozOut.position.set(3.8, 10.0, 0);
      boilerGrp.add(nozOut);

      const nozIn = new THREE.Mesh(new THREE.CylinderGeometry(0.45, 0.45, 1.2, 16), stainlessMat);
      nozIn.rotation.z = Math.PI / 2;
      nozIn.position.set(3.8, 2.5, 0);
      boilerGrp.add(nozIn);

      boilerGrp.userData = {
        id: "boiler_" + (idx + 1),
        name: "WHRU-" + (idx + 1) + " Atık Isı Kazanı",
        boilerIndex: idx + 1,
        type: "boiler"
      };

      plant3DGroup.add(boilerGrp);
      boilers3D.push(boilerGrp);
      interactiveObjects.push(body);
      body.userData = boilerGrp.userData;
    });

    // B. Siklopentan Aşırı Kızdırıcı (Superheater - SH)
    const shGrp = new THREE.Group();
    shGrp.position.set(26, 0, -18);

    const shBody = new THREE.Mesh(new THREE.CylinderGeometry(2.4, 2.4, 9.5, 24), stainlessMat);
    shBody.rotation.z = Math.PI / 2;
    shBody.position.y = 3.6;
    shBody.castShadow = true;
    shGrp.add(shBody);

    const shHead1 = new THREE.Mesh(new THREE.SphereGeometry(2.4, 20, 16, 0, Math.PI * 2, 0, Math.PI / 2), stainlessMat);
    shHead1.rotation.z = -Math.PI / 2;
    shHead1.position.set(-4.75, 3.6, 0);
    shGrp.add(shHead1);

    const shHead2 = new THREE.Mesh(new THREE.SphereGeometry(2.4, 20, 16, 0, Math.PI * 2, 0, Math.PI / 2), stainlessMat);
    shHead2.rotation.z = Math.PI / 2;
    shHead2.position.set(4.75, 3.6, 0);
    shGrp.add(shHead2);

    [-2, 2].forEach(sx => {
      const saddle = new THREE.Mesh(new THREE.BoxGeometry(0.5, 1.8, 5.0), steelShellMat);
      saddle.position.set(sx * 1.5, 1.8, 0);
      saddle.castShadow = true;
      shGrp.add(saddle);
    });

    // Flanşlı Nozullar
    // 1. Gövde Üstü Kızgın Yağ Girişi (Shell Top Oil Inlet - Above shell y=6.0)
    const shNozIn = new THREE.Mesh(new THREE.CylinderGeometry(0.42, 0.42, 1.0, 16), stainlessMat);
    shNozIn.position.set(-1.5, 6.0, 0);
    shGrp.add(shNozIn);
    const shFlangeIn = new THREE.Mesh(new THREE.CylinderGeometry(0.62, 0.62, 0.2, 16), stainlessMat);
    shFlangeIn.position.set(-1.5, 6.5, 0);
    shGrp.add(shFlangeIn);

    // 2. Gövde Altı Kızgın Yağ Çıkışı (Shell Bottom Oil Outlet)
    const shNozOut = new THREE.Mesh(new THREE.CylinderGeometry(0.40, 0.40, 0.8, 16), stainlessMat);
    shNozOut.position.set(2.0, 1.8, 0);
    shGrp.add(shNozOut);
    const shFlangeOut = new THREE.Mesh(new THREE.CylinderGeometry(0.60, 0.60, 0.2, 16), stainlessMat);
    shFlangeOut.position.set(2.0, 1.5, 0);
    shGrp.add(shFlangeOut);

    // 3. Doğu Ayna/Kanal Buhar Girişi (East Channel Head Vapor Inlet from PH)
    const shVapIn = new THREE.Mesh(new THREE.CylinderGeometry(0.38, 0.38, 1.6, 16), stainlessMat);
    shVapIn.rotation.z = Math.PI / 2;
    shVapIn.position.set(5.5, 3.6, 0);
    shGrp.add(shVapIn);

    // 4. Batı Ayna/Kanal Kızgın Buhar Çıkışı (West Channel Head Superheated Vapor Outlet to Turbine)
    const shVapOut = new THREE.Mesh(new THREE.CylinderGeometry(0.38, 0.38, 1.4, 16), stainlessMat);
    shVapOut.position.set(-5.5, 5.0, 0);
    shGrp.add(shVapOut);

    shGrp.userData = { id: "node_sh", name: "Siklopentan Aşırı Kızdırıcı (SH)", type: "sh" };
    plant3DGroup.add(shGrp);
    interactiveObjects.push(shBody);
    shBody.userData = shGrp.userData;

    // C. Ön Isıtıcı / Evaporatör (PH / Kettle Evaporator)
    const phGrp = new THREE.Group();
    phGrp.position.set(45, 0, -18);

    const phBody = new THREE.Mesh(new THREE.CylinderGeometry(2.8, 2.8, 11.0, 24), stainlessMat);
    phBody.rotation.z = Math.PI / 2;
    phBody.position.y = 3.9;
    phBody.castShadow = true;
    phGrp.add(phBody);

    const phHead1 = new THREE.Mesh(new THREE.SphereGeometry(2.8, 20, 16, 0, Math.PI * 2, 0, Math.PI / 2), stainlessMat);
    phHead1.rotation.z = -Math.PI / 2;
    phHead1.position.set(-5.5, 3.9, 0);
    phGrp.add(phHead1);

    const phHead2 = new THREE.Mesh(new THREE.SphereGeometry(2.8, 20, 16, 0, Math.PI * 2, 0, Math.PI / 2), stainlessMat);
    phHead2.rotation.z = Math.PI / 2;
    phHead2.position.set(5.5, 3.9, 0);
    phGrp.add(phHead2);

    [-2.5, 2.5].forEach(sx => {
      const saddle = new THREE.Mesh(new THREE.BoxGeometry(0.6, 2.1, 5.8), steelShellMat);
      saddle.position.set(sx * 1.5, 2.0, 0);
      saddle.castShadow = true;
      phGrp.add(saddle);
    });

    // PH Top Vapor Disengagement Dome (TEMA Kettle / Evaporator Dome)
    const phDome = new THREE.Mesh(new THREE.CylinderGeometry(1.6, 1.6, 1.4, 24), stainlessMat);
    phDome.position.set(0, 7.1, 0);
    phGrp.add(phDome);
    const phDomeFlange = new THREE.Mesh(new THREE.CylinderGeometry(1.8, 1.8, 0.22, 24), stainlessMat);
    phDomeFlange.position.set(0, 7.8, 0);
    phGrp.add(phDomeFlange);

    // PH Shell Top Oil Inlet Nozzle (Above shell y=6.7, clear of saddle)
    const phNozOilIn = new THREE.Mesh(new THREE.CylinderGeometry(0.40, 0.40, 1.2, 16), stainlessMat);
    phNozOilIn.position.set(-3.5, 7.0, 0);
    phGrp.add(phNozOilIn);

    // PH Shell Bottom Oil Outlet Nozzle
    const phNozOilOut = new THREE.Mesh(new THREE.CylinderGeometry(0.40, 0.40, 0.8, 16), stainlessMat);
    phNozOilOut.position.set(3.0, 1.8, 0);
    phGrp.add(phNozOilOut);

    // PH Front Channel Head Liquid Inlet Nozzle
    const phNozLiqIn = new THREE.Mesh(new THREE.CylinderGeometry(0.30, 0.30, 1.4, 16), stainlessMat);
    phNozLiqIn.rotation.z = Math.PI / 2;
    phNozLiqIn.position.set(-6.2, 3.5, 0);
    phGrp.add(phNozLiqIn);

    phGrp.userData = { id: "node_ph", name: "Siklopentan Evaporatör & Ön Isıtıcı (PH)", type: "ph" };
    plant3DGroup.add(phGrp);
    interactiveObjects.push(phBody);
    phBody.userData = phGrp.userData;

    // D. ORC Türbini & Jeneratör Seti (Turbo-Expander & Generator Skid)
    const turbGrp = new THREE.Group();
    turbGrp.position.set(38, 0, 32);

    const skid = new THREE.Mesh(new THREE.BoxGeometry(15, 0.6, 8.5), steelShellMat);
    skid.position.y = 1.7;
    turbGrp.add(skid);

    const turbCasing = new THREE.Mesh(new THREE.TorusGeometry(2.0, 1.2, 16, 24, Math.PI * 1.7), turbineGoldMat);
    turbCasing.rotation.y = Math.PI / 2;
    turbCasing.position.set(-3.5, 4.4, 0);
    turbCasing.castShadow = true;
    turbGrp.add(turbCasing);

    // Turbine High-Pressure (HP) Vapor Inlet Nozzle & Flange (World: x=34.5, y=5.6, z=32.0)
    const turbInletNoz = new THREE.Mesh(new THREE.CylinderGeometry(0.42, 0.48, 1.2, 16), stainlessMat);
    turbInletNoz.position.set(-3.5, 5.2, 0);
    turbGrp.add(turbInletNoz);

    // Turbine Low-Pressure (LP) Axial-Radial Exhaust Diffuser Hood & Top Nozzle (World: x=32.5, y=6.2, z=32.0)
    const turbExhaustHood = new THREE.Mesh(new THREE.CylinderGeometry(1.15, 1.45, 2.4, 20), steelShellMat);
    turbExhaustHood.position.set(-5.5, 4.6, 0);
    turbExhaustHood.castShadow = true;
    turbGrp.add(turbExhaustHood);

    const turbExhaustNoz = new THREE.Mesh(new THREE.CylinderGeometry(0.68, 0.68, 0.9, 20), stainlessMat);
    turbExhaustNoz.position.set(-5.5, 6.0, 0);
    turbGrp.add(turbExhaustNoz);

    const shaft = new THREE.Mesh(new THREE.CylinderGeometry(0.6, 0.6, 2.2, 16), stainlessMat);
    shaft.rotation.z = Math.PI / 2;
    shaft.position.set(-1.0, 4.4, 0);
    turbGrp.add(shaft);

    const gen = new THREE.Mesh(new THREE.CylinderGeometry(2.2, 2.2, 6.0, 24), motorBlueMat);
    gen.rotation.z = Math.PI / 2;
    gen.position.set(2.8, 4.4, 0);
    gen.castShadow = true;
    turbGrp.add(gen);

    const termBox = new THREE.Mesh(new THREE.BoxGeometry(1.4, 1.0, 1.4), darkExhaustMat);
    termBox.position.set(2.8, 6.8, 0);
    turbGrp.add(termBox);

    turbGrp.userData = { id: "node_turbine", name: "ORC Türbini & Jeneratör (Expander)", type: "turbine" };
    plant3DGroup.add(turbGrp);
    interactiveObjects.push(turbCasing);
    turbCasing.userData = turbGrp.userData;

    // E1. Hava Soğutmalı Kondenser (A-Frame ACC & Gantry Taşıyıcı Konstrüksiyon)
    accGroup = new THREE.Group();
    accGroup.position.set(-8, 0, 32);

    const gantryMat = new THREE.MeshStandardMaterial({ color: 0x64748b, metalness: 0.35, roughness: 0.38 });
    const safetyYellowMat = new THREE.MeshStandardMaterial({ color: 0xfacc15, roughness: 0.4 });
    const bundleMat = new THREE.MeshStandardMaterial({ color: 0xcbd5e1, metalness: 0.35, roughness: 0.35 });

    // 6 Vertical Structural Columns on Concrete Pedestals
    [-14, 0, 14].forEach(cx => {
      [-5.8, 5.8].forEach(cz => {
        // Concrete Pedestal under Column Base
        const ped = new THREE.Mesh(new THREE.BoxGeometry(1.5, 0.6, 1.5), new THREE.MeshStandardMaterial({ color: 0x94a3b8, roughness: 0.80 }));
        ped.position.set(cx, 0.3, cz);
        accGroup.add(ped);

        // Vertical Column (H-Beam / Steel Cylinder)
        const col = new THREE.Mesh(new THREE.CylinderGeometry(0.32, 0.32, 4.4, 16), gantryMat);
        col.position.set(cx, 2.8, cz);
        col.castShadow = true;
        accGroup.add(col);
      });

      // Transverse Structural Cross-Beam connecting column pair in Z
      const beamZ = new THREE.Mesh(new THREE.BoxGeometry(0.4, 0.45, 12.0), gantryMat);
      beamZ.position.set(cx, 4.8, 0);
      accGroup.add(beamZ);

      // Diagonal Cross-Bracing between column pair in Z
      const brace1 = new THREE.Mesh(new THREE.CylinderGeometry(0.08, 0.08, 12.5, 8), gantryMat);
      brace1.rotation.x = 0.36;
      brace1.position.set(cx, 2.8, 0);
      accGroup.add(brace1);
      const brace2 = new THREE.Mesh(new THREE.CylinderGeometry(0.08, 0.08, 12.5, 8), gantryMat);
      brace2.rotation.x = -0.36;
      brace2.position.set(cx, 2.8, 0);
      accGroup.add(brace2);
    });

    // Longitudinal Perimeter Gantry Girders in X
    [-5.8, 5.8].forEach(cz => {
      const beamX = new THREE.Mesh(new THREE.BoxGeometry(32.0, 0.45, 0.4), gantryMat);
      beamX.position.set(0, 4.8, cz);
      accGroup.add(beamX);

      // Longitudinal X-Bracing between bays
      [-7, 7].forEach(bx => {
        const braceX1 = new THREE.Mesh(new THREE.CylinderGeometry(0.08, 0.08, 14.5, 8), gantryMat);
        braceX1.rotation.z = 0.32;
        braceX1.position.set(bx, 2.8, cz);
        accGroup.add(braceX1);
        const braceX2 = new THREE.Mesh(new THREE.CylinderGeometry(0.08, 0.08, 14.5, 8), gantryMat);
        braceX2.rotation.z = -0.32;
        braceX2.position.set(bx, 2.8, cz);
        accGroup.add(braceX2);
      });
    });

    // Fan Deck Grating Platform (Yürüyüş ve Fan Katı)
    const fanDeck = new THREE.Mesh(new THREE.BoxGeometry(32.0, 0.15, 12.8), new THREE.MeshStandardMaterial({ color: 0x64748b, metalness: 0.30, roughness: 0.45 }));
    fanDeck.position.set(0, 5.0, 0);
    fanDeck.receiveShadow = true;
    accGroup.add(fanDeck);

    // Safety Perimeter Handrails around Fan Deck
    [-6.2, 6.2].forEach(rz => {
      const topRail = new THREE.Mesh(new THREE.BoxGeometry(32.0, 0.06, 0.06), safetyYellowMat);
      topRail.position.set(0, 6.1, rz);
      accGroup.add(topRail);
      const midRail = new THREE.Mesh(new THREE.BoxGeometry(32.0, 0.04, 0.04), safetyYellowMat);
      midRail.position.set(0, 5.6, rz);
      accGroup.add(midRail);
      for (let sx = -15; sx <= 15; sx += 3.0) {
        const post = new THREE.Mesh(new THREE.CylinderGeometry(0.04, 0.04, 1.1, 8), safetyYellowMat);
        post.position.set(sx, 5.55, rz);
        accGroup.add(post);
      }
    });

    // Vertical Access Ladder with Safety Cage
    const ladder = new THREE.Mesh(new THREE.BoxGeometry(0.6, 5.0, 0.1), safetyYellowMat);
    ladder.position.set(15.8, 2.5, 5.8);
    accGroup.add(ladder);

    // Apex Steam Distribution Header
    const steamHeader = new THREE.Mesh(new THREE.CylinderGeometry(0.85, 0.85, 30.0, 24), steelShellMat);
    steamHeader.rotation.z = Math.PI / 2;
    steamHeader.position.set(0, 12.0, 0);
    steamHeader.castShadow = true;
    accGroup.add(steamHeader);

    // Header 2:1 Dished Heads on Ends & East Steam Inlet Nozzle (World: x=7.0, y=12.0, z=32.0)
    [-15.0, 15.0].forEach(hx => {
      const dHead = new THREE.Mesh(new THREE.SphereGeometry(0.85, 16, 12), steelShellMat);
      dHead.scale.set(hx > 0 ? 0.4 : -0.4, 1, 1);
      dHead.position.set(hx, 12.0, 0);
      accGroup.add(dHead);
    });
    const accSteamInNoz = new THREE.Mesh(new THREE.CylinderGeometry(0.68, 0.68, 0.8, 20), stainlessMat);
    accSteamInNoz.rotation.z = Math.PI / 2;
    accSteamInNoz.position.set(15.2, 12.0, 0);
    accGroup.add(accSteamInNoz);

    // Two Sloped A-Frame Finned Tube Banks
    const bank1 = new THREE.Mesh(new THREE.BoxGeometry(30.0, 8.8, 0.7), bundleMat);
    bank1.rotation.x = 0.65;
    bank1.position.set(0, 8.5, -3.2);
    bank1.castShadow = true;
    accGroup.add(bank1);

    const bank2 = new THREE.Mesh(new THREE.BoxGeometry(30.0, 8.8, 0.7), bundleMat);
    bank2.rotation.x = -0.65;
    bank2.position.set(0, 8.5, 3.2);
    bank2.castShadow = true;
    accGroup.add(bank2);

    // Bottom Condensate Drain Headers (Extended to West Outlet Manifold at local x = -16.6 -> World x = -24.6)
    [-5.8, 5.8].forEach(cz => {
      const condHeader = new THREE.Mesh(new THREE.CylinderGeometry(0.35, 0.35, 31.6, 16), steelShellMat);
      condHeader.rotation.z = Math.PI / 2;
      condHeader.position.set(-0.8, 5.3, cz);
      accGroup.add(condHeader);

      const accCondNoz = new THREE.Mesh(new THREE.CylinderGeometry(0.32, 0.32, 0.5, 16), stainlessMat);
      accCondNoz.rotation.z = Math.PI / 2;
      accCondNoz.position.set(-16.6, 5.3, cz);
      accGroup.add(accCondNoz);
    });

    // 3 Forced-Draft Axial Fans Mounted Horizontally on the Fan Deck
    accFanRotors = [];
    [-10, 0, 10].forEach(fx => {
      // Fixed Aerodynamic Bellmouth Cowl / Shroud Ring
      const cowl = new THREE.Mesh(new THREE.CylinderGeometry(3.3, 3.3, 1.2, 28, 1, true), darkExhaustMat);
      cowl.position.set(fx, 5.0, 0);
      accGroup.add(cowl);

      // Motor Support Spider Spokes
      for (let s = 0; s < 4; s++) {
        const spoke = new THREE.Mesh(new THREE.BoxGeometry(3.3, 0.12, 0.12), gantryMat);
        spoke.rotation.y = (s * Math.PI) / 4;
        spoke.position.set(fx, 4.4, 0);
        accGroup.add(spoke);
      }

      // Stationary Electric Motor
      const motor = new THREE.Mesh(new THREE.CylinderGeometry(0.55, 0.55, 0.85, 16), motorBlueMat);
      motor.position.set(fx, 4.4, 0);
      accGroup.add(motor);

      // Rotating Rotor Group (Centric Local Axis)
      const fanRotor = new THREE.Group();
      fanRotor.position.set(fx, 5.0, 0);

      // Central Spinner Hub
      const hub = new THREE.Mesh(new THREE.CylinderGeometry(0.7, 0.7, 0.4, 16), motorBlueMat);
      fanRotor.add(hub);

      // 6 Aerodynamic Pitched Fan Blades
      for (let i = 0; i < 6; i++) {
        const bladeGrp = new THREE.Group();
        bladeGrp.rotation.y = (i * Math.PI) / 3;

        const blade = new THREE.Mesh(new THREE.BoxGeometry(2.4, 0.06, 0.42), steelShellMat);
        blade.position.set(1.6, 0, 0);
        blade.rotation.x = 0.24; // Realistic blade pitch
        bladeGrp.add(blade);

        fanRotor.add(bladeGrp);
      }

      accGroup.add(fanRotor);
      accFanRotors.push(fanRotor);
    });

    accGroup.userData = { id: "node_condenser", name: "Hava Soğutmalı Kondenser (A-Frame ACC)", type: "condenser" };
    plant3DGroup.add(accGroup);
    interactiveObjects.push(bank1, bank2);
    bank1.userData = accGroup.userData;
    bank2.userData = accGroup.userData;

    // E2. Su Soğutmalı Yüzey Kondenseri ve Sulu Soğutma Kulesi
    waterCondenserGroup = new THREE.Group();
    waterCondenserGroup.position.set(-8, 0, 32);

    const frpTowerMat = new THREE.MeshStandardMaterial({ color: 0x94a3b8, metalness: 0.20, roughness: 0.55 });
    const louverMat = new THREE.MeshStandardMaterial({ color: 0x475569, metalness: 0.25, roughness: 0.45 });
    const waterMat = new THREE.MeshStandardMaterial({ color: 0x0284c7, metalness: 0.1, roughness: 0.15, transparent: true, opacity: 0.85 });

    // --- BÖLÜM 1: TEMA Gövde-Boru Yüzey Kondenseri (Surface Condenser C-101) ---
    const sCondGrp = new THREE.Group();
    sCondGrp.position.set(22, 0, 0); // World coords ~ (14, 0, 32)

    // Concrete Plinth & Steel Saddles
    const sPlinth = new THREE.Mesh(new THREE.BoxGeometry(9.0, 0.6, 5.0), new THREE.MeshStandardMaterial({ color: 0x94a3b8, roughness: 0.80 }));
    sPlinth.position.set(0, 0.3, 0);
    sCondGrp.add(sPlinth);

    [-2.8, 2.8].forEach(sx => {
      const sad = new THREE.Mesh(new THREE.BoxGeometry(0.7, 0.9, 3.4), gantryMat);
      sad.position.set(sx, 0.75, 0);
      sCondGrp.add(sad);
    });

    // Horizontal Cylindrical Shell (TEMA E-Type)
    const sShell = new THREE.Mesh(new THREE.CylinderGeometry(1.5, 1.5, 7.2, 24), steelShellMat);
    sShell.rotation.z = Math.PI / 2;
    sShell.position.set(0, 2.4, 0);
    sShell.castShadow = true;
    sCondGrp.add(sShell);

    // Front and Rear Channel Heads
    [-3.6, 3.6].forEach(hx => {
      const chHead = new THREE.Mesh(new THREE.SphereGeometry(1.5, 20, 16), steelShellMat);
      chHead.scale.set(hx > 0 ? 0.4 : -0.4, 1, 1);
      chHead.position.set(hx, 2.4, 0);
      sCondGrp.add(chHead);

      const chFlange = new THREE.Mesh(new THREE.CylinderGeometry(1.65, 1.65, 0.25, 24), stainlessMat);
      chFlange.rotation.z = Math.PI / 2;
      chFlange.position.set(hx > 0 ? 3.5 : -3.5, 2.4, 0);
      sCondGrp.add(chFlange);
    });

    // Top Large Steam Inlet Nozzle Dome
    const sDome = new THREE.Mesh(new THREE.CylinderGeometry(1.1, 1.1, 1.6, 20), steelShellMat);
    sDome.position.set(0, 3.7, 0);
    sCondGrp.add(sDome);
    const sDomeFlange = new THREE.Mesh(new THREE.CylinderGeometry(1.3, 1.3, 0.25, 20), stainlessMat);
    sDomeFlange.position.set(0, 4.4, 0);
    sCondGrp.add(sDomeFlange);

    // Bottom Condensate Hotwell Sump & Suction Nozzle
    const hotwell = new THREE.Mesh(new THREE.CylinderGeometry(0.75, 0.75, 1.0, 16), darkExhaustMat);
    hotwell.position.set(0, 1.4, 0);
    sCondGrp.add(hotwell);
    const hotwellNoz = new THREE.Mesh(new THREE.CylinderGeometry(0.32, 0.32, 1.0, 16), stainlessMat);
    hotwellNoz.rotation.x = Math.PI / 2;
    hotwellNoz.position.set(0, 1.5, -0.7);
    sCondGrp.add(hotwellNoz);

    // Cooling Water Channel Nozzles (Supply & Return)
    const cwInNoz = new THREE.Mesh(new THREE.CylinderGeometry(0.35, 0.35, 0.8, 16), motorBlueMat);
    cwInNoz.position.set(-3.9, 1.9, 0.8);
    cwInNoz.rotation.z = Math.PI / 2;
    sCondGrp.add(cwInNoz);

    const cwOutNoz = new THREE.Mesh(new THREE.CylinderGeometry(0.35, 0.35, 0.8, 16), motorBlueMat);
    cwOutNoz.position.set(-3.9, 2.9, -0.8);
    cwOutNoz.rotation.z = Math.PI / 2;
    sCondGrp.add(cwOutNoz);

    sCondGrp.userData = { id: "node_condenser", name: "Su Soğutmalı Yüzey Kondenseri (TEMA C-101)", type: "condenser" };
    waterCondenserGroup.add(sCondGrp);
    interactiveObjects.push(sShell);
    sShell.userData = sCondGrp.userData;

    // --- BÖLÜM 2: Mekanik Çekmeli Sulu Soğutma Kulesi (Wet Cooling Tower CT-101) ---
    const towerGrp = new THREE.Group();
    towerGrp.position.set(-8, 0, 0); // World coords ~ (-16, 0, 32)

    // Reinforced Concrete Basin (Sump)
    const basin = new THREE.Mesh(new THREE.BoxGeometry(16.0, 1.2, 12.0), new THREE.MeshStandardMaterial({ color: 0x94a3b8, roughness: 0.80 }));
    basin.position.set(0, 0.6, 0);
    towerGrp.add(basin);

    // Water Surface Inside Basin
    const waterSurf = new THREE.Mesh(new THREE.BoxGeometry(15.2, 0.08, 11.2), waterMat);
    waterSurf.position.set(0, 1.1, 0);
    towerGrp.add(waterSurf);

    // Tower Main Casing (Upper Housing)
    const towerBody = new THREE.Mesh(new THREE.BoxGeometry(14.4, 6.2, 10.6), frpTowerMat);
    towerBody.position.set(0, 6.4, 0);
    towerBody.castShadow = true;
    towerGrp.add(towerBody);

    // Lower Air Intake Louver Slats (Panjurlar)
    [-5.3, 5.3].forEach(lz => {
      for (let ly = 1.6; ly <= 3.3; ly += 0.42) {
        const louver = new THREE.Mesh(new THREE.BoxGeometry(14.0, 0.08, 0.38), louverMat);
        louver.rotation.x = lz > 0 ? 0.6 : -0.6;
        louver.position.set(0, ly, lz);
        towerGrp.add(louver);
      }
    });
    [-7.2, 7.2].forEach(lx => {
      for (let ly = 1.6; ly <= 3.3; ly += 0.42) {
        const louverSide = new THREE.Mesh(new THREE.BoxGeometry(0.38, 0.08, 10.0), louverMat);
        louverSide.rotation.z = lx > 0 ? -0.6 : 0.6;
        louverSide.position.set(lx, ly, 0);
        towerGrp.add(louverSide);
      }
    });

    // Top Fan Stack (Induced-Draft Diffuser Shroud)
    const towerStack = new THREE.Mesh(new THREE.CylinderGeometry(3.6, 3.2, 2.0, 32, 1, true), darkExhaustMat);
    towerStack.position.set(0, 10.4, 0);
    towerGrp.add(towerStack);

    const stackRim = new THREE.Mesh(new THREE.TorusGeometry(3.6, 0.16, 12, 32), steelShellMat);
    stackRim.rotation.x = Math.PI / 2;
    stackRim.position.set(0, 11.4, 0);
    towerGrp.add(stackRim);

    // Fan Motor Support Bridge Beams
    const motorBeam = new THREE.Mesh(new THREE.BoxGeometry(7.2, 0.2, 0.2), gantryMat);
    motorBeam.position.set(0, 10.4, 0);
    towerGrp.add(motorBeam);

    const towerMotor = new THREE.Mesh(new THREE.CylinderGeometry(0.6, 0.6, 0.85, 16), motorBlueMat);
    towerMotor.position.set(0, 10.4, 0);
    towerGrp.add(towerMotor);

    // Induced-Draft Top Axial Cooling Fan Rotor
    towerFanRotor = new THREE.Group();
    towerFanRotor.position.set(0, 10.8, 0);

    const tHub = new THREE.Mesh(new THREE.CylinderGeometry(0.8, 0.8, 0.35, 16), motorBlueMat);
    towerFanRotor.add(tHub);

    // 6 Wide-Chord Cooling Tower Blades
    for (let i = 0; i < 6; i++) {
      const bGrp = new THREE.Group();
      bGrp.rotation.y = (i * Math.PI) / 3;

      const tBlade = new THREE.Mesh(new THREE.BoxGeometry(2.5, 0.06, 0.52), stainlessMat);
      tBlade.position.set(1.7, 0, 0);
      tBlade.rotation.x = 0.28;
      bGrp.add(tBlade);

      towerFanRotor.add(bGrp);
    }
    towerGrp.add(towerFanRotor);

    // Cooling Tower Rising Vapor / Mist Particles
    const mistGeo = new THREE.BufferGeometry();
    const mistCount = 45;
    const mistPos = new Float32Array(mistCount * 3);
    for (let m = 0; m < mistCount; m++) {
      const rad = Math.random() * 2.8;
      const ang = Math.random() * Math.PI * 2;
      mistPos[m * 3] = Math.cos(ang) * rad;
      mistPos[m * 3 + 1] = 11.4 + Math.random() * 7.5;
      mistPos[m * 3 + 2] = Math.sin(ang) * rad;
    }
    mistGeo.setAttribute("position", new THREE.BufferAttribute(mistPos, 3));
    const mistMat = new THREE.PointsMaterial({
      color: 0xe2e8f0,
      size: 1.8,
      transparent: true,
      opacity: 0.35,
      blending: THREE.AdditiveBlending
    });
    coolingTowerMist = new THREE.Points(mistGeo, mistMat);
    towerGrp.add(coolingTowerMist);

    // Circulating Cooling Water Pipes between Tower and Condenser (Orthogonal with Elbows)
    // CW Supply (Cold, Dark Blue): from Tower basin (x = -0.8, y = 1.9, z = 0.8) to C-101 cwInNoz (x = 18.1, y = 1.9, z = 0.8)
    const cwSupplyPipe = new THREE.Mesh(new THREE.CylinderGeometry(0.35, 0.35, 18.9, 16), motorBlueMat);
    cwSupplyPipe.rotation.z = Math.PI / 2;
    cwSupplyPipe.position.set(8.65, 1.9, 0.8);
    waterCondenserGroup.add(cwSupplyPipe);

    // CW Return (Warm, Cyan): from C-101 cwOutNoz (x = 18.1, y = 2.9, z = -0.8) -> riser at x = 16.0 -> Tower header (x = -0.8, y = 7.0, z = -0.8)
    const cwRetMat = new THREE.MeshStandardMaterial({ color: 0x06b6d4, metalness: 0.30, roughness: 0.38 });
    const cwRetHoriz1 = new THREE.Mesh(new THREE.CylinderGeometry(0.35, 0.35, 1.5, 16), cwRetMat);
    cwRetHoriz1.rotation.z = Math.PI / 2;
    cwRetHoriz1.position.set(17.35, 2.9, -0.8);
    waterCondenserGroup.add(cwRetHoriz1);

    const cwElbow1 = new THREE.Mesh(
      new THREE.TubeGeometry(
        new THREE.QuadraticBezierCurve3(
          new THREE.Vector3(16.6, 2.9, -0.8),
          new THREE.Vector3(16.0, 2.9, -0.8),
          new THREE.Vector3(16.0, 3.5, -0.8)
        ), 12, 0.35, 16, false
      ),
      cwRetMat
    );
    waterCondenserGroup.add(cwElbow1);

    const cwRetRiser = new THREE.Mesh(new THREE.CylinderGeometry(0.35, 0.35, 2.9, 16), cwRetMat);
    cwRetRiser.position.set(16.0, 4.95, -0.8);
    waterCondenserGroup.add(cwRetRiser);

    const cwElbow2 = new THREE.Mesh(
      new THREE.TubeGeometry(
        new THREE.QuadraticBezierCurve3(
          new THREE.Vector3(16.0, 6.4, -0.8),
          new THREE.Vector3(16.0, 7.0, -0.8),
          new THREE.Vector3(15.4, 7.0, -0.8)
        ), 12, 0.35, 16, false
      ),
      cwRetMat
    );
    waterCondenserGroup.add(cwElbow2);

    const cwReturnPipe = new THREE.Mesh(new THREE.CylinderGeometry(0.35, 0.35, 16.2, 16), cwRetMat);
    cwReturnPipe.rotation.z = Math.PI / 2;
    cwReturnPipe.position.set(7.3, 7.0, -0.8);
    waterCondenserGroup.add(cwReturnPipe);

    towerGrp.userData = { id: "node_condenser", name: "Mekanik Çekmeli Sulu Soğutma Kulesi (CT-101)", type: "condenser" };
    waterCondenserGroup.add(towerGrp);
    interactiveObjects.push(towerBody);
    towerBody.userData = towerGrp.userData;

    plant3DGroup.add(waterCondenserGroup);

    // Initial Condenser Visibility based on initialData or latestCalcResult (Default: ACC / "air")
    const initCond = (typeof initialData !== "undefined" && initialData && (initialData.condenser_type || (initialData.condenser && initialData.condenser.type))) ||
                     (window.latestCalcResult && window.latestCalcResult.condenser && window.latestCalcResult.condenser.type) || "air";
    const isAirInit = (initCond === "air" || initCond === "acc" || initCond === "hava" || initCond === "air_cooled");
    accGroup.visible = isAirInit;
    waterCondenserGroup.visible = !isAirInit;

    // F. Kızgın Yağ Sirkülasyon Pompası (P-101 - API 610 End-Suction Centrifugal)
    const pumpGrp = new THREE.Group();
    pumpGrp.position.set(34, 0, -2);

    const pumpVolute = new THREE.Mesh(new THREE.CylinderGeometry(1.4, 1.4, 1.0, 16), motorBlueMat);
    pumpVolute.rotation.z = Math.PI / 2;
    pumpVolute.position.set(-1.0, 1.8, 0);
    pumpGrp.add(pumpVolute);

    // Volute Axial Suction Nozzle (facing -X)
    const pumpSuctionNoz = new THREE.Mesh(new THREE.CylinderGeometry(0.42, 0.42, 1.2, 16), stainlessMat);
    pumpSuctionNoz.rotation.z = Math.PI / 2;
    pumpSuctionNoz.position.set(-1.8, 1.8, 0);
    pumpGrp.add(pumpSuctionNoz);

    // Volute Top Discharge Nozzle (facing +Y)
    const pumpDischargeNoz = new THREE.Mesh(new THREE.CylinderGeometry(0.38, 0.38, 0.8, 16), stainlessMat);
    pumpDischargeNoz.position.set(-1.0, 2.5, 0);
    pumpGrp.add(pumpDischargeNoz);

    const pumpMotor = new THREE.Mesh(new THREE.CylinderGeometry(1.2, 1.2, 2.4, 16), motorBlueMat);
    pumpMotor.rotation.z = Math.PI / 2;
    pumpMotor.position.set(1.2, 1.8, 0);
    pumpGrp.add(pumpMotor);

    pumpGrp.userData = { id: "node_pump", name: "Kızgın Yağ Sirkülasyon Pompası", type: "pump" };
    plant3DGroup.add(pumpGrp);
    interactiveObjects.push(pumpVolute);
    pumpVolute.userData = pumpGrp.userData;

    // G. Siklopentan Besleme Pompası (CP-Pump - API 610)
    const cpPumpGrp = new THREE.Group();
    cpPumpGrp.position.set(-15, 0, 12);

    const cpVolute = new THREE.Mesh(new THREE.CylinderGeometry(1.1, 1.1, 0.8, 16), motorBlueMat);
    cpVolute.rotation.z = Math.PI / 2;
    cpVolute.position.set(-0.8, 1.5, 0);
    cpPumpGrp.add(cpVolute);

    // CP Volute Suction Port (facing +Z)
    const cpSuctionNoz = new THREE.Mesh(new THREE.CylinderGeometry(0.32, 0.32, 1.5, 16), stainlessMat);
    cpSuctionNoz.rotation.x = Math.PI / 2;
    cpSuctionNoz.position.set(-0.8, 1.5, 0.75);
    cpPumpGrp.add(cpSuctionNoz);

    // CP Volute Top Discharge Port (facing +Y)
    const cpDischargeNoz = new THREE.Mesh(new THREE.CylinderGeometry(0.30, 0.30, 0.8, 16), stainlessMat);
    cpDischargeNoz.position.set(-0.8, 2.1, 0);
    cpPumpGrp.add(cpDischargeNoz);

    const cpMotor = new THREE.Mesh(new THREE.CylinderGeometry(0.9, 0.9, 1.8, 16), motorBlueMat);
    cpMotor.rotation.z = Math.PI / 2;
    cpMotor.position.set(0.8, 1.5, 0);
    cpPumpGrp.add(cpMotor);

    cpPumpGrp.userData = { id: "node_cp_pump", name: "Siklopentan Besleme Pompası", type: "cp_pump" };
    plant3DGroup.add(cpPumpGrp);
    interactiveObjects.push(cpVolute);
    cpVolute.userData = cpPumpGrp.userData;
  }

  /* -------------------------------------------------------------------------
   * 4. Traditional Plant Orthogonal Piping System (Düz Boru, Dirsek, U-Turn, Flanş)
   * ------------------------------------------------------------------------- */
  function buildOrthogonalPipingNetwork() {
    const pipeMatHot = new THREE.MeshStandardMaterial({ color: 0xef4444, metalness: 0.30, roughness: 0.32 });
    const pipeMatRet = new THREE.MeshStandardMaterial({ color: 0xf59e0b, metalness: 0.30, roughness: 0.32 });
    const pipeMatVap = new THREE.MeshStandardMaterial({ color: 0xa855f7, metalness: 0.30, roughness: 0.32 });
    const pipeMatLiq = new THREE.MeshStandardMaterial({ color: 0x06b6d4, metalness: 0.30, roughness: 0.32 });
    const flangeMat = new THREE.MeshStandardMaterial({ color: 0xcbd5e1, metalness: 0.38, roughness: 0.28 });
    const valveMat = new THREE.MeshStandardMaterial({ color: 0x0284c7, metalness: 0.32, roughness: 0.35 });
    const stainlessMat = new THREE.MeshStandardMaterial({ color: 0xf1f5f9, metalness: 0.35, roughness: 0.28 });

    // --- PIPING ELEMENT HELPERS ---

    // 1. Düz Boru Parçası (Straight Pipe Spool)
    function addStraightSpool(p1, p2, radius, mat, parentGrp) {
      const v1 = (p1 instanceof THREE.Vector3) ? p1 : new THREE.Vector3(p1[0], p1[1], p1[2]);
      const v2 = (p2 instanceof THREE.Vector3) ? p2 : new THREE.Vector3(p2[0], p2[1], p2[2]);
      const dist = v1.distanceTo(v2);
      if (dist < 0.05) return;

      const cylGeo = new THREE.CylinderGeometry(radius, radius, dist, 16);
      const mesh = new THREE.Mesh(cylGeo, mat);
      mesh.castShadow = true;

      // Position at midpoint
      mesh.position.copy(v1).add(v2).multiplyScalar(0.5);

      // Rotate cylinder (default orientation along Y) to align with direction vector
      const dir = new THREE.Vector3().subVectors(v2, v1).normalize();
      const up = new THREE.Vector3(0, 1, 0);
      if (!dir.equals(up)) {
        if (dir.equals(new THREE.Vector3(0, -1, 0))) {
          mesh.rotation.z = Math.PI;
        } else {
          mesh.quaternion.setFromUnitVectors(up, dir);
        }
      }

      (parentGrp || plant3DGroup).add(mesh);
      return mesh;
    }

    // 2. Standart 90° Dirsek (90° Butt-Weld Elbow — C1 Tangent-Continuous)
    function addElbow90(center, dirIn, dirOut, bendRadius, pipeRadius, mat, parentGrp) {
      const c = (center instanceof THREE.Vector3) ? center : new THREE.Vector3(center[0], center[1], center[2]);
      const dIn = dirIn.clone().normalize();
      const dOut = dirOut.clone().normalize();

      // Exact weld endpoints matching incoming spool endPt and outgoing spool startPt
      const pStart = c.clone().addScaledVector(dIn, -bendRadius);
      const pEnd = c.clone().addScaledVector(dOut, bendRadius);

      const curve = new THREE.QuadraticBezierCurve3(pStart, c, pEnd);
      const tubeGeo = new THREE.TubeGeometry(curve, 14, pipeRadius, 16, false);
      const mesh = new THREE.Mesh(tubeGeo, mat);
      mesh.castShadow = true;

      (parentGrp || plant3DGroup).add(mesh);
      return mesh;
    }

    // 3. Flanş Çifti (Flange Pair)
    function addFlangePair(position, axisDir, pipeRadius, parentGrp) {
      const p = (position instanceof THREE.Vector3) ? position : new THREE.Vector3(position[0], position[1], position[2]);
      const dir = axisDir.clone().normalize();
      const flGeo = new THREE.CylinderGeometry(pipeRadius * 1.55, pipeRadius * 1.55, 0.22, 18);
      const flMesh = new THREE.Mesh(flGeo, flangeMat);
      flMesh.position.copy(p);

      const up = new THREE.Vector3(0, 1, 0);
      if (!dir.equals(up)) {
        if (dir.y < -0.9999) {
          flMesh.rotation.z = Math.PI;
        } else {
          flMesh.quaternion.setFromUnitVectors(up, dir);
        }
      }
      (parentGrp || plant3DGroup).add(flMesh);
    }

    // 4. Geleneksel Ortogonal Hat Oluşturucu (Build Orthogonal Line with Elbows & Flanges)
    function buildOrthogonalRun(waypoints, pipeRadius, mat, parentGrp) {
      const rawPts = waypoints.map(wp => (wp instanceof THREE.Vector3) ? wp.clone() : new THREE.Vector3(...wp));
      // Filter out collinear or duplicate intermediate points so straight spools are never broken
      const pts = [rawPts[0]];
      for (let k = 1; k < rawPts.length - 1; k++) {
        const prev = pts[pts.length - 1];
        const curr = rawPts[k];
        const next = rawPts[k + 1];
        if (curr.distanceTo(prev) < 0.05 || next.distanceTo(curr) < 0.05) continue;
        const d1 = new THREE.Vector3().subVectors(curr, prev).normalize();
        const d2 = new THREE.Vector3().subVectors(next, curr).normalize();
        if (d1.dot(d2) > 0.995) continue;
        pts.push(curr);
      }
      pts.push(rawPts[rawPts.length - 1]);

      const baseBend = Math.min(0.8, pipeRadius * 2.2);
      const cornerRadii = new Array(pts.length).fill(0);
      for (let k = 1; k < pts.length - 1; k++) {
        const lenPrev = pts[k].distanceTo(pts[k - 1]);
        const lenNext = pts[k + 1].distanceTo(pts[k]);
        cornerRadii[k] = Math.min(baseBend, 0.42 * lenPrev, 0.42 * lenNext);
      }

      for (let i = 0; i < pts.length - 1; i++) {
        const pA = pts[i];
        const pB = pts[i + 1];
        const segDir = new THREE.Vector3().subVectors(pB, pA).normalize();

        const startPt = pA.clone().addScaledVector(segDir, cornerRadii[i]);
        const endPt = pB.clone().addScaledVector(segDir, -cornerRadii[i + 1]);

        addStraightSpool(startPt, endPt, pipeRadius, mat, parentGrp);

        // Add 90° elbow at corner welding endPt of segment i to startPt of segment i+1
        if (i < pts.length - 2) {
          const pC = pts[i + 2];
          const nextDir = new THREE.Vector3().subVectors(pC, pB).normalize();
          addElbow90(pB, segDir, nextDir, cornerRadii[i + 1], pipeRadius, mat, parentGrp);
        }
      }

      // Add connection flanges at line start and end
      const firstDir = new THREE.Vector3().subVectors(pts[1], pts[0]).normalize();
      addFlangePair(pts[0], firstDir, pipeRadius, parentGrp);

      const lastIdx = pts.length - 1;
      const lastDir = new THREE.Vector3().subVectors(pts[lastIdx], pts[lastIdx - 1]).normalize();
      addFlangePair(pts[lastIdx], lastDir, pipeRadius, parentGrp);
    }

    // --- PLANT PIPING NETWORK EXECUTION ---

    // A. Manifoldlar (Headers)
    // 1. Üst Sıcak Yağ Toplama Manifoldu (Hot Collection Header - High Elevation Y = 11.2)
    addStraightSpool([-52, 11.2, -12], [14, 11.2, -12], 0.70, pipeMatHot);
    addFlangePair([-52, 11.2, -12], new THREE.Vector3(-1, 0, 0), 0.70);
    addFlangePair([14, 11.2, -12], new THREE.Vector3(1, 0, 0), 0.70);

    // 2. Alt Soğuk Yağ Dağıtım Manifoldu (Cold Distribution Header - Mid Elevation Y = 4.2)
    addStraightSpool([-52, 4.2, -24], [14, 4.2, -24], 0.70, pipeMatRet);
    addFlangePair([-52, 4.2, -24], new THREE.Vector3(-1, 0, 0), 0.70);
    addFlangePair([14, 4.2, -24], new THREE.Vector3(1, 0, 0), 0.70);

    // B. Kazan Bağlantı Branşmanları (WHRU Boilers 1..5 Risers & Drops)
    const whruXCoords = [-52, -37, -22, -7, 8];
    whruXCoords.forEach((x, idx) => {
      const riserGroup = new THREE.Group();

      // Kazan Çıkışından Üst Sıcak Manifolda Ortogonal Düşüş Hattı (Hot Drop)
      const hotDropWaypoints = [
        new THREE.Vector3(x + 3.8, 10.0, -18),  // Boiler outlet nozzle
        new THREE.Vector3(x + 3.8, 11.2, -18),  // Vertical spool up to rack level
        new THREE.Vector3(x + 3.8, 11.2, -12),  // Horizontal cross spool along Z to manifold
        new THREE.Vector3(x, 11.2, -12)          // Tie-in tee to Hot Collection Header
      ];
      buildOrthogonalRun(hotDropWaypoints, 0.32, pipeMatHot, riserGroup);

      // Alt Manifolddan Kazan Girişine Ortogonal Besleme Hattı (Cold Riser)
      const coldRiserWaypoints = [
        new THREE.Vector3(x, 4.2, -24),          // Tie-in tee on Cold Distribution Header
        new THREE.Vector3(x + 3.8, 4.2, -24),  // Horizontal spool along X
        new THREE.Vector3(x + 3.8, 4.2, -18),  // Horizontal spool along Z to boiler
        new THREE.Vector3(x + 3.8, 2.5, -18)   // Vertical drop into boiler inlet nozzle
      ];
      buildOrthogonalRun(coldRiserWaypoints, 0.32, pipeMatRet, riserGroup);

      riserGroup.userData = { boilerIndex: idx + 1 };
      plant3DGroup.add(riserGroup);
      boilerRisers3D.push(riserGroup);
    });

    // C. Kızgın Yağ İletim Hattı (Hot Manifold -> 3-Yollu Vana V-101 -> Superheater SH)
    // Kuzey (z = -21.0) koridorundan yaklaşarak Siklopentan buhar hattından (z = -6.0) tamamen ayrışır
    const hotToShWaypoints = [
      new THREE.Vector3(14.0, 11.2, -12.0),  // Hot Collection Header east flange
      new THREE.Vector3(16.5, 11.2, -12.0),  // Continue east along Hot Header axis
      new THREE.Vector3(16.5, 7.8, -12.0),   // Vertical drop through V-101 3-way valve at (16.5, 9.5, -12.0)
      new THREE.Vector3(16.5, 7.8, -21.0),   // Turn north along -Z to dedicated oil approach corridor
      new THREE.Vector3(24.5, 7.8, -21.0),   // Run east behind SH West Channel Head
      new THREE.Vector3(24.5, 7.8, -18.0),   // Turn south to SH centerline above shNozIn
      new THREE.Vector3(24.5, 6.5, -18.0)    // Coaxial vertical drop into SH top nozzle (shNozIn)
    ];
    buildOrthogonalRun(hotToShWaypoints, 0.42, pipeMatHot);

    // 3-Yollu By-pass Vana Gövdesi (V-101)
    const valveBody = new THREE.Mesh(new THREE.BoxGeometry(1.2, 1.4, 1.2), valveMat);
    valveBody.position.set(16.5, 9.5, -12.0);
    valveBody.userData = { id: "node_valve", name: "Oransal 3-Yollu By-Pass Vanası (V-101)", type: "valve" };
    plant3DGroup.add(valveBody);
    interactiveObjects.push(valveBody);
    const valveActuator = new THREE.Mesh(new THREE.CylinderGeometry(0.5, 0.5, 1.0, 16), stainlessMat);
    valveActuator.position.set(17.5, 9.5, -12.0);
    valveActuator.rotation.z = Math.PI / 2;
    plant3DGroup.add(valveActuator);

    // 3-Yollu By-pass Hattı (V-101 3. Port -> Kızgın Yağ Pompası P-101 Emiş / Upstream Hattı)
    const v101BypassWaypoints = [
      new THREE.Vector3(16.5, 9.5, -12.0),   // V-101 3rd port (south bypass port)
      new THREE.Vector3(16.5, 9.5, -2.0),    // Run south along +Z to P-101 suction plane (z = -2.0)
      new THREE.Vector3(16.5, 1.8, -2.0),    // Vertical drop to P-101 suction centerline elevation (y = 1.8)
      new THREE.Vector3(28.0, 1.8, -2.0)     // Tie into P-101 suction return line UPSTREAM of P-101
    ];
    buildOrthogonalRun(v101BypassWaypoints, 0.38, pipeMatRet);

    // D. Kızgın Yağ: Superheater (SH) Çıkışı -> Evaporatör (PH) Girişi (Seri Bağlantı)
    // Güney (z = -13.5) koridorundan giderek kuzeydeki (z = -21.5) Siklopentan buhar köprüsünden ayrışır
    const shToPhWaypoints = [
      new THREE.Vector3(28.0, 1.5, -18.0),   // SH bottom shell outlet nozzle flange (shNozOut)
      new THREE.Vector3(28.0, 0.4, -18.0),   // Coaxial vertical drop to sleeper level
      new THREE.Vector3(28.0, 0.4, -13.5),   // Offset south along Z to sleeper corridor (clears PH saddles)
      new THREE.Vector3(41.5, 0.4, -13.5),   // Run east along sleeper corridor
      new THREE.Vector3(41.5, 8.6, -13.5),   // Vertical riser to overhead tier on south side
      new THREE.Vector3(41.5, 8.6, -18.0),   // Turn north to PH centerline
      new THREE.Vector3(41.5, 7.4, -18.0)    // Coaxial vertical drop into PH top oil inlet nozzle (phNozOilIn)
    ];
    buildOrthogonalRun(shToPhWaypoints, 0.40, pipeMatHot);

    // E. Kızgın Yağ: Evaporatör (PH) Çıkışı -> Sirkülasyon Pompası (P-101 Emiş / Upstream)
    const phToPumpWaypoints = [
      new THREE.Vector3(48.0, 1.5, -18.0),   // PH bottom shell outlet nozzle (phNozOilOut)
      new THREE.Vector3(48.0, 0.4, -18.0),   // Coaxial vertical drop to sleeper level
      new THREE.Vector3(48.0, 0.4, -6.5),    // Run south along Z on sleeper (clears P-101 plinth)
      new THREE.Vector3(28.0, 0.4, -6.5),    // Run west past P-101 pump to suction mixer alignment
      new THREE.Vector3(28.0, 1.8, -6.5),    // Vertical rise to P-101 suction centerline (y = 1.8)
      new THREE.Vector3(28.0, 1.8, -2.0),    // Turn south to P-101 suction axis (Mixer Tee with V-101 bypass!)
      new THREE.Vector3(31.8, 1.8, -2.0)     // Coaxial axial entry into P-101 suction nozzle (pumpSuctionNoz)
    ];
    buildOrthogonalRun(phToPumpWaypoints, 0.42, pipeMatRet);

    // F. Kızgın Yağ: Pompa Basma (Discharge / Downstream) -> Alt Dağıtım Manifoldu (Cold Header)
    const pumpToManifoldWaypoints = [
      new THREE.Vector3(33.0, 2.6, -2.0),    // P-101 top discharge nozzle (pumpDischargeNoz)
      new THREE.Vector3(33.0, 4.2, -2.0),    // Coaxial vertical riser to mid rack level
      new THREE.Vector3(33.0, 4.2, -24.0),   // Cross north along Z to Cold Manifold alignment
      new THREE.Vector3(14.0, 4.2, -24.0)    // Coaxial entry into Cold Distribution Header
    ];
    buildOrthogonalRun(pumpToManifoldWaypoints, 0.42, pipeMatRet);

    // G. Kondenser ve Soğutma Moduna Göre Ayrışan Borulama Grupları
    accPipingGroup = new THREE.Group();
    waterPipingGroup = new THREE.Group();

    // G1. ACC: İki Alt Kondensat Kolektörünü (z=37.8 ve z=26.2) Birleştiren Batı Manifoldu -> P-102 Emiş
    // ACC kolonları (x=-22, -8, +6) ve çapraz rüzgar gergileri ile hiçbir çakışma olmadan batı ucundan (x=-24.6) iner
    addFlangePair([-24.6, 5.3, 26.2], new THREE.Vector3(1, 0, 0), 0.35, accPipingGroup);
    const condToPumpWaypoints = [
      new THREE.Vector3(-24.6, 5.3, 37.8),   // ACC rear bottom condensate header west nozzle (z = 32 + 5.8)
      new THREE.Vector3(-24.6, 5.3, 24.0),   // Collects front header at z = 26.2 and exits north of ACC deck
      new THREE.Vector3(-24.6, 1.5, 24.0),   // Vertical downcomer in open air to sleeper elevation (y = 1.5)
      new THREE.Vector3(-15.8, 1.5, 24.0),   // East sleeper run north of ACC pedestals to P-102 suction axis
      new THREE.Vector3(-15.8, 1.5, 13.5)    // Coaxial north entry into P-102 suction nozzle (cpSuctionNoz)
    ];
    buildOrthogonalRun(condToPumpWaypoints, 0.30, pipeMatLiq, accPipingGroup);

    // G2. Su Soğutmalı: Yüzey Kondenseri Hotwell -> Besleme Pompası (P-102) [Kule Etrafından Bypass]
    const waterCondToPumpWaypoints = [
      new THREE.Vector3(14.0, 1.5, 31.2),    // Surface condenser C-101 hotwell side nozzle (hotwellNoz)
      new THREE.Vector3(14.0, 1.5, 24.0),    // Coaxial north run clearing Cooling Tower CT-101 basin (z=26..38)
      new THREE.Vector3(-15.8, 1.5, 24.0),   // West sleeper run north of Cooling Tower
      new THREE.Vector3(-15.8, 1.5, 13.5)    // Coaxial north run into P-102 suction nozzle (cpSuctionNoz)
    ];
    buildOrthogonalRun(waterCondToPumpWaypoints, 0.30, pipeMatLiq, waterPipingGroup);

    // H. Siklopentan ORC Hattı 2: Besleme Pompası (P-102) -> Evaporatör/Ön Isıtıcı (PH)
    const pumpToPhWaypoints = [
      new THREE.Vector3(-15.8, 2.3, 12.0),   // P-102 top discharge nozzle (cpDischargeNoz)
      new THREE.Vector3(-15.8, 3.5, 12.0),   // Coaxial vertical riser to liquid rack elevation
      new THREE.Vector3(36.5, 3.5, 12.0),    // East pipe rack transfer run across plant
      new THREE.Vector3(36.5, 3.5, -18.0),   // North cross run to PH centerline
      new THREE.Vector3(38.5, 3.5, -18.0)    // Coaxial east run into PH front channel nozzle (phNozLiqIn)
    ];
    buildOrthogonalRun(pumpToPhWaypoints, 0.30, pipeMatLiq);

    // I. Siklopentan ORC Hattı 3: Evaporatör (PH) -> Superheater (SH) [Doymuş Buhar Girişi]
    // Kuzey (z = -21.5) koridorundan giderek Kızgın Yağ ara bağlantı hattından (z = -13.5) tamamen ayrışır
    const phToShVaporWaypoints = [
      new THREE.Vector3(45.0, 7.8, -18.0),   // PH top vapor dome flange (phDomeFlange)
      new THREE.Vector3(45.0, 9.8, -18.0),   // Coaxial vertical riser above PH dome
      new THREE.Vector3(45.0, 9.8, -21.5),   // Offset north to dedicated vapor corridor (z = -21.5)
      new THREE.Vector3(33.8, 9.8, -21.5),   // West overhead bridge behind PH and SH
      new THREE.Vector3(33.8, 3.6, -21.5),   // Vertical drop to SH centerline elevation (y = 3.6)
      new THREE.Vector3(33.8, 3.6, -18.0),   // Turn south to SH East Channel Head axis
      new THREE.Vector3(32.2, 3.6, -18.0)    // Coaxial west entry into SH East Channel nozzle (shVapIn)
    ];
    buildOrthogonalRun(phToShVaporWaypoints, 0.38, pipeMatVap);

    // J. Siklopentan ORC Hattı 4: Superheater (SH) -> Türbin HP Girişi (GENLEŞME LUPU / U-TURN İLE)
    // Kuzeyden (z = 26.0 -> 32.0, y = 7.2) türbin HP salyangozuna yaklaşarak z = 32.0'deki egzoz hattından tamamen ayrışır
    const shToTurbWaypoints = [
      new THREE.Vector3(20.5, 5.6, -18.0),   // SH West Channel Head top vapor nozzle (shVapOut)
      new THREE.Vector3(20.5, 11.8, -18.0),  // Coaxial vertical riser to high pipe rack level
      new THREE.Vector3(20.5, 11.8, -6.0),   // Run south along +Z clearing SH and hot oil lines completely
      new THREE.Vector3(26.0, 11.8, -6.0),   // Turn east onto main north-south pipe rack (x = 26.0)
      new THREE.Vector3(26.0, 11.8, 2.0),    // Straight run on high rack along Z
      // --- U-TURN THERMAL EXPANSION LOOP (GENLEŞME LUPU) ---
      new THREE.Vector3(29.5, 11.8, 2.0),    // Turn +X (Loop arm 1)
      new THREE.Vector3(29.5, 11.8, 6.0),    // Turn +Z (Loop bridge)
      new THREE.Vector3(26.0, 11.8, 6.0),    // Turn -X (Loop arm 2)
      // ----------------------------------------------------
      new THREE.Vector3(26.0, 11.8, 26.0),   // Continue south along rack to north side of turbine skid (z = 26.0)
      new THREE.Vector3(34.5, 11.8, 26.0),   // Turn east to turbine HP inlet scroll plane (x = 34.5)
      new THREE.Vector3(34.5, 7.2, 26.0),    // Drop to turbine inlet approach elevation (y = 7.2)
      new THREE.Vector3(34.5, 7.2, 32.0),    // Run south through Trip & Throttle Valve (z = 29.0) to HP nozzle axis
      new THREE.Vector3(34.5, 5.6, 32.0)     // Coaxial vertical drop into Turbine HP Inlet Nozzle (turbInletNoz)
    ];
    buildOrthogonalRun(shToTurbWaypoints, 0.38, pipeMatVap);

    // Türbin Acil Stop / Trip & Throttle Vanası (Giriş yaklaşım hattı üzerinde)
    const tripValve = new THREE.Mesh(new THREE.BoxGeometry(1.1, 1.1, 1.2), valveMat);
    tripValve.position.set(34.5, 7.2, 29.0);
    plant3DGroup.add(tripValve);
    const tripActuator = new THREE.Mesh(new THREE.CylinderGeometry(0.45, 0.45, 0.9, 16), stainlessMat);
    tripActuator.position.set(34.5, 8.15, 29.0);
    plant3DGroup.add(tripActuator);

    // K1. ACC: Türbin LP Egzoz Difüzörü (x=32.5) -> Hava Soğutmalı Kondenser A-Frame Doğu Tepe Başlığı (x=7.0)
    const turbToAccWaypoints = [
      new THREE.Vector3(32.5, 6.2, 32.0),    // Turbine LP exhaust diffuser top nozzle (turbExhaustNoz)
      new THREE.Vector3(32.5, 12.0, 32.0),   // Coaxial vertical riser to overhead steam manifold elevation
      new THREE.Vector3(7.0, 12.0, 32.0)     // Coaxial entry into ACC east apex steam header nozzle (accSteamInNoz)
    ];
    buildOrthogonalRun(turbToAccWaypoints, 0.65, pipeMatVap, accPipingGroup);

    // K2. Su Soğutmalı: Türbin LP Egzoz Difüzörü (x=32.5) -> Yüzey Kondenseri C-101 Buhar Giriş Kubbesi (x=14.0)
    const turbToWaterCondWaypoints = [
      new THREE.Vector3(32.5, 6.2, 32.0),    // Turbine LP exhaust diffuser top nozzle (turbExhaustNoz)
      new THREE.Vector3(32.5, 8.2, 32.0),    // Coaxial vertical riser to overhead exhaust bridge
      new THREE.Vector3(14.0, 8.2, 32.0),    // West overhead run to Surface Condenser C-101 dome axis
      new THREE.Vector3(14.0, 4.4, 32.0)     // Coaxial vertical drop into C-101 top steam dome (sDomeFlange)
    ];
    buildOrthogonalRun(turbToWaterCondWaypoints, 0.65, pipeMatVap, waterPipingGroup);

    plant3DGroup.add(accPipingGroup);
    plant3DGroup.add(waterPipingGroup);

    const initCondPipe = (typeof initialData !== "undefined" && initialData && (initialData.condenser_type || (initialData.condenser && initialData.condenser.type))) ||
                         (window.latestCalcResult && window.latestCalcResult.condenser && window.latestCalcResult.condenser.type) || "air";
    const isAirInitPipe = (initCondPipe === "air" || initCondPipe === "acc" || initCondPipe === "hava" || initCondPipe === "air_cooled");
    accPipingGroup.visible = isAirInitPipe;
    waterPipingGroup.visible = !isAirInitPipe;
  }

  /* -------------------------------------------------------------------------
   * 5. Animated 3D Flow Particle Streams (Ortogonal Hatları İzleyen Akışkan)
   * ------------------------------------------------------------------------- */
  function buildParticleFlowStreams() {
    accParticles = [];
    waterParticles = [];

    const streamConfigs = [
      // 1. Sıcak Yağ İletim Akışı (Kazanlar -> SH -> PH) [Ortak]
      { mode: "common", color: 0xef4444, count: 32, path: [
        new THREE.Vector3(-45, 11.2, -12),
        new THREE.Vector3(16.5, 11.2, -12),
        new THREE.Vector3(16.5, 7.8, -12),
        new THREE.Vector3(16.5, 7.8, -21.0),
        new THREE.Vector3(24.5, 7.8, -21.0),
        new THREE.Vector3(24.5, 7.8, -18.0),
        new THREE.Vector3(24.5, 6.5, -18.0),
        new THREE.Vector3(28.0, 1.5, -18.0),
        new THREE.Vector3(28.0, 0.4, -18.0),
        new THREE.Vector3(28.0, 0.4, -13.5),
        new THREE.Vector3(41.5, 0.4, -13.5),
        new THREE.Vector3(41.5, 8.6, -13.5),
        new THREE.Vector3(41.5, 8.6, -18.0),
        new THREE.Vector3(41.5, 7.4, -18.0)
      ], speed: 0.0032 },

      // 2. Dönüş Yağı Akışı (PH -> Pompa Emiş / Upstream -> Pompa Basma / Downstream -> Alt Manifold) [Ortak]
      { mode: "common", color: 0xeab308, count: 28, path: [
        new THREE.Vector3(48.0, 1.5, -18.0),
        new THREE.Vector3(48.0, 0.4, -18.0),
        new THREE.Vector3(48.0, 0.4, -6.5),
        new THREE.Vector3(28.0, 0.4, -6.5),
        new THREE.Vector3(28.0, 1.8, -6.5),
        new THREE.Vector3(28.0, 1.8, -2.0),
        new THREE.Vector3(31.8, 1.8, -2.0),
        new THREE.Vector3(33.0, 2.6, -2.0),
        new THREE.Vector3(33.0, 4.2, -2.0),
        new THREE.Vector3(33.0, 4.2, -24.0),
        new THREE.Vector3(-45.0, 4.2, -24.0)
      ], speed: 0.0030 },

      // 3A. Siklopentan Kızgın Buhar: SH -> U-Turn -> Türbin HP Giriş -> LP Egzoz -> ACC (Hava Soğutmalı)
      { mode: "air", color: 0xc084fc, count: 28, path: [
        new THREE.Vector3(20.5, 5.6, -18.0),
        new THREE.Vector3(20.5, 11.8, -18.0),
        new THREE.Vector3(20.5, 11.8, -6.0),
        new THREE.Vector3(26.0, 11.8, -6.0),
        new THREE.Vector3(26.0, 11.8, 2.0),
        new THREE.Vector3(29.5, 11.8, 2.0),
        new THREE.Vector3(29.5, 11.8, 6.0),
        new THREE.Vector3(26.0, 11.8, 6.0),
        new THREE.Vector3(26.0, 11.8, 26.0),
        new THREE.Vector3(34.5, 11.8, 26.0),
        new THREE.Vector3(34.5, 7.2, 26.0),
        new THREE.Vector3(34.5, 7.2, 32.0),
        new THREE.Vector3(34.5, 5.6, 32.0),
        new THREE.Vector3(32.5, 6.2, 32.0),
        new THREE.Vector3(32.5, 12.0, 32.0),
        new THREE.Vector3(7.0, 12.0, 32.0),
        new THREE.Vector3(-22.0, 12.0, 32.0)
      ], speed: 0.0045 },

      // 3B. Siklopentan Kızgın Buhar: SH -> U-Turn -> Türbin HP Giriş -> LP Egzoz -> Yüzey Kondenseri (Su Soğutmalı)
      { mode: "water", color: 0xc084fc, count: 26, path: [
        new THREE.Vector3(20.5, 5.6, -18.0),
        new THREE.Vector3(20.5, 11.8, -18.0),
        new THREE.Vector3(20.5, 11.8, -6.0),
        new THREE.Vector3(26.0, 11.8, -6.0),
        new THREE.Vector3(26.0, 11.8, 2.0),
        new THREE.Vector3(29.5, 11.8, 2.0),
        new THREE.Vector3(29.5, 11.8, 6.0),
        new THREE.Vector3(26.0, 11.8, 6.0),
        new THREE.Vector3(26.0, 11.8, 26.0),
        new THREE.Vector3(34.5, 11.8, 26.0),
        new THREE.Vector3(34.5, 7.2, 26.0),
        new THREE.Vector3(34.5, 7.2, 32.0),
        new THREE.Vector3(34.5, 5.6, 32.0),
        new THREE.Vector3(32.5, 6.2, 32.0),
        new THREE.Vector3(32.5, 8.2, 32.0),
        new THREE.Vector3(14.0, 8.2, 32.0),
        new THREE.Vector3(14.0, 4.4, 32.0)
      ], speed: 0.0045 },

      // 4A. Siklopentan Sıvı Kondensat: ACC Kondensat Manifoldu -> CP Pompa (P-102) -> Evaporatör (PH)
      { mode: "air", color: 0x06b6d4, count: 24, path: [
        new THREE.Vector3(-24.6, 5.3, 37.8),
        new THREE.Vector3(-24.6, 5.3, 24.0),
        new THREE.Vector3(-24.6, 1.5, 24.0),
        new THREE.Vector3(-15.8, 1.5, 24.0),
        new THREE.Vector3(-15.8, 1.5, 13.5),
        new THREE.Vector3(-15.8, 2.3, 12.0),
        new THREE.Vector3(-15.8, 3.5, 12.0),
        new THREE.Vector3(36.5, 3.5, 12.0),
        new THREE.Vector3(36.5, 3.5, -18.0),
        new THREE.Vector3(38.5, 3.5, -18.0)
      ], speed: 0.0028 },

      // 4B. Siklopentan Sıvı Kondensat: Yüzey Kondenseri -> CP Pompa -> Evaporatör
      { mode: "water", color: 0x06b6d4, count: 22, path: [
        new THREE.Vector3(14.0, 1.5, 31.2),
        new THREE.Vector3(14.0, 1.5, 24.0),
        new THREE.Vector3(-15.8, 1.5, 24.0),
        new THREE.Vector3(-15.8, 1.5, 13.5),
        new THREE.Vector3(-15.8, 2.3, 12.0),
        new THREE.Vector3(-15.8, 3.5, 12.0),
        new THREE.Vector3(36.5, 3.5, 12.0),
        new THREE.Vector3(36.5, 3.5, -18.0),
        new THREE.Vector3(38.5, 3.5, -18.0)
      ], speed: 0.0028 },

      // 5. Doymuş Buhar Akışı: Evaporatör (PH) -> Superheater (SH) [Ortak]
      { mode: "common", color: 0x9333ea, count: 20, path: [
        new THREE.Vector3(45.0, 7.8, -18.0),
        new THREE.Vector3(45.0, 9.8, -18.0),
        new THREE.Vector3(45.0, 9.8, -21.5),
        new THREE.Vector3(33.8, 9.8, -21.5),
        new THREE.Vector3(33.8, 3.6, -21.5),
        new THREE.Vector3(33.8, 3.6, -18.0),
        new THREE.Vector3(32.2, 3.6, -18.0)
      ], speed: 0.0038 },

      // 6. Soğutma Suyu (CW): Kule Havuzundan Yüzey Kondenserine Soğuk Besleme
      { mode: "water", color: 0x3b82f6, count: 18, path: [
        new THREE.Vector3(-8.8, 1.9, 32.8),
        new THREE.Vector3(10.1, 1.9, 32.8)
      ], speed: 0.0035 },

      // 7. Soğutma Suyu (CW): Yüzey Kondenserinden Kuleye Ilık Dönüş
      { mode: "water", color: 0x38bdf8, count: 18, path: [
        new THREE.Vector3(10.1, 2.9, 31.2),
        new THREE.Vector3(8.0, 2.9, 31.2),
        new THREE.Vector3(8.0, 7.0, 31.2),
        new THREE.Vector3(-8.8, 7.0, 31.2)
      ], speed: 0.0035 }
    ];

    streamConfigs.forEach(cfg => {
      // Connect orthogonal waypoints using linear line segments
      const curve = new THREE.CurvePath();
      for (let i = 0; i < cfg.path.length - 1; i++) {
        curve.add(new THREE.LineCurve3(cfg.path[i], cfg.path[i + 1]));
      }

      const points = curve.getPoints(cfg.count);
      const pGeo = new THREE.BufferGeometry();
      const posArray = new Float32Array(cfg.count * 3);
      points.forEach((pt, i) => {
        posArray[i * 3] = pt.x;
        posArray[i * 3 + 1] = pt.y;
        posArray[i * 3 + 2] = pt.z;
      });
      pGeo.setAttribute("position", new THREE.BufferAttribute(posArray, 3));

      const pMat = new THREE.PointsMaterial({
        color: cfg.color,
        size: 1.25,
        transparent: true,
        opacity: 0.95
      });

      const pSystem = new THREE.Points(pGeo, pMat);
      plant3DGroup.add(pSystem);

      const pEntry = {
        system: pSystem,
        curve: curve,
        count: cfg.count,
        speed: cfg.speed,
        progress: 0.0,
        mode: cfg.mode
      };

      animatedParticles.push(pEntry);
      if (cfg.mode === "air") accParticles.push(pEntry);
      if (cfg.mode === "water") waterParticles.push(pEntry);
    });

    const initCondPart = (typeof initialData !== "undefined" && initialData && (initialData.condenser_type || (initialData.condenser && initialData.condenser.type))) ||
                         (window.latestCalcResult && window.latestCalcResult.condenser && window.latestCalcResult.condenser.type) || "air";
    const isAirInitPart = (initCondPart === "air" || initCondPart === "acc" || initCondPart === "hava" || initCondPart === "air_cooled");
    accParticles.forEach(p => { p.system.visible = isAirInitPart; });
    waterParticles.forEach(p => { p.system.visible = !isAirInitPart; });
  }

  /* -------------------------------------------------------------------------
   * 6. Render Loop & Animation Frame
   * ------------------------------------------------------------------------- */
  let animFrameId = null;
  let is3DActive = false;

  function animate3D() {
    if (!is3DActive) {
      animFrameId = null;
      return;
    }
    animFrameId = requestAnimationFrame(animate3D);

    // ACC Individual Fan Rotors Rotation (Each fan spins about its own local vertical axis)
    if (accGroup && accGroup.visible) {
      accFanRotors.forEach(r => {
        r.rotation.y += 0.045;
      });
    }

    // Cooling Tower Induced-Draft Top Fan Rotation
    if (waterCondenserGroup && waterCondenserGroup.visible && towerFanRotor) {
      towerFanRotor.rotation.y += 0.040;
    }

    // Cooling Tower Rising Vapor / Mist Particles Drift
    if (waterCondenserGroup && waterCondenserGroup.visible && coolingTowerMist) {
      const mistPos = coolingTowerMist.geometry.attributes.position.array;
      for (let m = 0; m < mistPos.length / 3; m++) {
        mistPos[m * 3 + 1] += 0.035;
        if (mistPos[m * 3 + 1] > 19.0) {
          mistPos[m * 3 + 1] = 11.4;
        }
      }
      coolingTowerMist.geometry.attributes.position.needsUpdate = true;
    }

    // Fluid Particles Flow Along Orthogonal Plant Curves
    animatedParticles.forEach(p => {
      if (!p.system.visible) return;
      p.progress = (p.progress + p.speed) % 1.0;
      const positions = p.system.geometry.attributes.position.array;
      for (let i = 0; i < p.count; i++) {
        const u = (p.progress + i / p.count) % 1.0;
        const pt = p.curve.getPointAt(u);
        if (pt) {
          positions[i * 3] = pt.x;
          positions[i * 3 + 1] = pt.y;
          positions[i * 3 + 2] = pt.z;
        }
      }
      p.system.geometry.attributes.position.needsUpdate = true;
    });

    if (controls3D) controls3D.update();
    if (renderer3D && scene3D && camera3D) {
      renderer3D.render(scene3D, camera3D);
    }
  }

  function start3DAnimation() {
    is3DActive = true;
    if (!animFrameId) {
      animFrameId = requestAnimationFrame(animate3D);
    }
  }

  function stop3DAnimation() {
    is3DActive = false;
    if (animFrameId) {
      cancelAnimationFrame(animFrameId);
      animFrameId = null;
    }
  }

  /* -------------------------------------------------------------------------
   * 7. Interactive Raycasting & Telemetry HUD Overlay
   * ------------------------------------------------------------------------- */
  function isObjectVisibleInHierarchy(obj) {
    let curr = obj;
    while (curr) {
      if (curr.visible === false) return false;
      curr = curr.parent;
    }
    return true;
  }

  function on3DMouseMove(event) {
    const rect = renderer3D.domElement.getBoundingClientRect();
    mouse3D.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
    mouse3D.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;

    raycaster3D.setFromCamera(mouse3D, camera3D);
    const visibleTargets = interactiveObjects.filter(isObjectVisibleInHierarchy);
    const intersects = raycaster3D.intersectObjects(visibleTargets, false);

    if (intersects.length > 0) {
      renderer3D.domElement.style.cursor = "pointer";
      const hit = intersects[0].object;
      if (hoveredObject !== hit) {
        if (hoveredObject && hoveredObject.material && hoveredObject.material.emissive) {
          hoveredObject.material.emissive.setHex(0x000000);
        }
        hoveredObject = hit;
        if (hoveredObject.material && hoveredObject.material.emissive) {
          hoveredObject.material.emissive.setHex(0x1e3a8a);
        }
      }
    } else {
      renderer3D.domElement.style.cursor = "grab";
      if (hoveredObject && hoveredObject.material && hoveredObject.material.emissive) {
        hoveredObject.material.emissive.setHex(0x000000);
      }
      hoveredObject = null;
    }
  }

  function on3DMouseClick(event) {
    const rect = renderer3D.domElement.getBoundingClientRect();
    mouse3D.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
    mouse3D.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;

    raycaster3D.setFromCamera(mouse3D, camera3D);
    const visibleTargets = interactiveObjects.filter(isObjectVisibleInHierarchy);
    const intersects = raycaster3D.intersectObjects(visibleTargets, false);

    if (intersects.length > 0) {
      const obj = intersects[0].object;
      const data = obj.userData || {};
      window.selected3DObject = obj;
      show3DTelemetryHUD(data);

      if (typeof selectNode === "function" && data.id) {
        selectNode(data.id);
      }
    }
  }

  window.sync3DSelectedEquipment = function(eqId) {
    if (!is3DInitialized || !interactiveObjects.length) return;
    const canon = String(eqId || "").replace(/^node_/, "");
    const match = interactiveObjects.find(obj => {
      if (!isObjectVisibleInHierarchy(obj) || !obj.userData) return false;
      const uid = String(obj.userData.id || "").replace(/^node_/, "");
      if (uid === canon) return true;
      if (canon === "boiler" && uid === "boiler_1") return true;
      if (canon === "superheater" && uid === "sh") return true;
      if (canon === "preheater" && uid === "ph") return true;
      return false;
    });
    if (match) {
      window.selected3DObject = match;
      show3DTelemetryHUD(match.userData);
    }
  };

  function show3DTelemetryHUD(data) {
    const hud = document.getElementById("hud_3d_card");
    const title = document.getElementById("hud_3d_title");
    const content = document.getElementById("hud_3d_content");
    if (!hud || !title || !content) return;

    title.innerText = data.name || "Ekipman Telemetrisi";

    let html = "";
    const res = window.latestCalcResult || {};

    if (data.type === "boiler") {
      const bIdx = data.boilerIndex || 1;
      const bData = (res.boilers && res.boilers[bIdx - 1]) ? res.boilers[bIdx - 1] : null;
      const qVal = bData ? bData.Q_kW.toFixed(1) : "2150.0";
      const tOut = bData ? bData.T_oil_out_C.toFixed(1) : "295.0";
      const mOil = bData ? bData.m_oil_kg_s.toFixed(2) : "16.0";
      const tFgOut = (bData && bData.T_flue_out_C) ? bData.T_flue_out_C.toFixed(1) : "210.0";
      const dpB = (bData && bData.dp_bar) ? bData.dp_bar.toFixed(2) : "0.35";
      html = `
        <div><b>Isıl Kapasite:</b> <span style="color:#ef4444;font-weight:700;">${qVal} kW</span></div>
        <div><b>Kızgın Yağ Çıkışı:</b> ${tOut} °C (ΔP: ${dpB} bar)</div>
        <div><b>Baca Gazı Çıkışı:</b> ${tFgOut} °C</div>
        <div><b>Yağ Kütlesel Debisi:</b> ${mOil} kg/s</div>
        <div><b>Borulama:</b> Ortogonal Riser & Flanşlı Çıkış</div>
        <div><b>Temel:</b> Pahlanmış Betonarme Kaide</div>
      `;
    } else if (data.type === "sh") {
      const shData = res.superheater || {};
      const qSH = shData.Q_kW !== undefined ? shData.Q_kW.toFixed(1) : "850.0";
      const tOilIn = shData.T_oil_in !== undefined ? shData.T_oil_in.toFixed(1) : "295.0";
      const tCpOut = shData.T_cp_out !== undefined ? shData.T_cp_out.toFixed(1) : "225.0";
      const fluidName = (res.orc && res.orc.fluid) ? res.orc.fluid : "Siklopentan";
      html = `
        <div><b>Isıl Görev:</b> <span style="color:#ef4444;font-weight:700;">${qSH} kW</span></div>
        <div><b>Kızgın Yağ Giriş:</b> ${tOilIn} °C</div>
        <div><b>${fluidName} Buhar Çıkış:</b> ${tCpOut} °C</div>
        <div><b>Bağlantı:</b> Termal Genleşme Lupu (U-Turn) ile Türbine</div>
        <div><b>Mesnet:</b> İkiz Çelik Semer & Beton Pabuç</div>
      `;
    } else if (data.type === "ph") {
      const phData = res.boiler || {};
      const qPH = phData.Q_kW !== undefined ? phData.Q_kW.toFixed(1) : "3450.0";
      const tOilOut = phData.T_oil_out !== undefined ? phData.T_oil_out.toFixed(1) : "205.0";
      const tSat = phData.T_sat !== undefined ? phData.T_sat.toFixed(1) : "175.0";
      html = `
        <div><b>Buharlaşma Yükü:</b> <span style="color:#f59e0b;font-weight:700;">${qPH} kW</span></div>
        <div><b>Kızgın Yağ Dönüş:</b> ${tOilOut} °C</div>
        <div><b>Doyma Sıcaklığı (T_sat):</b> ${tSat} °C</div>
        <div><b>TEMA Tipi:</b> Genişletilmiş Kubbeli Kettle Reboiler</div>
        <div><b>Mesnet:</b> İkiz Çelik Semer & Beton Pabuç</div>
      `;
    } else if (data.type === "turbine") {
      const turbData = res.turbine || {};
      const orcData = res.orc || {};
      const wNet = orcData.W_net_kW !== undefined ? orcData.W_net_kW.toFixed(1) : "720.0";
      const wEl = turbData.W_el_kW !== undefined ? turbData.W_el_kW.toFixed(1) : "765.0";
      const etaIs = turbData.eta_is !== undefined ? (turbData.eta_is * 100).toFixed(1) : "85.0";
      const dhIs = turbData.dh_is_kJ !== undefined ? turbData.dh_is_kJ.toFixed(1) : "84.2";
      const pr = turbData.pr !== undefined ? turbData.pr.toFixed(2) : "9.33";
      html = `
        <div><b>Net Elektrik Gücü:</b> <span style="color:#22c55e;font-weight:700;">${wNet} kW_e</span></div>
        <div><b>Türbin Brüt Üretim:</b> ${wEl} kW</div>
        <div><b>İzantropik Entalpi (Δh_is):</b> ${dhIs} kJ/kg (Basınç Oranı: ${pr})</div>
        <div><b>İzantropik Verim:</b> %${etaIs}</div>
        <div><b>Montaj:</b> Ortak Yapısal Çelik Şasi & Ağır Beton Kaide</div>
      `;
    } else if (data.type === "condenser") {
      const condData = res.condenser || {};
      const qCond = condData.Q_kW !== undefined ? condData.Q_kW.toFixed(1) : "3150.0";
      const isAir = condData.type ? (condData.type === "air" || condData.type === "acc" || condData.type === "hava") : (accGroup && accGroup.visible);
      if (isAir) {
        const pwrPar = condData.W_parasitic_kW !== undefined ? condData.W_parasitic_kW.toFixed(1) : "7.2";
        const tAirIn = condData.T_coolant_in_C !== undefined ? condData.T_coolant_in_C.toFixed(1) : "30.0";
        html = `
          <div><b>Isıl Kapasite:</b> <span style="color:#38bdf8;font-weight:700;">${qCond} kW</span></div>
          <div><b>Kondenser Tipi:</b> A-Frame Hava Soğutmalı Kondenser (ACC)</div>
          <div><b>Fan Düzeni:</b> 3 Adet Zorlamalı Çekme (Forced Draft) Fanı</div>
          <div><b>Fan Kanatları:</b> Her Biri 6 Kanatlı Aerodinamik Pervane</div>
          <div><b>Fan Güç Tüketimi:</b> ${pwrPar} kW (Parazitik)</div>
          <div><b>Çevre Havası Girişi:</b> ${tAirIn} °C</div>
          <div><b>Taşıyıcı Yapı:</b> Ağır Çelik Gantry & Çapraz Rüzgar Kirişleri</div>
          <div><b>Boru Bağlantısı:</b> Tepe Buhar Dağıtım Kollektörü & Taban Drenajı</div>
        `;
      } else {
        const mCw = condData.m_cw_kg_s !== undefined ? condData.m_cw_kg_s.toFixed(1) : "85.0";
        const tCwIn = condData.T_coolant_in_C !== undefined ? condData.T_coolant_in_C.toFixed(1) : "25.0";
        const pwrPar = condData.W_parasitic_kW !== undefined ? condData.W_parasitic_kW.toFixed(1) : "5.4";
        html = `
          <div><b>Isıl Kapasite:</b> <span style="color:#38bdf8;font-weight:700;">${qCond} kW</span></div>
          <div><b>Kondenser Tipi:</b> TEMA Gövde-Boru Yüzey Kondenseri (C-101)</div>
          <div><b>Soğutma Kulesi:</b> Mekanik Çekmeli Sulu Soğutma Kulesi (CT-101)</div>
          <div><b>Sirkülasyon Suyu (CW):</b> ${mCw} kg/s (Giriş: ${tCwIn} °C)</div>
          <div><b>Kule Fanı:</b> 1 Adet Üst Emişli Aksiyel Fan (Induced Draft)</div>
          <div><b>Toplam Parazitik Güç:</b> ${pwrPar} kW (Kule Fanı + Pompa)</div>
          <div><b>Kule Yapısı:</b> Betonarme Soğuk Su Havuzu & Dolgu Panjurları</div>
        `;
      }
    } else if (data.type === "pump") {
      const pumpData = res.pump_oil || {};
      const wP = pumpData.W_kW !== undefined ? pumpData.W_kW.toFixed(1) : "41.8";
      const dpP = pumpData.dp_bar !== undefined ? pumpData.dp_bar.toFixed(2) : "2.85";
      const mOil = pumpData.m_oil !== undefined ? pumpData.m_oil.toFixed(1) : "32.0";
      html = `
        <div><b>Pompa Güç Tüketimi:</b> <span style="color:#ef4444;font-weight:700;">${wP} kW</span></div>
        <div><b>Toplam Döngü Basınç Kaybı (ΔP):</b> ${dpP} bar</div>
        <div><b>Yağ Sirkülasyon Debisi:</b> ${mOil} kg/s</div>
        <div><b>Pompa Tipi:</b> Manyetik Kaplinli Santrifüj Kızgın Yağ Pompası</div>
      `;
    } else if (data.type === "cp_pump") {
      const cpPumpData = res.pump_cp || {};
      const wCp = cpPumpData.W_kW !== undefined ? cpPumpData.W_kW.toFixed(1) : "18.2";
      const dpCp = cpPumpData.dp_bar !== undefined ? cpPumpData.dp_bar.toFixed(1) : "12.0";
      const mCp = cpPumpData.m_cp !== undefined ? cpPumpData.m_cp.toFixed(2) : "11.5";
      html = `
        <div><b>Besleme Pompa Gücü:</b> <span style="color:#0284c7;font-weight:700;">${wCp} kW</span></div>
        <div><b>Basınç Farkı (ΔP):</b> ${dpCp} bar</div>
        <div><b>Siklopentan Debisi:</b> ${mCp} kg/s</div>
        <div><b>Pompa Tipi:</b> Çok Kademeli Santrifüj ORC Besleme Pompası (API 610)</div>
      `;
    } else if (data.type === "valve") {
      const vData = res.valve || {};
      const bPct = vData.bypass_pct !== undefined ? vData.bypass_pct.toFixed(0) : "0";
      const mByp = vData.m_bypass_kg_s !== undefined ? vData.m_bypass_kg_s.toFixed(1) : "0.0";
      const mAct = vData.m_active_kg_s !== undefined ? vData.m_active_kg_s.toFixed(1) : "32.0";
      html = `
        <div><b>By-Pass Açıklığı:</b> <span style="color:#d97706;font-weight:700;">%${bPct}</span></div>
        <div><b>By-Pass Yağ Debisi:</b> ${mByp} kg/s</div>
        <div><b>ORC Eşanjörlerine Giden:</b> ${mAct} kg/s</div>
        <div><b>Bağlantı:</b> 3. Port ➔ P-101 Pompa Emiş (Upstream) Hattı</div>
      `;
    } else {
      html = `<div><b>Durum:</b> Aktif İşletmede</div><div><b>Hattı:</b> Kapalı Devre Sirkülasyon</div>`;
    }

    content.innerHTML = html;
    hud.style.display = "block";
  }

  /* -------------------------------------------------------------------------
   * 8. Synchronization with 2D P&ID & Thermodynamic Solver
   * ------------------------------------------------------------------------- */
  window.sync3DBoilerCount = function(count) {
    const bCount = Math.max(1, Math.min(5, parseInt(count) || 2));
    window.currentBoilerCount = bCount;

    boilers3D.forEach((bGrp, idx) => {
      const isVisible = (idx < bCount);
      bGrp.visible = isVisible;
      if (plinths3D[idx]) plinths3D[idx].visible = isVisible;
      if (boilerRisers3D[idx]) boilerRisers3D[idx].visible = isVisible;
    });

    const lbl3D = document.getElementById("lbl_3d_whru_count");
    if (lbl3D) lbl3D.textContent = `🏭 WHRU: ${bCount} Kazan`;
  };

  window.change3DBoilerCount = function(delta) {
    if (typeof window.changeBoilerCount === "function") {
      window.changeBoilerCount(delta);
      return;
    }
    const nextCount = Math.max(1, Math.min(5, (window.currentBoilerCount || 2) + delta));
    window.sync3DBoilerCount(nextCount);
  };

  window.updatePlant3D = function(calcResult) {
    if (!calcResult) return;
    window.latestCalcResult = calcResult;
    const bCount = (calcResult.boilers && calcResult.boilers.length)
      ? calcResult.boilers.length
      : ((typeof calcResult.n_boilers === "number") ? calcResult.n_boilers : (window.currentBoilerCount || 2));
    window.currentBoilerCount = bCount;
    window.sync3DBoilerCount(bCount);
    if (!is3DInitialized) return;

    // Dynamic Condenser Specialization (ACC vs Water-Cooled Cooling Tower; Default: ACC / "air")
    const condType = (calcResult.condenser && calcResult.condenser.type) || calcResult.condenser_type || "air";
    const isAir = (condType === "air" || condType === "acc" || condType === "hava" || condType === "air_cooled");

    if (accGroup) accGroup.visible = isAir;
    if (waterCondenserGroup) waterCondenserGroup.visible = !isAir;
    if (accPipingGroup) accPipingGroup.visible = isAir;
    if (waterPipingGroup) waterPipingGroup.visible = !isAir;
    if (accParticles) accParticles.forEach(p => { p.system.visible = isAir; });
    if (waterParticles) waterParticles.forEach(p => { p.system.visible = !isAir; });

    const btn3DAir = document.getElementById("btn_3d_cond_air");
    const btn3DWater = document.getElementById("btn_3d_cond_water");
    if (btn3DAir) btn3DAir.style.borderColor = isAir ? "#38bdf8" : "rgba(71, 85, 105, 0.8)";
    if (btn3DWater) btn3DWater.style.borderColor = !isAir ? "#38bdf8" : "rgba(71, 85, 105, 0.8)";

    const activeHudObj = hoveredObject || window.selected3DObject;
    if (activeHudObj && activeHudObj.userData) {
      show3DTelemetryHUD(activeHudObj.userData);
    }
  };

  window.set3DCondenserType = function(type) {
    if (typeof window.setCondenserType === "function") {
      window.setCondenserType(type);
      return;
    }
    const prev = window.latestCalcResult || {};
    const next = Object.assign({}, prev, {
      condenser_type: type,
      condenser: Object.assign({}, prev.condenser || {}, { type: type })
    });
    window.updatePlant3D(next);
  };

  /* -------------------------------------------------------------------------
   * 9. Camera Presets & Navigation
   * ------------------------------------------------------------------------- */
  window.set3DCameraPreset = function(preset) {
    if (!camera3D || !controls3D) return;
    if (preset === "iso") {
      camera3D.position.set(0, 52, 90);
      controls3D.target.set(0, 10, 0);
    } else if (preset === "top") {
      camera3D.position.set(0, 130, 2);
      controls3D.target.set(0, 0, 0);
    } else if (preset === "front") {
      camera3D.position.set(0, 15, 100);
      controls3D.target.set(0, 10, 0);
    } else if (preset === "turbine") {
      camera3D.position.set(38, 16, 52);
      controls3D.target.set(38, 4, 32);
    } else if (preset === "condenser") {
      camera3D.position.set(-6, 20, 60);
      controls3D.target.set(-6, 6, 32);
    }
    controls3D.update();
  };

  window.reset3DCamera = function() {
    window.set3DCameraPreset("iso");
  };

  function on3DWindowResize() {
    const container = document.getElementById("canvas_3d_mount");
    if (!container || !renderer3D || !camera3D) return;
    const width = container.clientWidth || 800;
    const height = container.clientHeight || 600;
    camera3D.aspect = width / height;
    camera3D.updateProjectionMatrix();
    renderer3D.setSize(width, height);
  }

  // View Switcher (2D P&ID <-> 3D Digital Twin)
  window.switchViewMode = function(mode) {
    const svgEl = document.getElementById("schematic_svg");
    const container3D = document.getElementById("container_3d");
    const btn2D = document.getElementById("btn_view_2d");
    const btn3D = document.getElementById("btn_view_3d");

    if (mode === "3d") {
      if (svgEl) svgEl.style.display = "none";
      if (container3D) container3D.style.display = "block";
      if (btn2D) btn2D.classList.remove("active");
      if (btn3D) btn3D.classList.add("active");
      init3DPlant();
      start3DAnimation();
      on3DWindowResize();
      setTimeout(function() {
        on3DWindowResize();
      }, 50);
      if (typeof window.recalculate === "function") {
        window.recalculate();
      }
      if (window.latestCalcResult) {
        window.updatePlant3D(window.latestCalcResult);
      }
    } else {
      stop3DAnimation();
      if (svgEl) svgEl.style.display = "block";
      if (container3D) container3D.style.display = "none";
      if (btn2D) btn2D.classList.add("active");
      if (btn3D) btn3D.classList.remove("active");
    }
  };

  if (window.currentBoilerCount) {
    window.sync3DBoilerCount(window.currentBoilerCount);
  }
  if (window.latestCalcResult && typeof window.updatePlant3D === "function") {
    window.updatePlant3D(window.latestCalcResult);
  }
"""


def get_standalone_3d_plant_html(initial_data: dict[str, Any] | None = None) -> str:
    """Return self-contained HTML page rendering the 3D plant digital twin."""
    init_json = json.dumps(initial_data or {}, ensure_ascii=False).replace("</", "<\\/")
    container_html = get_orc_3d_plant_container_html()
    plant_js = get_orc_3d_plant_js()

    return f"""<!DOCTYPE html>
<html lang="tr">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>ORC & WHRU Endüstriyel Tesis 3D Dijital İkizi</title>
  <style>
    body {{ margin: 0; padding: 12px; background: #0f172a; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }}
    .btn-3d-cam {{
      padding: 5px 9px;
      font-size: 11.5px;
      font-weight: 700;
      color: #e2e8f0;
      background: rgba(30, 41, 59, 0.9);
      border: 1px solid rgba(71, 85, 105, 0.8);
      border-radius: 6px;
      cursor: pointer;
      transition: all 0.15s ease;
    }}
    .btn-3d-cam:hover {{
      background: #0284c7;
      color: #ffffff;
      border-color: #38bdf8;
    }}
  </style>
  <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/controls/OrbitControls.js"></script>
</head>
<body>
  {container_html}
  <script>
    const initialData = {init_json};
    {plant_js}
    document.addEventListener("DOMContentLoaded", function() {{
      const c = document.getElementById("container_3d");
      if (c) c.style.display = "block";
      init3DPlant();
    }});
  </script>
</body>
</html>"""
