"""Interactive SVG & Web Component for ORC & Thermal Oil Closed-Loop Plant Simulation.

Renders an interactive P&ID schematic with:
- Dynamic Scalable Waste Heat Recovery Boilers (1 to 5 Parallel WHRU Boilers)
- "+ WHRU Ekle" and "- WHRU Çıkar" controls & quick boiler count selectors (1..5)
- Hydraulic friction and manifold balancing calculations across all active boilers
- High-contrast Fluid Information Badges directly on/over fluid lines (Therminol 66, Cyclopentane, Flue gas, Cooling water)
- Cold oil distribution & hot oil collection manifolds
- Series Superheater + Preheater/Kettle Evaporator (Therminol 66 - Cyclopentane S&T)
- 3-Way Proportional Bypass Valve and Bypass Loop
- Thermal Oil Circulation Pump
- Cyclopentane ORC Power Loop (Turbine, Condenser, Feed Pump)
- Direct Click-to-Edit on equipment with synchronized slider & number inputs
- Real-time thermodynamic live updates
"""

import json


def get_orc_schematic_html(initial_data: dict | None = None) -> str:
    """Return self-contained HTML/CSS/JS for the interactive ORC plant schematic."""
    html_template = """<!DOCTYPE html>
<html lang="tr">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>ORC & Kızgın Yağ Canlı P&ID Şeması (1-5 Dinamik WHRU)</title>
  <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/controls/OrbitControls.js"></script>
  <style>
    :root {
      --bg: #f8fafc;
      --card: #ffffff;
      --border: #e2e8f0;
      --text: #0f172a;
      --muted: #64748b;
      --primary: #0f3a5d;
      --accent: #2563eb;
      --hot-red: #dc2626;
      --mid-orange: #ea580c;
      --ret-olive: #ca8a04;
      --cp-cyan: #0284c7;
      --cp-purple: #9333ea;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
    body { background: var(--bg); color: var(--text); padding: 12px; }
    .kpi-bar {
      display: grid;
      grid-template-columns: repeat(6, 1fr);
      gap: 10px;
      margin-bottom: 12px;
    }
    .kpi-card {
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 10px;
      box-shadow: 0 1px 3px rgba(0,0,0,0.04);
      text-align: center;
    }
    .kpi-title { font-size: 11.5px; text-transform: uppercase; color: #475569; font-weight: 700; letter-spacing: 0.2px; }
    .kpi-value { font-size: 20px; font-weight: 800; color: var(--primary); margin-top: 3px; }
    .kpi-sub { font-size: 11.5px; color: #64748b; font-weight: 500; margin-top: 2px; }

    .main-grid {
      display: grid;
      grid-template-columns: 1fr 390px;
      gap: 16px;
    }
    .schematic-box {
      background: #ffffff;
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 12px;
      box-shadow: 0 2px 10px rgba(0,0,0,0.04);
      position: relative;
    }
    .mode-bar {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 10px;
      background: #f1f5f9;
      padding: 8px 14px;
      border-radius: 8px;
      border: 1px solid #e2e8f0;
      flex-wrap: wrap;
      gap: 8px;
    }
    .mode-toggle-group {
      display: flex;
      gap: 6px;
      align-items: center;
      flex-wrap: wrap;
    }
    .btn-whru-action {
      padding: 5px 10px;
      font-size: 12px;
      font-weight: 700;
      border-radius: 6px;
      border: 1px solid #cbd5e1;
      cursor: pointer;
      transition: all 0.15s ease;
      display: inline-flex;
      align-items: center;
      gap: 4px;
    }
    .btn-whru-add {
      background: #ecfdf5;
      color: #065f46;
      border-color: #a7f3d0;
    }
    .btn-whru-add:hover {
      background: #10b981;
      color: #ffffff;
      border-color: #059669;
    }
    .btn-whru-del {
      background: #fef2f2;
      color: #991b1b;
      border-color: #fecaca;
    }
    .btn-whru-del:hover {
      background: #ef4444;
      color: #ffffff;
      border-color: #dc2626;
    }
    .mode-toggle-btn {
      padding: 5px 10px;
      font-size: 11.5px;
      font-weight: 700;
      border: 1px solid #cbd5e1;
      background: #ffffff;
      color: #334155;
      border-radius: 6px;
      cursor: pointer;
      transition: all 0.2s ease;
    }
    .mode-toggle-btn:hover {
      background: #e2e8f0;
    }
    .mode-toggle-btn.active {
      background: #0f3a5d;
      color: #ffffff;
      border-color: #0f3a5d;
      box-shadow: 0 1px 4px rgba(15, 58, 93, 0.25);
    }
    .btn-3d-cam {
      padding: 4px 8px;
      font-size: 11px;
      font-weight: 700;
      color: #e2e8f0;
      background: rgba(30, 41, 59, 0.9);
      border: 1px solid rgba(71, 85, 105, 0.8);
      border-radius: 5px;
      cursor: pointer;
      transition: all 0.15s ease;
    }
    .btn-3d-cam:hover {
      background: #0284c7;
      color: #ffffff;
      border-color: #38bdf8;
    }
    .badge-hydraulics {
      font-size: 11px;
      font-weight: 700;
      color: #1e293b;
      background: #ffffff;
      padding: 5px 10px;
      border-radius: 6px;
      border: 1px solid #cbd5e1;
    }

    .power-balance-bar {
      background: #f8fafc;
      border: 1px solid #cbd5e1;
      border-radius: 8px;
      padding: 8px 14px;
      margin-bottom: 12px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
      flex-wrap: wrap;
      box-shadow: 0 1px 3px rgba(0,0,0,0.03);
    }
    .pwr-item {
      display: flex;
      align-items: center;
      gap: 6px;
      font-size: 12px;
      font-weight: 600;
    }
    .pwr-label {
      color: #475569;
      font-size: 11.5px;
      font-weight: 700;
    }
    .pwr-val {
      font-size: 13.5px;
      font-weight: 800;
      color: #0f172a;
    }
    .pwr-sign {
      font-size: 16px;
      font-weight: 800;
      color: #94a3b8;
    }
    .pwr-group {
      display: flex;
      align-items: center;
      gap: 8px;
      flex-wrap: wrap;
    }
    .pwr-consume-total {
      color: #dc2626;
      margin-right: 4px;
    }
    .pwr-chips {
      display: flex;
      gap: 6px;
      align-items: center;
      flex-wrap: wrap;
    }
    .pwr-chip {
      display: inline-flex;
      align-items: center;
      gap: 4px;
      background: #ffffff;
      border: 1px solid #cbd5e1;
      border-radius: 5px;
      padding: 2px 7px;
      font-size: 11px;
      font-weight: 600;
      color: #334155;
      cursor: pointer;
      transition: all 0.15s ease;
    }
    .pwr-chip:hover {
      background: #e2e8f0;
      border-color: #94a3b8;
    }
    .pwr-chip b {
      color: #0f172a;
    }
    .pwr-net-val {
      color: #16a34a;
      font-size: 14.5px;
    }
    .mini-info-btn {
      background: transparent;
      border: none;
      cursor: pointer;
      font-size: 11.5px;
      padding: 0 2px;
      opacity: 0.75;
      transition: opacity 0.15s;
    }
    .mini-info-btn:hover {
      opacity: 1;
      transform: scale(1.15);
    }

    .inspector-box {
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 16px;
      box-shadow: 0 4px 14px rgba(0,0,0,0.05);
      display: flex;
      flex-direction: column;
      gap: 12px;
    }
    .inspector-header {
      border-bottom: 1px solid var(--border);
      padding-bottom: 10px;
    }
    .inspector-header h3 { font-size: 16px; color: var(--primary); display: flex; align-items: center; gap: 8px; font-weight: 800; }
    .inspector-header p { font-size: 12.5px; color: #475569; margin-top: 4px; line-height: 1.45; font-weight: 500; }

    .param-group {
      background: #f8fafc;
      border: 1px solid #e2e8f0;
      border-radius: 8px;
      padding: 10px 12px;
      margin-bottom: 10px;
      transition: all 0.15s ease;
    }
    .param-group:hover {
      border-color: #cbd5e1;
      background: #f1f5f9;
    }
    .param-group:focus-within {
      border-color: #2563eb;
      background: #ffffff;
      box-shadow: 0 0 0 2px rgba(37,99,235,0.15);
    }
    .param-title {
      font-size: 12.5px;
      font-weight: 700;
      color: #1e293b;
      margin-bottom: 6px;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }
    .param-controls-row {
      display: grid;
      grid-template-columns: 1fr 100px;
      gap: 10px;
      align-items: center;
    }
    .param-slider {
      width: 100%;
      height: 6px;
      accent-color: #2563eb;
      cursor: pointer;
    }
    .param-num-wrap {
      display: flex;
      align-items: center;
      background: #ffffff;
      border: 1px solid #cbd5e1;
      border-radius: 6px;
      padding: 3px 6px;
      box-shadow: inset 0 1px 2px rgba(0,0,0,0.04);
      transition: border-color 0.15s, box-shadow 0.15s;
    }
    .param-num-wrap:focus-within {
      border-color: #2563eb;
      box-shadow: 0 0 0 2px rgba(37,99,235,0.15);
    }
    .param-num-input {
      width: 100%;
      border: none;
      background: transparent;
      font-size: 13.5px;
      font-weight: 700;
      color: #0f172a;
      text-align: right;
      padding: 2px 2px;
      outline: none;
      -moz-appearance: textfield;
    }
    .param-num-input::-webkit-outer-spin-button,
    .param-num-input::-webkit-inner-spin-button {
      -webkit-appearance: none;
      margin: 0;
    }
    .param-unit-badge {
      font-size: 11.5px;
      font-weight: 700;
      color: #475569;
      margin-left: 4px;
      user-select: none;
      white-space: nowrap;
    }

    .equipment-node { cursor: pointer; transition: transform 0.15s ease, filter 0.15s ease; }
    .equipment-node:hover { filter: drop-shadow(0 0 6px rgba(37, 99, 235, 0.45)); }
    .equipment-node.active { filter: drop-shadow(0 0 8px rgba(220, 38, 38, 0.65)); }

    .pipe-line { fill: none; stroke-linecap: round; transition: stroke 0.3s ease, stroke-width 0.3s ease; }
    .pipe-flow {
      stroke-dasharray: 6, 8;
      animation: flowAnim 1.2s linear infinite;
    }
    @keyframes flowAnim {
      from { stroke-dashoffset: 28; }
      to { stroke-dashoffset: 0; }
    }

    .pipe-clickable {
      cursor: pointer;
      pointer-events: stroke;
      transition: stroke-width 0.15s ease, filter 0.15s ease, stroke 0.15s ease;
    }
    .pipe-clickable:hover {
      stroke-width: 8px !important;
      filter: drop-shadow(0 0 6px #0284c7) !important;
    }
    .pipe-clickable.active {
      stroke-width: 8.5px !important;
      stroke: #2563eb !important;
      filter: drop-shadow(0 0 10px #2563eb) !important;
    }

    .insp-section-header {
      font-size: 11px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.3px;
      padding: 5px 8px;
      border-radius: 4px;
      margin: 10px 0 6px 0;
      background: #f1f5f9;
      color: #0f3a5d;
      border-left: 3px solid #0284c7;
      display: flex;
      align-items: center;
      justify-content: space-between;
    }
    .insp-section-header.hot { border-left-color: #dc2626; color: #991b1b; background: #fef2f2; }
    .insp-section-header.oil { border-left-color: #ea580c; color: #9a3412; background: #fff7ed; }
    .insp-section-header.cold { border-left-color: #0284c7; color: #0369a1; background: #f0f9ff; }
    .insp-section-header.orc { border-left-color: #9333ea; color: #6b21a8; background: #faf5ff; }

    .param-select {
      width: 100%;
      padding: 6px 10px;
      background: #ffffff;
      border: 1px solid #cbd5e1;
      border-radius: 6px;
      font-size: 12px;
      font-weight: 600;
      color: #0f172a;
      outline: none;
      cursor: pointer;
      transition: border-color 0.15s ease;
    }
    .param-select:focus {
      border-color: #2563eb;
      box-shadow: 0 0 0 2px rgba(37,99,235,0.15);
    }

    .balance-warning-box {
      background: #fef2f2;
      border: 1px solid #fecaca;
      color: #991b1b;
      padding: 8px 10px;
      border-radius: 6px;
      font-size: 11px;
      line-height: 1.45;
      margin: 8px 0;
    }
    .btn-balance-action {
      margin-top: 6px;
      width: 100%;
      padding: 6px 10px;
      background: #ef4444;
      color: #ffffff;
      border: none;
      border-radius: 5px;
      font-size: 11px;
      font-weight: 700;
      cursor: pointer;
      transition: all 0.15s ease;
    }
    .btn-balance-action:hover {
      background: #dc2626;
    }

    .flue-gas-box {
      background: #f8fafc;
      border: 1px solid #e2e8f0;
      border-radius: 8px;
      padding: 10px;
      margin: 10px 0;
    }
    .flue-gas-preset-row {
      display: flex;
      gap: 6px;
      margin: 8px 0;
      flex-wrap: wrap;
    }
    .btn-preset {
      flex: 1 1 calc(50% - 6px);
      padding: 5px 8px;
      background: #ffffff;
      border: 1px solid #cbd5e1;
      border-radius: 5px;
      font-size: 11px;
      font-weight: 600;
      color: #334155;
      cursor: pointer;
      text-align: center;
      transition: all 0.15s ease;
    }
    .btn-preset:hover {
      background: #f1f5f9;
      border-color: #94a3b8;
    }
    .btn-preset.active {
      background: #fee2e2;
      border-color: #ef4444;
      color: #991b1b;
      font-weight: 700;
    }
    .basis-toggle-row {
      display: flex;
      gap: 6px;
      margin-bottom: 8px;
    }
    .btn-basis {
      flex: 1;
      padding: 4px 6px;
      background: #ffffff;
      border: 1px solid #cbd5e1;
      border-radius: 4px;
      font-size: 10.5px;
      font-weight: 600;
      color: #475569;
      cursor: pointer;
      transition: all 0.15s ease;
    }
    .btn-basis.active {
      background: #e0f2fe;
      border-color: #0284c7;
      color: #0369a1;
      font-weight: 700;
    }
    .flue-comp-grid {
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: 6px;
      margin: 8px 0;
    }
    .flue-comp-cell {
      background: #ffffff;
      border: 1px solid #e2e8f0;
      border-radius: 5px;
      padding: 4px 6px;
      display: flex;
      align-items: center;
      justify-content: space-between;
    }
    .flue-comp-label {
      font-size: 10.5px;
      font-weight: 600;
      color: #334155;
    }
    .flue-comp-input {
      width: 52px;
      padding: 3px 5px;
      font-size: 11px;
      text-align: right;
      border: 1px solid #cbd5e1;
      border-radius: 4px;
    }
    .badge-auto {
      background: #dcfce7;
      color: #166534;
      border: 1px solid #bbf7d0;
      padding: 2px 6px;
      border-radius: 4px;
      font-size: 10px;
      font-weight: 600;
    }
    .badge-manual {
      background: #fef3c7;
      color: #92400e;
      border: 1px solid #fde68a;
      padding: 2px 6px;
      border-radius: 4px;
      font-size: 10px;
      font-weight: 600;
    }

    .pipe-tab-group {
      display: flex;
      gap: 4px;
      margin-bottom: 10px;
      flex-wrap: wrap;
    }
    .pipe-tab-btn {
      flex: 1;
      min-width: 70px;
      padding: 5px 4px;
      font-size: 10.5px;
      font-weight: 700;
      border: 1px solid #cbd5e1;
      background: #ffffff;
      color: #475569;
      border-radius: 5px;
      cursor: pointer;
      text-align: center;
      transition: all 0.15s ease;
    }
    .pipe-tab-btn:hover { background: #f1f5f9; }
    .pipe-tab-btn.active {
      background: #0f3a5d;
      color: #ffffff;
      border-color: #0f3a5d;
    }

    .preset-btn-group {
      display: flex;
      flex-direction: column;
      gap: 6px;
      margin-top: 8px;
    }
    .preset-btn {
      width: 100%;
      padding: 8px 6px;
      border: 1px solid var(--border);
      background: #f8fafc;
      border-radius: 8px;
      font-size: 11px;
      font-weight: 600;
      color: #334155;
      cursor: pointer;
      transition: all 0.2s ease;
      box-shadow: 0 1px 2px rgba(0,0,0,0.03);
      text-align: center;
    }
    .preset-btn:hover {
      background: #0f3a5d;
      color: #ffffff;
      border-color: #0f3a5d;
      box-shadow: 0 2px 6px rgba(15, 58, 93, 0.2);
    }

    .whru2-element, .whru3-element, .whru4-element, .whru5-element {
      transition: opacity 0.3s ease, transform 0.3s ease;
    }

    /* Fluid Line Information Badges */
    .fluid-badge rect {
      fill: #ffffff;
      stroke-width: 1.2;
      filter: drop-shadow(0 1px 3px rgba(0,0,0,0.12));
    }
    .fluid-badge text {
      font-weight: 700;
      font-size: 10px;
    }

    /* KPI Info Buttons & Modal */
    .kpi-title-wrap {
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 5px;
    }
    .kpi-info-btn {
      background: none;
      border: none;
      cursor: pointer;
      font-size: 12px;
      color: #94a3b8;
      padding: 1px 3px;
      border-radius: 4px;
      line-height: 1;
      transition: all 0.15s ease;
    }
    .kpi-info-btn:hover {
      color: #0f172a;
      background: #e2e8f0;
      transform: scale(1.1);
    }
    .modal-backdrop {
      display: none;
      position: fixed;
      top: 0; left: 0; right: 0; bottom: 0;
      background: rgba(15, 23, 42, 0.6);
      z-index: 99999;
      align-items: center;
      justify-content: center;
      padding: 16px;
      backdrop-filter: blur(2px);
    }
    .modal-content {
      background: #ffffff;
      border-radius: 12px;
      box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.25);
      max-width: 540px;
      width: 100%;
      border: 1px solid #cbd5e1;
      overflow: hidden;
      animation: modalFadeIn 0.18s ease-out;
    }
    @keyframes modalFadeIn {
      from { opacity: 0; transform: scale(0.96); }
      to { opacity: 1; transform: scale(1.0); }
    }
    .modal-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 14px 18px;
      border-bottom: 1px solid #e2e8f0;
      background: #f8fafc;
    }
    .modal-close {
      background: none;
      border: none;
      font-size: 22px;
      line-height: 1;
      cursor: pointer;
      color: #64748b;
      padding: 2px 6px;
      border-radius: 4px;
    }
    .modal-close:hover {
      color: #0f172a;
      background: #e2e8f0;
    }
    .modal-body {
      padding: 18px 20px;
      font-size: 13px;
      line-height: 1.6;
      color: #334155;
    }
    .modal-formula {
      background: #f1f5f9;
      padding: 9px 13px;
      border-radius: 6px;
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
      font-size: 12px;
      color: #0f3a5d;
      margin: 8px 0 12px 0;
      border-left: 3px solid #2563eb;
    }
  </style>
</head>
<body>

  <!-- Top KPI Dashboard -->
  <div class="kpi-bar">
    <div class="kpi-card" style="border-top: 3px solid #dc2626;">
      <div class="kpi-title kpi-title-wrap">
        <span>🔥 Toplam Kazan Yükü</span>
        <button class="kpi-info-btn" onclick="showKpiInfo('q_boiler')" title="Hesaplama formülü ve mühendislik detayı">ℹ️</button>
      </div>
      <div class="kpi-value" id="kpi_q_boiler">4,280 kW</div>
      <div class="kpi-sub" id="kpi_boiler_sub">2 Kazan (Paralel)</div>
    </div>
    <div class="kpi-card" style="border-top: 3px solid #16a34a;">
      <div class="kpi-title kpi-title-wrap">
        <span>⚡ Net ORC Gücü</span>
        <button class="kpi-info-btn" onclick="showKpiInfo('w_net')" title="Hesaplama formülü ve mühendislik detayı">ℹ️</button>
      </div>
      <div class="kpi-value" id="kpi_w_net" style="color:#16a34a;">765 kW</div>
      <div class="kpi-sub" id="kpi_w_net_sub">Brüt: 832 kW | İç Tüketim: 67 kW</div>
    </div>
    <div class="kpi-card" style="border-top: 3px solid #ea580c;">
      <div class="kpi-title kpi-title-wrap">
        <span>🔄 ORC Isı Girişi</span>
        <button class="kpi-info-btn" onclick="showKpiInfo('q_orc')" title="Hesaplama formülü ve mühendislik detayı">ℹ️</button>
      </div>
      <div class="kpi-value" id="kpi_q_orc">3,950 kW</div>
      <div class="kpi-sub">Süperheater + Evaporatör</div>
    </div>
    <div class="kpi-card" style="border-top: 3px solid #9333ea;">
      <div class="kpi-title kpi-title-wrap">
        <span>📊 Tesis Isıl Verimi</span>
        <button class="kpi-info-btn" onclick="showKpiInfo('plant_eff')" title="Hesaplama formülü ve mühendislik detayı">ℹ️</button>
      </div>
      <div class="kpi-value" id="kpi_plant_eff">%17.9</div>
      <div class="kpi-sub">Net Elektrik / Toplam Q</div>
    </div>
    <div class="kpi-card" style="border-top: 3px solid #d97706;">
      <div class="kpi-title kpi-title-wrap">
        <span>🔀 By-Pass Durumu</span>
        <button class="kpi-info-btn" onclick="showKpiInfo('bypass')" title="Hesaplama formülü ve mühendislik detayı">ℹ️</button>
      </div>
      <div class="kpi-value" id="kpi_bypass" style="color:#d97706;">%0 (Kapalı)</div>
      <div class="kpi-sub" id="kpi_bypass_flow">0.0 kg/s yağı by-pass</div>
    </div>
    <div class="kpi-card" id="card_pinch" style="border-top: 3px solid #0284c7;">
      <div class="kpi-title kpi-title-wrap">
        <span>📐 Pinch Yaklaşımı (ΔT)</span>
        <button class="kpi-info-btn" onclick="showKpiInfo('pinch')" title="Hesaplama formülü ve mühendislik detayı">ℹ️</button>
      </div>
      <div class="kpi-value" id="kpi_pinch" style="color:#0284c7;">50.7 °C</div>
      <div class="kpi-sub" id="kpi_pinch_sub">✅ Normal / Güvenli</div>
    </div>
  </div>

  <!-- Electrical Power & Parasitic Consumption Balance Strip -->
  <div class="power-balance-bar">
    <div class="pwr-item pwr-gross">
      <span class="pwr-label">⚡ Brüt Türbin Üretimi (W_türbin):</span>
      <b class="pwr-val" id="pwr_w_turb">832 kW</b>
      <button class="mini-info-btn" onclick="showKpiInfo('w_turb')" title="Türbin brüt üretim hesaplama formülü">ℹ️</button>
    </div>
    <div class="pwr-sign">−</div>
    <div class="pwr-group">
      <span class="pwr-label" style="color:#b91c1c;">🔌 Toplam İç Tüketim:</span>
      <b class="pwr-val pwr-consume-total" id="pwr_w_parasitic_total">67.2 kW</b>
      <div class="pwr-chips">
        <span class="pwr-chip" onclick="showKpiInfo('pump_oil_power')" title="Kızgın yağ sirkülasyon pompası tüketimi ve formülü">
          🔄 Yağ Pompası: <b id="pwr_w_oil_pump">41.8 kW</b> <button class="mini-info-btn" onclick="showKpiInfo('pump_oil_power'); event.stopPropagation();">ℹ️</button>
        </span>
        <span class="pwr-chip" onclick="showKpiInfo('cp_pump_power')" title="Siklopentan sıvı besleme pompası tüketimi ve formülü">
          💧 CP Besleme Pompası: <b id="pwr_w_cp_pump">18.2 kW</b> <button class="mini-info-btn" onclick="showKpiInfo('cp_pump_power'); event.stopPropagation();">ℹ️</button>
        </span>
        <span class="pwr-chip" onclick="showKpiInfo('cond_power')" title="Kondenser aksiyal fan veya kule pompası tüketimi">
          <span id="pwr_lbl_cond_type">💨 ACC Fanı:</span> <b id="pwr_w_cond">7.2 kW</b> <button class="mini-info-btn" onclick="showKpiInfo('cond_power'); event.stopPropagation();">ℹ️</button>
        </span>
      </div>
    </div>
    <div class="pwr-sign">=</div>
    <div class="pwr-item pwr-net">
      <span class="pwr-label" style="color:#15803d;">⚡ Net Tesis Gücü (W_net):</span>
      <b class="pwr-val pwr-net-val" id="pwr_w_net">765 kW</b>
      <button class="mini-info-btn" onclick="showKpiInfo('w_net')" title="Net güç formülü">ℹ️</button>
    </div>
  </div>

  <!-- KPI Info Modal Dialog -->
  <div id="kpi_modal" class="modal-backdrop" onclick="closeKpiModal(event)">
    <div class="modal-content" onclick="event.stopPropagation()">
      <div class="modal-header">
        <h3 id="modal_title" style="font-size:15px; font-weight:700; color:#0f172a; margin:0;">Hesaplama Detayı</h3>
        <button class="modal-close" onclick="closeKpiModal()">&times;</button>
      </div>
      <div id="modal_body" class="modal-body"></div>
    </div>
  </div>

  <div class="main-grid">
    <!-- SVG Interactive Schematic Canvas (1520 x 620 Expanded ViewBox) -->
    <div class="schematic-box">
      <!-- Mode & WHRU Scaler Bar -->
      <div class="mode-bar">
        <div class="mode-toggle-group">
          <!-- View Switcher (2D P&ID <-> 3D Digital Twin) -->
          <div style="display: flex; gap: 4px; margin-right: 10px; background: #e2e8f0; padding: 2px 4px; border-radius: 7px;">
            <button id="btn_view_2d" class="mode-toggle-btn active" style="font-size: 11.5px; padding: 4px 9px;" onclick="switchViewMode('2d')">📐 2D P&ID Şema</button>
            <button id="btn_view_3d" class="mode-toggle-btn" style="font-size: 11.5px; padding: 4px 9px;" onclick="switchViewMode('3d')">🌐 3D Dijital İkiz</button>
          </div>

          <span style="font-size: 12px; font-weight: 700; color: #1e293b;">🏭 Atık Isı Kazanları (WHRU):</span>
          <button id="btn_remove_whru" class="btn-whru-action btn-whru-del" onclick="changeBoilerCount(-1)" title="Bir kazan eksilt">➖ WHRU Çıkar</button>
          <button id="btn_add_whru" class="btn-whru-action btn-whru-add" onclick="changeBoilerCount(1)" title="Bir kazan ekle">➕ WHRU Ekle</button>
          <span style="font-size: 11px; color:#64748b; margin: 0 4px;">|</span>
          <button id="btn_mode_single" class="mode-toggle-btn" onclick="setBoilerCount(1)">1</button>
          <button id="btn_mode_dual" class="mode-toggle-btn active" onclick="setBoilerCount(2)">2</button>
          <button id="btn_mode_3" class="mode-toggle-btn" onclick="setBoilerCount(3)">3</button>
          <button id="btn_mode_4" class="mode-toggle-btn" onclick="setBoilerCount(4)">4</button>
          <button id="btn_mode_5" class="mode-toggle-btn" onclick="setBoilerCount(5)">5</button>
          <span id="lbl_whru_count" style="font-size: 11.5px; font-weight: 700; color: #0f3a5d; margin-left: 6px;">(2 Adet Aktif)</span>
          <span style="font-size: 11px; color:#64748b; margin: 0 6px;">|</span>
          <span style="font-size: 11.5px; font-weight: 700; color: #1e293b;">❄️ Kondenser:</span>
          <button id="btn_cond_mode_air" class="mode-toggle-btn active" style="font-size: 11px; padding: 3px 8px;" onclick="setCondenserType('air')" title="Hava Soğutmalı Kondenser (A-Frame ACC)">💨 ACC (Hava)</button>
          <button id="btn_cond_mode_water" class="mode-toggle-btn" style="font-size: 11px; padding: 3px 8px;" onclick="setCondenserType('water')" title="Su Soğutmalı Yüzey Kondenseri & Soğutma Kulesi">💧 Kule (Su)</button>
        </div>
        <div style="display: flex; align-items: center; gap: 8px;">
          <div id="badge_hydraulics" class="badge-hydraulics">
            ⚖️ Hidrolik: Dengeli (ΔP = 0.35 bar)
          </div>
          <button id="btn_export_json" class="btn-whru-action" style="background:#0284c7; color:#ffffff; border-color:#0284c7; font-weight:600; padding:4px 9px; font-size:11.5px; border-radius:6px; cursor:pointer;" onclick="exportSimulationJSON()" title="Mevcut tesis ve simülasyon parametrelerini JSON veri paketi olarak indir">
            📥 JSON İndir
          </button>
        </div>
      </div>

      <svg id="schematic_svg" viewBox="0 0 1520 620" style="width: 100%; height: auto;">
        <defs>
          <linearGradient id="gradBoiler1" x1="0" y1="0" x2="1" y2="1"><stop offset="0%" stop-color="#fee2e2"/><stop offset="100%" stop-color="#fecaca"/></linearGradient>
          <linearGradient id="gradBoiler2" x1="0" y1="0" x2="1" y2="1"><stop offset="0%" stop-color="#ffedd5"/><stop offset="100%" stop-color="#fed7aa"/></linearGradient>
          <linearGradient id="gradBoiler3" x1="0" y1="0" x2="1" y2="1"><stop offset="0%" stop-color="#fef3c7"/><stop offset="100%" stop-color="#fde68a"/></linearGradient>
          <linearGradient id="gradBoiler4" x1="0" y1="0" x2="1" y2="1"><stop offset="0%" stop-color="#e0e7ff"/><stop offset="100%" stop-color="#c7d2fe"/></linearGradient>
          <linearGradient id="gradBoiler5" x1="0" y1="0" x2="1" y2="1"><stop offset="0%" stop-color="#f3e8ff"/><stop offset="100%" stop-color="#e9d5ff"/></linearGradient>
          <linearGradient id="gradSH" x1="0" y1="0" x2="1" y2="1"><stop offset="0%" stop-color="#ffedd5"/><stop offset="100%" stop-color="#fed7aa"/></linearGradient>
          <linearGradient id="gradPH" x1="0" y1="0" x2="1" y2="1"><stop offset="0%" stop-color="#fef9c3"/><stop offset="100%" stop-color="#fef08a"/></linearGradient>
          <linearGradient id="gradPump" x1="0" y1="0" x2="1" y2="1"><stop offset="0%" stop-color="#e2e8f0"/><stop offset="100%" stop-color="#cbd5e1"/></linearGradient>
          <linearGradient id="gradCond" x1="0" y1="0" x2="1" y2="1"><stop offset="0%" stop-color="#e0f2fe"/><stop offset="100%" stop-color="#bae6fd"/></linearGradient>
          <linearGradient id="gradCPPump" x1="0" y1="0" x2="1" y2="1"><stop offset="0%" stop-color="#ede9fe"/><stop offset="100%" stop-color="#ddd6fe"/></linearGradient>
          <filter id="shadow" x="-5%" y="-5%" width="110%" height="110%">
            <feDropShadow dx="0" dy="2" stdDeviation="2" flood-opacity="0.12"/>
          </filter>
        </defs>

        <!-- ================= PIPELINES (Background Layer) ================= -->

        <!-- 1. Flue Gas Ducts for Boilers 1..5 -->
        <!-- WHRU-1 Ducts -->
        <g id="duct_fg1">
          <path d="M 40 45 L 105 45 L 105 105" stroke="#475569" stroke-width="7" fill="none"/>
          <path d="M 105 245 L 105 315 L 40 315" stroke="#64748b" stroke-width="7" fill="none"/>
        </g>
        <!-- WHRU-2 Ducts (Dynamic) -->
        <g id="duct_fg2" class="whru2-element">
          <path d="M 155 45 L 215 45 L 215 105" stroke="#ea580c" stroke-width="7" fill="none"/>
          <path d="M 215 245 L 215 315 L 155 315" stroke="#64748b" stroke-width="7" fill="none"/>
        </g>
        <!-- WHRU-3 Ducts (Dynamic) -->
        <g id="duct_fg3" class="whru3-element">
          <path d="M 270 45 L 325 45 L 325 105" stroke="#d97706" stroke-width="7" fill="none"/>
          <path d="M 325 245 L 325 315 L 270 315" stroke="#64748b" stroke-width="7" fill="none"/>
        </g>
        <!-- WHRU-4 Ducts (Dynamic) -->
        <g id="duct_fg4" class="whru4-element">
          <path d="M 380 45 L 435 45 L 435 105" stroke="#4338ca" stroke-width="7" fill="none"/>
          <path d="M 435 245 L 435 315 L 380 315" stroke="#64748b" stroke-width="7" fill="none"/>
        </g>
        <!-- WHRU-5 Ducts (Dynamic) -->
        <g id="duct_fg5" class="whru5-element">
          <path d="M 490 45 L 545 45 L 545 105" stroke="#7e22ce" stroke-width="7" fill="none"/>
          <path d="M 545 245 L 545 315 L 490 315" stroke="#64748b" stroke-width="7" fill="none"/>
        </g>

        <!-- 2. Cold Oil Distribution Manifold: Pump -> Bottom Header -> Boilers 1..5 -->
        <!-- Main pump vertical rise to header at y=275 -->
        <path id="pipe_pump_rise" d="M 320 420 L 320 275" stroke="#854d0e" stroke-width="6" class="pipe-line pipe-clickable pipe-bin" onclick="selectEquipment('pipe_boiler_inlet')" title="Kazan Dağıtım Hattı (Tıkla & Düzenle)"/>
        <path id="pipe_pump_rise_flow" d="M 320 420 L 320 275" stroke="#ffffff" stroke-width="2" class="pipe-line pipe-flow pipe-clickable pipe-bin" onclick="selectEquipment('pipe_boiler_inlet')"/>

        <!-- Common bottom distribution header from WHRU-1 to pump -->
        <path id="pipe_cold_header_base" d="M 135 275 L 320 275" stroke="#854d0e" stroke-width="6" class="pipe-line pipe-clickable pipe-bin" onclick="selectEquipment('pipe_boiler_inlet')" title="Kazan Dağıtım Hattı (Tıkla & Düzenle)"/>
        <path id="pipe_cold_header_base_flow" d="M 320 275 L 135 275" stroke="#ffffff" stroke-width="2" class="pipe-line pipe-flow pipe-clickable pipe-bin" onclick="selectEquipment('pipe_boiler_inlet')"/>
        <path id="pipe_cold_manifold" d="M 135 275 L 320 275" stroke="none" fill="none" opacity="0"/>

        <!-- WHRU-1 Cold Riser -->
        <g id="pipe_cold_b1_group" class="pipe-clickable pipe-bin" onclick="selectEquipment('pipe_boiler_inlet')">
          <path d="M 135 275 L 135 245" stroke="#854d0e" stroke-width="5" class="pipe-line"/>
          <path d="M 135 275 L 135 245" stroke="#ffffff" stroke-width="2" class="pipe-line pipe-flow"/>
          <circle cx="135" cy="275" r="4.5" fill="#854d0e" stroke="#ffffff" stroke-width="1.5"/>
        </g>

        <!-- WHRU-2 Cold Riser (Dynamic) -->
        <g id="pipe_cold_b2_group" class="whru2-element pipe-clickable pipe-bin" onclick="selectEquipment('pipe_boiler_inlet')">
          <path d="M 245 275 L 245 245" stroke="#854d0e" stroke-width="5" class="pipe-line"/>
          <path d="M 245 275 L 245 245" stroke="#ffffff" stroke-width="2" class="pipe-line pipe-flow"/>
          <circle cx="245" cy="275" r="4.5" fill="#854d0e" stroke="#ffffff" stroke-width="1.5"/>
        </g>

        <!-- WHRU-3 Cold Header Extension & Riser (Dynamic) -->
        <g id="pipe_cold_b3_group" class="whru3-element pipe-clickable pipe-bin" onclick="selectEquipment('pipe_boiler_inlet')">
          <path d="M 320 275 L 355 275 L 355 245" stroke="#854d0e" stroke-width="5" class="pipe-line"/>
          <path d="M 320 275 L 355 275 L 355 245" stroke="#ffffff" stroke-width="2" class="pipe-line pipe-flow"/>
          <circle cx="355" cy="275" r="4.5" fill="#854d0e" stroke="#ffffff" stroke-width="1.5"/>
        </g>

        <!-- WHRU-4 Cold Header Extension & Riser (Dynamic) -->
        <g id="pipe_cold_b4_group" class="whru4-element pipe-clickable pipe-bin" onclick="selectEquipment('pipe_boiler_inlet')">
          <path d="M 355 275 L 465 275 L 465 245" stroke="#854d0e" stroke-width="5" class="pipe-line"/>
          <path d="M 355 275 L 465 275 L 465 245" stroke="#ffffff" stroke-width="2" class="pipe-line pipe-flow"/>
          <circle cx="465" cy="275" r="4.5" fill="#854d0e" stroke="#ffffff" stroke-width="1.5"/>
        </g>

        <!-- WHRU-5 Cold Header Extension & Riser (Dynamic) -->
        <g id="pipe_cold_b5_group" class="whru5-element pipe-clickable pipe-bin" onclick="selectEquipment('pipe_boiler_inlet')">
          <path d="M 465 275 L 575 275 L 575 245" stroke="#854d0e" stroke-width="5" class="pipe-line"/>
          <path d="M 465 275 L 575 275 L 575 245" stroke="#ffffff" stroke-width="2" class="pipe-line pipe-flow"/>
          <circle cx="575" cy="275" r="4.5" fill="#854d0e" stroke="#ffffff" stroke-width="1.5"/>
        </g>

        <!-- 3. Hot Oil Collection Manifold: Boiler Outlets -> Top Header (y=80) -> 3-Way Valve -->
        <!-- WHRU-1 Hot Riser & Base Top Header -->
        <g id="pipe_hot_b1_group" class="pipe-clickable pipe-sup" onclick="selectEquipment('pipe_supply')" title="Kızgın Yağ Sıcak Besleme Hattı (Tıkla & Düzenle)">
          <path id="pipe_oil_sup_b1" d="M 135 105 L 135 80" stroke="#dc2626" stroke-width="5" class="pipe-line"/>
          <path d="M 135 105 L 135 80" stroke="#ffffff" stroke-width="2" class="pipe-line pipe-flow"/>
          <circle cx="135" cy="80" r="4.5" fill="#dc2626" stroke="#ffffff" stroke-width="1.5"/>
          <path id="pipe_oil_sup_manifold" d="M 135 80 L 680 80 L 680 140 L 700 140" stroke="#dc2626" stroke-width="6" class="pipe-line"/>
          <path id="pipe_oil_sup_manifold_flow" d="M 135 80 L 680 80 L 680 140 L 700 140" stroke="#ffffff" stroke-width="2" class="pipe-line pipe-flow"/>
        </g>

        <!-- WHRU-2 Hot Riser (Dynamic) -->
        <g id="pipe_hot_b2_group" class="whru2-element pipe-clickable pipe-sup" onclick="selectEquipment('pipe_supply')">
          <path d="M 245 105 L 245 80" stroke="#dc2626" stroke-width="5" class="pipe-line"/>
          <path d="M 245 105 L 245 80" stroke="#ffffff" stroke-width="2" class="pipe-line pipe-flow"/>
          <circle cx="245" cy="80" r="4.5" fill="#dc2626" stroke="#ffffff" stroke-width="1.5"/>
        </g>

        <!-- WHRU-3 Hot Riser (Dynamic) -->
        <g id="pipe_hot_b3_group" class="whru3-element pipe-clickable pipe-sup" onclick="selectEquipment('pipe_supply')">
          <path d="M 355 105 L 355 80" stroke="#dc2626" stroke-width="5" class="pipe-line"/>
          <path d="M 355 105 L 355 80" stroke="#ffffff" stroke-width="2" class="pipe-line pipe-flow"/>
          <circle cx="355" cy="80" r="4.5" fill="#dc2626" stroke="#ffffff" stroke-width="1.5"/>
        </g>

        <!-- WHRU-4 Hot Riser (Dynamic) -->
        <g id="pipe_hot_b4_group" class="whru4-element pipe-clickable pipe-sup" onclick="selectEquipment('pipe_supply')">
          <path d="M 465 105 L 465 80" stroke="#dc2626" stroke-width="5" class="pipe-line"/>
          <path d="M 465 105 L 465 80" stroke="#ffffff" stroke-width="2" class="pipe-line pipe-flow"/>
          <circle cx="465" cy="80" r="4.5" fill="#dc2626" stroke="#ffffff" stroke-width="1.5"/>
        </g>

        <!-- WHRU-5 Hot Riser (Dynamic) -->
        <g id="pipe_hot_b5_group" class="whru5-element pipe-clickable pipe-sup" onclick="selectEquipment('pipe_supply')">
          <path d="M 575 105 L 575 80" stroke="#dc2626" stroke-width="5" class="pipe-line"/>
          <path d="M 575 105 L 575 80" stroke="#ffffff" stroke-width="2" class="pipe-line pipe-flow"/>
          <circle cx="575" cy="80" r="4.5" fill="#dc2626" stroke="#ffffff" stroke-width="1.5"/>
        </g>

        <!-- 4. 3-Way Valve straight outlet to Superheater Shell Inlet (Top Nozzle) -->
        <path id="pipe_oil_to_sh" d="M 740 140 L 780 140 L 780 75 L 890 75 L 890 90" stroke="#dc2626" stroke-width="5" class="pipe-line pipe-clickable pipe-sup" onclick="selectEquipment('pipe_supply')" title="Kızgın Yağ Besleme Hattı (Tıkla & Düzenle)"/>
        <path id="pipe_oil_to_sh_flow" d="M 740 140 L 780 140 L 780 75 L 890 75 L 890 90" stroke="#ffffff" stroke-width="2" class="pipe-line pipe-flow pipe-clickable pipe-sup" onclick="selectEquipment('pipe_supply')"/>

        <!-- 5. 3-Way Valve By-Pass Line downward to mixer -->
        <path id="pipe_bypass" d="M 720 160 L 720 460 L 820 460" stroke="#f59e0b" stroke-width="4" stroke-dasharray="4,4" class="pipe-line pipe-clickable pipe-byp" onclick="selectEquipment('pipe_bypass')" title="By-Pass Hattı (Tıkla & Düzenle)"/>

        <!-- 6. Series Intermediate Oil Line: Superheater Bottom Shell Outlet -> Preheater U-Tube Inlet -->
        <path id="pipe_oil_mid" d="M 980 185 L 980 280" stroke="#ea580c" stroke-width="5" class="pipe-line"/>
        <path id="pipe_oil_mid_flow" d="M 980 185 L 980 280" stroke="#ffffff" stroke-width="2" class="pipe-line pipe-flow"/>

        <!-- 7. Oil Return from Preheater to Mixer -->
        <path id="pipe_oil_ret" d="M 860 350 L 820 350 L 820 460" stroke="#ca8a04" stroke-width="5" class="pipe-line pipe-clickable pipe-ret" onclick="selectEquipment('pipe_return')" title="Kızgın Yağ Dönüş / Emiş Hattı (Tıkla & Düzenle)"/>
        <path id="pipe_oil_ret_flow" d="M 860 350 L 820 350 L 820 460" stroke="#ffffff" stroke-width="2" class="pipe-line pipe-flow pipe-clickable pipe-ret" onclick="selectEquipment('pipe_return')"/>

        <!-- 8. Mixed Oil from Mixer back to Circulation Pump -->
        <path id="pipe_mixed_to_pump" d="M 820 460 L 350 460 L 350 450" stroke="#854d0e" stroke-width="5" class="pipe-line pipe-clickable pipe-ret" onclick="selectEquipment('pipe_return')" title="Kızgın Yağ Dönüş / Emiş Hattı (Tıkla & Düzenle)"/>
        <path id="pipe_mixed_to_pump_flow" d="M 820 460 L 350 460 L 350 450" stroke="#ffffff" stroke-width="2" class="pipe-line pipe-flow pipe-clickable pipe-ret" onclick="selectEquipment('pipe_return')"/>

        <!-- 9. Cyclopentane Closed Loop Lines -->
        <!-- Saturated vapor from Kettle Reboiler Dome to Superheater -->
        <path id="pipe_cp_vap" d="M 935 260 L 935 220 L 830 220 L 830 138 L 860 138" stroke="#9333ea" stroke-width="5" class="pipe-line"/>
        <path id="pipe_cp_vap_flow" d="M 935 260 L 935 220 L 830 220 L 830 138 L 860 138" stroke="#ffffff" stroke-width="1.8" class="pipe-line pipe-flow"/>

        <!-- Superheated vapor from Superheater to Turbine -->
        <path id="pipe_cp_sup" d="M 1010 138 L 1180 138" stroke="#c026d3" stroke-width="5" class="pipe-line"/>
        <path id="pipe_cp_sup_flow" d="M 1010 138 L 1180 138" stroke="#ffffff" stroke-width="1.8" class="pipe-line pipe-flow"/>

        <!-- Turbine exhaust low pressure vapor to Condenser -->
        <path id="pipe_turb_to_cond" d="M 1215 180 L 1215 230" stroke="#a855f7" stroke-width="4.5" class="pipe-line"/>
        <path id="pipe_turb_to_cond_flow" d="M 1215 180 L 1215 230" stroke="#ffffff" stroke-width="1.5" class="pipe-line pipe-flow"/>

        <!-- Condenser liquid outlet to Feed Pump -->
        <path id="pipe_cond_to_pump" d="M 1215 315 L 1215 350" stroke="#0284c7" stroke-width="4.5" class="pipe-line"/>
        <path id="pipe_cond_to_pump_flow" d="M 1215 315 L 1215 350" stroke="#ffffff" stroke-width="1.5" class="pipe-line pipe-flow"/>

        <!-- High pressure liquid feed from Feed Pump to Preheater -->
        <path id="pipe_cp_to_ph" d="M 1200 370 L 1050 370 L 1050 350 L 1010 350" stroke="#0284c7" stroke-width="4.5" class="pipe-line"/>
        <path id="pipe_cp_to_ph_flow" d="M 1200 370 L 1050 370 L 1050 350 L 1010 350" stroke="#ffffff" stroke-width="1.5" class="pipe-line pipe-flow"/>

        <!-- ================= EQUIPMENT NODES ================= -->

        <!-- 1. WHRU-1 -->
        <g id="node_boiler_1" class="equipment-node" onclick="selectEquipment('boiler_1')">
          <rect x="50" y="105" width="100" height="140" rx="8" fill="url(#gradBoiler1)" stroke="#dc2626" stroke-width="2.2" filter="url(#shadow)"/>
          <text x="100" y="128" text-anchor="middle" font-size="11.5" font-weight="700" fill="#991b1b">🔥 WHRU-1</text>
          <text x="100" y="142" text-anchor="middle" font-size="9" font-weight="600" fill="#7f1d1d">WHRU / Serpantini 1</text>
          <path d="M 68 158 L 132 158 A 5 5 0 0 1 132 168 L 74 168 A 5 5 0 0 0 74 178 L 132 178 A 5 5 0 0 1 132 188 L 74 188 A 5 5 0 0 0 74 198 L 132 198" fill="none" stroke="#dc2626" stroke-width="2.2" stroke-linecap="round"/>
          <rect x="58" y="214" width="84" height="20" rx="4" fill="#ffffff" fill-opacity="0.95" stroke="#dc2626" stroke-width="1.2"/>
          <text id="lbl_boiler1_q" x="100" y="228" text-anchor="middle" font-size="10.5" font-weight="700" fill="#b91c1c">Q1 = 2,140 kW</text>
        </g>

        <!-- 2. WHRU-2 (Dynamic) -->
        <g id="node_boiler_2" class="equipment-node whru2-element" onclick="selectEquipment('boiler_2')">
          <rect x="160" y="105" width="100" height="140" rx="8" fill="url(#gradBoiler2)" stroke="#ea580c" stroke-width="2.2" filter="url(#shadow)"/>
          <text x="210" y="128" text-anchor="middle" font-size="11.5" font-weight="700" fill="#9a3412">🔥 WHRU-2</text>
          <text x="210" y="142" text-anchor="middle" font-size="9" font-weight="600" fill="#c2410c">WHRU / Serpantini 2</text>
          <path d="M 178 158 L 242 158 A 5 5 0 0 1 242 168 L 184 168 A 5 5 0 0 0 184 178 L 242 178 A 5 5 0 0 1 242 188 L 184 188 A 5 5 0 0 0 184 198 L 242 198" fill="none" stroke="#ea580c" stroke-width="2.2" stroke-linecap="round"/>
          <rect x="168" y="214" width="84" height="20" rx="4" fill="#ffffff" fill-opacity="0.95" stroke="#ea580c" stroke-width="1.2"/>
          <text id="lbl_boiler2_q" x="210" y="228" text-anchor="middle" font-size="10.5" font-weight="700" fill="#ea580c">Q2 = 2,140 kW</text>
        </g>

        <!-- 3. WHRU-3 (Dynamic) -->
        <g id="node_boiler_3" class="equipment-node whru3-element" onclick="selectEquipment('boiler_3')">
          <rect x="270" y="105" width="100" height="140" rx="8" fill="url(#gradBoiler3)" stroke="#d97706" stroke-width="2.2" filter="url(#shadow)"/>
          <text x="320" y="128" text-anchor="middle" font-size="11.5" font-weight="700" fill="#b45309">🔥 WHRU-3</text>
          <text x="320" y="142" text-anchor="middle" font-size="9" font-weight="600" fill="#b45309">WHRU / Serpantini 3</text>
          <path d="M 288 158 L 352 158 A 5 5 0 0 1 352 168 L 294 168 A 5 5 0 0 0 294 178 L 352 178 A 5 5 0 0 1 352 188 L 294 188 A 5 5 0 0 0 294 198 L 352 198" fill="none" stroke="#d97706" stroke-width="2.2" stroke-linecap="round"/>
          <rect x="278" y="214" width="84" height="20" rx="4" fill="#ffffff" fill-opacity="0.95" stroke="#d97706" stroke-width="1.2"/>
          <text id="lbl_boiler3_q" x="320" y="228" text-anchor="middle" font-size="10.5" font-weight="700" fill="#b45309">Q3 = 0 kW</text>
        </g>

        <!-- 4. WHRU-4 (Dynamic) -->
        <g id="node_boiler_4" class="equipment-node whru4-element" onclick="selectEquipment('boiler_4')">
          <rect x="380" y="105" width="100" height="140" rx="8" fill="url(#gradBoiler4)" stroke="#4338ca" stroke-width="2.2" filter="url(#shadow)"/>
          <text x="430" y="128" text-anchor="middle" font-size="11.5" font-weight="700" fill="#3730a3">🔥 WHRU-4</text>
          <text x="430" y="142" text-anchor="middle" font-size="9" font-weight="600" fill="#3730a3">WHRU / Serpantini 4</text>
          <path d="M 398 158 L 462 158 A 5 5 0 0 1 462 168 L 404 168 A 5 5 0 0 0 404 178 L 462 178 A 5 5 0 0 1 462 188 L 404 188 A 5 5 0 0 0 404 198 L 462 198" fill="none" stroke="#4338ca" stroke-width="2.2" stroke-linecap="round"/>
          <rect x="388" y="214" width="84" height="20" rx="4" fill="#ffffff" fill-opacity="0.95" stroke="#4338ca" stroke-width="1.2"/>
          <text id="lbl_boiler4_q" x="430" y="228" text-anchor="middle" font-size="10.5" font-weight="700" fill="#3730a3">Q4 = 0 kW</text>
        </g>

        <!-- 5. WHRU-5 (Dynamic) -->
        <g id="node_boiler_5" class="equipment-node whru5-element" onclick="selectEquipment('boiler_5')">
          <rect x="490" y="105" width="100" height="140" rx="8" fill="url(#gradBoiler5)" stroke="#7e22ce" stroke-width="2.2" filter="url(#shadow)"/>
          <text x="540" y="128" text-anchor="middle" font-size="11.5" font-weight="700" fill="#6b21a8">🔥 WHRU-5</text>
          <text x="540" y="142" text-anchor="middle" font-size="9" font-weight="600" fill="#6b21a8">WHRU / Serpantini 5</text>
          <path d="M 508 158 L 572 158 A 5 5 0 0 1 572 168 L 514 168 A 5 5 0 0 0 514 178 L 572 178 A 5 5 0 0 1 572 188 L 514 188 A 5 5 0 0 0 514 198 L 572 198" fill="none" stroke="#7e22ce" stroke-width="2.2" stroke-linecap="round"/>
          <rect x="498" y="214" width="84" height="20" rx="4" fill="#ffffff" fill-opacity="0.95" stroke="#7e22ce" stroke-width="1.2"/>
          <text id="lbl_boiler5_q" x="540" y="228" text-anchor="middle" font-size="10.5" font-weight="700" fill="#6b21a8">Q5 = 0 kW</text>
        </g>

        <!-- 6. 3-Way Proportional Bypass Valve -->
        <g id="node_valve" class="equipment-node" onclick="selectEquipment('valve')">
          <circle cx="720" cy="140" r="24" fill="#ffffff" stroke="#d97706" stroke-width="2.4" filter="url(#shadow)"/>
          <polygon points="698,131 698,149 720,140" fill="#d97706"/>
          <polygon points="742,131 742,149 720,140" fill="#d97706"/>
          <polygon points="711,161 729,161 720,140" fill="#d97706"/>
          <circle cx="720" cy="140" r="4" fill="#78350f"/>
          <rect x="676" y="66" width="88" height="20" rx="4" fill="#ffffff" stroke="#d97706" stroke-width="1.2" filter="url(#shadow)"/>
          <text x="720" y="80" text-anchor="middle" font-size="11" font-weight="700" fill="#b45309">🔀 BY-PASS</text>
          <rect x="674" y="174" width="92" height="20" rx="4" fill="#ffffff" stroke="#d97706" stroke-width="1.2" filter="url(#shadow)"/>
          <text id="lbl_valve_pct" x="720" y="188" text-anchor="middle" font-size="11" font-weight="700" fill="#92400e">%0 Açık</text>
        </g>

        <!-- 7. Superheater (TEMA BEM Shell & Tube - Stage 1 in series) -->
        <g id="node_sh" class="equipment-node" onclick="selectEquipment('superheater')">
          <rect x="860" y="90" width="150" height="95" rx="8" fill="url(#gradSH)" stroke="#ea580c" stroke-width="2.5" filter="url(#shadow)"/>
          <line x1="880" y1="90" x2="880" y2="185" stroke="#9a3412" stroke-width="3"/>
          <line x1="990" y1="90" x2="990" y2="185" stroke="#9a3412" stroke-width="3"/>
          <line x1="910" y1="90" x2="910" y2="155" stroke="#c2410c" stroke-width="2.2"/>
          <line x1="940" y1="120" x2="940" y2="185" stroke="#c2410c" stroke-width="2.2"/>
          <line x1="970" y1="90" x2="970" y2="155" stroke="#c2410c" stroke-width="2.2"/>
          <text x="935" y="112" text-anchor="middle" font-size="12" font-weight="700" fill="#9a3412">♨️ AŞIRI KIZDIRICI</text>
          <text x="935" y="125" text-anchor="middle" font-size="9" font-weight="600" fill="#c2410c">TEMA Shell &amp; Tube (1. Kademe)</text>
          <rect x="890" y="158" width="90" height="20" rx="4" fill="#ffffff" fill-opacity="0.95" stroke="#ea580c" stroke-width="1.2"/>
          <text id="lbl_sh_q" x="935" y="172" text-anchor="middle" font-size="11" font-weight="700" fill="#ea580c">Q = 620 kW</text>
        </g>

        <!-- 8. Preheater & Evaporator (TEMA K Kettle Reboiler - Stage 2 in series) -->
        <g id="node_ph" class="equipment-node" onclick="selectEquipment('preheater')">
          <path d="M 910 280 C 910 262, 960 262, 960 280" fill="url(#gradPH)" stroke="#ca8a04" stroke-width="2.5"/>
          <rect x="860" y="280" width="150" height="100" rx="8" fill="url(#gradPH)" stroke="#ca8a04" stroke-width="2.5" filter="url(#shadow)"/>
          <rect x="862" y="332" width="146" height="46" rx="6" fill="#e0f2fe" fill-opacity="0.85"/>
          <circle cx="885" cy="346" r="2" fill="#38bdf8" fill-opacity="0.75"/>
          <circle cx="915" cy="340" r="1.5" fill="#38bdf8" fill-opacity="0.75"/>
          <circle cx="945" cy="348" r="2.2" fill="#38bdf8" fill-opacity="0.75"/>
          <circle cx="970" cy="342" r="1.8" fill="#38bdf8" fill-opacity="0.75"/>
          <path d="M 980 348 L 895 348 A 6 6 0 0 0 895 360 L 980 360" fill="none" stroke="#d97706" stroke-width="2.2"/>
          <text x="935" y="302" text-anchor="middle" font-size="12" font-weight="700" fill="#854d0e">💧 ÖN ISITICI / EVAP</text>
          <text x="935" y="316" text-anchor="middle" font-size="9" font-weight="600" fill="#a16207">Kettle Reboiler (2. Kademe)</text>
          <rect x="890" y="356" width="90" height="20" rx="4" fill="#ffffff" fill-opacity="0.95" stroke="#ca8a04" stroke-width="1.2"/>
          <text id="lbl_ph_q" x="935" y="370" text-anchor="middle" font-size="11" font-weight="700" fill="#ca8a04">Q = 3,330 kW</text>
        </g>

        <!-- 9. Thermal Oil Circulation Pump -->
        <g id="node_pump" class="equipment-node" onclick="selectEquipment('pump')">
          <circle cx="320" cy="445" r="24" fill="url(#gradPump)" stroke="#334155" stroke-width="2.5" filter="url(#shadow)"/>
          <polygon points="310,445 330,435 330,455" fill="#1e293b"/>
          <rect x="250" y="432" width="45" height="28" rx="3" fill="#cbd5e1" stroke="#475569" stroke-width="2"/>
          <text x="320" y="488" text-anchor="middle" font-size="11" font-weight="700" fill="#1e293b">🔄 SİRKÜLASYON POMPASI</text>
          <rect x="275" y="495" width="90" height="18" rx="4" fill="#ffffff" stroke="#475569" stroke-width="1.2" filter="url(#shadow)"/>
          <text id="lbl_pump_w" x="320" y="508" text-anchor="middle" font-size="10.5" font-weight="700" fill="#334155">W_el = 38 kW</text>
        </g>

        <!-- Mixer Junction -->
        <circle cx="820" cy="460" r="7" fill="#854d0e" stroke="#ffffff" stroke-width="2"/>
        <rect x="770" y="474" width="100" height="16" rx="3" fill="#ffffff" stroke="#854d0e" stroke-width="1" filter="url(#shadow)"/>
        <text x="820" y="486" text-anchor="middle" font-size="9.5" fill="#854d0e" font-weight="700">Karışım Noktası</text>

        <!-- 10. ORC Turbine & Generator -->
        <g id="node_turbine" class="equipment-node" onclick="selectEquipment('turbine')">
          <polygon points="1180,118 1225,132 1225,172 1180,186" fill="#f3e8ff" stroke="#9333ea" stroke-width="2.2" filter="url(#shadow)"/>
          <rect x="1225" y="132" width="26" height="38" rx="3" fill="#e9d5ff" stroke="#7e22ce" stroke-width="2"/>
          <text x="1238" y="155" text-anchor="middle" font-size="12" fill="#7e22ce">⚡</text>
          <text x="1202" y="155" text-anchor="middle" font-size="11" font-weight="700" fill="#7e22ce">TÜRBİN</text>
          <rect x="1165" y="196" width="85" height="18" rx="4" fill="#ffffff" stroke="#9333ea" stroke-width="1.2" filter="url(#shadow)"/>
          <text id="lbl_turb_w" x="1207" y="209" text-anchor="middle" font-size="10.5" font-weight="700" fill="#9333ea">P = 820 kW</text>
        </g>

        <!-- 11. ORC Condenser (Dynamic ACC A-Frame / Water Shell & Tube) -->
        <g id="node_condenser" class="equipment-node" onclick="selectEquipment('condenser')">
          <rect x="1160" y="230" width="110" height="85" rx="6" fill="url(#gradCond)" stroke="#0284c7" stroke-width="2.2" filter="url(#shadow)"/>
          <!-- ACC A-Frame Finned Tube Bundle + Axial Fan Visual (Default Active) -->
          <g id="svg_cond_acc">
            <polygon points="1175,274 1215,248 1255,274" fill="none" stroke="#0369a1" stroke-width="2.2" stroke-linejoin="round"/>
            <line x1="1185" y1="268" x2="1215" y2="248" stroke="#0284c7" stroke-width="1.2" stroke-dasharray="2,2"/>
            <line x1="1245" y1="268" x2="1215" y2="248" stroke="#0284c7" stroke-width="1.2" stroke-dasharray="2,2"/>
            <ellipse cx="1200" cy="279" rx="11" ry="4" fill="#38bdf8" stroke="#0369a1" stroke-width="1.2"/>
            <ellipse cx="1230" cy="279" rx="11" ry="4" fill="#38bdf8" stroke="#0369a1" stroke-width="1.2"/>
          </g>
          <!-- Water-Cooled Shell & Tube Serpentine Coil Visual -->
          <g id="svg_cond_water" style="display:none;">
            <path id="cond_coils" d="M 1172 250 L 1258 250 A 4 4 0 0 1 1258 258 L 1172 258 A 4 4 0 0 0 1172 266 L 1258 266" fill="none" stroke="#0369a1" stroke-width="1.8"/>
            <rect x="1162" y="285" width="106" height="28" rx="3" fill="#bae6fd" fill-opacity="0.9"/>
          </g>
          <text id="lbl_cond_title" x="1215" y="244" text-anchor="middle" font-size="10.5" font-weight="700" fill="#0369a1">💨 KONDENSER (ACC)</text>
          <rect x="1177" y="291" width="76" height="16" rx="3" fill="#ffffff" stroke="#0284c7" stroke-width="1"/>
          <text id="lbl_cond_q" x="1215" y="303" text-anchor="middle" font-size="10" font-weight="700" fill="#0284c7">Q_c = 3.5 MW</text>
        </g>

        <!-- 12. ORC Feed Pump -->
        <g id="node_cp_pump" class="equipment-node" onclick="selectEquipment('cp_pump')">
          <circle cx="1215" cy="370" r="18" fill="url(#gradCPPump)" stroke="#7c3aed" stroke-width="2" filter="url(#shadow)"/>
          <polygon points="1205,370 1225,360 1225,380" fill="#7c3aed"/>
          <rect x="1235" y="360" width="18" height="20" rx="2" fill="#ddd6fe" stroke="#6d28d9" stroke-width="1.2"/>
          <text x="1215" y="402" text-anchor="middle" font-size="10.5" font-weight="700" fill="#6d28d9">ORC POMPA</text>
          <rect x="1181" y="406" width="68" height="16" rx="3" fill="#ffffff" stroke="#7c3aed" stroke-width="1"/>
          <text id="lbl_cp_pump_w" x="1215" y="418" text-anchor="middle" font-size="10" font-weight="700" fill="#7c3aed">W = 29 kW</text>
        </g>

        <!-- ================= FLUID LINE INFORMATION BADGES (Live Overlays) ================= -->

        <!-- 1. Hot Oil Supply Header Badge (Top Manifold Header) -->
        <g id="badge_line_oil_sup" class="fluid-badge" transform="translate(430, 48)">
          <rect width="215" height="24" rx="5" stroke="#dc2626"/>
          <text id="txt_oil_sup_fluid" x="107" y="16" text-anchor="middle" fill="#dc2626">Therminol 66 (Kazan Manifold) | 295.0 °C</text>
        </g>

        <!-- 1b. Superheater Oil Inlet Badge (After pipe loss / manual setting) -->
        <g id="badge_line_sh_in" class="fluid-badge" transform="translate(760, 48)">
          <rect width="200" height="24" rx="5" stroke="#ea580c"/>
          <text id="txt_sh_in_fluid" x="100" y="16" text-anchor="middle" fill="#ea580c">SH Giriş | 288.0 °C (Kayıp: 7.0 °C)</text>
        </g>

        <!-- 2. Intermediate Oil Line Badge (Between SH and Evap) -->
        <g id="badge_line_oil_mid" class="fluid-badge" transform="translate(988, 222)">
          <rect width="180" height="24" rx="5" stroke="#ea580c"/>
          <text id="txt_oil_mid_fluid" x="90" y="16" text-anchor="middle" fill="#ea580c">Therminol 66 | 274.0 °C | 5.8 bar</text>
        </g>

        <!-- 3. Oil Return Line Badge (After Evaporator to Mixer) -->
        <g id="badge_line_oil_ret" class="fluid-badge" transform="translate(710, 395)">
          <rect width="180" height="24" rx="5" stroke="#ca8a04"/>
          <text id="txt_oil_ret_fluid" x="90" y="16" text-anchor="middle" fill="#ca8a04">Therminol 66 | 188.0 °C | 4.2 bar</text>
        </g>

        <!-- 4. Mixed Oil Return to Pump Line Badge -->
        <g id="badge_line_oil_mixed" class="fluid-badge" transform="translate(480, 448)">
          <rect width="200" height="24" rx="5" stroke="#854d0e"/>
          <text id="txt_oil_mixed_fluid" x="100" y="16" text-anchor="middle" fill="#854d0e">Therminol 66 (Dönüş) | 188.0 °C</text>
        </g>

        <!-- 5. Cyclopentane Saturated Vapor (Evap Dome -> SH) -->
        <g id="badge_line_cp_vap" class="fluid-badge" transform="translate(740, 208)">
          <rect width="215" height="24" rx="5" stroke="#9333ea"/>
          <text id="txt_cp_vap_fluid" x="107" y="16" text-anchor="middle" fill="#9333ea">Siklopentan (Doymuş) | 178.5 °C | 14 bar</text>
        </g>

        <!-- 6. Cyclopentane Superheated Vapor (SH -> Turbine) -->
        <g id="badge_line_cp_sup" class="fluid-badge" transform="translate(1015, 122)">
          <rect width="215" height="24" rx="5" stroke="#c026d3"/>
          <text id="txt_cp_sup_fluid" x="107" y="16" text-anchor="middle" fill="#c026d3">Siklopentan (Kızgın) | 210.0 °C | 14 bar</text>
        </g>

        <!-- 7. Cyclopentane Turbine Exhaust to Condenser -->
        <g id="badge_line_cp_exh" class="fluid-badge" transform="translate(1225, 192)">
          <rect width="175" height="22" rx="4" stroke="#a855f7"/>
          <text id="txt_cp_exh_fluid" x="87" y="15" text-anchor="middle" fill="#a855f7">Siklopentan | 85 °C | 1.5 bar</text>
        </g>

        <!-- 8. Cyclopentane Liquid Return to Preheater -->
        <g id="badge_line_cp_liq" class="fluid-badge" transform="translate(1030, 375)">
          <rect width="190" height="24" rx="5" stroke="#0284c7"/>
          <text id="txt_cp_liq_fluid" x="95" y="16" text-anchor="middle" fill="#0284c7">Siklopentan (Sıvı) | 45.0 °C | 14 bar</text>
        </g>

        <!-- 9. Condenser Cooling Water Badge -->
        <g id="badge_line_cw" class="fluid-badge" transform="translate(1280, 260)">
          <rect width="165" height="24" rx="5" stroke="#0284c7"/>
          <text id="txt_cw_fluid" x="82" y="16" text-anchor="middle" fill="#0284c7">Soğutma Suyu: 25 -> 33 °C</text>
        </g>

        <!-- Flue Gas Duct In/Out Badges -->
        <g id="b_fg1_in" transform="translate(20, 20)"><rect width="150" height="20" rx="4" fill="#ffffff" stroke="#dc2626" stroke-width="1.2" filter="url(#shadow)"/><text id="txt_fg1_in" x="75" y="14" text-anchor="middle" font-size="10" font-weight="700" fill="#dc2626">B1 Giriş: 480 °C (18 kg/s)</text></g>
        <g id="b_fg1_out" transform="translate(20, 320)"><rect width="115" height="20" rx="4" fill="#ffffff" stroke="#475569" stroke-width="1.2" filter="url(#shadow)"/><text id="txt_fg1_out" x="57" y="14" text-anchor="middle" font-size="10" font-weight="700" fill="#475569">B1 Çıkış: 168 °C</text></g>

        <g id="b_fg2_in" class="whru2-element" transform="translate(140, 20)"><rect width="150" height="20" rx="4" fill="#ffffff" stroke="#ea580c" stroke-width="1.2" filter="url(#shadow)"/><text id="txt_fg2_in" x="75" y="14" text-anchor="middle" font-size="10" font-weight="700" fill="#ea580c">B2 Giriş: 480 °C (18 kg/s)</text></g>
        <g id="b_fg2_out" class="whru2-element" transform="translate(140, 320)"><rect width="115" height="20" rx="4" fill="#ffffff" stroke="#475569" stroke-width="1.2" filter="url(#shadow)"/><text id="txt_fg2_out" x="57" y="14" text-anchor="middle" font-size="10" font-weight="700" fill="#475569">B2 Çıkış: 168 °C</text></g>

        <g id="b_fg3_in" class="whru3-element" transform="translate(250, 20)"><rect width="150" height="20" rx="4" fill="#ffffff" stroke="#d97706" stroke-width="1.2" filter="url(#shadow)"/><text id="txt_fg3_in" x="75" y="14" text-anchor="middle" font-size="10" font-weight="700" fill="#d97706">B3 Giriş: 480 °C</text></g>
        <g id="b_fg3_out" class="whru3-element" transform="translate(250, 320)"><rect width="115" height="20" rx="4" fill="#ffffff" stroke="#475569" stroke-width="1.2" filter="url(#shadow)"/><text id="txt_fg3_out" x="57" y="14" text-anchor="middle" font-size="10" font-weight="700" fill="#475569">B3 Çıkış: 168 °C</text></g>

        <g id="b_fg4_in" class="whru4-element" transform="translate(360, 20)"><rect width="150" height="20" rx="4" fill="#ffffff" stroke="#4338ca" stroke-width="1.2" filter="url(#shadow)"/><text id="txt_fg4_in" x="75" y="14" text-anchor="middle" font-size="10" font-weight="700" fill="#4338ca">B4 Giriş: 480 °C</text></g>
        <g id="b_fg4_out" class="whru4-element" transform="translate(360, 320)"><rect width="115" height="20" rx="4" fill="#ffffff" stroke="#475569" stroke-width="1.2" filter="url(#shadow)"/><text id="txt_fg4_out" x="57" y="14" text-anchor="middle" font-size="10" font-weight="700" fill="#475569">B4 Çıkış: 168 °C</text></g>

        <g id="b_fg5_in" class="whru5-element" transform="translate(470, 20)"><rect width="150" height="20" rx="4" fill="#ffffff" stroke="#7e22ce" stroke-width="1.2" filter="url(#shadow)"/><text id="txt_fg5_in" x="75" y="14" text-anchor="middle" font-size="10" font-weight="700" fill="#7e22ce">B5 Giriş: 480 °C</text></g>
        <g id="b_fg5_out" class="whru5-element" transform="translate(470, 320)"><rect width="115" height="20" rx="4" fill="#ffffff" stroke="#475569" stroke-width="1.2" filter="url(#shadow)"/><text id="txt_fg5_out" x="57" y="14" text-anchor="middle" font-size="10" font-weight="700" fill="#475569">B5 Çıkış: 168 °C</text></g>

      </svg>
      <!-- 3D Digital Twin Container Placeholder -->
      __CONTAINER_3D_PLACEHOLDER__
    </div>

    <!-- Right Dynamic Component Inspector (Click to Edit) -->
    <div class="inspector-box">
      <div class="inspector-header">
        <h3 id="insp_title">🔥 Atık Isı Baca Kazanı 1 (WHRU-1)</h3>
        <p id="insp_desc">Bileşene tıklayarak parametrelerini canlı ayarlayabilirsiniz.</p>
      </div>

      <!-- Dynamic Controls Container -->
      <div id="insp_controls"></div>

      <!-- Dynamic Live Telemetry HUD -->
      <div id="insp_live_hud"></div>

      <div class="preset-btn-group">
        <button class="preset-btn" onclick="applyPreset('single')">1️⃣ Tek Kazan (%100 Yük - WHRU-1)</button>
        <button class="preset-btn" onclick="applyPreset('dual_balanced')">2️⃣ Çift Kazan (%50/%50 Paralel Dengeli)</button>
        <button class="preset-btn" onclick="applyPreset('tri_balanced')">3️⃣ 3 Kazan Dengeli Paylaşım</button>
        <button class="preset-btn" onclick="applyPreset('five_train')">5️⃣ 5 Kazan Tam Kapasite Treni</button>
        <button class="preset-btn" onclick="applyPreset('part_bypass')">🔀 %30 By-Pass Modu</button>
      </div>
    </div>
  </div>

  <script>
    // Thermodynamic property dictionaries for selectable ORC working fluids and thermal oils
    const ORC_FLUIDS = {
      'Cyclopentane': {
        name: 'Siklopentan (Cyclopentane - Retrograde)',
        t_boil: 49.25,
        t_crit: 238.6,
        p_crit: 45.15,
        antoine: [6.88676, 1121.1, 230.56], // log10(P_mmHg) = A - B / (T_C + C)
        cp_liq: 2250.0,
        cp_vap: 1680.0,
        h_fg_ref: 395000.0,
        gamma: 1.08,
        rho_liq: 705.0,
        retrograde: true
      },
      'n-Pentane': {
        name: 'n-Pentan (n-Pentane)',
        t_boil: 36.1,
        t_crit: 196.5,
        p_crit: 33.7,
        antoine: [6.85221, 1064.63, 232.0],
        cp_liq: 2320.0,
        cp_vap: 1750.0,
        h_fg_ref: 358000.0,
        gamma: 1.07,
        rho_liq: 626.0,
        retrograde: true
      },
      'Isopentane': {
        name: 'İzopentan (Isopentane)',
        t_boil: 27.8,
        t_crit: 187.2,
        p_crit: 33.8,
        antoine: [6.78967, 1020.01, 233.1],
        cp_liq: 2360.0,
        cp_vap: 1790.0,
        h_fg_ref: 342000.0,
        gamma: 1.07,
        rho_liq: 620.0,
        retrograde: true
      },
      'R245fa': {
        name: 'R245fa (HFC - Düşük Sıcaklık)',
        t_boil: 15.3,
        t_crit: 154.0,
        p_crit: 36.5,
        antoine: [7.1524, 1122.5, 239.5],
        cp_liq: 1360.0,
        cp_vap: 980.0,
        h_fg_ref: 196000.0,
        gamma: 1.09,
        rho_liq: 1340.0,
        retrograde: true
      },
      'R1233zd(E)': {
        name: 'R1233zd(E) (HFO - Çevre Dostu)',
        t_boil: 18.3,
        t_crit: 166.4,
        p_crit: 36.2,
        antoine: [7.085, 1115.0, 238.0],
        cp_liq: 1290.0,
        cp_vap: 920.0,
        h_fg_ref: 194000.0,
        gamma: 1.09,
        rho_liq: 1280.0,
        retrograde: true
      },
      'Toluene': {
        name: 'Toluen (Toluene - Yüksek Sıcaklık)',
        t_boil: 110.6,
        t_crit: 318.6,
        p_crit: 41.26,
        antoine: [6.95334, 1343.94, 219.38],
        cp_liq: 1750.0,
        cp_vap: 1420.0,
        h_fg_ref: 363000.0,
        gamma: 1.06,
        rho_liq: 867.0,
        retrograde: true
      }
    };

    const THERMAL_OILS = {
      'Therminol 66': {
        name: 'Therminol 66',
        rho: 880.0,
        cp: 2300.0,
        mu: 0.00085,
        k: 0.115,
        cp_base: 1450.0,
        cp_slope: 3.12
      },
      'Dowtherm A': {
        name: 'Dowtherm A',
        rho: 990.0,
        cp: 2100.0,
        mu: 0.00075,
        k: 0.118,
        cp_base: 1500.0,
        cp_slope: 2.50
      },
      'Mobiltherm 605': {
        name: 'Mobiltherm 605',
        rho: 850.0,
        cp: 2200.0,
        mu: 0.00150,
        k: 0.125,
        cp_base: 1700.0,
        cp_slope: 2.10
      },
      'Calflo AF': {
        name: 'Calflo AF',
        rho: 830.0,
        cp: 2350.0,
        mu: 0.00120,
        k: 0.120,
        cp_base: 1750.0,
        cp_slope: 2.30
      },
      'Custom Oil': {
        name: 'Özel Yağ (Manuel Tanım)',
        rho: 880.0,
        cp: 2250.0,
        mu: 0.00090,
        k: 0.115,
        cp_base: 1500.0,
        cp_slope: 2.50
      }
    };

    // State of all thermodynamic, hydraulic & equipment parameters
    const state = {
      n_boilers: 2, // 1 to 5 active boilers
      boilers: [
        { m_flue: 18.0, T_flue_in: 480.0, UA: 35.0, split: 0.50 },
        { m_flue: 18.0, T_flue_in: 480.0, UA: 35.0, split: 0.50 },
        { m_flue: 18.0, T_flue_in: 480.0, UA: 35.0, split: 0.0 },
        { m_flue: 18.0, T_flue_in: 480.0, UA: 35.0, split: 0.0 },
        { m_flue: 18.0, T_flue_in: 480.0, UA: 35.0, split: 0.0 }
      ],
      whru_solver_method: 'Kendi Algoritmamız (Epsilon-NTU)', // Matches SOLVER_OPTIONS exactly
      whru_exch_type: 'Kanatçıklı Borulu (Finned Tube - WHRU Baca Kazanı)',
      whru_flow_type: 'Çapraz Akış (Her İki Akışkan Karışmamış)',
      whru_calc_purpose: 'Performans / Rating (Mevcut Alan ile Doğrulama)',
      whru_u_mode: 'Basit Mod (Manuel U Değeri)',
      whru_T_hot_out_opt: 200.0,
      whru_T_cold_out_opt: 280.0,
      // Hot Side Flue Gas Mixture & Properties
      flue_gas_preset: 'Doğal Gaz',
      flue_gas_basis: 'mole', // 'mole' or 'mass'
      flue_gas_mix: {
        Nitrogen: 76.0,
        Oxygen: 11.0,
        Water: 6.0,
        CarbonDioxide: 7.0,
        SulfurDioxide: 0.0,
        Argon: 0.0,
        CarbonMonoxide: 0.0
      },
      flue_gas_is_manual: false,
      flue_gas_cp: 1144.0,
      flue_gas_rho: 0.469,
      flue_gas_mu: 0.0000348,
      flue_gas_k: 0.054,

      // Cold Side Thermal Oil & Properties
      oil_fluid_sel: 'Therminol 66',
      oil_rho: 880.0,
      oil_cp: 2300.0,
      oil_mu: 0.00085,
      oil_k: 0.115,
      m_oil: 32.0,
      pump_eff: 0.75,
      static_elevation_m: 8.0,
      hx_dp_bar: 0.35,

      // Segmented Piping Network (Darcy-Weisbach)
      pipe_roughness_mm: 0.045,
      pipes: {
        supply: { name: 'Kızgın Yağ Sıcak Besleme Hattı', dn: 'DN150', di_mm: 154.0, length_m: 45.0, roughness_mm: 0.045 },
        boiler_inlet: { name: 'Kazan Giriş Dağıtım Hattı', dn: 'DN150', di_mm: 154.0, length_m: 25.0, roughness_mm: 0.045 },
        bypass: { name: '3 Yollu By-Pass Hattı', dn: 'DN100', di_mm: 102.3, length_m: 15.0, roughness_mm: 0.045 },
        return_line: { name: 'Kızgın Yağ Soğuk Dönüş / Emiş Hattı', dn: 'DN150', di_mm: 154.0, length_m: 35.0, roughness_mm: 0.045 }
      },
      pipe_di_mm: 154.0, // Default DN150
      pipe_length_m: 80.0, // Default equivalent length

      // Flow Control & Superheater
      bypass_ratio: 0.0,
      UA_sh: 15.0,
      UA_ph: 45.0,
      is_manual_t_sh_in: false,
      T_oil_sh_in: null,
      delta_T_pipe_loss: 0.0,
      sh_tema_type: 'BEM',
      sh_shell_fluid: 'Therminol 66 (Kızgın Yağ)',
      sh_tube_fluid: 'Siklopentan (ORC Çevrim Akışkanı)',
      sh_shell_p_des: 16.0,
      sh_tube_p_des: 10.0,
      sh_shell_fouling: 0.0002,
      sh_tube_fouling: 0.0001,

      // Preheater & Evaporator (Kettle Reboiler)
      st_tema_type: 'K (Kettle Reboiler Evaporatör - Genişletilmiş Kubbeli)',
      st_shell_fluid: 'Therminol 66 (Kızgın Yağ)',
      st_tube_fluid: 'Siklopentan (ORC Çevrim Akışkanı)',
      st_kettle_dome_ratio: 1.80,
      st_demister_type: 'SS316 Tel Örgü Ped (Wire Mesh Pad - 100 mm)',
      st_baffle_cut: 25.0,
      st_baffle_pitch: 150.0,
      st_pinch_min_target: 8.0,
      ph_shell_fouling: 0.0002,
      ph_tube_fouling: 0.0001,
      glide_c: 0.0,

      // ORC Power Cycle & Working Fluid
      orc_fluid_sel: 'Cyclopentane',
      P_evap_bar: 14.0,
      P_cond_bar: 2.0,
      m_cp: 11.5,
      T_cp_in: 55.0,
      turb_eta_is: 0.85,
      turb_eta_gen: 0.96,
      z_hw: 1.5,
      feed_pump_eff: 0.70,

      // Condenser & Cooling (Default: Air-Cooled Condenser ACC)
      condenser_type: 'air', // 'air' (ACC) or 'water'
      T_cw_in: 25.0,
      T_air_in: 30.0,
      cw_pump_eff: 0.75,
      acc_fan_eff: 0.65,
      enable_multizone: false,
      t_subcool: 95.0,

      selected_eq: 'boiler_1',
      selected_pipe_tab: 'supply',

      // Backward compatible aliases
      get enable_dual_whru() { return this.n_boilers >= 2; },
      set enable_dual_whru(val) { this.n_boilers = val ? 2 : 1; },
      get m_flue_1() { return this.boilers[0].m_flue; },
      set m_flue_1(val) { this.boilers[0].m_flue = val; },
      get T_flue_in_1() { return this.boilers[0].T_flue_in; },
      set T_flue_in_1(val) { this.boilers[0].T_flue_in = val; },
      get UA_boiler_1() { return this.boilers[0].UA; },
      set UA_boiler_1(val) { this.boilers[0].UA = val; },
      get m_flue_2() { return this.boilers[1].m_flue; },
      set m_flue_2(val) { this.boilers[1].m_flue = val; },
      get T_flue_in_2() { return this.boilers[1].T_flue_in; },
      set T_flue_in_2(val) { this.boilers[1].T_flue_in = val; },
      get UA_boiler_2() { return this.boilers[1].UA; },
      set UA_boiler_2(val) { this.boilers[1].UA = val; },
      get split_oil_whru() { return this.boilers[0].split; },
      set split_oil_whru(val) { this.boilers[0].split = val; if (this.n_boilers === 2) this.boilers[1].split = 1.0 - val; }
    };

    function setBoilerMode(isDual) {
      setBoilerCount(isDual ? 2 : 1);
    }

    function changeBoilerCount(delta) {
      const target = Math.max(1, Math.min(5, state.n_boilers + delta));
      setBoilerCount(target);
    }

    function setBoilerCount(count) {
      state.n_boilers = Math.max(1, Math.min(5, count));
      window.currentBoilerCount = state.n_boilers;

      // Update quick toggle buttons
      [1, 2, 3, 4, 5].forEach(i => {
        const btnId = (i === 1) ? 'btn_mode_single' : (i === 2) ? 'btn_mode_dual' : `btn_mode_${i}`;
        const btn = document.getElementById(btnId);
        if (btn) {
          if (i === state.n_boilers) btn.classList.add('active');
          else btn.classList.remove('active');
        }
      });

      const lbl = document.getElementById('lbl_whru_count');
      if (lbl) lbl.innerText = `(${state.n_boilers} Adet Aktif)`;

      // Equal flow split initialization across active boilers
      const equalSplit = 1.0 / state.n_boilers;
      for (let i = 0; i < 5; i++) {
        if (!state.boilers[i]) {
          state.boilers[i] = { m_flue: 18.0, T_flue_in: 480.0, UA: 35.0, split: 0.0 };
        }
        state.boilers[i].split = (i < state.n_boilers) ? equalSplit : 0.0;
      }

      // Toggle SVG visibility for elements 2..5
      for (let i = 2; i <= 5; i++) {
        const isShown = (i <= state.n_boilers);
        document.querySelectorAll(`.whru${i}-element`).forEach(el => {
          el.style.display = isShown ? '' : 'none';
        });
      }

      const boilerSub = document.getElementById('kpi_boiler_sub');
      if (boilerSub) {
        boilerSub.innerText = `${state.n_boilers} Kazan (${state.n_boilers === 1 ? 'Tekil' : 'Paralel'})`;
      }

      // Fallback selection if current selected boiler was removed
      const selIdxMatch = state.selected_eq.match(/boiler_([1-5])/);
      if (selIdxMatch) {
        const selIdx = parseInt(selIdxMatch[1]);
        if (selIdx > state.n_boilers) {
          state.selected_eq = `boiler_${state.n_boilers}`;
        }
      }

      selectEquipment(state.selected_eq);
      recalculate();
      if (typeof window.sync3DBoilerCount === "function") {
        try { window.sync3DBoilerCount(state.n_boilers); } catch (e) {}
      }
    }

    function setCondenserType(type) {
      state.condenser_type = type;
      if (type === 'air') {
        if (state.P_cond_bar < 1.8) state.P_cond_bar = 2.0;
        if (state.T_cp_in < 55.0) state.T_cp_in = 55.0;
      } else {
        if (state.P_cond_bar > 1.8) state.P_cond_bar = 1.5;
        if (state.T_cp_in > 50.0) state.T_cp_in = 45.0;
      }
      recalculate();
      if (state.selected_eq === 'condenser') {
        selectEquipment('condenser');
      }
    }

    function setShInletMode(manual) {
      state.is_manual_t_sh_in = manual;
      if (manual && state.T_oil_sh_in === null) {
        state.T_oil_sh_in = 288.0;
      }
      recalculate();
      if (state.selected_eq === 'superheater') {
        selectEquipment('superheater');
      }
    }

    // Active ORC fluid helper
    function getActiveOrcFluid() {
      return ORC_FLUIDS[state.orc_fluid_sel] || ORC_FLUIDS['Cyclopentane'];
    }

    // Antoine saturation temperature calculation for selectable ORC fluid
    function orcFluidTsat(p_bar, fluidKey) {
      const f = ORC_FLUIDS[fluidKey || state.orc_fluid_sel] || ORC_FLUIDS['Cyclopentane'];
      const p_mmhg = Math.max(0.05, Math.min(f.p_crit * 0.95, p_bar)) * 750.06168;
      const log_p = Math.log10(p_mmhg);
      const [A, B, C] = f.antoine;
      const denom = A - log_p;
      if (denom <= 0.02) return f.t_crit * 0.98;
      const t_calc = (B / denom) - C;
      return Math.max(-20.0, Math.min(f.t_crit, t_calc));
    }

    // Watson correlation for latent heat of vaporization
    function orcFluidHfg(t_c, fluidKey) {
      const f = ORC_FLUIDS[fluidKey || state.orc_fluid_sel] || ORC_FLUIDS['Cyclopentane'];
      const t = Math.max(-20.0, Math.min(f.t_crit - 1.0, t_c));
      const tr = Math.max(0.01, (f.t_crit - t) / (f.t_crit - f.t_boil));
      return f.h_fg_ref * Math.pow(tr, 0.38);
    }

    // Backward compatibility alias for tests
    function cyclopentaneTsat(p_bar) {
      return orcFluidTsat(p_bar, 'Cyclopentane');
    }

    // Thermal oil specific heat calculation based on active fluid
    function oilCp(tempC) {
      const oil = THERMAL_OILS[state.oil_fluid_sel] || THERMAL_OILS['Therminol 66'];
      const t = Math.max(0.0, Math.min(360.0, tempC));
      if (oil.cp_slope) {
        return oil.cp_base + oil.cp_slope * t;
      }
      return state.oil_cp || 2300.0;
    }

    // LMTD cross-flow / counterflow solver (supports Custom & HT formulation)
    function calcHxLMTD(c_hot, c_cold, ua, t_h_in, t_c_in, isHt = false) {
      if (c_hot <= 1e-4 || c_cold <= 1e-4 || ua <= 1e-4 || t_h_in <= t_c_in) {
        return { q: 0.0, t_h_out: t_h_in, t_c_out: t_c_in };
      }
      const q_max = Math.min(c_hot, c_cold) * (t_h_in - t_c_in);
      let F = 0.95; // Cross-flow serpentine default
      if (state.whru_flow_type === 'Ters Akış (Counter-Current)') {
        F = 1.0;
      }
      const ntu = ua / Math.min(c_hot, c_cold);
      const cr = Math.min(c_hot, c_cold) / Math.max(c_hot, c_cold);
      let eps = (cr < 1.0) ? (1.0 - Math.exp(-ntu * (1.0 - cr))) / (1.0 - cr * Math.exp(-ntu * (1.0 - cr))) : ntu / (1.0 + ntu);
      let q = Math.max(0.0, Math.min(q_max * 0.98, eps * q_max * F));

      for (let step = 0; step < 6; step++) {
        const t_h_out = t_h_in - q / c_hot;
        const t_c_out = t_c_in + q / c_cold;
        const dt1 = Math.max(0.1, t_h_in - t_c_out);
        const dt2 = Math.max(0.1, t_h_out - t_c_in);
        let lmtd = (Math.abs(dt1 - dt2) < 0.1) ? (dt1 + dt2) / 2.0 : (dt1 - dt2) / Math.log(dt1 / dt2);
        if (isHt && state.whru_flow_type !== 'Ters Akış (Counter-Current)') {
          const P = Math.max(0.01, Math.min(0.95, (t_c_out - t_c_in) / Math.max(0.1, t_h_in - t_c_in)));
          const R = Math.max(0.05, Math.min(20.0, (t_h_in - t_h_out) / Math.max(0.1, t_c_out - t_c_in)));
          F = Math.max(0.85, Math.min(0.99, 1.0 - (0.08 / (1.0 + R)) * Math.pow(P, 1.4)));
        }
        const q_calc = ua * F * lmtd;
        q = 0.5 * q + 0.5 * q_calc;
        q = Math.max(0.0, Math.min(q_max * 0.99, q));
      }
      return {
        q: q,
        t_h_out: t_h_in - q / c_hot,
        t_c_out: t_c_in + q / c_cold
      };
    }

    // Heat exchanger solver router matching SOLVER_OPTIONS
    function calcHx(c_hot, c_cold, ua, t_h_in, t_c_in) {
      const method = state.whru_solver_method || 'Kendi Algoritmamız (Epsilon-NTU)';
      if (String(method).toLowerCase().includes('lmtd')) {
        const isHt = String(method).toLowerCase().includes('ht');
        return calcHxLMTD(c_hot, c_cold, ua, t_h_in, t_c_in, isHt);
      }
      // Epsilon-NTU routing (Kendi Algoritmamız or HT Kütüphanesi)
      if (c_hot <= 1e-4 || c_cold <= 1e-4 || ua <= 1e-4 || t_h_in <= t_c_in) {
        return { q: 0.0, t_h_out: t_h_in, t_c_out: t_c_in };
      }
      const c_min = Math.min(c_hot, c_cold);
      const c_max = Math.max(c_hot, c_cold);
      const cr = c_min / c_max;
      const ntu = ua / c_min;

      let eps = 0.5;
      if (state.whru_flow_type === 'Ters Akış (Counter-Current)') {
        eps = (cr < 1.0)
          ? (1.0 - Math.exp(-ntu * (1.0 - cr))) / (1.0 - cr * Math.exp(-ntu * (1.0 - cr)))
          : ntu / (1.0 + ntu);
      } else if (state.whru_flow_type === 'Paralel Akış (Co-Current)') {
        eps = (1.0 - Math.exp(-ntu * (1.0 + cr))) / (1.0 + cr);
      } else {
        // Çapraz Akış (Her İki Akışkan Karışmamış) - Cross-flow unmixed
        if (cr < 1e-4) {
          eps = 1.0 - Math.exp(-ntu);
        } else {
          const inner = Math.exp(-Math.min(100.0, cr * Math.pow(ntu, 0.78))) - 1.0;
          const outer = (1.0 / cr) * Math.pow(ntu, 0.22) * inner;
          eps = 1.0 - Math.exp(Math.max(-100.0, outer));
        }
      }
      eps = Math.max(0.02, Math.min(0.98, eps));
      const q = eps * c_min * (t_h_in - t_c_in);
      return {
        q: q,
        t_h_out: t_h_in - q / c_hot,
        t_c_out: t_c_in + q / c_cold
      };
    }

    // Darcy-Weisbach & Swamee-Jain rigorous hydraulic calculation helper
    function calcPipeDarcy(di_mm, length_m, mass_flow_kg_s, rho, mu, roughness_mm = 0.045) {
      const d_m = Math.max(0.02, di_mm / 1000.0);
      const l_m = Math.max(1.0, length_m);
      const rough_m = Math.max(1e-6, roughness_mm / 1000.0);
      const area = (Math.PI * d_m * d_m) / 4.0;
      const v = (mass_flow_kg_s > 0 && area > 0) ? (mass_flow_kg_s / rho) / area : 0.0;
      const re = (v > 0) ? (rho * v * d_m) / mu : 0.0;

      let f = 0.02;
      if (re > 0) {
        if (re < 2300) {
          f = 64.0 / re;
        } else if (re < 4000) {
          // Smooth transition between laminar and turbulent Swamee-Jain
          const f_lam_trans = 64.0 / 2300.0;
          const term1 = (rough_m / d_m) / 3.7;
          const term2 = 5.74 / Math.pow(4000.0, 0.9);
          const f_turb_trans = 0.25 / Math.pow(Math.log10(term1 + term2), 2);
          const weight = (re - 2300.0) / (4000.0 - 2300.0);
          f = (1.0 - weight) * f_lam_trans + weight * f_turb_trans;
        } else {
          const term1 = (rough_m / d_m) / 3.7;
          const term2 = 5.74 / Math.pow(re, 0.9);
          f = 0.25 / Math.pow(Math.log10(term1 + term2), 2);
          f = Math.max(0.008, Math.min(0.08, f));
        }
      }
      f = Math.max(0.008, f);
      const dp_pa = f * (l_m / d_m) * (rho * v * v / 2.0);
      const dp_bar = dp_pa / 1e5;
      return { v, re, f, dp_bar, dp_pa };
    }

    // Automatically balance flow across active WHRU boilers
    function autoBalanceBoilerFlows() {
      const eqSplit = 1.0 / state.n_boilers;
      for (let i = 0; i < state.n_boilers; i++) {
        state.boilers[i].split = eqSplit;
        const numEl = document.getElementById(`num_b${i+1}_split`);
        if (numEl) numEl.value = Math.round(eqSplit * 100);
        const rngEl = document.getElementById(`rng_b${i+1}_split`);
        if (rngEl) rngEl.value = Math.round(eqSplit * 100);
        const flowEl = document.getElementById(`num_b${i+1}_m_oil`);
        if (flowEl) flowEl.value = (eqSplit * state.m_oil).toFixed(1);
      }
      recalculate();
      if (state.selected_eq && state.selected_eq.startsWith('boiler')) {
        selectEquipment(state.selected_eq);
      }
    }

    // Change active ORC working fluid
    function setOrcFluid(fluidKey) {
      if (!ORC_FLUIDS[fluidKey]) return;
      state.orc_fluid_sel = fluidKey;
      if (fluidKey === 'Toluene') {
        state.P_evap_bar = 8.0;
        state.P_cond_bar = 0.4;
      } else if (fluidKey.includes('R245fa') || fluidKey.includes('R1233zd')) {
        state.P_evap_bar = 18.0;
        state.P_cond_bar = 2.5;
      } else {
        state.P_evap_bar = 14.0;
        state.P_cond_bar = 1.5;
      }
      selectEquipment('turbine');
      recalculate();
    }

    // Change active thermal oil
    function setThermalOil(oilKey) {
      if (!THERMAL_OILS[oilKey]) return;
      state.oil_fluid_sel = oilKey;
      const o = THERMAL_OILS[oilKey];
      state.oil_rho = o.rho;
      state.oil_cp = o.cp;
      state.oil_mu = o.mu;
      state.oil_k = o.k;
      selectEquipment('pump');
      recalculate();
    }

    // Change WHRU solver algorithm (matches SOLVER_OPTIONS)
    function setWhruSolverMethod(method) {
      state.whru_solver_method = method;
      recalculate();
      if (state.selected_eq && state.selected_eq.startsWith('boiler')) {
        selectEquipment(state.selected_eq);
      }
    }

    // Change WHRU flow type
    function setWhruFlowType(ft) {
      state.whru_flow_type = ft;
      recalculate();
      if (state.selected_eq && state.selected_eq.startsWith('boiler')) {
        selectEquipment(state.selected_eq);
      }
    }

    // Change WHRU calculation purpose
    function setWhruCalcPurpose(cp) {
      state.whru_calc_purpose = cp;
      recalculate();
      if (state.selected_eq && state.selected_eq.startsWith('boiler')) {
        selectEquipment(state.selected_eq);
      }
    }

    // Change WHRU U mode
    function setWhruUMode(um) {
      state.whru_u_mode = um;
      recalculate();
      if (state.selected_eq && state.selected_eq.startsWith('boiler')) {
        selectEquipment(state.selected_eq);
      }
    }

    // Change WHRU Exchanger Type
    function setWhruExchType(et) {
      state.whru_exch_type = et;
      recalculate();
      if (state.selected_eq && state.selected_eq.startsWith('boiler')) {
        selectEquipment(state.selected_eq);
      }
    }

    // Change SH TEMA Type
    function setShTemaType(val) {
      state.sh_tema_type = val;
      recalculate();
      if (state.selected_eq === 'superheater') {
        selectEquipment('superheater');
      }
    }

    // Change Preheater/Evaporator TEMA Type
    function setStTemaType(val) {
      state.st_tema_type = val;
      recalculate();
      if (state.selected_eq === 'preheater') {
        selectEquipment('preheater');
      }
    }

    // Change Steam Dome Demister Type
    function setStDemisterType(val) {
      state.st_demister_type = val;
      recalculate();
      if (state.selected_eq === 'preheater') {
        selectEquipment('preheater');
      }
    }

    // Toggle Condenser Multi-Zone Analysis
    function setMultizoneToggle(checked) {
      state.enable_multizone = checked;
      recalculate();
      if (state.selected_eq === 'condenser') {
        selectEquipment('condenser');
      }
    }

    // Rigorous thermophysical properties of flue gas mixture (Ideal gas, Shomate Cp, Sutherland & Wilke viscosity)
    function calcFlueGasMixtureProperties(comp, basis = 'mole', tempC = 480.0) {
      const MW = {
        Nitrogen: 28.0134, Oxygen: 31.998, CarbonDioxide: 44.0095,
        Water: 18.0153, SulfurDioxide: 64.066, Argon: 39.948,
        CarbonMonoxide: 28.0101, Methane: 16.0425, Hydrogen: 2.01588
      };
      const t_c = Math.max(20.0, Math.min(800.0, tempC));
      const t_k = t_c + 273.15;

      let tot = 0;
      for (const k in comp) {
        const val = parseFloat(comp[k]);
        if (!isNaN(val) && val > 0 && MW[k]) tot += val;
      }
      if (tot <= 0) tot = 100.0;

      const raw = {};
      for (const k in comp) {
        const val = parseFloat(comp[k]);
        if (!isNaN(val) && val > 0 && MW[k]) raw[k] = val / tot;
      }

      let x = {}, w = {}, mw_mix = 28.9;
      if (basis === 'mass') {
        w = raw;
        let tot_moles = 0;
        for (const k in w) tot_moles += w[k] / MW[k];
        mw_mix = 1.0 / (tot_moles || 0.0345);
        for (const k in w) x[k] = (w[k] / MW[k]) / (tot_moles || 1.0);
      } else {
        x = raw;
        let tot_mass = 0;
        for (const k in x) tot_mass += x[k] * MW[k];
        mw_mix = tot_mass || 28.9;
        for (const k in x) w[k] = (x[k] * MW[k]) / (tot_mass || 1.0);
      }

      // Density (Ideal Gas Law at 101325 Pa)
      const rho = (101325.0 * mw_mix) / (8314.46 * t_k);

      // Pure gas cp [J/kgK]
      function getCpI(name, t) {
        if (name === 'Nitrogen') return 1030.0 + 0.165 * t;
        if (name === 'Oxygen') return 915.0 + 0.235 * t;
        if (name === 'CarbonDioxide') return 825.0 + 0.685 * t - 0.00018 * t * t;
        if (name === 'Water') return 1855.0 + 0.420 * t;
        if (name === 'SulfurDioxide') return 610.0 + 0.320 * t;
        if (name === 'Argon') return 520.3;
        if (name === 'CarbonMonoxide') return 1035.0 + 0.170 * t;
        if (name === 'Methane') return 2150.0 + 3.40 * t;
        if (name === 'Hydrogen') return 14300.0 + 0.85 * t;
        return 1050.0;
      }

      // Pure gas viscosity [Pa.s]
      function getMuI(name, tk) {
        const pMap = {
          Nitrogen: [1.78e-5, 0.72], Oxygen: [2.07e-5, 0.74],
          CarbonDioxide: [1.50e-5, 0.78], Water: [1.00e-5, 1.05],
          SulfurDioxide: [1.28e-5, 0.80], Argon: [2.29e-5, 0.72],
          CarbonMonoxide: [1.78e-5, 0.72], Methane: [1.12e-5, 0.78],
          Hydrogen: [0.89e-5, 0.68]
        };
        const p = pMap[name] || [1.8e-5, 0.72];
        return p[0] * Math.pow(tk / 300.0, p[1]);
      }

      // Mixture Cp
      let cp_mix = 0;
      for (const k in w) {
        cp_mix += w[k] * getCpI(k, t_c);
      }

      // Wilke Viscosity
      const keys = Object.keys(x);
      const n = keys.length;
      let mu_mix = 0.000032;
      if (n > 0) {
        const mu_list = keys.map(k => getMuI(k, t_k));
        const mw_list = keys.map(k => MW[k]);
        const x_list = keys.map(k => x[k]);

        const phi = Array.from({ length: n }, () => new Array(n).fill(1.0));
        for (let i = 0; i < n; i++) {
          for (let j = 0; j < n; j++) {
            if (i !== j) {
              const num = Math.pow(1.0 + Math.sqrt(mu_list[i] / mu_list[j]) * Math.pow(mw_list[j] / mw_list[i], 0.25), 2);
              const den = Math.sqrt(8.0 * (1.0 + mw_list[i] / mw_list[j]));
              phi[i][j] = num / den;
            }
          }
        }
        mu_mix = 0;
        for (let i = 0; i < n; i++) {
          let denom = 0;
          for (let j = 0; j < n; j++) denom += x_list[j] * phi[i][j];
          if (denom > 1e-12) mu_mix += (x_list[i] * mu_list[i]) / denom;
        }
      }

      const k_mix = (mu_mix * (cp_mix + 1.25 * (8314.46 / mw_mix))) * 0.35;

      return {
        cp: cp_mix,
        density: rho,
        mu: mu_mix,
        k: k_mix,
        mw: mw_mix
      };
    }

    // Update flue gas properties automatically from composition
    function updateFlueGasPropertiesFromMix(bIdx = 0) {
      if (state.flue_gas_is_manual) return;
      const t_fg = (state.boilers && state.boilers[bIdx]) ? state.boilers[bIdx].T_flue_in : 480.0;
      const res = calcFlueGasMixtureProperties(state.flue_gas_mix, state.flue_gas_basis, t_fg);
      state.flue_gas_cp = res.cp;
      state.flue_gas_rho = res.density;
      state.flue_gas_mu = res.mu;
      state.flue_gas_k = res.k;
    }

    // Apply standard combustion gas preset
    function applyFlueGasPreset(presetName, bNum = 1) {
      state.flue_gas_preset = presetName;
      if (presetName === 'Doğal Gaz') {
        state.flue_gas_mix = { Nitrogen: 76.0, Oxygen: 11.0, Water: 6.0, CarbonDioxide: 7.0, SulfurDioxide: 0.0, Argon: 0.0 };
      } else if (presetName === 'Kömür') {
        state.flue_gas_mix = { Nitrogen: 72.0, Oxygen: 6.0, Water: 6.0, CarbonDioxide: 15.0, SulfurDioxide: 1.0, Argon: 0.0 };
      } else if (presetName === 'Biyogaz') {
        state.flue_gas_mix = { Nitrogen: 65.0, Oxygen: 5.0, Water: 15.0, CarbonDioxide: 15.0, SulfurDioxide: 0.0, Argon: 0.0 };
      }
      state.flue_gas_is_manual = false;
      updateFlueGasPropertiesFromMix(bNum - 1);
      recalculate();
      selectEquipment(`boiler_${bNum}`);
    }

    // Set mixture basis (mole vs mass)
    function setFlueGasBasis(basis, bNum = 1) {
      state.flue_gas_basis = basis;
      state.flue_gas_is_manual = false;
      updateFlueGasPropertiesFromMix(bNum - 1);
      recalculate();
      selectEquipment(`boiler_${bNum}`);
    }

    // On component percentage change
    function onFlueGasCompChange(compName, val, bNum = 1) {
      const num = parseFloat(val) || 0.0;
      state.flue_gas_mix[compName] = Math.max(0.0, num);
      state.flue_gas_preset = 'Özel (Custom)';
      state.flue_gas_is_manual = false;
      updateFlueGasPropertiesFromMix(bNum - 1);
      recalculate();
      selectEquipment(`boiler_${bNum}`);
    }

    // Reset manual overrides and recalculate from mixture
    function resetFlueGasToAuto(bNum = 1) {
      state.flue_gas_is_manual = false;
      updateFlueGasPropertiesFromMix(bNum - 1);
      recalculate();
      selectEquipment(`boiler_${bNum}`);
    }

    // Select nominal DN for pipe segment
    function onPipeDnSelect(pKey, dn) {
      const dnMap = { 'DN80': 82.5, 'DN100': 102.3, 'DN125': 127.0, 'DN150': 154.0, 'DN200': 204.9 };
      if (state.pipes && state.pipes[pKey]) {
        state.pipes[pKey].dn = dn;
        if (dnMap[dn]) {
          state.pipes[pKey].di_mm = dnMap[dn];
          if (pKey === 'supply') state.pipe_di_mm = dnMap[dn];
        }
      }
      selectEquipment('pipe_' + (pKey === 'return_line' ? 'return' : pKey));
      recalculate();
    }

    // Solve entire network live
    function recalculate() {
      const orcFluid = getActiveOrcFluid();
      const cp_flue = state.flue_gas_cp || 1100.0;
      const t_sat = orcFluidTsat(state.P_evap_bar, state.orc_fluid_sel);
      const cp_cp_liq = orcFluid.cp_liq;
      const cp_cp_vap = orcFluid.cp_vap;
      const h_fg = orcFluidHfg(t_sat, state.orc_fluid_sel);

      const m_active = state.m_oil * (1.0 - state.bypass_ratio);
      const m_bypass = state.m_oil * state.bypass_ratio;

      let t_oil_sup = 295.0;
      let new_t_oil_sup = 295.0;
      let t_oil_ret_mixed = 190.0;
      let q_boiler = 0;
      let q_sh = 0, q_ph = 0, q_evap = 0, q_pre = 0;
      let delta_t_pinch = 45.0;
      let t_oil_sh_out = t_oil_sup;
      let t_oil_evap_out = t_oil_sup;
      let t_oil_ph_out = t_oil_ret_mixed;
      let t_cp_sup = t_sat;

      const boiler_q = [0, 0, 0, 0, 0];
      const boiler_t_fg_out = [480, 480, 480, 480, 480];
      const boiler_dp = [0, 0, 0, 0, 0];

      // Closed loop iteration
      for (let iter = 0; iter < 25; iter++) {
        const cp_oil_avg = oilCp((t_oil_sup + t_oil_ret_mixed) / 2.0);

        let sum_m_t_oil = 0.0;
        let sum_m_oil_active = 0.0;
        q_boiler = 0.0;

        for (let i = 0; i < state.n_boilers; i++) {
          const b = (state.boilers && state.boilers[i]) ? state.boilers[i] : { m_flue: 18.0, T_flue_in: 480.0, UA: 35.0, split: 1.0 / state.n_boilers };
          const m_oil_i = state.m_oil * b.split;
          const c_f_i = b.m_flue * cp_flue;
          const c_o_i = m_oil_i * cp_oil_avg;

          const hx = calcHx(c_f_i, c_o_i, b.UA * 1000.0, b.T_flue_in, t_oil_ret_mixed);
          boiler_q[i] = hx.q;
          boiler_t_fg_out[i] = hx.t_h_out;
          q_boiler += hx.q;
          sum_m_t_oil += m_oil_i * hx.t_c_out;
          sum_m_oil_active += m_oil_i;
        }

        const unheated_oil = Math.max(0.0, state.m_oil - sum_m_oil_active);
        sum_m_t_oil += unheated_oil * t_oil_ret_mixed;
        new_t_oil_sup = (state.m_oil > 0) ? (sum_m_t_oil / state.m_oil) : t_oil_ret_mixed;

        if (m_active < 0.1) {
          q_sh = 0; q_evap = 0; q_pre = 0; q_ph = 0;
          t_oil_sh_out = new_t_oil_sup;
          t_oil_evap_out = new_t_oil_sup;
          t_oil_ph_out = new_t_oil_sup;
          t_cp_sup = t_sat;
          delta_t_pinch = new_t_oil_sup - t_sat;
          t_oil_ret_mixed = new_t_oil_sup;
        } else {
          const c_oil_active = m_active * cp_oil_avg;

          // Superheater Hot Oil Inlet Temperature (with line loss or manual override)
          let t_oil_sh_in = new_t_oil_sup;
          if (state.is_manual_t_sh_in && state.T_oil_sh_in !== null) {
            t_oil_sh_in = state.T_oil_sh_in;
          } else {
            t_oil_sh_in = new_t_oil_sup - (state.delta_T_pipe_loss || 0.0);
          }
          const delta_t_loss = Math.max(0.0, new_t_oil_sup - t_oil_sh_in);
          const q_pipe_loss_kw = (m_active * cp_oil_avg * delta_t_loss) / 1000.0;

          // Superheater
          const c_cp_v = state.m_cp * cp_cp_vap;
          const c_min_sh = Math.min(c_oil_active, c_cp_v);
          const c_max_sh = Math.max(c_oil_active, c_cp_v);
          const cr_sh = c_min_sh / c_max_sh;
          const ntu_sh = (state.UA_sh * 1000.0) / c_min_sh;
          let eps_sh = (cr_sh < 1.0) ? (1.0 - Math.exp(-ntu_sh * (1.0 - cr_sh))) / (1.0 - cr_sh * Math.exp(-ntu_sh * (1.0 - cr_sh))) : ntu_sh / (1.0 + ntu_sh);
          eps_sh = Math.max(0.05, Math.min(0.88, eps_sh));

          q_sh = eps_sh * c_min_sh * Math.max(0.0, t_oil_sh_in - t_sat);
          t_cp_sup = t_sat + q_sh / c_cp_v;
          t_oil_sh_out = t_oil_sh_in - q_sh / c_oil_active;

          // Evaporator (Pool Boiling)
          const q_evap_dem = state.m_cp * h_fg;
          const ua_evap = (state.UA_ph * 0.65) * 1000.0;
          const ntu_evap = ua_evap / c_oil_active;
          const eps_evap = Math.max(0.05, Math.min(0.95, 1.0 - Math.exp(-ntu_evap)));
          const q_evap_max = c_oil_active * Math.max(0.0, t_oil_sh_out - t_sat);
          q_evap = Math.min(q_evap_dem, eps_evap * q_evap_max);
          t_oil_evap_out = t_oil_sh_out - q_evap / c_oil_active;

          delta_t_pinch = t_oil_evap_out - t_sat;

          // Liquid Preheater
          const q_pre_dem = state.m_cp * cp_cp_liq * Math.max(0.0, t_sat - state.T_cp_in);
          const c_cp_l = state.m_cp * cp_cp_liq;
          const c_min_pre = Math.min(c_oil_active, c_cp_l);
          const c_max_pre = Math.max(c_oil_active, c_cp_l);
          const cr_pre = c_min_pre / c_max_pre;
          const ua_pre = (state.UA_ph * 0.35) * 1000.0;
          const ntu_pre = ua_pre / c_min_pre;
          let eps_pre = (cr_pre < 1.0) ? (1.0 - Math.exp(-ntu_pre * (1.0 - cr_pre))) / (1.0 - cr_pre * Math.exp(-ntu_pre * (1.0 - cr_pre))) : ntu_pre / (1.0 + ntu_pre);
          eps_pre = Math.max(0.05, Math.min(0.92, eps_pre));

          const q_pre_max = c_min_pre * Math.max(0.0, t_oil_evap_out - state.T_cp_in);
          q_pre = Math.min(q_pre_dem, eps_pre * q_pre_max);
          t_oil_ph_out = t_oil_evap_out - q_pre / c_oil_active;
          q_ph = q_evap + q_pre;

          t_oil_ret_mixed = (1.0 - state.bypass_ratio) * t_oil_ph_out + state.bypass_ratio * new_t_oil_sup;
        }

        t_oil_sup = 0.5 * t_oil_sup + 0.5 * new_t_oil_sup;
      }

      // Hydraulic calculations for active boilers
      let max_dp = 0.0;
      let min_dp = 999.0;
      for (let i = 0; i < state.n_boilers; i++) {
        const m_i = state.m_oil * state.boilers[i].split;
        boiler_dp[i] = (m_i > 0) ? 0.35 * Math.pow(m_i / (32.0 / state.n_boilers), 1.85) : 0.0;
        if (boiler_dp[i] > max_dp) max_dp = boiler_dp[i];
        if (boiler_dp[i] < min_dp) min_dp = boiler_dp[i];
      }
      const dp_diff = (state.n_boilers > 1) ? Math.abs(max_dp - min_dp) : 0.0;

      // First Law Enforced: ORC Heat input cannot exceed boiler heat duty transmitted minus line heat loss
      let t_oil_sh_in_final = new_t_oil_sup;
      if (state.is_manual_t_sh_in && state.T_oil_sh_in !== null) {
        t_oil_sh_in_final = state.T_oil_sh_in;
      } else {
        t_oil_sh_in_final = new_t_oil_sup - (state.delta_T_pipe_loss || 0.0);
      }
      const delta_t_loss_final = Math.max(0.0, new_t_oil_sup - t_oil_sh_in_final);
      const q_pipe_loss_kw_final = (m_active * (state.oil_cp || 2200.0) * delta_t_loss_final) / 1000.0;
      const q_orc_max = Math.max(0.0, q_boiler * (1.0 - state.bypass_ratio) - q_pipe_loss_kw_final * 1000.0);
      let q_orc_total = q_sh + q_ph;
      if (q_orc_total > q_orc_max && q_orc_total > 0) {
        const factor = q_orc_max / q_orc_total;
        q_sh *= factor;
        q_ph *= factor;
        q_orc_total = q_orc_max;
      }

      // Segmented Darcy-Weisbach calculations for all pipe legs
      const rho_oil = state.oil_rho || 880.0;
      const mu_oil = state.oil_mu || 0.00085;
      const rough_m = (state.pipe_roughness_mm || 0.045) / 1000.0;

      if (!state.pipes) {
        state.pipes = {
          supply: { name: 'Kızgın Yağ Sıcak Besleme Hattı', dn: 'DN150', di_mm: state.pipe_di_mm || 154.0, length_m: 45.0, roughness_mm: 0.045 },
          boiler_inlet: { name: 'Kazan Giriş Dağıtım Hattı', dn: 'DN150', di_mm: 154.0, length_m: 25.0, roughness_mm: 0.045 },
          bypass: { name: '3 Yollu By-Pass Hattı', dn: 'DN100', di_mm: 102.3, length_m: 15.0, roughness_mm: 0.045 },
          return_line: { name: 'Kızgın Yağ Soğuk Dönüş / Emiş Hattı', dn: 'DN150', di_mm: 154.0, length_m: 35.0, roughness_mm: 0.045 }
        };
      }

      const res_supply = calcPipeDarcy(state.pipes.supply.di_mm, state.pipes.supply.length_m, m_active, rho_oil, mu_oil, state.pipes.supply.roughness_mm);
      const res_bin = calcPipeDarcy(state.pipes.boiler_inlet.di_mm, state.pipes.boiler_inlet.length_m, state.m_oil, rho_oil, mu_oil, state.pipes.boiler_inlet.roughness_mm);
      const res_ret = calcPipeDarcy(state.pipes.return_line.di_mm, state.pipes.return_line.length_m, state.m_oil, rho_oil, mu_oil, state.pipes.return_line.roughness_mm);
      const res_byp = calcPipeDarcy(state.pipes.bypass.di_mm, state.pipes.bypass.length_m, m_bypass, rho_oil, mu_oil, state.pipes.bypass.roughness_mm);

      // Primary pipe aliases for test suite compatibility
      const d_i_m = Math.max(0.04, (state.pipes.supply.di_mm || 154.0) / 1000.0);
      const l_pipe_m = Math.max(5.0, (state.pipes.supply.length_m || 45.0));
      const v_oil = res_supply.v;
      const re_oil = res_supply.re;
      const f_darcy = res_supply.f;

      const dp_pipes_sum_bar = res_supply.dp_bar + res_bin.dp_bar + res_ret.dp_bar + (state.bypass_ratio > 0.01 ? res_byp.dp_bar * state.bypass_ratio : 0.0);
      const dp_pipe_bar = dp_pipes_sum_bar;
      const dp_static_bar = (rho_oil * 9.81 * (state.static_elevation_m ?? 8.0)) / 1e5;
      const dp_hx_bar = (state.hx_dp_bar ?? 0.35) * Math.pow(Math.max(0.05, m_active / 32.0), 1.85);

      // Closed-loop dynamic friction head: Pipes + Boilers + Exchangers
      // (shortcut: closed circulation loop static elevation head cancels out between riser and downcomer)
      const dp_bar = dp_pipes_sum_bar + max_dp + dp_hx_bar;
      const w_pump_kw = ((state.m_oil / rho_oil) * dp_bar * 1e5) / (state.pump_eff || 0.75) / 1000.0;

      // Update Hydraulic Badge
      const hydEl = document.getElementById('badge_hydraulics');
      if (hydEl) {
        if (state.n_boilers === 1) {
          hydEl.innerHTML = `⚖️ Hidrolik: Tek Hat (Kazan ΔP = ${max_dp.toFixed(2)} bar, Toplam = ${dp_bar.toFixed(2)} bar)`;
        } else if (dp_diff < 0.05) {
          hydEl.innerHTML = `⚖️ Hidrolik: Dengeli ${state.n_boilers} Kazan (ΔP_kazan = ${max_dp.toFixed(2)} bar, Toplam = ${dp_bar.toFixed(2)} bar)`;
        } else {
          hydEl.innerHTML = `⚠️ Balans Farkı: <b>${dp_diff.toFixed(2)} bar</b> (Maks: ${max_dp.toFixed(2)}, Min: ${min_dp.toFixed(2)})`;
        }
      }

      const p_cond_actual = Math.max(0.1, state.P_cond_bar || 1.5);
      const has_head = state.P_evap_bar > p_cond_actual;
      const pr = has_head ? Math.max(1.0, state.P_evap_bar / p_cond_actual) : 1.0;
      const gamma = orcFluid.gamma || 1.08;
      const dh_is = (has_head && pr > 1.0)
        ? cp_cp_vap * (t_cp_sup + 273.15) * (1.0 - Math.pow(1.0 / pr, (gamma - 1.0) / gamma))
        : 0.0;

      // Working fluid total specific heat required to heat liquid from T_cp_in, evaporate, and superheat (J/kg)
      const dh_cycle_req = cp_cp_liq * Math.max(0.0, t_sat - state.T_cp_in) + h_fg + cp_cp_vap * Math.max(0.0, t_cp_sup - t_sat);

      // First Law Enforced: Actual vapor mass flow rate to turbine cannot exceed heat absorbed by ORC fluid
      const m_cp_actual = (dh_cycle_req > 0 && q_orc_total > 0)
        ? Math.min(state.m_cp, q_orc_total / dh_cycle_req)
        : 0.0;

      // Turbine isentropic expansion & electrical generation power
      const turb_eta_is = state.turb_eta_is !== undefined ? state.turb_eta_is : 0.85;
      const turb_eta_gen = state.turb_eta_gen !== undefined ? state.turb_eta_gen : 0.96;
      let w_turb_mech_kw = (m_cp_actual * dh_is * turb_eta_is) / 1000.0;
      let w_turb_kw = w_turb_mech_kw * turb_eta_gen;

      // Second Law Enforced: Carnot ceiling (eta_carnot * Q_orc)
      const t_c_sat_k = orcFluidTsat(p_cond_actual, state.orc_fluid_sel) + 273.15;
      const t_h_sup_k = t_cp_sup + 273.15;
      const eta_carnot = Math.max(0.0, 1.0 - (t_c_sat_k / t_h_sup_k));
      const w_turb_carnot_max = (q_orc_total / 1000.0) * Math.min(0.28, eta_carnot * 0.85);
      w_turb_kw = Math.min(w_turb_kw, w_turb_carnot_max);
      if (turb_eta_gen > 0) w_turb_mech_kw = Math.min(w_turb_mech_kw, w_turb_kw / turb_eta_gen);

      // Feed pump power (pumping actual cycle fluid flow)
      const w_cp_pump_kw = (m_cp_actual * Math.max(0.0, state.P_evap_bar - p_cond_actual) * 1e5) / (orcFluid.rho_liq * (state.feed_pump_eff || 0.70)) / 1000.0;

      // Condenser & Parasitic Power (ACC Fan vs Water Pump)
      // 1st law on cycle fluid: Q_in + W_pump(fluid) = Q_cond + W_shaft (generator loss is NOT condenser heat)
      const q_cond = Math.max(0.0, q_orc_total + w_cp_pump_kw * (state.feed_pump_eff || 0.70) * 1000.0 - w_turb_mech_kw * 1000.0);
      let w_cond_parasitic_kw = 0.0;
      const isAirCond = (state.condenser_type === 'air');
      const svgCondAcc = document.getElementById('svg_cond_acc');
      const svgCondWater = document.getElementById('svg_cond_water');
      if (svgCondAcc) svgCondAcc.style.display = isAirCond ? '' : 'none';
      if (svgCondWater) svgCondWater.style.display = isAirCond ? 'none' : '';
      const btnCondAir = document.getElementById('btn_cond_mode_air');
      const btnCondWater = document.getElementById('btn_cond_mode_water');
      if (btnCondAir) btnCondAir.classList.toggle('active', isAirCond);
      if (btnCondWater) btnCondWater.classList.toggle('active', !isAirCond);

      if (isAirCond) {
        w_cond_parasitic_kw = (q_cond / 1000.0) * (0.015 / (state.acc_fan_eff || 0.65));
        const condTitle = document.getElementById('lbl_cond_title');
        if (condTitle) condTitle.textContent = '💨 KONDENSER (ACC)';
        const cwFluid = document.getElementById('txt_cw_fluid');
        if (cwFluid) {
          const delta_t_air = 12.0;
          const cp_air = 1005.0;
          const m_air = (delta_t_air > 0) ? (q_cond / (cp_air * delta_t_air)) : 0.0;
          const tAir = (state.T_air_in !== undefined && state.T_air_in !== null) ? state.T_air_in : 30.0;
          cwFluid.textContent = `ACC Havası | ${tAir.toFixed(0)} -> ${(tAir + delta_t_air).toFixed(0)} °C | ${m_air.toFixed(1)} kg/s | Fan: ${w_cond_parasitic_kw.toFixed(1)} kW`;
        }
      } else {
        w_cond_parasitic_kw = (q_cond / 1000.0) * (0.004 / (state.cw_pump_eff || 0.75));
        const condTitle = document.getElementById('lbl_cond_title');
        if (condTitle) condTitle.textContent = '❄️ KONDENSER (SU)';
        const cwFluid = document.getElementById('txt_cw_fluid');
        if (cwFluid) {
          const delta_t_cw = 8.0;
          const cp_w = 4184.0;
          const m_cw = (delta_t_cw > 0) ? (q_cond / (cp_w * delta_t_cw)) : 0.0;
          const tCw = (state.T_cw_in !== undefined && state.T_cw_in !== null) ? state.T_cw_in : 25.0;
          cwFluid.textContent = `Soğutma Suyu | ${tCw.toFixed(0)} -> ${(tCw + delta_t_cw).toFixed(0)} °C | ${m_cw.toFixed(1)} kg/s | Pompa: ${w_cond_parasitic_kw.toFixed(1)} kW`;
        }
      }

      // Net ORC Power cannot exceed Turbine Power minus parasitic loads, and can never exceed Boiler Heat Duty
      let w_net_kw = Math.max(0.0, w_turb_kw - w_pump_kw - w_cp_pump_kw - w_cond_parasitic_kw);
      if (q_boiler > 0) {
        w_net_kw = Math.min(w_net_kw, (q_boiler / 1000.0) * eta_carnot);
      } else {
        w_net_kw = 0.0;
      }
      const plant_eff = (q_boiler > 0) ? (w_net_kw / (q_boiler / 1000.0) * 100.0) : 0.0;

      // Safe DOM helper
      const setTxt = (id, text) => {
        const el = document.getElementById(id);
        if (el) el.textContent = text;
      };

      // Update Top KPIs
      const w_parasitic_total_kw = w_pump_kw + w_cp_pump_kw + w_cond_parasitic_kw;
      setTxt('kpi_q_boiler', (q_boiler / 1000.0).toFixed(0) + ' kW');
      setTxt('kpi_w_net', w_net_kw.toFixed(0) + ' kW');
      setTxt('kpi_w_net_sub', `Brüt: ${w_turb_kw.toFixed(0)} kW | İç Tüketim: ${w_parasitic_total_kw.toFixed(1)} kW`);
      setTxt('kpi_q_orc', (q_orc_total / 1000.0).toFixed(0) + ' kW');
      setTxt('kpi_plant_eff', '%' + plant_eff.toFixed(1));
      setTxt('kpi_bypass', (state.bypass_ratio === 0) ? '%0 (Kapalı)' : '%' + (state.bypass_ratio * 100).toFixed(0));
      setTxt('kpi_bypass_flow', m_bypass.toFixed(1) + ' kg/s yağı by-pass');

      // Update Power & Parasitic Consumption Balance Strip
      setTxt('pwr_w_turb', w_turb_kw.toFixed(0) + ' kW');
      setTxt('pwr_w_parasitic_total', w_parasitic_total_kw.toFixed(1) + ' kW');
      setTxt('pwr_w_oil_pump', w_pump_kw.toFixed(1) + ' kW');
      setTxt('pwr_w_cp_pump', w_cp_pump_kw.toFixed(1) + ' kW');
      setTxt('pwr_w_cond', w_cond_parasitic_kw.toFixed(1) + ' kW');
      setTxt('pwr_w_net', w_net_kw.toFixed(0) + ' kW');
      const condTypeLbl = document.getElementById('pwr_lbl_cond_type');
      if (condTypeLbl) {
        condTypeLbl.textContent = (state.condenser_type === 'air') ? '💨 ACC Fanı:' : '❄️ Kule Pompası:';
      }

      const pinchEl = document.getElementById('kpi_pinch');
      const pinchSub = document.getElementById('kpi_pinch_sub');
      if (pinchEl) {
        pinchEl.textContent = delta_t_pinch.toFixed(1) + ' °C';
        if (delta_t_pinch < 5.0) {
          pinchEl.style.color = '#dc2626';
          if (pinchSub) pinchSub.innerHTML = '⚠️ <span style="color:#dc2626; font-weight:700;">Pinch İhlali!</span>';
        } else if (delta_t_pinch < 15.0) {
          pinchEl.style.color = '#d97706';
          if (pinchSub) pinchSub.innerHTML = '⚠️ Sınırda Aralık';
        } else {
          pinchEl.style.color = '#0284c7';
          if (pinchSub) pinchSub.innerHTML = '✅ Normal / Güvenli';
        }
      }

      // Update Boiler Node Badges
      for (let i = 1; i <= 5; i++) {
        setTxt(`lbl_boiler${i}_q`, `Q${i} = ${(boiler_q[i - 1] / 1000.0).toFixed(0)} kW`);
        if (state.boilers && state.boilers[i - 1]) {
          setTxt(`txt_fg${i}_in`, `B${i}: ${state.boilers[i-1].T_flue_in.toFixed(0)} °C (${state.boilers[i-1].m_flue.toFixed(1)} kg/s)`);
        }
        setTxt(`txt_fg${i}_out`, `B${i} Çıkış: ${boiler_t_fg_out[i-1].toFixed(0)} °C`);
      }

      // Equipment Labels
      setTxt('lbl_sh_q', 'Q = ' + (q_sh / 1000.0).toFixed(0) + ' kW');
      setTxt('lbl_ph_q', 'Q = ' + (q_ph / 1000.0).toFixed(0) + ' kW');
      setTxt('lbl_pump_w', 'W_el = ' + w_pump_kw.toFixed(1) + ' kW');
      setTxt('lbl_turb_w', 'P = ' + w_turb_kw.toFixed(0) + ' kW');
      setTxt('lbl_valve_pct', '%' + (state.bypass_ratio * 100).toFixed(0) + ' By-Pass');
      setTxt('lbl_cond_q', 'Q = ' + (q_cond / 1e6).toFixed(2) + ' MW');
      setTxt('lbl_cp_pump_w', 'W = ' + w_cp_pump_kw.toFixed(1) + ' kW');

      // ================= DIRECT FLUID LINE BADGE UPDATES =================
      const dp_factor = Math.pow(Math.max(0.1, state.m_oil / 32.0), 1.85);
      const p_oil_sup_bar = (4.0 + 2.5 * dp_factor).toFixed(1);
      const p_oil_mid_bar = (4.0 + 1.8 * dp_factor).toFixed(1);
      const p_oil_ret_bar = (4.0 + 0.2 * dp_factor).toFixed(1);

      const t_c_sat = orcFluidTsat(p_cond_actual, state.orc_fluid_sel);
      const t_cp_exh = (m_cp_actual > 0.05 && w_turb_kw > 0)
        ? Math.max(t_c_sat + 2.0, t_cp_sup - ((w_turb_mech_kw * 1000.0) / (m_cp_actual * cp_cp_vap)))
        : (t_c_sat + 2.0);

      const t_cp_liq_in = Math.max(20.0, Math.min(t_c_sat - 2.0, state.condenser_type === 'air' ? (state.T_air_in + 8.0) : (state.T_cw_in + 5.0)));
      state.T_cp_in = t_cp_liq_in;

      const oilName = state.oil_fluid_sel || 'Therminol 66';
      const orcName = state.orc_fluid_sel || 'Siklopentan';

      setTxt('txt_oil_sup_fluid', `Kazan Manifoldu | ${state.m_oil.toFixed(1)} kg/s | ${t_oil_sup.toFixed(1)} °C | ${p_oil_sup_bar} bar`);
      setTxt('txt_sh_in_fluid', `SH Giriş | ${m_active.toFixed(1)} kg/s | ${t_oil_sh_in_final.toFixed(1)} °C (Kayıp: ${delta_t_loss_final.toFixed(1)} °C)`);
      setTxt('txt_oil_mid_fluid', `${oilName} | ${m_active.toFixed(1)} kg/s | ${t_oil_sh_out.toFixed(1)} °C | ${p_oil_mid_bar} bar`);
      setTxt('txt_oil_ret_fluid', `${oilName} | ${m_active.toFixed(1)} kg/s | ${t_oil_ph_out.toFixed(1)} °C | ${p_oil_ret_bar} bar`);
      setTxt('txt_oil_mixed_fluid', `${oilName} (Dönüş) | ${state.m_oil.toFixed(1)} kg/s | ${t_oil_ret_mixed.toFixed(1)} °C`);

      setTxt('txt_cp_vap_fluid', `${orcName} | ${m_cp_actual.toFixed(1)} kg/s | ${t_sat.toFixed(1)} °C | ${state.P_evap_bar.toFixed(1)} bar | Doymuş`);
      setTxt('txt_cp_sup_fluid', `${orcName} | ${m_cp_actual.toFixed(1)} kg/s | ${t_cp_sup.toFixed(1)} °C | ${state.P_evap_bar.toFixed(1)} bar | Kızgın`);
      setTxt('txt_cp_exh_fluid', `${orcName} | ${m_cp_actual.toFixed(1)} kg/s | ${t_cp_exh.toFixed(1)} °C | ${p_cond_actual.toFixed(1)} bar | Egzoz`);
      setTxt('txt_cp_liq_fluid', `${orcName} | ${m_cp_actual.toFixed(1)} kg/s | ${t_cp_liq_in.toFixed(1)} °C | ${state.P_evap_bar.toFixed(1)} bar | Sıvı`);

      // Bypass pipe visuals
      const bypassPipe = document.getElementById('pipe_bypass');
      if (bypassPipe) {
        if (state.bypass_ratio > 0.02) {
          bypassPipe.style.stroke = '#f59e0b';
          bypassPipe.style.strokeWidth = 3 + state.bypass_ratio * 4;
          bypassPipe.style.opacity = '1.0';
        } else {
          bypassPipe.style.opacity = '0.25';
        }
      }

      const orcOpacity = (state.bypass_ratio >= 0.98) ? '0.3' : '1.0';
      const pipeOilSh = document.getElementById('pipe_oil_to_sh');
      if (pipeOilSh) pipeOilSh.style.opacity = orcOpacity;
      const pipeOilMid = document.getElementById('pipe_oil_mid');
      if (pipeOilMid) pipeOilMid.style.opacity = orcOpacity;
      const pipeOilRet = document.getElementById('pipe_oil_ret');
      if (pipeOilRet) pipeOilRet.style.opacity = orcOpacity;

      // Update Live Diagnostic HUD in Right-Side Inspector
      updateInspectorLiveHUD({
        q_boiler: q_boiler / 1000.0,
        q_sh: q_sh / 1000.0,
        q_ph: q_ph / 1000.0,
        q_orc_total: q_orc_total / 1000.0,
        q_cond: q_cond / 1000.0,
        w_turb_mech_kw: w_turb_mech_kw,
        w_turb_kw: w_turb_kw,
        w_net_kw: w_net_kw,
        w_pump_kw: w_pump_kw,
        w_cp_pump_kw: w_cp_pump_kw,
        w_cond_parasitic_kw: w_cond_parasitic_kw,
        m_active: m_active,
        m_bypass: m_bypass,
        m_cp_actual: m_cp_actual,
        t_oil_sup: t_oil_sup,
        t_oil_sh_in: t_oil_sh_in_final,
        t_oil_sh_out: t_oil_sh_out,
        t_oil_ph_out: t_oil_ph_out,
        t_oil_ret_mixed: t_oil_ret_mixed,
        t_sat: t_sat,
        t_cp_sup: t_cp_sup,
        t_cp_exh: t_cp_exh,
        t_c_sat: t_c_sat,
        t_cp_liq_in: t_cp_liq_in,
        delta_t_pinch: delta_t_pinch,
        boiler_q: boiler_q.map(q => q / 1000.0),
        boiler_t_fg_out: boiler_t_fg_out,
        boiler_dp: boiler_dp,
        dp_bar: dp_bar,
        dp_pipe_bar: dp_pipe_bar,
        dp_pipes_sum_bar: dp_pipes_sum_bar,
        dp_static_bar: dp_static_bar,
        dp_hx_bar: dp_hx_bar,
        v_oil: v_oil,
        re_oil: re_oil,
        f_darcy: f_darcy,
        max_dp: max_dp,
        p_cond_actual: p_cond_actual,
        pr: pr,
        dh_is: dh_is / 1000.0, // in kJ/kg
        res_supply: res_supply,
        res_bin: res_bin,
        res_ret: res_ret,
        res_byp: res_byp
      });

      const boilerTelemetry = [];
      for (let i = 0; i < state.n_boilers; i++) {
        const m_i = state.m_oil * state.boilers[i].split;
        boilerTelemetry.push({
          index: i + 1,
          Q_kW: (boiler_q[i] || 0) / 1000.0,
          T_oil_out_C: (m_i > 0) ? (t_oil_ret_mixed + (boiler_q[i] / (m_i * (state.oil_cp || 2200.0)))) : t_oil_ret_mixed,
          T_flue_out_C: boiler_t_fg_out[i] || 0,
          m_oil_kg_s: m_i,
          dp_bar: boiler_dp[i] || 0
        });
      }

      const plant3DTelemetry = {
        n_boilers: state.n_boilers,
        boilers: boilerTelemetry,
        superheater: { Q_kW: q_sh / 1000.0, T_oil_in: t_oil_sh_in_final, T_cp_out: t_cp_sup },
        boiler: { Q_kW: q_ph / 1000.0, T_oil_out: t_oil_ph_out, T_sat: t_sat },
        turbine: { W_mech_kW: w_turb_mech_kw, W_el_kW: w_turb_kw, eta_is: turb_eta_is, dh_is_kJ: dh_is / 1000.0, pr: pr },
        condenser: { Q_kW: q_cond / 1000.0, type: state.condenser_type, W_parasitic_kW: w_cond_parasitic_kw, T_coolant_in_C: isAirCond ? state.T_air_in : state.T_cw_in },
        pump_oil: { W_kW: w_pump_kw, m_oil: state.m_oil, dp_bar: dp_bar },
        pump_cp: { W_kW: w_cp_pump_kw, m_cp: m_cp_actual, dp_bar: Math.max(0.0, state.P_evap_bar - p_cond_actual) },
        valve: { bypass_pct: state.bypass_ratio * 100.0, m_bypass_kg_s: m_bypass, m_active_kg_s: m_active },
        orc: { W_net_kW: w_net_kw, fluid: state.orc_fluid_sel, eta_cycle: (q_orc_total > 0 ? (w_net_kw / (q_orc_total / 1000.0)) : 0.0) }
      };
      window.latestCalcResult = plant3DTelemetry;

      if (typeof window.updatePlant3D === "function") {
        try {
          window.updatePlant3D(plant3DTelemetry);
        } catch (err3d) {
          console.warn("3D plant sync warning:", err3d);
        }
      }
    }

    function normalizeEquipmentId(rawEq) {
      let canon = String(rawEq || 'boiler_1').replace(/^node_/, '');
      if (canon === 'sh') canon = 'superheater';
      if (canon === 'ph') canon = 'preheater';
      return canon;
    }

    // Update Live Diagnostic HUD in Right-Side Inspector
    function updateInspectorLiveHUD(data) {
      const hud = document.getElementById('insp_live_hud');
      if (!hud) return;

      const eq = normalizeEquipmentId(state.selected_eq || 'boiler_1');
      let title = '';
      let badge = '';
      let rows = [];

      const bMatch = eq.match(/^boiler_?([1-5])?$/);
      if (bMatch || eq === 'boiler') {
        const bNum = bMatch && bMatch[1] ? parseInt(bMatch[1]) : 1;
        const bIdx = Math.max(0, Math.min(state.n_boilers - 1, bNum - 1));
        const q_b = (data.boiler_q && data.boiler_q[bIdx] !== undefined) ? data.boiler_q[bIdx] : 0;
        const t_fg_out = (data.boiler_t_fg_out && data.boiler_t_fg_out[bIdx] !== undefined) ? data.boiler_t_fg_out[bIdx] : 0;
        const dp_b = (data.boiler_dp && data.boiler_dp[bIdx] !== undefined) ? data.boiler_dp[bIdx] : 0;
        const splitPct = Math.round((state.boilers[bIdx].split || 0) * 100);
        const m_oil_b = ((state.boilers[bIdx].split || 0) * state.m_oil);

        const methodLabel = state.whru_solver_method || 'Kendi Algoritmamız (Epsilon-NTU)';
        const isLmtd = String(methodLabel).toLowerCase().includes('lmtd');
        const dt_pinch_boiler = t_fg_out - data.t_oil_ret_mixed;
        const pinchSafe = dt_pinch_boiler >= 15.0;
        const pinchStatus = pinchSafe
          ? `✅ Güvenli (${dt_pinch_boiler.toFixed(1)} °C)`
          : `⚠️ DÜŞÜK PINCH (${dt_pinch_boiler.toFixed(1)} < 15 °C)`;

        title = `📊 WHRU-${bIdx + 1} Canlı Telemetri (${isLmtd ? 'LMTD' : 'ε-NTU'})`;
        badge = `${q_b.toFixed(0)} kW`;
        rows = [
          { label: 'Kazan Isıl Gücü (Q_kazan):', val: `${q_b.toFixed(0)} kW`, color: '#ea580c' },
          { label: 'Ana Çözücü Algoritması:', val: methodLabel, color: '#0f3a5d' },
          { label: 'Akış Tipi & U Modu:', val: `${(state.whru_flow_type || 'Çapraz').split(' ')[0]} / ${(state.whru_u_mode || 'Basit').split(' ')[0]}`, color: '#475569' },
          { label: 'Baca Gazı Giriş / Çıkış:', val: `${state.boilers[bIdx].T_flue_in.toFixed(1)} °C ➔ ${t_fg_out.toFixed(1)} °C`, color: '#0f172a' },
          { label: 'Kızgın Yağ Debisi (Pay):', val: `${m_oil_b.toFixed(1)} kg/s (%${splitPct})`, color: '#0284c7' },
          { label: 'Yağ Döngüsü Sıcaklıkları:', val: `${data.t_oil_ret_mixed.toFixed(1)} °C ➔ ${data.t_oil_sup.toFixed(1)} °C`, color: '#0f172a' },
          { label: 'Kazan Pinch Farkı (ΔT_pinch):', val: pinchStatus, color: pinchSafe ? '#16a34a' : '#dc2626' },
          { label: 'Hidrolik Direnç (ΔP):', val: `${dp_b.toFixed(2)} bar`, color: '#475569' }
        ];
      } else if (eq.startsWith('pipe_')) {
        let pKey = eq.replace('pipe_', '');
        if (pKey === 'return') pKey = 'return_line';
        const pObj = (state.pipes && state.pipes[pKey]) ? state.pipes[pKey] : state.pipes.supply;
        const pRes = (pKey === 'boiler_inlet') ? data.res_bin : (pKey === 'bypass') ? data.res_byp : (pKey === 'return_line') ? data.res_ret : data.res_supply;

        const v = pRes ? pRes.v : 0;
        const velSafe = (v >= 1.2 && v <= 2.6);
        const velStatus = velSafe ? '✅ İdeal Hız' : (v < 1.0 ? '⚠️ Düşük / Çökelme' : '⚠️ Yüksek / Aşınma');
        title = `🔄 ${pObj.name} (${pObj.dn})`;
        badge = `${(pRes ? pRes.dp_bar : 0).toFixed(3)} bar`;
        rows = [
          { label: 'Nominal Çap / İç Çap:', val: `${pObj.dn} (Di = ${pObj.di_mm.toFixed(1)} mm)`, color: '#0f3a5d' },
          { label: 'Eşdeğer Hat Uzunluğu:', val: `${pObj.length_m.toFixed(1)} m`, color: '#0f172a' },
          { label: 'Akış Hızı (v):', val: `${v.toFixed(2)} m/s (${velStatus})`, color: velSafe ? '#16a34a' : '#d97706' },
          { label: 'Reynolds Sayısı (Re):', val: `${Math.round(pRes ? pRes.re : 0).toLocaleString('en-US')}`, color: '#0f172a' },
          { label: 'Darcy Sürtünme Faktörü (f):', val: `${(pRes ? pRes.f : 0.02).toFixed(4)}`, color: '#475569' },
          { label: 'Segment Basınç Kaybı (ΔP):', val: `${(pRes ? pRes.dp_bar : 0).toFixed(3)} bar`, color: '#ea580c' },
          { label: 'Toplam Hatlar Kaybı (ΣΔP_hat):', val: `${data.dp_pipes_sum_bar.toFixed(3)} bar`, color: '#0284c7' }
        ];
      } else if (eq === 'valve') {
        const isBypassActive = state.bypass_ratio > 0.01;
        const isFullBypass = state.bypass_ratio >= 0.98;
        title = '🔀 By-Pass Hattı Hidrolik Dengesi';
        badge = isFullBypass ? '🔴 Tam By-Pass' : (isBypassActive ? `🟡 %${Math.round(state.bypass_ratio * 100)} By-Pass` : '🟢 Tam Kapalı');
        rows = [
          { label: 'Eşanjörlere Giden Aktif Debi:', val: `${data.m_active.toFixed(1)} kg/s (%${Math.round((1 - state.bypass_ratio) * 100)})`, color: '#16a34a' },
          { label: 'By-Pass Edilen Yağ Debisi:', val: `${data.m_bypass.toFixed(1)} kg/s (%${Math.round(state.bypass_ratio * 100)})`, color: isBypassActive ? '#ea580c' : '#64748b' },
          { label: 'Kızgın Yağ Dağıtım Sıcaklığı:', val: `${data.t_oil_sup.toFixed(1)} °C`, color: '#0f172a' },
          { label: 'Dönüş Karışım Sıcaklığı:', val: `${data.t_oil_ret_mixed.toFixed(1)} °C`, color: '#0f172a' },
          { label: 'ORC Eşanjör Isı Transferi:', val: `${data.q_orc_total.toFixed(0)} kW`, color: '#0284c7' }
        ];
      } else if (eq === 'superheater') {
        title = `♨️ Süperheater (TEMA ${state.sh_tema_type})`;
        badge = `${data.q_sh.toFixed(0)} kW`;
        const dt_sup = data.t_cp_sup - data.t_sat;
        const p_des_sh = Math.max(16.0, state.P_evap_bar * 1.20);
        const r_sh_mm = 250.0;
        const ca_mm = 1.5;
        const s_mpa = 118.0;
        const e_eff = 0.85;
        const p_mpa = p_des_sh * 0.1;
        const t_min_sh = ((p_mpa * (r_sh_mm + ca_mm)) / (s_mpa * e_eff - 0.6 * p_mpa)) + ca_mm;

        rows = [
          { label: 'Kızdırıcı Isıl Gücü (Q_sh):', val: `${data.q_sh.toFixed(0)} kW`, color: '#ea580c' },
          { label: 'Yağ Giriş / Çıkış:', val: `${data.t_oil_sh_in.toFixed(1)} °C ➔ ${data.t_oil_sh_out.toFixed(1)} °C`, color: '#0f172a' },
          { label: 'ORC Akışkan Doyma / Aşırı Kızdırma:', val: `${data.t_sat.toFixed(1)} °C ➔ ${data.t_cp_sup.toFixed(1)} °C`, color: '#0284c7' },
          { label: 'Aşırı Kızdırma Farkı (ΔT_sup):', val: `${dt_sup.toFixed(1)} K ${dt_sup < 5.0 ? '⚠️ Düşük' : '✅ Kuru Buhar'}`, color: dt_sup < 5.0 ? '#dc2626' : '#16a34a' },
          { label: 'ASME UG-27 Cidar Kalınlığı (t_min):', val: `${t_min_sh.toFixed(1)} mm (P_des=${p_des_sh.toFixed(1)} bar, CA=${ca_mm}mm)`, color: '#0f3a5d' },
          { label: 'Aktif Yağ Debisi:', val: `${data.m_active.toFixed(1)} kg/s`, color: '#475569' }
        ];
      } else if (eq === 'preheater') {
        title = `💧 Kettle Reboiler (${(state.st_tema_type || 'K').split(' ')[0]}) & Evap`;
        badge = `${data.q_ph.toFixed(0)} kW`;
        const targetPinch = state.st_pinch_min_target || 8.0;
        const pinchTargetMet = data.delta_t_pinch >= targetPinch;
        const p_des_ph = Math.max(16.0, state.P_evap_bar * 1.20);
        const r_ph_mm = 350.0;
        const ca_mm_ph = 1.5;
        const p_mpa_ph = p_des_ph * 0.1;
        const t_min_ph = ((p_mpa_ph * (r_ph_mm + ca_mm_ph)) / (118.0 * 0.85 - 0.6 * p_mpa_ph)) + ca_mm_ph;
        rows = [
          { label: 'Buharlaştırıcı Isıl Gücü (Q_ph):', val: `${data.q_ph.toFixed(0)} kW`, color: '#ea580c' },
          { label: 'TEMA Tipi & Buhar Kubbesi:', val: `${(state.st_tema_type || 'K').split(' ')[0]} | Kubbe Çap Oranı: ${state.st_kettle_dome_ratio.toFixed(2)}`, color: '#0f3a5d' },
          { label: 'Demister (Damla Tutucu):', val: `${(state.st_demister_type || 'SS316').split(' ')[0]}`, color: '#475569' },
          { label: 'Yağ Giriş / Çıkış:', val: `${data.t_oil_sh_out.toFixed(1)} °C ➔ ${data.t_oil_ph_out.toFixed(1)} °C`, color: '#0f172a' },
          { label: 'Doyma Sıcaklığı (T_sat):', val: `${data.t_sat.toFixed(1)} °C (${state.P_evap_bar.toFixed(1)} bar)`, color: '#0284c7' },
          { label: 'Pinch Yaklaşımı (ΔT_pinch):', val: `${data.delta_t_pinch.toFixed(1)} °C (Hedef: ≥${targetPinch.toFixed(1)} °C) ${pinchTargetMet ? '✅ Sağlandı' : '⚠️ PINCH İHLALİ'}`, color: pinchTargetMet ? '#16a34a' : '#dc2626' },
          { label: 'ASME UG-27 Kettle Gövde (t_min):', val: `${t_min_ph.toFixed(1)} mm (Kubbe R=${r_ph_mm}mm, P_des=${p_des_ph.toFixed(1)} bar)`, color: '#0f3a5d' },
          { label: 'ORC Buharlaşma Debisi:', val: `${data.m_cp_actual.toFixed(2)} kg/s`, color: '#0891b2' },
          { label: 'Şaşırtma (Baffle Cut / Pitch):', val: `%${state.st_baffle_cut.toFixed(0)} / ${state.st_baffle_pitch.toFixed(0)} mm`, color: '#64748b' }
        ];
      } else if (eq === 'condenser') {
        const isAir = (state.condenser_type === 'air');
        const itd = isAir ? (data.t_c_sat - state.T_air_in) : (data.t_c_sat - state.T_cw_in);
        const subcool = Math.max(0.0, data.t_c_sat - data.t_cp_liq_in);
        title = isAir ? '💨 ACC Hava Soğutmalı Kondenser' : '❄️ Su Soğutmalı Kondenser (Shell & Tube)';
        badge = `${data.q_cond.toFixed(0)} kW`;
        rows = [
          { label: 'Atılan Isı Yükü (Q_cond):', val: `${data.q_cond.toFixed(0)} kW`, color: '#0284c7' },
          { label: 'Yoğuşma Sıcaklığı / Basıncı:', val: `${data.t_c_sat.toFixed(1)} °C (${data.p_cond_actual.toFixed(2)} bar)`, color: '#0f172a' },
          { label: 'Sıvı Kondensat Çıkış Sıcaklığı:', val: `${data.t_cp_liq_in.toFixed(1)} °C`, color: '#0f172a' },
          { label: 'Aşırı Soğutma (Subcooling):', val: `${subcool.toFixed(1)} K ✅ Güvenli`, color: '#16a34a' },
          { label: 'Giriş Sıcaklık Farkı (ITD):', val: `${itd.toFixed(1)} K ${itd < 10.0 ? '⚠️ Düşük ITD' : '✅ Normal'}`, color: itd < 10.0 ? '#dc2626' : '#16a34a' },
          { label: 'Kondenser Parazitik Güç:', val: `${data.w_cond_parasitic_kw.toFixed(1)} kW`, color: '#64748b' }
        ];

        if (state.enable_multizone) {
          const cp_v = getActiveOrcFluid().cp_vap || 1700.0;
          const cp_l = getActiveOrcFluid().cp_liq || 2200.0;
          const q_desup_kw = (data.m_cp_actual * cp_v * Math.max(0.0, data.t_cp_exh - data.t_c_sat)) / 1000.0;
          const q_sub_kw = (data.m_cp_actual * cp_l * Math.max(0.0, data.t_c_sat - data.t_cp_liq_in)) / 1000.0;
          const q_cond_latent_kw = Math.max(0.0, data.q_cond - q_desup_kw - q_sub_kw);

          rows.push({
            label: '🔬 3-Bölge Isı Dağılımı:',
            val: `Kızgınlık: ${q_desup_kw.toFixed(0)} kW | Yoğuşma: ${q_cond_latent_kw.toFixed(0)} kW | Aşırı Soğutma: ${q_sub_kw.toFixed(0)} kW`,
            color: '#7c3aed'
          });
        }
      } else if (eq === 'cp_pump') {
        const activeOrcFluid = getActiveOrcFluid();
        const [antA, antB, antC] = activeOrcFluid.antoine || [6.88676, 1121.1, 230.56];
        const p_sat_cp = Math.max(0.05, Math.pow(10, antA - antB / (data.t_cp_liq_in + antC)) / 750.06168);
        const npsh_a = Math.max(0.0, ((data.p_cond_actual - p_sat_cp) * 1e5 / (activeOrcFluid.rho_liq * 9.81)) + state.z_hw - 0.2);
        const npsh_r = 1.6 + 1.0 * Math.pow(data.m_cp_actual / 11.5, 2);
        const margin = npsh_a - npsh_r;
        const cavSafe = margin >= 0.5;
        title = '⚡ ORC Sıvı Besleme Pompası';
        badge = `${data.w_cp_pump_kw.toFixed(1)} kW`;
        rows = [
          { label: 'Sıvı Basma Gücü (W_besleme):', val: `${data.w_cp_pump_kw.toFixed(1)} kW`, color: '#7c3aed' },
          { label: 'Basınç Yükseltme (ΔP):', val: `${data.p_cond_actual.toFixed(2)} ➔ ${state.P_evap_bar.toFixed(1)} bar`, color: '#0f172a' },
          { label: 'Sıvı Kütlesel Debisi:', val: `${data.m_cp_actual.toFixed(2)} kg/s`, color: '#0284c7' },
          { label: 'Kavitasyon Güvenlik Payı (NPSH):', val: `${margin.toFixed(2)} m ${cavSafe ? '✅ Güvenli' : '⚠️ KAVİTASYON RİSKİ'}`, color: cavSafe ? '#16a34a' : '#dc2626' },
          { label: 'Hotwell Emiş Yüksekliği (z_hw):', val: `${state.z_hw.toFixed(1)} m`, color: '#475569' }
        ];
      } else if (eq === 'turbine') {
        const isDry = data.t_cp_exh > data.t_c_sat;
        title = `⚡ ORC Türbini (${state.orc_fluid_sel})`;
        badge = `${data.w_turb_kw.toFixed(0)} kW`;
        rows = [
          { label: 'İzantropik Entalpi Farkı (Δh_is):', val: `${data.dh_is.toFixed(1)} kJ/kg`, color: '#9333ea' },
          { label: 'Basınç Oranı (PR):', val: `${data.pr.toFixed(2)} (P_in=${state.P_evap_bar.toFixed(1)} / P_exh=${data.p_cond_actual.toFixed(2)})`, color: '#0f172a' },
          { label: 'Brüt Mekanik Güç (W_mech):', val: `${data.w_turb_mech_kw.toFixed(0)} kW (η_is = %${Math.round((state.turb_eta_is || 0.85)*100)})`, color: '#16a34a' },
          { label: 'Jeneratör Elektrik Gücü (W_el):', val: `${data.w_turb_kw.toFixed(0)} kW (η_gen = %${Math.round((state.turb_eta_gen || 0.96)*100)})`, color: '#0284c7' },
          { label: 'Giriş / Egzoz Sıcaklığı:', val: `${data.t_cp_sup.toFixed(1)} °C ➔ ${data.t_cp_exh.toFixed(1)} °C`, color: '#0f172a' },
          { label: 'Kuru Buhar / Aşınma Durumu:', val: isDry ? '✅ Kuru Genleşme (Sıfır Aşınma)' : '⚠️ Sıvı Yoğuşma Riski', color: isDry ? '#16a34a' : '#dc2626' }
        ];
      } else if (eq === 'pump') {
        const v = data.v_oil || 0;
        const velSafe = (v >= 1.2 && v <= 2.6);
        const velStatus = velSafe ? '✅ Optimum Hız' : (v < 1.0 ? '⚠️ Düşük Hız / Çökelme' : '⚠️ Yüksek Hız / Aşınma');
        title = `🔄 Yağ Sirkülasyon Pompası (${state.oil_fluid_sel})`;
        badge = `${data.w_pump_kw.toFixed(1)} kW`;
        rows = [
          { label: 'Pompa Tüketimi (W_pompa):', val: `${data.w_pump_kw.toFixed(1)} kW`, color: '#ea580c' },
          { label: 'Döngü Akışkanı:', val: `${state.oil_fluid_sel} (ρ=${state.oil_rho} kg/m³)`, color: '#0f3a5d' },
          { label: 'Hatlar Sürtünme Kaybı (ΣΔP_hat):', val: `${data.dp_pipes_sum_bar.toFixed(3)} bar`, color: '#0284c7' },
          { label: 'Kazan Demetleri Kaybı (ΔP_kazan):', val: `${data.max_dp.toFixed(3)} bar`, color: '#475569' },
          { label: 'Eşanjörler Direnç Kaybı (ΔP_eşanjör):', val: `${data.dp_hx_bar.toFixed(3)} bar`, color: '#475569' },
          { label: 'Statik Kot Farkı (ΔP_statik):', val: `${data.dp_static_bar.toFixed(3)} bar (${(state.static_elevation_m ?? 8.0).toFixed(1)} m)`, color: '#0f172a' },
          { label: 'Toplam Karşı Basınç (ΔP_toplam):', val: `${data.dp_bar.toFixed(3)} bar`, color: '#0f172a' }
        ];
      }

      hud.innerHTML = `
        <div style="background:#f8fafc; border:1px solid #cbd5e1; border-radius:8px; padding:10px; margin-top:10px; box-shadow:0 1px 3px rgba(0,0,0,0.04);">
          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px; border-bottom:1px solid #e2e8f0; padding-bottom:5px;">
            <span style="font-size:12px; font-weight:700; color:#0f3a5d;">${title}</span>
            <span style="font-size:11px; font-weight:800; background:#e0f2fe; color:#0369a1; padding:2px 6px; border-radius:4px;">${badge}</span>
          </div>
          <div style="display:flex; flex-direction:column; gap:4px;">
            ${rows.map(r => `
              <div style="display:flex; justify-content:space-between; font-size:11.5px;">
                <span style="color:#64748b; font-weight:500;">${r.label}</span>
                <b style="color:${r.color};">${r.val}</b>
              </div>
            `).join('')}
          </div>
        </div>
      `;
    }

    // Equipment Inspector selection & rendering
    function makeParamControl(key, label, min, max, step, val, unit, isPct = false) {
      const displayVal = isPct ? Math.round(val * 100.0) : val;
      const minVal = isPct ? Math.round(min * 100.0) : min;
      const maxVal = isPct ? Math.round(max * 100.0) : max;
      const stepVal = isPct ? Math.round(step * 100.0) : step;

      return `
        <div class="param-group">
          <div class="param-title">
            <span>${label}</span>
          </div>
          <div class="param-controls-row">
            <input type="range" class="param-slider" id="rng_${key}" min="${minVal}" max="${maxVal}" step="${stepVal}" value="${displayVal}"
              oninput="onParamInput('${key}', this.value, 'slider', ${isPct})">
            <div class="param-num-wrap">
              <input type="number" class="param-num-input" id="num_${key}" min="${minVal}" max="${maxVal}" step="any" value="${displayVal}"
                oninput="onParamInput('${key}', this.value, 'num', ${isPct})">
              <span class="param-unit-badge">${unit}</span>
            </div>
          </div>
        </div>
      `;
    }

    function onParamInput(key, val, source, isPct = false) {
      let numVal = parseFloat(val);
      if (isNaN(numVal)) return;

      // Check if updating an array boiler property (e.g. b1_T_flue_in, b1_split, b1_m_oil)
      const bMatch = key.match(/^b([1-5])_(.+)$/);
      if (bMatch) {
        const bIdx = parseInt(bMatch[1]) - 1;
        const prop = bMatch[2];
        if (prop === 'split') {
          const newSplit = (state.n_boilers === 1) ? 1.0 : Math.max(0.0, Math.min(1.0, isPct ? numVal / 100.0 : numVal));
          state.boilers[bIdx].split = newSplit;
          const flowEl = document.getElementById(`num_b${bIdx + 1}_m_oil`);
          if (flowEl) flowEl.value = (newSplit * state.m_oil).toFixed(1);
        } else if (prop === 'm_oil') {
          // Direct flow in kg/s: compute split
          const newFlow = Math.max(0.0, numVal);
          const newSplit = (state.n_boilers === 1) ? 1.0 : (state.m_oil > 0 ? (newFlow / state.m_oil) : 0.0);
          state.boilers[bIdx].split = newSplit;
          const numSplit = document.getElementById(`num_b${bIdx + 1}_split`);
          if (numSplit) numSplit.value = Math.round(newSplit * 100);
          const rngSplit = document.getElementById(`rng_b${bIdx + 1}_split`);
          if (rngSplit) rngSplit.value = Math.round(newSplit * 100);
        } else {
          if (isPct) {
            state.boilers[bIdx][prop] = numVal / 100.0;
          } else {
            state.boilers[bIdx][prop] = numVal;
          }
          if (prop === 'T_flue_in' && !state.flue_gas_is_manual) {
            updateFlueGasPropertiesFromMix(bIdx);
            const cpEl = document.getElementById('num_flue_gas_cp');
            if (cpEl) cpEl.value = Math.round(state.flue_gas_cp);
            const rngCp = document.getElementById('rng_flue_gas_cp');
            if (rngCp) rngCp.value = Math.round(state.flue_gas_cp);

            const rhoEl = document.getElementById('num_flue_gas_rho');
            if (rhoEl) rhoEl.value = state.flue_gas_rho.toFixed(2);
            const rngRho = document.getElementById('rng_flue_gas_rho');
            if (rngRho) rngRho.value = state.flue_gas_rho.toFixed(2);

            const muEl = document.getElementById('num_flue_gas_mu');
            if (muEl) muEl.value = state.flue_gas_mu.toFixed(6);
            const rngMu = document.getElementById('rng_flue_gas_mu');
            if (rngMu) rngMu.value = state.flue_gas_mu.toFixed(6);
          }
        }
      } else {
        // Check if pipe property e.g. pipe_supply_di_mm
        const pMatch = key.match(/^pipe_([a-z_]+)_(di_mm|length_m|roughness_mm)$/);
        if (pMatch && state.pipes) {
          let pKey = pMatch[1];
          if (pKey === 'return') pKey = 'return_line';
          const pProp = pMatch[2];
          if (state.pipes[pKey]) {
            state.pipes[pKey][pProp] = numVal;
            if (pKey === 'supply' && pProp === 'di_mm') state.pipe_di_mm = numVal;
            if (pKey === 'supply' && pProp === 'length_m') state.pipe_length_m = numVal;
          }
        } else {
          if (isPct) {
            state[key] = numVal / 100.0;
          } else {
            state[key] = numVal;
          }
          if (key === 'flue_gas_cp' || key === 'flue_gas_rho' || key === 'flue_gas_mu') {
            state.flue_gas_is_manual = true;
            const badge = document.getElementById('flue_gas_status_badge');
            if (badge) badge.innerHTML = '<span class="badge-manual">📝 Manuel Giriş</span>';
          }
        }
      }

      if (source === 'slider') {
        const numInput = document.getElementById('num_' + key);
        if (numInput) numInput.value = numVal;
      } else if (source === 'num') {
        const slider = document.getElementById('rng_' + key);
        if (slider) slider.value = numVal;
      }

      recalculate();
    }

    function selectEquipment(rawEq) {
      const eq = normalizeEquipmentId(rawEq);
      state.selected_eq = eq;
      if (typeof window.sync3DSelectedEquipment === "function") {
        try { window.sync3DSelectedEquipment(eq); } catch (e) {}
      }
      document.querySelectorAll('.equipment-node').forEach(el => el.classList.remove('active'));
      document.querySelectorAll('.pipe-clickable').forEach(el => el.classList.remove('active'));

      const eqMap = {
        boiler: 'boiler_1',
        boiler_1: 'boiler_1',
        boiler_2: 'boiler_2',
        boiler_3: 'boiler_3',
        boiler_4: 'boiler_4',
        boiler_5: 'boiler_5',
        valve: 'valve',
        superheater: 'sh',
        preheater: 'ph',
        pump: 'pump',
        turbine: 'turbine',
        condenser: 'condenser',
        cp_pump: 'cp_pump'
      };
      const activeEl = document.getElementById('node_' + (eqMap[eq] || eq));
      if (activeEl) activeEl.classList.add('active');

      // Highlight active clicked pipe
      if (eq === 'pipe_supply') {
        document.querySelectorAll('.pipe-sup').forEach(el => el.classList.add('active'));
      } else if (eq === 'pipe_boiler_inlet') {
        document.querySelectorAll('.pipe-bin').forEach(el => el.classList.add('active'));
      } else if (eq === 'pipe_bypass') {
        document.querySelectorAll('.pipe-byp').forEach(el => el.classList.add('active'));
      } else if (eq === 'pipe_return') {
        document.querySelectorAll('.pipe-ret').forEach(el => el.classList.add('active'));
      }

      const title = document.getElementById('insp_title');
      const desc = document.getElementById('insp_desc');
      const c = document.getElementById('insp_controls');

      // Check if a boiler was selected (boiler_1 .. boiler_5)
      const bMatch = eq.match(/^boiler_?([1-5])?$/);
      if (bMatch || eq === 'boiler') {
        const bNum = bMatch && bMatch[1] ? parseInt(bMatch[1]) : 1;
        const bIdx = bNum - 1;
        const b = state.boilers[bIdx];

        title.innerHTML = `🔥 Atık Isı Baca Kazanı ${bNum} (WHRU-${bNum})`;
        desc.innerText = `${bNum}. Hat Baca Kazanı mimarisi, çözücü yöntemi ve akışkan parametreleri.`;

        const curFlow = ((b.split || 0) * state.m_oil);
        const sumFlow = state.boilers.slice(0, state.n_boilers).reduce((acc, curr) => acc + (curr.split || 0) * state.m_oil, 0);
        const isUnbalanced = Math.abs(sumFlow - state.m_oil) > 0.05;

        let solverOptionsHtml = `
          <div class="insp-section-header oil">⚙️ WHRU Mimarisi & Çözücü Ayarları</div>
          <div class="param-group">
            <div class="param-title"><span>Eşanjör Tipi (WHRU Mimarisi)</span></div>
            <select class="param-select" onchange="setWhruExchType(this.value)">
              <option value="Kanatçıklı Borulu (Finned Tube - WHRU Baca Kazanı)" ${state.whru_exch_type.includes('Kanatçıklı') ? 'selected' : ''}>Kanatçıklı Borulu (Finned Tube - WHRU Baca Kazanı)</option>
              <option value="Gövde Borulu (Shell & Tube TEMA)" ${state.whru_exch_type.includes('Gövde Borulu') ? 'selected' : ''}>Gövde Borulu (Shell & Tube TEMA)</option>
              <option value="Çift Borulu (Hairpin / Double Pipe)" ${state.whru_exch_type.includes('Çift Borulu') ? 'selected' : ''}>Çift Borulu (Hairpin / Double Pipe)</option>
              <option value="Plakalı (PHE - Contalı / Kaynaklı)" ${state.whru_exch_type.includes('Plakalı') ? 'selected' : ''}>Plakalı (PHE - Contalı / Kaynaklı)</option>
            </select>
          </div>
          <div class="param-group">
            <div class="param-title"><span>Ana Çözücü Algoritması</span></div>
            <select class="param-select" onchange="setWhruSolverMethod(this.value)">
              <option value="Kendi Algoritmamız (Epsilon-NTU)" ${state.whru_solver_method === 'Kendi Algoritmamız (Epsilon-NTU)' ? 'selected' : ''}>Kendi Algoritmamız (Epsilon-NTU)</option>
              <option value="Kendi Algoritmamız (LMTD)" ${state.whru_solver_method === 'Kendi Algoritmamız (LMTD)' ? 'selected' : ''}>Kendi Algoritmamız (LMTD)</option>
              <option value="HT Kütüphanesi (Epsilon-NTU)" ${state.whru_solver_method === 'HT Kütüphanesi (Epsilon-NTU)' ? 'selected' : ''}>HT Kütüphanesi (Epsilon-NTU)</option>
              <option value="HT Kütüphanesi (LMTD)" ${state.whru_solver_method === 'HT Kütüphanesi (LMTD)' ? 'selected' : ''}>HT Kütüphanesi (LMTD)</option>
            </select>
          </div>
          <div class="param-group">
            <div class="param-title"><span>Akış Konfigürasyonu</span></div>
            <select class="param-select" onchange="setWhruFlowType(this.value)">
              <option value="Çapraz Akış (Her İki Akışkan Karışmamış)" ${state.whru_flow_type === 'Çapraz Akış (Her İki Akışkan Karışmamış)' ? 'selected' : ''}>Çapraz Akış (Her İki Akışkan Karışmamış)</option>
              <option value="Ters Akış (Counter-Current)" ${state.whru_flow_type === 'Ters Akış (Counter-Current)' ? 'selected' : ''}>Ters Akış (Counter-Current)</option>
              <option value="Paralel Akış (Co-Current)" ${state.whru_flow_type === 'Paralel Akış (Co-Current)' ? 'selected' : ''}>Paralel Akış (Co-Current)</option>
            </select>
          </div>
          <div class="param-group">
            <div class="param-title"><span>Hesaplama Amacı</span></div>
            <select class="param-select" onchange="setWhruCalcPurpose(this.value)">
              <option value="Performans / Rating (Mevcut Alan ile Doğrulama)" ${state.whru_calc_purpose === 'Performans / Rating (Mevcut Alan ile Doğrulama)' ? 'selected' : ''}>Performans / Rating (Mevcut Alan ile Doğrulama)</option>
              <option value="Boyutlandırma (Alan / Çıkış Sıcaklığı)" ${state.whru_calc_purpose === 'Boyutlandırma (Alan / Çıkış Sıcaklığı)' ? 'selected' : ''}>Boyutlandırma (Alan / Çıkış Sıcaklığı)</option>
            </select>
          </div>
          ${state.whru_calc_purpose.includes('Boyutlandırma') ? `
            ${makeParamControl('whru_T_hot_out_opt', 'Hedef Baca Gazı Çıkış (T_hot,out)', 100, 350, 5, state.whru_T_hot_out_opt, '°C')}
            ${makeParamControl('whru_T_cold_out_opt', 'Hedef Yağ Çıkış Sıcaklığı (T_cold,out)', 150, 330, 5, state.whru_T_cold_out_opt, '°C')}
          ` : ''}
          <div class="param-group">
            <div class="param-title"><span>U Katsayısı Yöntemi</span></div>
            <select class="param-select" onchange="setWhruUMode(this.value)">
              <option value="Basit Mod (Manuel U Değeri)" ${state.whru_u_mode === 'Basit Mod (Manuel U Değeri)' ? 'selected' : ''}>Basit Mod (Manuel U Değeri)</option>
              <option value="Geometrik Mod (Malzeme ve Çap ile Hesapla)" ${state.whru_u_mode === 'Geometrik Mod (Malzeme ve Çap ile Hesapla)' ? 'selected' : ''}>Geometrik Mod (Malzeme ve Çap ile Hesapla)</option>
            </select>
          </div>
          ${makeParamControl(`b${bNum}_UA`, `Kazan ${bNum} Isı Transfer Katsayısı (UA)`, 10, 80, 1, b.UA, 'kW/K')}
        `;

        const flueMixTotal = Object.values(state.flue_gas_mix || {}).reduce((a, b) => a + (parseFloat(b) || 0), 0);
        const isNormOk = Math.abs(flueMixTotal - 100.0) < 0.2;

        let hotControlsHtml = `
          <div class="insp-section-header hot">🔴 Sıcak Akışkan (Hot Side - Baca Gazı)</div>
          ${makeParamControl(`b${bNum}_T_flue_in`, `Baca Gazı ${bNum} Giriş Sıcaklığı`, 350, 550, 5, b.T_flue_in, '°C')}
          ${makeParamControl(`b${bNum}_m_flue`, `Baca Gazı ${bNum} Debisi`, 5, 45, 0.5, b.m_flue, 'kg/s')}

          <div class="flue-gas-box">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
              <span style="font-weight:700; font-size:11.5px; color:#991b1b;">🔧 Sıcak Akışkan Egzoz Gazı Kompozisyonu</span>
              <span id="flue_gas_status_badge">${state.flue_gas_is_manual ? '<span class="badge-manual">📝 Manuel Giriş</span>' : '<span class="badge-auto">⚡ Otomatik Hesap</span>'}</span>
            </div>

            <div style="font-size:10px; color:#64748b; margin-bottom:4px;">Hazır Şablonlar:</div>
            <div class="flue-gas-preset-row">
              <button type="button" class="btn-preset ${state.flue_gas_preset === 'Doğal Gaz' ? 'active' : ''}" onclick="applyFlueGasPreset('Doğal Gaz', ${bNum})">🔥 Doğal Gaz</button>
              <button type="button" class="btn-preset ${state.flue_gas_preset === 'Kömür' ? 'active' : ''}" onclick="applyFlueGasPreset('Kömür', ${bNum})">⛏️ Kömür</button>
              <button type="button" class="btn-preset ${state.flue_gas_preset === 'Biyogaz' ? 'active' : ''}" onclick="applyFlueGasPreset('Biyogaz', ${bNum})">🌱 Biyogaz</button>
              <button type="button" class="btn-preset ${state.flue_gas_preset === 'Özel (Custom)' ? 'active' : ''}" onclick="applyFlueGasPreset('Özel (Custom)', ${bNum})">⚙️ Özel</button>
            </div>

            <div style="font-size:10px; color:#64748b; margin:6px 0 2px 0;">Kompozisyon Bazı:</div>
            <div class="basis-toggle-row">
              <button type="button" class="btn-basis ${state.flue_gas_basis === 'mole' ? 'active' : ''}" onclick="setFlueGasBasis('mole', ${bNum})">Molar Yüzde (%)</button>
              <button type="button" class="btn-basis ${state.flue_gas_basis === 'mass' ? 'active' : ''}" onclick="setFlueGasBasis('mass', ${bNum})">Kütlesel Yüzde (%)</button>
            </div>

            <div class="flue-comp-grid">
              <div class="flue-comp-cell">
                <span class="flue-comp-label">N₂ (Azot)</span>
                <input type="number" class="flue-comp-input" step="0.5" min="0" max="100" value="${(state.flue_gas_mix.Nitrogen || 0).toFixed(1)}" oninput="onFlueGasCompChange('Nitrogen', this.value, ${bNum})">
              </div>
              <div class="flue-comp-cell">
                <span class="flue-comp-label">O₂ (Oksijen)</span>
                <input type="number" class="flue-comp-input" step="0.5" min="0" max="100" value="${(state.flue_gas_mix.Oxygen || 0).toFixed(1)}" oninput="onFlueGasCompChange('Oxygen', this.value, ${bNum})">
              </div>
              <div class="flue-comp-cell">
                <span class="flue-comp-label">CO₂ (Karbondioksit)</span>
                <input type="number" class="flue-comp-input" step="0.5" min="0" max="100" value="${(state.flue_gas_mix.CarbonDioxide || 0).toFixed(1)}" oninput="onFlueGasCompChange('CarbonDioxide', this.value, ${bNum})">
              </div>
              <div class="flue-comp-cell">
                <span class="flue-comp-label">H₂O (Su Buharı)</span>
                <input type="number" class="flue-comp-input" step="0.5" min="0" max="100" value="${(state.flue_gas_mix.Water || 0).toFixed(1)}" oninput="onFlueGasCompChange('Water', this.value, ${bNum})">
              </div>
              <div class="flue-comp-cell">
                <span class="flue-comp-label">SO₂ (Kükürtdioksit)</span>
                <input type="number" class="flue-comp-input" step="0.1" min="0" max="100" value="${(state.flue_gas_mix.SulfurDioxide || 0).toFixed(1)}" oninput="onFlueGasCompChange('SulfurDioxide', this.value, ${bNum})">
              </div>
              <div class="flue-comp-cell">
                <span class="flue-comp-label">Ar (Argon)</span>
                <input type="number" class="flue-comp-input" step="0.1" min="0" max="100" value="${(state.flue_gas_mix.Argon || 0).toFixed(1)}" oninput="onFlueGasCompChange('Argon', this.value, ${bNum})">
              </div>
            </div>

            <div style="display:flex; justify-content:space-between; align-items:center; font-size:10.5px; padding:3px 2px; color:#475569;">
              <span>Toplam: <b>%${flueMixTotal.toFixed(1)}</b></span>
              <span>${isNormOk ? '<span style="color:#16a34a; font-weight:700;">✅ Dengeli</span>' : '<span style="color:#dc2626; font-weight:700;">⚠️ Normalize Edilecek</span>'}</span>
            </div>
            ${state.flue_gas_is_manual ? `
              <button type="button" class="btn-balance-action" style="background:#0284c7; margin-top:6px;" onclick="resetFlueGasToAuto(${bNum})">🔄 Kompozisyondan Yeniden Hesapla</button>
            ` : ''}
          </div>

          <div style="font-size:11px; font-weight:700; color:#334155; margin:10px 0 4px 0;">
            Termofiziksel Özellikler (Kompozisyondan veya Manuel):
          </div>
          ${makeParamControl('flue_gas_cp', 'Baca Gazı Özgül Isısı (Cp,hot)', 900, 1400, 10, state.flue_gas_cp, 'J/kgK')}
          ${makeParamControl('flue_gas_rho', 'Baca Gazı Yoğunluğu (ρ_hot)', 0.30, 1.20, 0.02, state.flue_gas_rho, 'kg/m³')}
          ${makeParamControl('flue_gas_mu', 'Baca Gazı Viskozitesi (μ_hot)', 0.000015, 0.000055, 0.000001, state.flue_gas_mu, 'Pa.s')}
        `;

        let coldControlsHtml = `
          <div class="insp-section-header cold">🔵 Soğuk Akışkan (Cold Side - Kızgın Yağ)</div>
          ${makeParamControl(`b${bNum}_split`, `Kızgın Yağ Debisi Payı (% WHRU-${bNum})`, 0, 1, 0.05, b.split, '%', true)}
          <div class="param-group">
            <div class="param-title"><span>WHRU-${bNum} Yağ Kütlesel Debisi</span></div>
            <div class="param-controls-row">
              <input type="number" class="param-num-input" id="num_b${bNum}_m_oil" min="0" max="${state.m_oil}" step="0.5" value="${curFlow.toFixed(1)}"
                oninput="onParamInput('b${bNum}_m_oil', this.value, 'direct_flow')" style="flex:1;">
              <span class="param-unit-badge">kg/s</span>
            </div>
          </div>
          ${isUnbalanced ? `
            <div class="balance-warning-box">
              ⚠️ <b>Hidrolik Debi Uyuşmazlığı:</b><br>
              WHRU Kazanları Toplamı: <b>${sumFlow.toFixed(1)} kg/s</b> ≠ Pompa: <b>${state.m_oil.toFixed(1)} kg/s</b> (Fark: ${(sumFlow - state.m_oil).toFixed(1)} kg/s)
              <button class="btn-balance-action" onclick="autoBalanceBoilerFlows()">⚖️ Otomatik Dengele (%${(100/state.n_boilers).toFixed(0)} Eşit Paylaştır)</button>
            </div>
          ` : ''}
          ${makeParamControl('oil_cp', 'Kızgın Yağ Özgül Isı (Cp,oil)', 1500, 3000, 10, state.oil_cp, 'J/kgK')}
          ${makeParamControl('oil_rho', 'Kızgın Yağ Yoğunluğu (ρ_oil)', 700, 1100, 5, state.oil_rho, 'kg/m³')}
        `;

        let actionsHtml = `
          <div style="margin-top:8px; display:flex; gap:6px;">
            <button class="btn-whru-action btn-whru-add" style="flex:1; justify-content:center; padding:7px;" onclick="changeBoilerCount(1)">
              ➕ Yeni WHRU Kazanı Ekle (${state.n_boilers}/5)
            </button>
            ${state.n_boilers > 1 ? `
            <button class="btn-whru-action btn-whru-del" style="flex:1; justify-content:center; padding:7px;" onclick="changeBoilerCount(-1)">
              ➖ 1 Kazan Eksilt
            </button>` : ''}
          </div>
        `;
        c.innerHTML = solverOptionsHtml + hotControlsHtml + coldControlsHtml + actionsHtml;
      } else if (eq.startsWith('pipe_')) {
        let pKey = eq.replace('pipe_', '');
        if (pKey === 'return') pKey = 'return_line';
        if (!state.pipes || !state.pipes[pKey]) pKey = 'supply';

        const pData = state.pipes[pKey];
        title.innerHTML = `🔄 ${pData.name}`;
        desc.innerText = `Darcy-Weisbach ve Swamee-Jain formülleriyle hat sürtünmesi ve basınç kaybı hesabı.`;

        let tabsHtml = `
          <div class="pipe-tab-group">
            <button class="pipe-tab-btn ${pKey === 'supply' ? 'active' : ''}" onclick="selectEquipment('pipe_supply')">🔥 Sıcak Besleme</button>
            <button class="pipe-tab-btn ${pKey === 'boiler_inlet' ? 'active' : ''}" onclick="selectEquipment('pipe_boiler_inlet')">📥 Kazan Giriş</button>
            <button class="pipe-tab-btn ${pKey === 'bypass' ? 'active' : ''}" onclick="selectEquipment('pipe_bypass')">🔀 By-Pass</button>
            <button class="pipe-tab-btn ${pKey === 'return_line' ? 'active' : ''}" onclick="selectEquipment('pipe_return')">📤 Soğuk Dönüş</button>
          </div>
        `;

        const dnOptions = [
          { val: 'DN80', label: 'DN80 (Di=82.5 mm)' },
          { val: 'DN100', label: 'DN100 (Di=102.3 mm)' },
          { val: 'DN125', label: 'DN125 (Di=127.0 mm)' },
          { val: 'DN150', label: 'DN150 (Di=154.0 mm)' },
          { val: 'DN200', label: 'DN200 (Di=204.9 mm)' },
          { val: 'Custom', label: 'Özel / Manuel' }
        ];

        let selectDnHtml = `
          <div class="param-group">
            <div class="param-title"><span>Boru Nominal Çapı (DN)</span></div>
            <select class="param-select" onchange="onPipeDnSelect('${pKey}', this.value)">
              ${dnOptions.map(opt => `<option value="${opt.val}" ${pData.dn === opt.val ? 'selected' : ''}>${opt.label}</option>`).join('')}
            </select>
          </div>
        `;

        let controlsHtml = tabsHtml + selectDnHtml +
          makeParamControl(`pipe_${pKey}_di_mm`, 'Boru İç Çapı (Di)', 40, 300, 1, pData.di_mm, 'mm') +
          makeParamControl(`pipe_${pKey}_length_m`, 'Eşdeğer Hat Uzunluğu (Leq)', 2, 250, 1, pData.length_m, 'm') +
          makeParamControl(`pipe_${pKey}_roughness_mm`, 'Boru Yüzey Pürüzlülüğü (ε)', 0.01, 0.20, 0.005, pData.roughness_mm, 'mm') +
          `<p style="font-size:11px; color:#475569; line-height:1.4; margin-top:8px; background:#f8fafc; padding:8px; border-radius:6px; border-left:3px solid #0f3a5d;">
            ⚡ <b>Hidrolik Dağılım:</b> Bu borunun basınç kaybı toplam pompa karşı basıncına (ΔP_toplam = ΣΔP_hat + ΔP_kazan + ΔP_eşanjör + ΔP_statik) eklenir.
          </p>`;

        c.innerHTML = controlsHtml;
      } else if (eq === 'valve') {
        title.innerHTML = '🔀 Oransal By-Pass Vanası & Hattı';
        desc.innerText = 'Kızgın yağı eşanjörlere sokmadan doğrudan dönüşe yönlendirir.';
        c.innerHTML =
          makeParamControl('bypass_ratio', 'By-Pass Açıklık Oranı', 0, 1, 0.02, state.bypass_ratio, '%', true) +
          `<p style="font-size:11.5px; color:#64748b; line-height:1.4; margin-top:6px;">
            ℹ️ <b>By-Pass Fonksiyonu:</b> %100 açıldığında tüm kızgın yağ döngüsü aşırı kızdırıcı ve evaporatörü atlayarak doğrudan pompaya döner; ORC türbini devre dışı kalır.
          </p>`;
      } else if (eq === 'superheater') {
        title.innerHTML = '♨️ Siklopentan Aşırı Kızdırıcı (SH)';
        desc.innerText = 'Kızgın Yağ & Siklopentan S&T Eşanjörü (Therminol 66 / ORC).';
        const isManual = state.is_manual_t_sh_in;
        let modeHtml = `
          <div class="insp-section-header oil">🔥 SH Giriş Sıcaklığı Belirleme Yöntemi</div>
          <div style="display:flex; gap:6px; margin-bottom:10px;">
            <button class="btn-mode-toggle ${!isManual ? 'active' : ''}" style="flex:1; padding:6px; font-size:11.5px; font-weight:700; border-radius:5px; cursor:pointer;" onclick="setShInletMode(false)">
              🔗 Otomatik (Kazan)
            </button>
            <button class="btn-mode-toggle ${isManual ? 'active' : ''}" style="flex:1; padding:6px; font-size:11.5px; font-weight:700; border-radius:5px; cursor:pointer;" onclick="setShInletMode(true)">
              ✏️ Manuel Giriş
            </button>
          </div>
        `;
        let tempControls = '';
        if (isManual) {
          const currentVal = (state.T_oil_sh_in !== null) ? state.T_oil_sh_in : 288.0;
          tempControls = makeParamControl('T_oil_sh_in', 'SH Kızgın Yağ Giriş Sıcaklığı', 180, 340, 1, currentVal, '°C');
        } else {
          tempControls = makeParamControl('delta_T_pipe_loss', 'Boru Hattı Isı Kaybı (ΔT)', 0, 40, 0.5, state.delta_T_pipe_loss || 0, '°C');
        }
        let temaHtml = `
          <div class="insp-section-header hot">⚙️ TEMA Tasarım & Isı Yüzeyi</div>
          <div class="param-group">
            <div class="param-title"><span>TEMA Eşanjör Tipi</span></div>
            <select class="param-select" onchange="setShTemaType(this.value)">
              <option value="BEM" ${state.sh_tema_type === 'BEM' ? 'selected' : ''}>BEM (Sabit Boru Aynası - Tek Geçişli Gövde)</option>
              <option value="BEU" ${state.sh_tema_type === 'BEU' ? 'selected' : ''}>BEU (U-Borulu Demet - Termal Genleşmeye Dayanıklı)</option>
              <option value="AKT" ${state.sh_tema_type === 'AKT' ? 'selected' : ''}>AKT (Kayan Kafalı - Temizlenebilir Boru Demeti)</option>
              <option value="AES" ${state.sh_tema_type === 'AES' ? 'selected' : ''}>AES (Bölünmüş Halka Yüzer Başlıklı)</option>
            </select>
          </div>
          <div class="param-group" style="display:flex; justify-content:space-between; font-size:11.5px; background:#f8fafc; padding:6px 8px; border-radius:5px; border:1px solid #e2e8f0; margin-bottom:8px;">
            <span style="color:#64748b;">Gövde Akışkanı:</span>
            <b style="color:#0f3a5d;">${state.sh_shell_fluid || 'Therminol 66 (Kızgın Yağ)'}</b>
          </div>
          <div class="param-group" style="display:flex; justify-content:space-between; font-size:11.5px; background:#f8fafc; padding:6px 8px; border-radius:5px; border:1px solid #e2e8f0; margin-bottom:8px;">
            <span style="color:#64748b;">Boru Akışkanı:</span>
            <b style="color:#0284c7;">${state.sh_tube_fluid || 'Siklopentan (ORC Çevrim Akışkanı)'}</b>
          </div>
          ${makeParamControl('UA_sh', 'Süperheater Isı Katsayısı (UA_sh)', 5, 100, 1, state.UA_sh, 'kW/K')}
          ${makeParamControl('sh_shell_p_des', 'Gövde Tasarım Basıncı (P_des,shell)', 5, 30, 0.5, state.sh_shell_p_des, 'bar')}
          ${makeParamControl('sh_tube_p_des', 'Boru Tasarım Basıncı (P_des,tube)', 5, 30, 0.5, state.sh_tube_p_des, 'bar')}
          ${makeParamControl('sh_shell_fouling', 'Gövde Kirlilik Direnci (R_f,shell)', 0.0001, 0.0008, 0.00005, state.sh_shell_fouling, 'm²K/W')}
          ${makeParamControl('sh_tube_fouling', 'Boru Kirlilik Direnci (R_f,tube)', 0.00005, 0.0005, 0.00005, state.sh_tube_fouling, 'm²K/W')}
        `;
        c.innerHTML = modeHtml + tempControls + temaHtml;
      } else if (eq === 'preheater') {
        title.innerHTML = '💧 Siklopentan Ön Isıtıcı & Evap (PH)';
        desc.innerText = '2. Seri Kademe: Sıvı siklopentanı ısıtır ve buharlaştırır (Kettle Reboiler, 3-Bölge Termodinamik & Pinch Analizi).';

        const temaOptions = [
          'K (Kettle Reboiler Evaporatör - Genişletilmiş Kubbeli)',
          'BEM (Sabit Boru Aynası - Tek Geçişli Gövde)',
          'BEU (U-Borulu Demet - Termal Genleşmeye Dayanıklı)'
        ];

        const demisterOptions = [
          'SS316 Tel Örgü Ped (Wire Mesh Pad - 100 mm)',
          'Vane / Kanatçıklı Damla Tutucu (Chevron Type)',
          'Siklonik Ayırıcı Giriş Difüzörü'
        ];

        let kettleSntHtml = `
          <div class="insp-section-header cold">🛢️ Kettle Reboiler S&T & Termodinamik</div>
          <div class="param-group">
            <div class="param-title"><span>TEMA Eşanjör Tipi</span></div>
            <select class="param-select" onchange="setStTemaType(this.value)">
              ${temaOptions.map(opt => `<option value="${opt}" ${state.st_tema_type.includes(opt.split(' ')[0]) ? 'selected' : ''}>${opt}</option>`).join('')}
            </select>
          </div>
          <div class="param-group">
            <div class="param-title"><span>Buhar Kubbesi Demister (Damla Tutucu) Tipi</span></div>
            <select class="param-select" onchange="setStDemisterType(this.value)">
              ${demisterOptions.map(opt => `<option value="${opt}" ${state.st_demister_type.includes(opt.split(' ')[0]) ? 'selected' : ''}>${opt}</option>`).join('')}
            </select>
          </div>
          ${makeParamControl('st_kettle_dome_ratio', 'Kettle Kubbe Çap Oranı (D_dome/D_bundle)', 1.2, 3.0, 0.05, state.st_kettle_dome_ratio, '')}
          ${makeParamControl('st_baffle_cut', 'Şaşırtma Kesme Oranı / Baffle Cut', 15, 45, 5, state.st_baffle_cut, '%', true)}
          ${makeParamControl('st_baffle_pitch', 'Şaşırtma Aralığı (Baffle Pitch)', 50, 1000, 25, state.st_baffle_pitch, 'mm')}
          ${makeParamControl('st_pinch_min_target', 'Hedef Min. Pinch Payı ΔT', 2.0, 30.0, 0.5, state.st_pinch_min_target, '°C')}
          ${makeParamControl('ph_shell_fouling', 'Gövde Kirlilik Rf (Therminol 66)', 0.0001, 0.0008, 0.00005, state.ph_shell_fouling, 'm²K/W')}
          ${makeParamControl('ph_tube_fouling', 'Boru Kirlilik Rf (Siklopentan)', 0.00005, 0.0005, 0.00005, state.ph_tube_fouling, 'm²K/W')}
          ${makeParamControl('glide_c', 'Zeotropik Sıcaklık Kayması (Glide)', 0.0, 50.0, 0.5, state.glide_c, '°C')}
        `;

        let orcControlsHtml = `
          <div class="insp-section-header hot">⚡ Basınç, Debi & Isı Yüzeyi</div>
          ${makeParamControl('P_evap_bar', 'ORC Buharlaşma Basıncı (P_evap)', 6, 25, 0.5, state.P_evap_bar, 'bar')}
          ${makeParamControl('m_cp', 'Siklopentan Tasarım Debisi', 4, 25, 0.5, state.m_cp, 'kg/s')}
          ${makeParamControl('UA_ph', 'Ön Isıtıcı / Evap UA Toplamı', 10, 250, 2, state.UA_ph, 'kW/K')}
          <p style="font-size:11.5px; color:#475569; line-height:1.4; margin-top:8px; background:#f1f5f9; padding:8px; border-radius:6px; border-left:3px solid #0284c7;">
            📐 <b>Pinch Noktası Kontrolü:</b> Buharlaşma basıncı (P_evap) arttıkça doyma sıcaklığı (T_sat) artar ve evaporatör çıkışındaki yağ ile buharlaşma sıcaklığı arasındaki fark (ΔT_pinch) daralır. Hedef pinch eşiğinin (${state.st_pinch_min_target.toFixed(1)} °C) altına düşüldüğünde uyarı verilir.
          </p>
        `;
        c.innerHTML = kettleSntHtml + orcControlsHtml;
      } else if (eq === 'condenser') {
        const isAir = (state.condenser_type === 'air');
        title.innerHTML = isAir ? '💨 Hava Soğutmalı Kondenser (ACC)' : '❄️ Su Soğutmalı Kondenser (Shell & Tube)';
        desc.innerText = isAir
          ? 'ORC Kondenseri (Yoğuşturucu) Tipi & Soğutma Kaynağı: Cebri çekişli aksiyal fanlar ile çevre havasına yoğuşturma.'
          : 'ORC Kondenseri (Yoğuşturucu) Tipi & Soğutma Kaynağı: Su soğutmalı kule suyu ile yoğuşturma.';

        let typeToggleHtml = `
          <div class="insp-section-header cold">❄️ Kondenser Soğutma Yöntemi</div>
          <div style="display:flex; gap:8px; margin-bottom:12px;">
            <button class="btn-mode-toggle ${!isAir ? 'active' : ''}" style="flex:1; padding:7px; font-size:12px; font-weight:700; border-radius:6px; cursor:pointer;" onclick="setCondenserType('water')">
              💧 Su Soğutmalı
            </button>
            <button class="btn-mode-toggle ${isAir ? 'active' : ''}" style="flex:1; padding:7px; font-size:12px; font-weight:700; border-radius:6px; cursor:pointer;" onclick="setCondenserType('air')">
              💨 Hava Soğutmalı (ACC)
            </button>
          </div>
        `;

        let paramControls = '';
        if (isAir) {
          paramControls += makeParamControl('T_air_in', 'Çevre Havası Sıcaklığı (T_air)', 10, 45, 1, state.T_air_in, '°C');
          paramControls += makeParamControl('acc_fan_eff', 'ACC Fan Verimi (η_fan)', 0.40, 0.90, 0.05, state.acc_fan_eff, '%', true);
        } else {
          paramControls += makeParamControl('T_cw_in', 'Soğutma Suyu Sıcaklığı (T_cw)', 15, 35, 1, state.T_cw_in, '°C');
          paramControls += makeParamControl('cw_pump_eff', 'Kule Pompası Verimi (η_cw)', 0.40, 0.90, 0.05, state.cw_pump_eff, '%', true);
        }
        paramControls += makeParamControl('P_cond_bar', 'Kondenser Basıncı (P_cond)', 0.3, 3.5, 0.1, state.P_cond_bar, 'bar');

        let multizoneHtml = `
          <div class="insp-section-header cold">🔬 3 Bölgeli Analiz (Multi-Zone)</div>
          <div class="param-group" style="display:flex; justify-content:space-between; align-items:center; background:#f8fafc; padding:8px 10px; border-radius:6px; border:1px solid #e2e8f0; margin-bottom:8px;">
            <label style="font-size:11.5px; font-weight:600; color:#0f3a5d; cursor:pointer;" for="chk_multizone">
              3 Bölgeli Analiz (Kızgınlık+Yoğuşma+Aşırı Soğutma)
            </label>
            <input type="checkbox" id="chk_multizone" ${state.enable_multizone ? 'checked' : ''} onchange="setMultizoneToggle(this.checked)" style="width:16px; height:16px; cursor:pointer;">
          </div>
          ${state.enable_multizone ? makeParamControl('t_subcool', 'Aşırı Soğutma Hedefi T_sub', 60.0, 120.0, 1.0, state.t_subcool, '°C') : ''}
        `;

        c.innerHTML = typeToggleHtml + paramControls + multizoneHtml;
      } else if (eq === 'cp_pump') {
        title.innerHTML = '⚡ Siklopentan Sıvı Besleme Pompası';
        desc.innerText = 'Kondenserden sıvıyı emerek yüksek basınca (P_evap) basar.';
        c.innerHTML =
          makeParamControl('z_hw', 'Kondenser Hotwell Emiş Yüksekliği', 0.5, 4.0, 0.2, state.z_hw, 'm') +
          makeParamControl('feed_pump_eff', 'Besleme Pompa Verimi', 0.4, 0.9, 0.05, state.feed_pump_eff, '%', true);
      } else if (eq === 'turbine') {
        title.innerHTML = '⚡ ORC Türbini & Jeneratör Güç Üretimi';
        desc.innerText = 'Yüksek basınçlı kızgın buharın izantropik genleşmesinden mekanik ve elektrik üretimi.';

        const orcOptions = [
          { val: 'Cyclopentane', label: 'Siklopentan (Cyclopentane - Retrograde)' },
          { val: 'n-Pentane', label: 'n-Pentan (n-Pentane)' },
          { val: 'Isopentane', label: 'İzopentan (Isopentane)' },
          { val: 'R245fa', label: 'R245fa (HFC - Düşük Sıcaklık)' },
          { val: 'R1233zd(E)', label: 'R1233zd(E) (HFO - Çevre Dostu)' },
          { val: 'Toluene', label: 'Toluen (Toluene - Yüksek Sıcaklık)' }
        ];

        let fluidSelectHtml = `
          <div class="insp-section-header orc">🧪 ORC Akışkanı Seçimi</div>
          <div class="param-group">
            <div class="param-title"><span>Çevrim Akışkanı</span></div>
            <select class="param-select" onchange="setOrcFluid(this.value)">
              ${orcOptions.map(opt => `<option value="${opt.val}" ${state.orc_fluid_sel === opt.val ? 'selected' : ''}>${opt.label}</option>`).join('')}
            </select>
          </div>
        `;

        let effControlsHtml = `
          <div class="insp-section-header hot">⚙️ Türbin-Jeneratör Verimleri</div>
          ${makeParamControl('turb_eta_is', 'Türbin İzantropik Verimi (η_is)', 0.60, 0.95, 0.01, state.turb_eta_is, '%', true)}
          ${makeParamControl('turb_eta_gen', 'Jeneratör Elektrik Verimi (η_gen)', 0.85, 0.99, 0.01, state.turb_eta_gen, '%', true)}
          <p style="font-size:11.5px; color:#475569; line-height:1.5; background:#faf5ff; padding:8px 10px; border-radius:6px; border-left:3px solid #9333ea; margin-top:10px;">
            ⚡ <b>İzantropik Güç:</b> İzantropik entalpi düşüşü Δh_is = cp_vap × (T_sup + 273.15) × [1 - (1/PR)^((γ-1)/γ)] formülüyle hesaplanır. Mekanik güç W_turb,mech = m_orc × Δh_is × η_is, jeneratör çıkışı W_turb,el = W_turb,mech × η_gen olarak canlı hesaplanır.
          </p>
        `;

        c.innerHTML = fluidSelectHtml + effControlsHtml;
      } else if (eq === 'pump') {
        title.innerHTML = '🔄 Kızgın Yağ Sirkülasyon Pompası & Döngü Akışkanı';
        desc.innerText = 'Tab 1 Soğuk Akışkan (Cold Side) termofiziksel özellikleri ve döngü hidrolik gereksinimleri.';

        const oilOptions = [
          { val: 'Therminol 66', label: 'Therminol 66 (Standart)' },
          { val: 'Dowtherm A', label: 'Dowtherm A' },
          { val: 'Mobiltherm 605', label: 'Mobiltherm 605' },
          { val: 'Calflo AF', label: 'Calflo AF' },
          { val: 'Custom Oil', label: 'Özel Yağ (Manuel Tanım)' }
        ];

        let fluidSelectHtml = `
          <div class="insp-section-header cold">🔵 Akışkan Seçimi (Cold Side - Kızgın Yağ)</div>
          <div class="param-group">
            <div class="param-title"><span>Kızgın Yağ Cinsi</span></div>
            <select class="param-select" onchange="setThermalOil(this.value)">
              ${oilOptions.map(opt => `<option value="${opt.val}" ${state.oil_fluid_sel === opt.val ? 'selected' : ''}>${opt.label}</option>`).join('')}
            </select>
          </div>
          ${makeParamControl('oil_rho', 'Yağ Yoğunluğu (ρ_oil)', 700, 1100, 5, state.oil_rho, 'kg/m³')}
          ${makeParamControl('oil_cp', 'Özgül Isı (Cp,oil)', 1500, 3000, 10, state.oil_cp, 'J/kgK')}
          ${makeParamControl('oil_mu', 'Dinamik Viskozite (μ_oil)', 0.0002, 0.0100, 0.0001, state.oil_mu, 'Pa.s')}
          ${makeParamControl('oil_k', 'Isıl İletkenlik (k_oil)', 0.08, 0.20, 0.005, state.oil_k, 'W/mK')}
        `;

        let hydControlsHtml = `
          <div class="insp-section-header oil">⚙️ Hidrolik & Pompa Parametreleri</div>
          ${makeParamControl('m_oil', 'Kızgın Yağ Toplam Debisi', 10, 80, 1, state.m_oil, 'kg/s')}
          ${makeParamControl('pump_eff', 'Pompa Verimi (η_pompa)', 0.40, 0.95, 0.05, state.pump_eff, '%', true)}
          ${makeParamControl('static_elevation_m', 'Statik Kot / Yükseklik Farkı (Δz)', 0.0, 30.0, 0.5, state.static_elevation_m, 'm')}
          ${makeParamControl('hx_dp_bar', 'Eşanjörler Direnç Kaybı (ΔP_eşanjör)', 0.10, 1.50, 0.05, state.hx_dp_bar, 'bar')}
        `;

        c.innerHTML = fluidSelectHtml + hydControlsHtml;
      }

      recalculate();
    }

    function applyPreset(preset) {
      if (preset === 'single') {
        setBoilerCount(1);
        state.bypass_ratio = 0.0;
      } else if (preset === 'dual_balanced') {
        setBoilerCount(2);
        state.bypass_ratio = 0.0;
      } else if (preset === 'tri_balanced') {
        setBoilerCount(3);
        state.bypass_ratio = 0.0;
      } else if (preset === 'five_train') {
        setBoilerCount(5);
        state.bypass_ratio = 0.0;
      } else if (preset === 'part_bypass') {
        state.bypass_ratio = 0.30;
      }
      selectEquipment(state.selected_eq);
      recalculate();
      if (typeof window.sync3DBoilerCount === "function") {
        try { window.sync3DBoilerCount(state.n_boilers); } catch (e) {}
      }
    }

    // Interactive KPI Engineering & Formula Info Modal
    const kpiInfoData = {
      q_boiler: {
        title: "🔥 Toplam Kazan Yükü (Q_kazan) Hesaplaması",
        formula: "Q_kazan = Σ [ ε_i × C_min,i × (T_flue_in,i - T_oil_ret) ]  (i=1..N)",
        desc: "Atık Isı Baca Kazanlarından (1 ila 5 adet WHRU) kızgın yağa (Therminol 66) aktarılan toplam ısıl güçtür. Her kazan için baca gazı ve termal yağ debileriyle ε-NTU (Etkinlik-Geçiş Sayısı) eşanjör çözücüsü çalışır. Yağ debisi paralel kazanlar arasında manifold bölünme katsayılarına göre hidrolik basınç dengesiyle paylaştırılır."
      },
      w_net: {
        title: "⚡ Net ORC Gücü (W_net) Hesaplaması",
        formula: "W_net = W_türbin - W_yağ_pompa - W_besleme_pompa - W_kondenser_parazitik ≤ Q_kazan × η_carnot",
        desc: "Siklopentan buharının genleşmesinden elde edilen türbin izantropik gücünden, döngüdeki yağ sirkülasyon pompası, siklopentan sıvı besleme pompası ve ACC fan / kule pompası iç tüketimleri düşülerek hesaplanır. Termodinamiğin 1. ve 2. Yasası uyarınca üretilen net elektrik gücü, eşanjörlerden çekilen gerçek buharlaşma ısısı (Q_orc) ve Carnot tavanı ile kesin sınırlandırılmıştır; asla kazan yükünü aşamaz."
      },
      q_orc: {
        title: "🔄 ORC Isı Girişi (Q_orc) Hesaplaması",
        formula: "Q_orc = Q_sh + Q_ph ≤ Q_kazan × (1 - By-Pass) - Q_hat_kaybı",
        desc: "Kazan kolektöründen gelen kızgın yağın, aşırı kızdırıcı (SH), buharlaştırıcı ve ön ısıtıcıya (PH) aktardığı faydalı ısıl güçtür. Oransal by-pass vanası açıldığında yağ ORC eşanjörlerini atlayarak doğrudan dönüş hattına yönelir ve döngüye aktarılan ısı yükü orantılı olarak düşer."
      },
      plant_eff: {
        title: "📊 Tesis Isıl Verimi (η_tesis) Hesaplaması",
        formula: "η_tesis = (W_net / Q_kazan) × 100",
        desc: "Toplam kazan atık ısı girişine göre sisteme kazandırılan net elektriksel dönüşüm verimidir. Bu değer Siklopentan için Carnot tavanı (η_carnot = 1 - T_soğuk / T_sıcak) ve türbin/pompa izantropik kayıpları ile fiziksel olarak sınırlandırılmıştır (tipik subkritik ORC aralığı %12 - %22)."
      },
      bypass: {
        title: "🔀 By-Pass Durumu & Debi Hesaplaması",
        formula: "m_bypass = m_yağ_toplam × By-Pass_oranı",
        desc: "3 yollu oransal kontrol vanası açıklık yüzdesine göre kızgın yağ debisinin eşanjörlere girmeden doğrudan ana sirkülasyon pompasına döndürülen kısmıdır. By-pass %100 yapıldığında ORC türbini ve eşanjörleri devre dışı kalarak tesis koruma moduna geçer."
      },
      pinch: {
        title: "📐 Pinch Noktası Sıcaklık Farkı (ΔT_pinch) Hesaplaması",
        formula: "ΔT_pinch = T_yağ_evap_çıkış - T_sat(P_evap)",
        desc: "Evaporatör çıkışındaki kızgın yağ sıcaklığı ile siklopentanın buharlaşma doyma sıcaklığı (T_sat) arasındaki minimum sıcaklık yaklaşımıdır. Bu fark 5 °C altına düşerse sistem termodinamik pinch ihlali (ters ısı transferi riski) uyarısı verir."
      },
      w_turb: {
        title: "⚡ Brüt ORC Türbin Gücü (W_türbin) Hesaplaması",
        formula: "W_türbin [kW] = [ m_cp_gerçek × Δh_is × η_izantropik ] / 1000 ≤ Q_orc × η_carnot × 0.85",
        desc: "Yüksek basınçlı kızgın siklopentan buharının (P_evap, T_cp_sup) türbin kanatlarında kondenser basıncına (P_cond) genleşmesiyle elde edilen brüt mekanik/elektriksel güçtür. Formüldeki m_cp_gerçek evaporatör ve süperheaterdan buharlaşan akışkan debisidir. Δh_is = cp_vap × (T_cp_sup + 273.15) × [1 - (1/PR)^((γ-1)/γ)] izantropik entalpi düşüşüdür. η_izantropik (%82) türbin-jeneratör iç verimidir. Bu değer iç tüketimler düşülmeden önceki brüt üretimdir."
      },
      pump_oil_power: {
        title: "🔄 Kızgın Yağ Sirkülasyon Pompası Güç Tüketimi (W_yağ_pompa) Hesaplaması",
        formula: "W_yağ_pompa [kW] = [ (m_yağ / ρ_yağ) × (ΔP_toplam × 10⁵) ] / (η_pompa × 1000)  |  ΔP_hat = f × (L_eq / D_i) × (ρ_yağ × v² / 2)",
        desc: "Kızgın yağ döngüsünde Therminol 66 akışkanını dolaştıran sirkülasyon pompasının elektrik tüketimidir. Fiziksel hesaplama adımları: 1) Akış Hızı: v = 4×m_yağ / (π×Di²×ρ_yağ) [m/s]. 2) Reynolds Sayısı: Re = ρ_yağ×v×Di / μ_yağ. 3) Darcy Sürtünme Faktörü: f = Swamee-Jain(Re, ε/Di) çelik boru pürüzlülüğü ε=0.045 mm. 4) Hat Basınç Kaybı: ΔP_hat = f×(Leq/Di)×(ρ_yağ×v²/2) [Pa]. 5) Toplam Direnç: ΔP_toplam = ΔP_hat × (1 - 0.3×Bypass) + ΔP_kazan. 6) Pompa Gücü: Hacimsel debi (V = m_yağ / ρ_yağ) ve pompa verimi (%75) ile kW cinsinden elektrik tüketimi hesaplanır."
      },
      cp_pump_power: {
        title: "💧 Siklopentan Sıvı Besleme Pompası Tüketimi (W_cp_pompa) Hesaplaması",
        formula: "W_cp_pompa [kW] = [ m_cp_gerçek × (P_evap - P_cond) × 10⁵ ] / (ρ_cp_sıvı × η_besleme × 1000)",
        desc: "Kondenser hotwell haznesinden toplanan doymuş sıvı siklopentanın evaporatör buharlaşma basıncına (P_evap) basılması için harcanan elektrik gücüdür. Burada m_cp_gerçek çevrimdeki anlık buhar debisi, ρ_cp_sıvı kondensat yoğunluğu (~705 kg/m³) ve η_besleme besleme pompası verimidir (%70)."
      },
      cond_power: {
        title: "❄️ / 💨 Kondenser Soğutma Parazitik Tüketimi (W_kond) Hesaplaması",
        formula: "W_kond [kW] = (Q_kondenser / 1000) × f_parazitik",
        desc: "Hava soğutmalı kondenserlerde (ACC) cebri çekişli aksiyal fan motorlarının elektrik tüketimidir (f_parazitik ≈ %2.0). Su soğutmalı kondenser modunda ise soğutma kulesi devridaim pompası tüketimidir (f_parazitik ≈ %0.5)."
      }
    };

    window.showKpiInfo = function(key) {
      const data = kpiInfoData[key];
      if (!data) return;
      const modal = document.getElementById('kpi_modal');
      const t = document.getElementById('modal_title');
      const b = document.getElementById('modal_body');
      if (t) t.innerText = data.title;
      if (b) {
        b.innerHTML = `
          <div style="font-weight:700; color:#475569; font-size:12px; margin-bottom:4px;">Matematiksel Formül:</div>
          <div class="modal-formula">${data.formula}</div>
          <div style="font-weight:700; color:#475569; font-size:12px; margin:12px 0 4px 0;">Mühendislik Açıklaması:</div>
          <p style="margin:0; line-height:1.55; color:#334155;">${data.desc}</p>
        `;
      }
      if (modal) modal.style.display = 'flex';
    };

    window.closeKpiModal = function(e) {
      if (!e || e.target === document.getElementById('kpi_modal') || (e.target && e.target.classList && e.target.classList.contains('modal-close'))) {
        const modal = document.getElementById('kpi_modal');
        if (modal) modal.style.display = 'none';
      }
    };

    // Initialize configuration with live inputs
    const initData = __INIT_DATA_PLACEHOLDER__;
    if (initData && typeof initData === 'object') {
      if (initData.solver_method) {
        const sm = String(initData.solver_method);
        if (sm.includes('HT') && sm.includes('LMTD')) state.whru_solver_method = 'HT Kütüphanesi (LMTD)';
        else if (sm.includes('HT')) state.whru_solver_method = 'HT Kütüphanesi (Epsilon-NTU)';
        else if (sm.includes('LMTD')) state.whru_solver_method = 'Kendi Algoritmamız (LMTD)';
        else state.whru_solver_method = 'Kendi Algoritmamız (Epsilon-NTU)';
      }
      if (initData.flow_type) state.whru_flow_type = String(initData.flow_type);
      if (initData.calc_purpose) state.whru_calc_purpose = String(initData.calc_purpose);
      if (initData.u_calc_mode) state.whru_u_mode = String(initData.u_calc_mode);
      if (initData.condenser_type) state.condenser_type = initData.condenser_type;
      if (initData.T_air_in !== undefined && !isNaN(parseFloat(initData.T_air_in))) state.T_air_in = parseFloat(initData.T_air_in);
      if (initData.T_cw_in !== undefined && !isNaN(parseFloat(initData.T_cw_in))) state.T_cw_in = parseFloat(initData.T_cw_in);
      if (initData.n_boilers !== undefined && !isNaN(parseInt(initData.n_boilers))) state.n_boilers = Math.max(1, Math.min(5, parseInt(initData.n_boilers)));
      if (initData.is_manual_t_sh_in !== undefined) state.is_manual_t_sh_in = Boolean(initData.is_manual_t_sh_in);
      if (initData.T_oil_sh_in_C !== undefined && initData.T_oil_sh_in_C !== null) {
        state.T_oil_sh_in = parseFloat(initData.T_oil_sh_in_C);
        state.is_manual_t_sh_in = true;
      } else if (initData.sh_t_oil_in !== undefined && initData.sh_t_oil_in !== null) {
        state.T_oil_sh_in = parseFloat(initData.sh_t_oil_in);
        state.is_manual_t_sh_in = true;
      }
      if (initData.delta_T_pipe_loss_C !== undefined && !isNaN(parseFloat(initData.delta_T_pipe_loss_C))) {
        state.delta_T_pipe_loss = parseFloat(initData.delta_T_pipe_loss_C);
      } else if (initData.sh_pipe_loss_c !== undefined && !isNaN(parseFloat(initData.sh_pipe_loss_c))) {
        state.delta_T_pipe_loss = parseFloat(initData.sh_pipe_loss_c);
      }

      // Live flow rates, temperatures & pressures from main app inputs
      const mOilVal = initData.m_oil !== undefined ? initData.m_oil : initData.m_hot;
      if (mOilVal !== undefined && !isNaN(parseFloat(mOilVal)) && parseFloat(mOilVal) > 0) {
        state.m_oil = parseFloat(mOilVal);
      }
      const mCpVal = initData.m_cp !== undefined ? initData.m_cp : initData.m_cold;
      if (mCpVal !== undefined && !isNaN(parseFloat(mCpVal)) && parseFloat(mCpVal) > 0) {
        state.m_cp = parseFloat(mCpVal);
      }
      const tCpVal = initData.T_cp_in !== undefined ? initData.T_cp_in : initData.T_cold_in;
      if (tCpVal !== undefined && !isNaN(parseFloat(tCpVal))) {
        const parsedTCp = parseFloat(tCpVal);
        if (parsedTCp <= 115.0) {
          state.T_cp_in = parsedTCp;
        }
      }
      const pEvapVal = initData.P_evap_bar !== undefined ? initData.P_evap_bar : (initData.st_shell_p_des_bar !== undefined ? initData.st_shell_p_des_bar : initData.st_tube_p_des_bar);
      if (pEvapVal !== undefined && !isNaN(parseFloat(pEvapVal)) && parseFloat(pEvapVal) > 0) {
        state.P_evap_bar = parseFloat(pEvapVal);
      }
      if (initData.P_cond_bar !== undefined && !isNaN(parseFloat(initData.P_cond_bar)) && parseFloat(initData.P_cond_bar) > 0) {
        state.P_cond_bar = parseFloat(initData.P_cond_bar);
      }
      if (initData.bypass_ratio !== undefined && !isNaN(parseFloat(initData.bypass_ratio))) {
        state.bypass_ratio = Math.max(0.0, Math.min(1.0, parseFloat(initData.bypass_ratio)));
      }
      const pumpEffVal = initData.pump_eff !== undefined ? initData.pump_eff : initData.pump_efficiency;
      if (pumpEffVal !== undefined && !isNaN(parseFloat(pumpEffVal))) {
        const pe = parseFloat(pumpEffVal);
        state.pump_eff = pe > 1.0 ? pe / 100.0 : pe;
      }
      if (initData.acc_fan_eff !== undefined && !isNaN(parseFloat(initData.acc_fan_eff))) {
        const fe = parseFloat(initData.acc_fan_eff);
        state.acc_fan_eff = fe > 1.0 ? fe / 100.0 : fe;
      }
      if (initData.cw_pump_eff !== undefined && !isNaN(parseFloat(initData.cw_pump_eff))) {
        const cwe = parseFloat(initData.cw_pump_eff);
        state.cw_pump_eff = cwe > 1.0 ? cwe / 100.0 : cwe;
      }
      if (initData.UA_sh !== undefined && !isNaN(parseFloat(initData.UA_sh))) {
        state.UA_sh = parseFloat(initData.UA_sh);
      }
      if (initData.UA_ph !== undefined && !isNaN(parseFloat(initData.UA_ph))) {
        state.UA_ph = parseFloat(initData.UA_ph);
      } else if (initData.U_value !== undefined && initData.Area !== undefined) {
        const uaTotal = (parseFloat(initData.U_value) * parseFloat(initData.Area)) / 1000.0;
        if (uaTotal > 0) {
          state.UA_ph = Math.max(10.0, uaTotal * 0.70);
          state.UA_sh = Math.max(5.0, uaTotal * 0.30);
        }
      }
      if (initData.pipe_di_mm !== undefined && !isNaN(parseFloat(initData.pipe_di_mm))) {
        state.pipe_di_mm = Math.max(40.0, parseFloat(initData.pipe_di_mm));
        if (state.pipes && state.pipes.supply) state.pipes.supply.di_mm = state.pipe_di_mm;
      }
      if (initData.pipe_length_m !== undefined && !isNaN(parseFloat(initData.pipe_length_m))) {
        state.pipe_length_m = Math.max(5.0, parseFloat(initData.pipe_length_m));
        if (state.pipes && state.pipes.supply) state.pipes.supply.length_m = state.pipe_length_m;
      }

      // Fluid thermo properties from Tab 1
      if (initData.hot_mix_data && typeof initData.hot_mix_data === 'object') {
        state.flue_gas_mix = Object.assign({}, state.flue_gas_mix, initData.hot_mix_data);
      }
      if (initData.hot_mix_basis) state.flue_gas_basis = initData.hot_mix_basis;
      const cpFgVal = initData.flue_gas_cp !== undefined ? initData.flue_gas_cp : initData.cp_hot;
      if (cpFgVal !== undefined && !isNaN(parseFloat(cpFgVal))) state.flue_gas_cp = parseFloat(cpFgVal);
      const rhoFgVal = initData.flue_gas_rho !== undefined ? initData.flue_gas_rho : initData.density_hot;
      if (rhoFgVal !== undefined && !isNaN(parseFloat(rhoFgVal))) state.flue_gas_rho = parseFloat(rhoFgVal);
      const muFgVal = initData.flue_gas_mu !== undefined ? initData.flue_gas_mu : initData.mu_hot;
      if (muFgVal !== undefined && !isNaN(parseFloat(muFgVal))) state.flue_gas_mu = parseFloat(muFgVal);
      const kFgVal = initData.flue_gas_k !== undefined ? initData.flue_gas_k : initData.k_hot;
      if (kFgVal !== undefined && !isNaN(parseFloat(kFgVal))) state.flue_gas_k = parseFloat(kFgVal);

      // Thermal Oil Selection & Properties
      const rawOilSel = initData.oil_fluid_sel || (initData.cold_fluid_sel && Object.keys(THERMAL_OILS).some(k => initData.cold_fluid_sel.includes(k)) ? initData.cold_fluid_sel : initData.hot_fluid_sel);
      if (rawOilSel && typeof rawOilSel === 'string') {
        const matched = Object.keys(THERMAL_OILS).find(k => rawOilSel.includes(k));
        if (matched) state.oil_fluid_sel = matched;
      }
      const cpOilVal = initData.oil_cp !== undefined ? initData.oil_cp : initData.cp_cold;
      if (cpOilVal !== undefined && !isNaN(parseFloat(cpOilVal))) state.oil_cp = parseFloat(cpOilVal);
      const rhoOilVal = initData.oil_rho !== undefined ? initData.oil_rho : initData.density_cold;
      if (rhoOilVal !== undefined && !isNaN(parseFloat(rhoOilVal))) state.oil_rho = parseFloat(rhoOilVal);
      const muOilVal = initData.oil_mu !== undefined ? initData.oil_mu : initData.mu_cold;
      if (muOilVal !== undefined && !isNaN(parseFloat(muOilVal))) state.oil_mu = parseFloat(muOilVal);
      const kOilVal = initData.oil_k !== undefined ? initData.oil_k : initData.k_cold;
      if (kOilVal !== undefined && !isNaN(parseFloat(kOilVal))) state.oil_k = parseFloat(kOilVal);

      // ORC Fluid Selection
      const rawOrcSel = initData.orc_fluid_sel || initData.cold_fluid_sel;
      if (rawOrcSel && typeof rawOrcSel === 'string') {
        const matchedOrc = Object.keys(ORC_FLUIDS).find(k => rawOrcSel.toLowerCase().includes(k.toLowerCase()));
        if (matchedOrc) state.orc_fluid_sel = matchedOrc;
      }

      if (initData.exch_type) state.whru_exch_type = String(initData.exch_type);
      if (initData.T_hot_out_opt !== undefined && !isNaN(parseFloat(initData.T_hot_out_opt)) && parseFloat(initData.T_hot_out_opt) > 0) {
        state.whru_T_hot_out_opt = parseFloat(initData.T_hot_out_opt);
      }
      if (initData.T_cold_out_opt !== undefined && !isNaN(parseFloat(initData.T_cold_out_opt)) && parseFloat(initData.T_cold_out_opt) > 0) {
        state.whru_T_cold_out_opt = parseFloat(initData.T_cold_out_opt);
      }

      if (initData.st_tema_type) {
        state.st_tema_type = String(initData.st_tema_type);
        const code = String(initData.st_tema_type).split(' ')[0];
        if (['BEM', 'BEU', 'AKT', 'AES'].includes(code)) state.sh_tema_type = code;
      }
      if (initData.st_shell_fluid) {
        state.st_shell_fluid = String(initData.st_shell_fluid);
        state.sh_shell_fluid = String(initData.st_shell_fluid);
      }
      if (initData.st_tube_fluid) {
        state.st_tube_fluid = String(initData.st_tube_fluid);
        state.sh_tube_fluid = String(initData.st_tube_fluid);
      }
      if (initData.st_kettle_dome_ratio !== undefined && !isNaN(parseFloat(initData.st_kettle_dome_ratio))) {
        state.st_kettle_dome_ratio = parseFloat(initData.st_kettle_dome_ratio);
      }
      if (initData.st_demister_type) state.st_demister_type = String(initData.st_demister_type);
      if (initData.st_baffle_cut_pct !== undefined && !isNaN(parseFloat(initData.st_baffle_cut_pct))) {
        state.st_baffle_cut = parseFloat(initData.st_baffle_cut_pct);
      }
      if (initData.st_baffle_spacing_mm !== undefined && !isNaN(parseFloat(initData.st_baffle_spacing_mm))) {
        state.st_baffle_pitch = parseFloat(initData.st_baffle_spacing_mm);
      }
      if (initData.st_pinch_min_target_c !== undefined && !isNaN(parseFloat(initData.st_pinch_min_target_c))) {
        state.st_pinch_min_target = parseFloat(initData.st_pinch_min_target_c);
      }
      if (initData.st_shell_fouling !== undefined && !isNaN(parseFloat(initData.st_shell_fouling))) {
        state.sh_shell_fouling = parseFloat(initData.st_shell_fouling);
        state.ph_shell_fouling = parseFloat(initData.st_shell_fouling);
      }
      if (initData.st_tube_fouling !== undefined && !isNaN(parseFloat(initData.st_tube_fouling))) {
        state.sh_tube_fouling = parseFloat(initData.st_tube_fouling);
        state.ph_tube_fouling = parseFloat(initData.st_tube_fouling);
      }
      if (initData.glide_c !== undefined && !isNaN(parseFloat(initData.glide_c))) {
        state.glide_c = parseFloat(initData.glide_c);
      }
      if (initData.enable_multizone !== undefined) {
        state.enable_multizone = Boolean(initData.enable_multizone);
      }
      if (initData.t_subcool !== undefined && !isNaN(parseFloat(initData.t_subcool))) {
        state.t_subcool = parseFloat(initData.t_subcool);
      }

      // Boiler array or flue gas inputs
      if (Array.isArray(initData.boilers)) {
        for (let i = 0; i < Math.min(initData.boilers.length, 5); i++) {
          Object.assign(state.boilers[i], initData.boilers[i]);
        }
      } else {
        if (initData.T_flue_in !== undefined && !isNaN(parseFloat(initData.T_flue_in))) {
          const tfg = parseFloat(initData.T_flue_in);
          for (let i = 0; i < 5; i++) state.boilers[i].T_flue_in = tfg;
        }
        if (initData.m_flue !== undefined && !isNaN(parseFloat(initData.m_flue))) {
          const mfg = parseFloat(initData.m_flue) / (state.n_boilers || 1);
          for (let i = 0; i < 5; i++) state.boilers[i].m_flue = mfg;
        }
      }
    }

    setBoilerCount(state.n_boilers || 2);
    if (state.condenser_type === 'air') {
      const condTitle = document.getElementById('lbl_cond_title');
      if (condTitle) condTitle.textContent = '💨 KONDENSER (ACC)';
    }

    // Immediately calculate and sync active equipment inspector
    selectEquipment(state.selected_eq);
    recalculate();

    window.exportSimulationJSON = function() {
      const exportData = {
        meta: {
          title: "ORC & WHRU Canlı Simülasyon Veri Paketi",
          exported_at: new Date().toISOString(),
          version: "2.4.2-web"
        },
        plant_configuration: {
          n_boilers: state.n_boilers,
          whru_solver: state.whru_solver_method,
          whru_type: state.whru_exch_type,
          flue_gas: {
            preset: state.flue_gas_preset,
            basis: state.flue_gas_basis,
            composition: state.flue_gas_mix,
            cp: state.flue_gas_cp,
            rho: state.flue_gas_rho,
            mu: state.flue_gas_mu,
            k: state.flue_gas_k
          },
          thermal_oil: {
            fluid: state.oil_fluid_sel,
            m_total_kg_s: state.m_oil,
            rho: state.oil_rho,
            cp: state.oil_cp,
            pump_eff: state.pump_eff
          },
          piping_network: state.pipes,
          superheater: {
            tema: state.sh_tema_type,
            UA_kW_K: state.UA_sh,
            fouling_shell: state.sh_shell_fouling,
            fouling_tube: state.sh_tube_fouling
          },
          preheater_evaporator: {
            tema: state.st_tema_type,
            UA_kW_K: state.UA_ph,
            kettle_dome_ratio: state.st_kettle_dome_ratio,
            demister: state.st_demister_type,
            pinch_target_C: state.st_pinch_min_target
          },
          orc_power_cycle: {
            fluid: state.orc_fluid_sel,
            m_cp_kg_s: state.m_cp,
            P_evap_bar: state.P_evap_bar,
            P_cond_bar: state.P_cond_bar,
            turb_eta_is: state.turb_eta_is,
            turb_eta_gen: state.turb_eta_gen
          },
          condenser: {
            type: state.condenser_type,
            multizone: state.enable_multizone,
            t_subcool_C: state.t_subcool
          }
        },
        live_telemetry: window.latestCalcResult || null
      };
      const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `orc_simulasyon_${new Date().toISOString().replace(/[:.]/g, "-")}.json`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    };

    window.selectNode = selectEquipment;
    window.setCondenserType = setCondenserType;
    window.setBoilerCount = setBoilerCount;
    window.changeBoilerCount = changeBoilerCount;
    window.recalculate = recalculate;
  </script>
  <script>
    __PLANT_3D_JS_PLACEHOLDER__
  </script>
</body>
</html>
"""
    import importlib
    import sys

    import orc_3d_plant_component

    if not getattr(sys, "frozen", False):
        importlib.reload(orc_3d_plant_component)
    from orc_3d_plant_component import get_orc_3d_plant_container_html, get_orc_3d_plant_js

    res_html = html_template.replace(
        "__INIT_DATA_PLACEHOLDER__",
        json.dumps(initial_data or {}).replace("</", "<\\/"),
    )
    res_html = res_html.replace("__CONTAINER_3D_PLACEHOLDER__", get_orc_3d_plant_container_html())
    res_html = res_html.replace("__PLANT_3D_JS_PLACEHOLDER__", get_orc_3d_plant_js())
    return res_html
