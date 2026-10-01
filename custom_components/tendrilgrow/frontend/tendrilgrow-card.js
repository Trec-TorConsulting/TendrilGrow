/**
 * TendrilGrow Ultimate Digital Twin & Cockpit Cards for Home Assistant
 *
 * Features:
 * - <tendrilgrow-twin-card>: Interactive 2.5D visual grow tent with live telemetry HUD,
 *   animated equipment states (spinning fans, glowing lights, bubbling reservoir),
 *   tactile tap-to-toggle controls, sweet-spot target meters, and live camera PIP.
 * - <tendrilgrow-overview-card>: Multi-space executive overview card with health scores,
 *   active alerts, and at-a-glance telemetry.
 */

const CARD_VERSION = "2.0.0";
console.info(
  `%c TENDRILGROW DIGITAL TWIN CARD %c v${CARD_VERSION} `,
  "color: #0d1117; background: #10b981; font-weight: 700; padding: 3px 6px; border-radius: 3px 0 0 3px;",
  "color: #fff; background: #1f2937; font-weight: 600; padding: 3px 6px; border-radius: 0 3px 3px 0;"
);

// Helper to safely get state and attributes from HA
function getState(hass, entityId) {
  if (!hass || !entityId) return null;
  return hass.states[entityId] || null;
}

function getStateStr(hass, entityId, fallback = "--") {
  const s = getState(hass, entityId);
  if (!s || s.state === "unavailable" || s.state === "unknown") return fallback;
  return s.state;
}

function getStateNum(hass, entityId, fallback = null) {
  const s = getState(hass, entityId);
  if (!s || s.state === "unavailable" || s.state === "unknown") return fallback;
  const num = parseFloat(s.state);
  return isNaN(num) ? fallback : num;
}

// ============================================================================
// 1. TENDRILGROW DIGITAL TWIN CARD (<tendrilgrow-twin-card>)
// ============================================================================
class TendrilGrowTwinCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._config = {};
    this._hass = null;
    this._viewMode = "schematic"; // 'schematic' | 'camera'
    this._activeDrawer = null; // 'bands' | 'advisor' | 'lung' | null
    this._fanPopoverOpen = false;
    this._lightPopoverOpen = false;
  }

  setConfig(config) {
    if (!config) throw new Error("Invalid configuration");
    this._config = {
      title: config.name || config.title || "Grow Space",
      prefix: config.prefix || "",
      camera: config.camera || null,
      // Controls
      light: config.light || null,
      fan: config.fan || null,
      duct_fan: config.duct_fan || null,
      rdwc_pump: config.rdwc_pump || null,
      air_pump: config.air_pump || null,
      chiller_pump: config.chiller_pump || null,
      // Sensors
      temperature: config.temperature || null,
      humidity: config.humidity || null,
      vpd: config.vpd || null,
      leaf_vpd: config.leaf_vpd || null,
      dew_point: config.dew_point || null,
      // Hydro
      ph: config.ph || null,
      ec: config.ec || null,
      water_temperature: config.water_temperature || null,
      tds: config.tds || null,
      orp: config.orp || null,
      // Lifecycle & AI
      stage: config.stage || null,
      week: config.week || null,
      projection: config.projection || null,
      ai_health_score: config.ai_health_score || null,
      ai_health_summary: config.ai_health_summary || null,
      run_ai_health_check: config.run_ai_health_check || null,
      // Alerts
      mold_risk: config.mold_risk || null,
      flush_due: config.flush_due || null,
      metrics_out_of_range: config.metrics_out_of_range || null,
      ai_critical_alert: config.ai_critical_alert || null,
      // Target bands
      target_ph_low: config.target_ph_low || null,
      target_ph_high: config.target_ph_high || null,
      target_ec_low: config.target_ec_low || null,
      target_ec_high: config.target_ec_high || null,
      target_vpd_low: config.target_vpd_low || null,
      target_vpd_high: config.target_vpd_high || null,
      // Ambient
      ambient_temperature: config.ambient_temperature || null,
      ambient_humidity: config.ambient_humidity || null,
      ...config,
    };

    // Auto-detect based on prefix if fields are empty
    const p = this._config.prefix;
    if (p) {
      if (!this._config.camera) this._config.camera = `camera.grow_tent_${p}_fluent`;
      if (!this._config.light) this._config.light = `light.${p}_controller_grow_light`;
      if (!this._config.fan) this._config.fan = `fan.${p}_controller_circulation_fan`;
      if (!this._config.duct_fan) this._config.duct_fan = `fan.${p}_controller_duct_fan`;
      if (!this._config.temperature) this._config.temperature = `sensor.${p}_controller_inside_temperature`;
      if (!this._config.humidity) this._config.humidity = `sensor.${p}_controller_inside_humidity`;
      if (!this._config.ph) this._config.ph = `sensor.${p}_water_monitor_ph`;
      if (!this._config.ec) this._config.ec = `sensor.${p}_water_monitor_electrical_conductivity`;
      if (!this._config.water_temperature) this._config.water_temperature = `sensor.${p}_water_monitor_temperature`;
    }

    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._updateStates();
  }

  getCardSize() {
    return 7;
  }

  _callService(domain, service, data = {}) {
    if (!this._hass) return;
    this._hass.callService(domain, service, data);
  }

  _moreInfo(entityId) {
    if (!entityId) return;
    const event = new CustomEvent("hass-more-info", {
      bubbles: true,
      composed: true,
      detail: { entityId },
    });
    this.dispatchEvent(event);
  }

  _toggleViewMode() {
    this._viewMode = this._viewMode === "schematic" ? "camera" : "schematic";
    this._render();
  }

  _toggleDrawer(drawerName) {
    this._activeDrawer = this._activeDrawer === drawerName ? null : drawerName;
    this._render();
  }

  _render() {
    if (!this.shadowRoot) return;

    const title = this._config.title;
    const hasCamera = Boolean(this._config.camera);

    this.shadowRoot.innerHTML = `
      <style>
        :host {
          display: block;
          font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
          color: #e6edf3;
          --tg-bg: #0d1117;
          --tg-card-bg: rgba(22, 27, 34, 0.85);
          --tg-border: rgba(255, 255, 255, 0.08);
          --tg-green: #10b981;
          --tg-cyan: #06b6d4;
          --tg-amber: #f59e0b;
          --tg-red: #ef4444;
          --tg-violet: #8b5cf6;
          --tg-glow-green: 0 0 16px rgba(16, 185, 129, 0.4);
          --tg-glow-cyan: 0 0 16px rgba(6, 182, 212, 0.4);
          --tg-glow-amber: 0 0 16px rgba(245, 158, 11, 0.4);
        }

        * {
          box-sizing: border-box;
          margin: 0;
          padding: 0;
        }

        .container {
          background: var(--tg-bg);
          border-radius: 16px;
          border: 1px solid var(--tg-border);
          overflow: hidden;
          box-shadow: 0 8px 32px rgba(0, 0, 0, 0.45);
          position: relative;
        }

        /* HEADER */
        .header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: 14px 18px;
          background: rgba(13, 17, 23, 0.95);
          border-bottom: 1px solid var(--tg-border);
          backdrop-filter: blur(10px);
        }

        .header-title-box {
          display: flex;
          align-items: center;
          gap: 10px;
        }

        .brand-badge {
          width: 32px;
          height: 32px;
          border-radius: 8px;
          background: linear-gradient(135deg, #10b981, #059669);
          display: flex;
          align-items: center;
          justify-content: center;
          font-weight: 800;
          font-size: 16px;
          color: #fff;
          box-shadow: var(--tg-glow-green);
        }

        .title-text h2 {
          font-size: 17px;
          font-weight: 700;
          letter-spacing: -0.3px;
          color: #f0f6fc;
        }

        .stage-pill {
          display: inline-flex;
          align-items: center;
          gap: 5px;
          font-size: 11px;
          font-weight: 600;
          text-transform: uppercase;
          letter-spacing: 0.5px;
          color: #34d399;
          background: rgba(16, 185, 129, 0.12);
          padding: 2px 8px;
          border-radius: 12px;
          border: 1px solid rgba(16, 185, 129, 0.25);
          margin-top: 2px;
        }

        .header-actions {
          display: flex;
          align-items: center;
          gap: 12px;
        }

        /* AI HEALTH SCORE RING */
        .health-ring-box {
          display: flex;
          align-items: center;
          gap: 8px;
          cursor: pointer;
        }

        .health-dial {
          position: relative;
          width: 44px;
          height: 44px;
        }

        .health-dial svg {
          transform: rotate(-90deg);
        }

        .health-dial circle {
          fill: none;
          stroke-width: 3.5;
        }

        .dial-track {
          stroke: rgba(255, 255, 255, 0.08);
        }

        .dial-progress {
          stroke: var(--tg-green);
          stroke-linecap: round;
          transition: stroke-dashoffset 0.8s ease, stroke 0.3s ease;
        }

        .dial-value {
          position: absolute;
          inset: 0;
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 13px;
          font-weight: 700;
          color: #fff;
        }

        .health-label {
          display: flex;
          flex-direction: column;
        }

        .health-label-text {
          font-size: 10px;
          text-transform: uppercase;
          color: #8b949e;
          font-weight: 600;
        }

        .health-status-text {
          font-size: 12px;
          font-weight: 600;
          color: var(--tg-green);
        }

        /* VIEW TOGGLE BUTTON */
        .btn-view-toggle {
          background: rgba(255, 255, 255, 0.06);
          border: 1px solid var(--tg-border);
          color: #c9d1d9;
          padding: 6px 12px;
          border-radius: 8px;
          font-size: 12px;
          font-weight: 600;
          cursor: pointer;
          display: flex;
          align-items: center;
          gap: 6px;
          transition: all 0.2s ease;
        }

        .btn-view-toggle:hover {
          background: rgba(255, 255, 255, 0.12);
          color: #fff;
        }

        /* ALERT BANNER */
        .alert-ribbon {
          display: none;
          align-items: center;
          justify-content: space-between;
          padding: 10px 16px;
          background: linear-gradient(90deg, rgba(239, 68, 68, 0.2), rgba(245, 158, 11, 0.2));
          border-bottom: 1px solid rgba(239, 68, 68, 0.4);
          font-size: 12px;
          font-weight: 600;
          color: #fca5a5;
          animation: pulse-ribbon 2s infinite ease-in-out;
        }

        .alert-ribbon.visible {
          display: flex;
        }

        @keyframes pulse-ribbon {
          0%, 100% { opacity: 0.9; }
          50% { opacity: 1; filter: brightness(1.15); }
        }

        .alert-content {
          display: flex;
          align-items: center;
          gap: 8px;
        }

        .alert-action-btn {
          background: #ef4444;
          color: #fff;
          border: none;
          padding: 4px 10px;
          border-radius: 6px;
          font-size: 11px;
          font-weight: 700;
          cursor: pointer;
        }

        /* DIGITAL TWIN CANVAS */
        .twin-canvas {
          position: relative;
          width: 100%;
          min-height: 380px;
          background: radial-gradient(circle at 50% 30%, #161f2e 0%, #090d13 85%);
          overflow: hidden;
          display: flex;
          flex-direction: column;
          justify-content: space-between;
          padding: 16px;
        }

        /* CAMERA MODE CONTAINER */
        .camera-container {
          position: absolute;
          inset: 0;
          display: none;
          background: #000;
          z-index: 1;
        }

        .camera-container.active {
          display: block;
        }

        .camera-feed {
          width: 100%;
          height: 100%;
          object-fit: cover;
        }

        .camera-scrim {
          position: absolute;
          inset: 0;
          background: linear-gradient(to bottom, rgba(13,17,23,0.4) 0%, transparent 40%, rgba(13,17,23,0.7) 100%);
        }

        /* SCHEMATIC LAYERS */
        .schematic-content {
          position: relative;
          z-index: 2;
          width: 100%;
          height: 100%;
          display: flex;
          flex-direction: column;
          justify-content: space-between;
          gap: 16px;
        }

        /* TOP RIG (LIGHT & DUCT FAN) */
        .overhead-rig {
          display: flex;
          justify-content: space-between;
          align-items: flex-start;
          width: 100%;
          position: relative;
        }

        .light-assembly {
          position: absolute;
          left: 50%;
          transform: translateX(-50%);
          display: flex;
          flex-direction: column;
          align-items: center;
          cursor: pointer;
        }

        .light-bar {
          width: 240px;
          height: 14px;
          background: #30363d;
          border-radius: 4px;
          border: 1px solid #484f58;
          position: relative;
          box-shadow: 0 4px 12px rgba(0,0,0,0.5);
          transition: all 0.3s ease;
        }

        .light-bar.on {
          background: #fffbeb;
          border-color: #fde68a;
          box-shadow: 0 0 25px rgba(253, 224, 71, 0.75), 0 0 50px rgba(245, 158, 11, 0.4);
        }

        .light-cone {
          width: 290px;
          height: 160px;
          background: linear-gradient(to bottom, rgba(254, 240, 138, 0.28) 0%, rgba(254, 240, 138, 0.03) 80%, transparent 100%);
          clip-path: polygon(15% 0%, 85% 0%, 100% 100%, 0% 100%);
          opacity: 0;
          transition: opacity 0.4s ease;
          pointer-events: none;
        }

        .light-cone.on {
          opacity: 1;
        }

        .light-badge {
          margin-top: 4px;
          background: rgba(22, 27, 34, 0.85);
          border: 1px solid var(--tg-border);
          padding: 3px 8px;
          border-radius: 12px;
          font-size: 11px;
          font-weight: 600;
          color: #fbbf24;
          display: flex;
          align-items: center;
          gap: 4px;
          backdrop-filter: blur(6px);
        }

        /* DUCT / INLINE EXHAUST FAN */
        .duct-fan-box {
          display: flex;
          align-items: center;
          gap: 8px;
          background: rgba(22, 27, 34, 0.85);
          border: 1px solid var(--tg-border);
          padding: 6px 12px;
          border-radius: 10px;
          cursor: pointer;
          backdrop-filter: blur(8px);
          transition: all 0.2s ease;
        }

        .duct-fan-box:hover {
          background: rgba(30, 41, 59, 0.95);
          border-color: rgba(6, 182, 212, 0.4);
        }

        .fan-icon {
          width: 24px;
          height: 24px;
          display: flex;
          align-items: center;
          justify-content: center;
        }

        .fan-rotor {
          transform-origin: center;
        }

        .fan-rotor.spinning {
          animation: spin 1s linear infinite;
        }

        .fan-rotor.spinning-fast {
          animation: spin 0.4s linear infinite;
        }

        @keyframes spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }

        .duct-fan-info {
          display: flex;
          flex-direction: column;
        }

        .fan-title {
          font-size: 10px;
          color: #8b949e;
          text-transform: uppercase;
          font-weight: 600;
        }

        .fan-speed {
          font-size: 12px;
          font-weight: 700;
          color: var(--tg-cyan);
        }

        /* CIRCULATION FAN */
        .circ-fan-box {
          display: flex;
          align-items: center;
          gap: 8px;
          background: rgba(22, 27, 34, 0.85);
          border: 1px solid var(--tg-border);
          padding: 6px 12px;
          border-radius: 10px;
          cursor: pointer;
          backdrop-filter: blur(8px);
        }

        /* CANOPY HUD CAPSULE */
        .canopy-hud-wrapper {
          display: flex;
          justify-content: center;
          width: 100%;
          position: relative;
          z-index: 3;
        }

        .hud-capsule {
          background: rgba(13, 17, 23, 0.88);
          border: 1px solid rgba(16, 185, 129, 0.4);
          border-radius: 16px;
          padding: 10px 18px;
          display: flex;
          align-items: center;
          gap: 20px;
          box-shadow: 0 8px 24px rgba(0, 0, 0, 0.5), var(--tg-glow-green);
          backdrop-filter: blur(14px);
          transition: all 0.3s ease;
        }

        .hud-capsule.alert {
          border-color: var(--tg-red);
          box-shadow: 0 8px 24px rgba(0, 0, 0, 0.5), 0 0 16px rgba(239, 68, 68, 0.4);
        }

        .hud-metric {
          display: flex;
          flex-direction: column;
          align-items: center;
        }

        .hud-metric-label {
          font-size: 10px;
          color: #8b949e;
          font-weight: 600;
          text-transform: uppercase;
          letter-spacing: 0.5px;
        }

        .hud-metric-val {
          font-size: 18px;
          font-weight: 800;
          color: #f0f6fc;
          letter-spacing: -0.5px;
        }

        .hud-metric-val span {
          font-size: 12px;
          font-weight: 500;
          color: #8b949e;
        }

        .hud-divider {
          width: 1px;
          height: 28px;
          background: rgba(255, 255, 255, 0.1);
        }

        /* RESERVOIR & PUMP DOCK (BOTTOM) */
        .reservoir-dock {
          width: 100%;
          background: rgba(13, 17, 23, 0.92);
          border: 1px solid rgba(6, 182, 212, 0.3);
          border-radius: 14px;
          padding: 12px 16px;
          display: flex;
          flex-wrap: wrap;
          align-items: center;
          justify-content: space-between;
          gap: 12px;
          box-shadow: 0 4px 20px rgba(0,0,0,0.5), var(--tg-glow-cyan);
          backdrop-filter: blur(12px);
          position: relative;
          overflow: hidden;
        }

        .water-wave-bg {
          position: absolute;
          inset: 0;
          background: linear-gradient(180deg, transparent 40%, rgba(6, 182, 212, 0.08) 100%);
          pointer-events: none;
        }

        .reservoir-metrics {
          display: flex;
          align-items: center;
          gap: 16px;
        }

        .res-pill {
          display: flex;
          flex-direction: column;
        }

        .res-pill-label {
          font-size: 9px;
          font-weight: 700;
          color: #8b949e;
          text-transform: uppercase;
        }

        .res-pill-val {
          font-size: 14px;
          font-weight: 700;
          color: #e6edf3;
        }

        .res-pill-val.ph { color: #38bdf8; }
        .res-pill-val.ec { color: #a78bfa; }
        .res-pill-val.temp { color: #34d399; }

        /* PUMP CONTROL BUTTONS */
        .pump-controls {
          display: flex;
          align-items: center;
          gap: 8px;
          z-index: 2;
        }

        .pump-btn {
          background: rgba(255, 255, 255, 0.05);
          border: 1px solid var(--tg-border);
          border-radius: 8px;
          padding: 6px 10px;
          display: flex;
          align-items: center;
          gap: 6px;
          font-size: 11px;
          font-weight: 600;
          color: #8b949e;
          cursor: pointer;
          transition: all 0.2s ease;
        }

        .pump-btn:hover {
          background: rgba(255, 255, 255, 0.1);
          color: #fff;
        }

        .pump-btn.active {
          background: rgba(6, 182, 212, 0.2);
          border-color: var(--tg-cyan);
          color: #e0f2fe;
          box-shadow: 0 0 10px rgba(6, 182, 212, 0.35);
        }

        .pump-btn.active.chiller {
          background: rgba(56, 189, 248, 0.2);
          border-color: #38bdf8;
          color: #f0f9ff;
        }

        .pump-dot {
          width: 7px;
          height: 7px;
          border-radius: 50%;
          background: #484f58;
        }

        .pump-btn.active .pump-dot {
          background: var(--tg-cyan);
          box-shadow: 0 0 6px var(--tg-cyan);
        }

        /* BOTTOM DRAWER / TABS */
        .drawer-bar {
          display: flex;
          border-top: 1px solid var(--tg-border);
          background: rgba(13, 17, 23, 0.95);
        }

        .drawer-tab {
          flex: 1;
          text-align: center;
          padding: 10px 0;
          font-size: 11px;
          font-weight: 600;
          color: #8b949e;
          cursor: pointer;
          border-bottom: 2px solid transparent;
          transition: all 0.2s ease;
          text-transform: uppercase;
          letter-spacing: 0.5px;
        }

        .drawer-tab:hover {
          color: #e6edf3;
        }

        .drawer-tab.active {
          color: var(--tg-green);
          border-bottom-color: var(--tg-green);
          background: rgba(16, 185, 129, 0.05);
        }

        /* DRAWER CONTENT BODY */
        .drawer-body {
          display: none;
          padding: 16px;
          background: #11161d;
          border-top: 1px solid var(--tg-border);
          font-size: 13px;
        }

        .drawer-body.open {
          display: block;
        }

        /* RANGE METER COMPONENT */
        .meter-group {
          display: flex;
          flex-direction: column;
          gap: 12px;
        }

        .meter-row {
          display: flex;
          flex-direction: column;
          gap: 4px;
        }

        .meter-header {
          display: flex;
          justify-content: space-between;
          font-size: 11px;
          font-weight: 600;
          color: #8b949e;
        }

        .meter-track {
          height: 8px;
          background: #21262d;
          border-radius: 4px;
          position: relative;
          overflow: hidden;
        }

        .meter-optimal {
          position: absolute;
          top: 0;
          bottom: 0;
          background: rgba(16, 185, 129, 0.4);
          border-left: 1px solid var(--tg-green);
          border-right: 1px solid var(--tg-green);
        }

        .meter-needle {
          position: absolute;
          top: -2px;
          width: 4px;
          height: 12px;
          background: #fff;
          border-radius: 2px;
          box-shadow: 0 0 6px #fff;
          transform: translateX(-50%);
          transition: left 0.5s ease;
        }

        /* QUICK ACTION BUTTONS */
        .actions-tray {
          display: flex;
          gap: 8px;
          margin-top: 12px;
          flex-wrap: wrap;
        }

        .action-chip {
          background: rgba(255, 255, 255, 0.05);
          border: 1px solid var(--tg-border);
          border-radius: 8px;
          padding: 8px 12px;
          font-size: 12px;
          font-weight: 600;
          color: #c9d1d9;
          cursor: pointer;
          display: flex;
          align-items: center;
          gap: 6px;
        }

        .action-chip:hover {
          background: rgba(255, 255, 255, 0.1);
          color: #fff;
        }

        /* RESPONSIVE QUERIES */
        @media (max-width: 600px) {
          .hud-capsule {
            padding: 8px 12px;
            gap: 12px;
          }
          .hud-metric-val {
            font-size: 15px;
          }
          .light-bar {
            width: 160px;
          }
          .light-cone {
            width: 200px;
          }
          .reservoir-dock {
            flex-direction: column;
            align-items: stretch;
          }
          .pump-controls {
            justify-content: space-between;
          }
        }
      </style>

      <div class="container">
        <!-- TOP HEADER -->
        <div class="header">
          <div class="header-title-box">
            <div class="brand-badge">🌿</div>
            <div class="title-text">
              <h2>${title}</h2>
              <div class="stage-pill" id="stage-badge">Loading stage...</div>
            </div>
          </div>

          <div class="header-actions">
            <!-- AI HEALTH SCORE DIAL -->
            <div class="health-ring-box" id="health-ring-box" title="AI Health Diagnostics">
              <div class="health-dial">
                <svg width="44" height="44">
                  <circle class="dial-track" cx="22" cy="22" r="17" />
                  <circle class="dial-progress" id="dial-bar" cx="22" cy="22" r="17" stroke-dasharray="106.8" stroke-dashoffset="106.8" />
                </svg>
                <div class="dial-value" id="dial-val">--</div>
              </div>
              <div class="health-label">
                <span class="health-label-text">AI Health</span>
                <span class="health-status-text" id="health-status">Nominal</span>
              </div>
            </div>

            <!-- VIEW MODE TOGGLE -->
            ${
              hasCamera
                ? `<button class="btn-view-toggle" id="btn-view-toggle">
                    ${this._viewMode === "schematic" ? "📷 Live Cam" : "📐 Schematic"}
                   </button>`
                : ""
            }
          </div>
        </div>

        <!-- CONDITIONAL ALERT RIBBON -->
        <div class="alert-ribbon" id="alert-ribbon">
          <div class="alert-content">
            <span>⚠️</span>
            <span id="alert-text">Attention Required</span>
          </div>
          <button class="alert-action-btn" id="alert-btn">Inspect</button>
        </div>

        <!-- MAIN DIGITAL TWIN CANVAS -->
        <div class="twin-canvas">
          <!-- LIVE CAMERA BACKDROP -->
          <div class="camera-container ${this._viewMode === "camera" ? "active" : ""}" id="camera-box">
            ${
              hasCamera
                ? (() => {
                    const camState = getState(this._hass, this._config.camera);
                    const token = camState?.attributes?.access_token;
                    const initialSrc = token
                      ? `/api/camera_proxy_stream/${this._config.camera}?token=${token}`
                      : (camState?.attributes?.entity_picture || `/api/camera_proxy/${this._config.camera}`);
                    return `<img class="camera-feed" id="camera-img" src="${initialSrc}" alt="Live Tent Feed" />`;
                  })()
                : ""
            }
            <div class="camera-scrim"></div>
          </div>

          <!-- SCHEMATIC OVERLAY -->
          <div class="schematic-content">
            <!-- OVERHEAD LIGHT & DUCT FAN RIG -->
            <div class="overhead-rig">
              <!-- DUCT FAN -->
              <div class="duct-fan-box" id="duct-fan-box" title="Inline Exhaust Fan">
                <div class="fan-icon">
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#06b6d4" stroke-width="2">
                    <g class="fan-rotor" id="duct-rotor">
                      <path d="M12 12c-2-2-4-1-6 0s-3 3-2 5 3 2 5 0 3-3 3-5z" />
                      <path d="M12 12c2-2 1-4 0-6s-3-3-5-2-2 3 0 5 3 3 5 3z" />
                      <path d="M12 12c2 2 4 1 6 0s3-3 2-5-3-2-5 0-3 3-3 5z" />
                      <path d="M12 12c-2 2-1 4 0 6s3 3 5 2 2-3 0-5-3-3-5-3z" />
                    </g>
                    <circle cx="12" cy="12" r="2" fill="#06b6d4" />
                  </svg>
                </div>
                <div class="duct-fan-info">
                  <span class="fan-title">Exhaust</span>
                  <span class="fan-speed" id="duct-speed-text">--%</span>
                </div>
              </div>

              <!-- GROW LIGHT -->
              <div class="light-assembly" id="light-box" title="Grow Light Fixture">
                <div class="light-bar" id="light-bar"></div>
                <div class="light-cone" id="light-cone"></div>
                <div class="light-badge">
                  <span>💡</span>
                  <span id="light-power-text">OFF</span>
                </div>
              </div>

              <!-- CIRCULATION FAN -->
              <div class="circ-fan-box" id="circ-fan-box" title="Circulation Fan">
                <div class="fan-icon">
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#10b981" stroke-width="2">
                    <g class="fan-rotor" id="circ-rotor">
                      <path d="M12 12c-2-2-4-1-6 0s-3 3-2 5 3 2 5 0 3-3 3-5z" />
                      <path d="M12 12c2-2 1-4 0-6s-3-3-5-2-2 3 0 5 3 3 5 3z" />
                      <path d="M12 12c2 2 4 1 6 0s3-3 2-5-3-2-5 0-3 3-3 5z" />
                      <path d="M12 12c-2 2-1 4 0 6s3 3 5 2 2-3 0-5-3-3-5-3z" />
                    </g>
                    <circle cx="12" cy="12" r="2" fill="#10b981" />
                  </svg>
                </div>
                <div class="duct-fan-info">
                  <span class="fan-title">Circ Fan</span>
                  <span class="fan-speed" id="circ-fan-text" style="color: #10b981;">--</span>
                </div>
              </div>
            </div>

            <!-- CANOPY HUD CAPSULE -->
            <div class="canopy-hud-wrapper">
              <div class="hud-capsule" id="canopy-hud">
                <div class="hud-metric">
                  <span class="hud-metric-label">Temp</span>
                  <div class="hud-metric-val" id="canopy-temp">--<span>°F</span></div>
                </div>
                <div class="hud-divider"></div>
                <div class="hud-metric">
                  <span class="hud-metric-label">Humidity</span>
                  <div class="hud-metric-val" id="canopy-rh">--<span>%</span></div>
                </div>
                <div class="hud-divider"></div>
                <div class="hud-metric">
                  <span class="hud-metric-label">Leaf VPD</span>
                  <div class="hud-metric-val" id="canopy-vpd" style="color: #34d399;">--<span> kPa</span></div>
                </div>
              </div>
            </div>

            <!-- RESERVOIR BASE DOCK -->
            <div class="reservoir-dock">
              <div class="water-wave-bg"></div>
              <div class="reservoir-metrics">
                <div class="res-pill">
                  <span class="res-pill-label">pH</span>
                  <span class="res-pill-val ph" id="res-ph">--</span>
                </div>
                <div class="res-pill">
                  <span class="res-pill-label">EC</span>
                  <span class="res-pill-val ec" id="res-ec">--</span>
                </div>
                <div class="res-pill">
                  <span class="res-pill-label">H₂O Temp</span>
                  <span class="res-pill-val temp" id="res-temp">--°F</span>
                </div>
                <div class="res-pill">
                  <span class="res-pill-label">TDS</span>
                  <span class="res-pill-val" id="res-tds">--</span>
                </div>
              </div>

              <!-- PUMP CONTROLS -->
              <div class="pump-controls">
                <button class="pump-btn" id="btn-rdwc" title="Toggle RDWC Circulation Pump">
                  <span class="pump-dot"></span>
                  <span>RDWC</span>
                </button>
                <button class="pump-btn" id="btn-air" title="Toggle Aeration Bubbler">
                  <span class="pump-dot"></span>
                  <span>Air Pump</span>
                </button>
                <button class="pump-btn chiller" id="btn-chiller" title="Toggle Water Chiller Pump">
                  <span class="pump-dot"></span>
                  <span>Chiller</span>
                </button>
              </div>
            </div>
          </div>
        </div>

        <!-- DRAWER TABS -->
        <div class="drawer-bar">
          <div class="drawer-tab ${this._activeDrawer === "bands" ? "active" : ""}" id="tab-bands">Target Bands</div>
          <div class="drawer-tab ${this._activeDrawer === "advisor" ? "active" : ""}" id="tab-advisor">AI Advisor</div>
          <div class="drawer-tab ${this._activeDrawer === "actions" ? "active" : ""}" id="tab-actions">Quick Actions</div>
        </div>

        <!-- DRAWER BODIES -->
        <div class="drawer-body ${this._activeDrawer === "bands" ? "open" : ""}" id="body-bands">
          <div class="meter-group" id="meters-container">
            <!-- Rendered dynamically -->
          </div>
        </div>

        <div class="drawer-body ${this._activeDrawer === "advisor" ? "open" : ""}" id="body-advisor">
          <p id="advisor-summary-text" style="line-height: 1.5; color: #c9d1d9;">No AI summary available yet.</p>
          <div style="margin-top: 12px; display: flex; gap: 8px;">
            <button class="alert-action-btn" id="btn-run-ai" style="background: var(--tg-violet);">🧠 Run AI Health Check Now</button>
          </div>
        </div>

        <div class="drawer-body ${this._activeDrawer === "actions" ? "open" : ""}" id="body-actions">
          <div class="actions-tray">
            <button class="action-chip" id="action-inspect">💡 Inspection Light (100%)</button>
            <button class="action-chip" id="action-feed">🧪 Feeding Mode</button>
            <button class="action-chip" id="action-flush">🚀 Flush Routine</button>
          </div>
        </div>
      </div>
    `;

    this._bindEvents();
    this._updateStates();
  }

  _bindEvents() {
    const root = this.shadowRoot;
    if (!root) return;

    // View toggle
    const btnView = root.getElementById("btn-view-toggle");
    if (btnView) btnView.onclick = () => this._toggleViewMode();

    // Drawer tabs
    const tabBands = root.getElementById("tab-bands");
    if (tabBands) tabBands.onclick = () => this._toggleDrawer("bands");
    const tabAdvisor = root.getElementById("tab-advisor");
    if (tabAdvisor) tabAdvisor.onclick = () => this._toggleDrawer("advisor");
    const tabActions = root.getElementById("tab-actions");
    if (tabActions) tabActions.onclick = () => this._toggleDrawer("actions");

    // Controls
    const lightBox = root.getElementById("light-box");
    if (lightBox && this._config.light) {
      lightBox.onclick = () => this._callService("homeassistant", "toggle", { entity_id: this._config.light });
    }

    const ductBox = root.getElementById("duct-fan-box");
    if (ductBox && this._config.duct_fan) {
      ductBox.onclick = () => this._moreInfo(this._config.duct_fan);
    }

    const circBox = root.getElementById("circ-fan-box");
    if (circBox && this._config.fan) {
      circBox.onclick = () => this._callService("homeassistant", "toggle", { entity_id: this._config.fan });
    }

    // Pump buttons
    const btnRdwc = root.getElementById("btn-rdwc");
    if (btnRdwc && this._config.rdwc_pump) {
      btnRdwc.onclick = () => this._callService("homeassistant", "toggle", { entity_id: this._config.rdwc_pump });
    }

    const btnAir = root.getElementById("btn-air");
    if (btnAir && this._config.air_pump) {
      btnAir.onclick = () => this._callService("homeassistant", "toggle", { entity_id: this._config.air_pump });
    }

    const btnChiller = root.getElementById("btn-chiller");
    if (btnChiller && this._config.chiller_pump) {
      btnChiller.onclick = () => this._callService("homeassistant", "toggle", { entity_id: this._config.chiller_pump });
    }

    // Health click
    const healthBox = root.getElementById("health-ring-box");
    if (healthBox && this._config.ai_health_score) {
      healthBox.onclick = () => this._moreInfo(this._config.ai_health_score);
    }

    // AI Check button
    const btnRunAi = root.getElementById("btn-run-ai");
    if (btnRunAi) {
      btnRunAi.onclick = () => {
        btnRunAi.textContent = "⏳ Running AI Diagnostic...";
        this._callService("tendrilgrow", "run_ai_health_check", {});
        setTimeout(() => {
          btnRunAi.textContent = "🧠 Run AI Health Check Now";
        }, 4000);
      };
    }

    // Preset Inspection Light
    const actInspect = root.getElementById("action-inspect");
    if (actInspect && this._config.light) {
      actInspect.onclick = () => {
        this._callService("light", "turn_on", {
          entity_id: this._config.light,
          brightness: 255,
        });
      };
    }
  }

  _updateStates() {
    if (!this._hass || !this.shadowRoot) return;
    const root = this.shadowRoot;

    // Stage
    const stage = getStateStr(this._hass, this._config.stage, "Vegetative");
    const week = getStateStr(this._hass, this._config.week, "1");
    const stageBadge = root.getElementById("stage-badge");
    if (stageBadge) {
      stageBadge.textContent = `${stage.toUpperCase()} • WEEK ${week}`;
    }

    // AI Health Dial
    const score = getStateNum(this._hass, this._config.ai_health_score, 90);
    const dialVal = root.getElementById("dial-val");
    const dialBar = root.getElementById("dial-progress") || root.getElementById("dial-bar");
    const healthStatus = root.getElementById("health-status");
    if (dialVal && dialBar) {
      dialVal.textContent = score !== null ? Math.round(score) : "--";
      const circumference = 2 * Math.PI * 17; // ~106.8
      const offset = circumference - ((score || 0) / 100) * circumference;
      dialBar.style.strokeDashoffset = offset;
      if (score >= 75) {
        dialBar.style.stroke = "var(--tg-green)";
        if (healthStatus) {
          healthStatus.textContent = "Nominal";
          healthStatus.style.color = "var(--tg-green)";
        }
      } else if (score >= 50) {
        dialBar.style.stroke = "var(--tg-amber)";
        if (healthStatus) {
          healthStatus.textContent = "Attention";
          healthStatus.style.color = "var(--tg-amber)";
        }
      } else {
        dialBar.style.stroke = "var(--tg-red)";
        if (healthStatus) {
          healthStatus.textContent = "Critical";
          healthStatus.style.color = "var(--tg-red)";
        }
      }
    }

    // Light State
    const lightState = getState(this._hass, this._config.light);
    const lightBar = root.getElementById("light-bar");
    const lightCone = root.getElementById("light-cone");
    const lightPower = root.getElementById("light-power-text");
    if (lightState && lightBar && lightCone && lightPower) {
      const isOn = lightState.state === "on";
      const brightness = lightState.attributes.brightness ? Math.round((lightState.attributes.brightness / 255) * 100) : null;
      if (isOn) {
        lightBar.classList.add("on");
        lightCone.classList.add("on");
        lightPower.textContent = brightness !== null ? `${brightness}%` : "ON";
      } else {
        lightBar.classList.remove("on");
        lightCone.classList.remove("on");
        lightPower.textContent = "OFF";
      }
    }

    // Duct Fan
    const ductState = getState(this._hass, this._config.duct_fan);
    const ductRotor = root.getElementById("duct-rotor");
    const ductSpeed = root.getElementById("duct-speed-text");
    if (ductState && ductRotor && ductSpeed) {
      const isFanOn = ductState.state === "on";
      const pct = ductState.attributes.percentage || (isFanOn ? 100 : 0);
      ductSpeed.textContent = isFanOn ? `${pct}%` : "OFF";
      if (isFanOn) {
        ductRotor.classList.add(pct > 60 ? "spinning-fast" : "spinning");
      } else {
        ductRotor.classList.remove("spinning", "spinning-fast");
      }
    }

    // Circulation Fan
    const circState = getState(this._hass, this._config.fan);
    const circRotor = root.getElementById("circ-rotor");
    const circText = root.getElementById("circ-fan-text");
    if (circState && circRotor && circText) {
      const isOn = circState.state === "on";
      circText.textContent = isOn ? "ON" : "OFF";
      if (isOn) {
        circRotor.classList.add("spinning");
      } else {
        circRotor.classList.remove("spinning");
      }
    }

    // Canopy Climate
    const temp = getStateStr(this._hass, this._config.temperature, "--");
    const rh = getStateStr(this._hass, this._config.humidity, "--");
    const vpd = getStateStr(this._hass, this._config.leaf_vpd || this._config.vpd, "--");
    const elTemp = root.getElementById("canopy-temp");
    const elRh = root.getElementById("canopy-rh");
    const elVpd = root.getElementById("canopy-vpd");
    if (elTemp) elTemp.innerHTML = `${temp}<span>°F</span>`;
    if (elRh) elRh.innerHTML = `${rh}<span>%</span>`;
    if (elVpd) elVpd.innerHTML = `${vpd}<span> kPa</span>`;

    // Hydro Reservoir
    const ph = getStateStr(this._hass, this._config.ph, "--");
    const ec = getStateStr(this._hass, this._config.ec, "--");
    const wtemp = getStateStr(this._hass, this._config.water_temperature, "--");
    const tds = getStateStr(this._hass, this._config.tds, "--");
    const elPh = root.getElementById("res-ph");
    const elEc = root.getElementById("res-ec");
    const elWtemp = root.getElementById("res-temp");
    const elTds = root.getElementById("res-tds");
    if (elPh) elPh.textContent = ph;
    if (elEc) elEc.textContent = ec;
    if (elWtemp) elWtemp.textContent = `${wtemp}°F`;
    if (elTds) elTds.textContent = tds;

    // Pumps
    const rdwcState = getState(this._hass, this._config.rdwc_pump);
    const airState = getState(this._hass, this._config.air_pump);
    const chillerState = getState(this._hass, this._config.chiller_pump);
    const btnRdwc = root.getElementById("btn-rdwc");
    const btnAir = root.getElementById("btn-air");
    const btnChiller = root.getElementById("btn-chiller");
    if (btnRdwc && rdwcState) {
      btnRdwc.classList.toggle("active", rdwcState.state === "on");
    }
    if (btnAir && airState) {
      btnAir.classList.toggle("active", airState.state === "on");
    }
    if (btnChiller && chillerState) {
      btnChiller.classList.toggle("active", chillerState.state === "on");
    }

    // Alerts
    const moldRisk = getState(this._hass, this._config.mold_risk);
    const flushDue = getState(this._hass, this._config.flush_due);
    const metricsOutOfRange = getState(this._hass, this._config.metrics_out_of_range);
    const ribbon = root.getElementById("alert-ribbon");
    const alertText = root.getElementById("alert-text");
    if (ribbon && alertText) {
      if (moldRisk && moldRisk.state === "on") {
        ribbon.classList.add("visible");
        alertText.textContent = "High Mold Risk Detected: Low VPD & Elevated Humidity";
      } else if (flushDue && flushDue.state === "on") {
        ribbon.classList.add("visible");
        alertText.textContent = "Reservoir Flush Cycle Due";
      } else if (metricsOutOfRange && metricsOutOfRange.state === "on") {
        ribbon.classList.add("visible");
        alertText.textContent = "Environmental Metrics Out of Optimal Target Bands";
      } else {
        ribbon.classList.remove("visible");
      }
    }

    // AI Summary in Advisor Drawer
    const aiSummary = getStateStr(this._hass, this._config.ai_health_summary, null);
    const advisorText = root.getElementById("advisor-summary-text");
    if (advisorText && aiSummary) {
      advisorText.textContent = aiSummary;
    }

    // Range Meters in Bands Drawer
    this._renderRangeMeters();

    // Camera Feed Refresh with Access Token
    const camImg = root.getElementById("camera-img");
    if (camImg && this._config.camera) {
      const camState = getState(this._hass, this._config.camera);
      if (camState) {
        const token = camState.attributes?.access_token;
        const pic = camState.attributes?.entity_picture;
        const targetSrc = token
          ? `/api/camera_proxy_stream/${this._config.camera}?token=${token}`
          : (pic || `/api/camera_proxy/${this._config.camera}`);
        if (targetSrc && camImg.src !== targetSrc && !camImg.src.endsWith(targetSrc)) {
          camImg.src = targetSrc;
        }
      }
    }
  }

  _renderRangeMeters() {
    const root = this.shadowRoot;
    const container = root.getElementById("meters-container");
    if (!container || this._activeDrawer !== "bands") return;

    const meters = [
      {
        label: "Canopy Temperature",
        val: getStateNum(this._hass, this._config.temperature, 76),
        unit: "°F",
        min: 60,
        max: 90,
        optLow: 72,
        optHigh: 82,
      },
      {
        label: "Relative Humidity",
        val: getStateNum(this._hass, this._config.humidity, 60),
        unit: "%",
        min: 30,
        max: 85,
        optLow: 55,
        optHigh: 68,
      },
      {
        label: "Leaf VPD",
        val: getStateNum(this._hass, this._config.leaf_vpd || this._config.vpd, 1.1),
        unit: "kPa",
        min: 0.4,
        max: 2.0,
        optLow: 0.9,
        optHigh: 1.3,
      },
      {
        label: "Hydroponic pH",
        val: getStateNum(this._hass, this._config.ph, 5.9),
        unit: "",
        min: 4.5,
        max: 7.5,
        optLow: 5.7,
        optHigh: 6.2,
      },
      {
        label: "Electrical Conductivity (EC)",
        val: getStateNum(this._hass, this._config.ec, 1.8),
        unit: "mS",
        min: 0.5,
        max: 3.5,
        optLow: 1.4,
        optHigh: 2.2,
      },
      {
        label: "Water Temperature",
        val: getStateNum(this._hass, this._config.water_temperature, 68),
        unit: "°F",
        min: 55,
        max: 80,
        optLow: 66,
        optHigh: 70,
      },
    ];

    container.innerHTML = meters
      .map((m) => {
        const span = m.max - m.min;
        const optLeft = Math.max(0, Math.min(100, ((m.optLow - m.min) / span) * 100));
        const optWidth = Math.max(0, Math.min(100, ((m.optHigh - m.optLow) / span) * 100));
        const currentPos = m.val !== null ? Math.max(0, Math.min(100, ((m.val - m.min) / span) * 100)) : 50;

        return `
          <div class="meter-row">
            <div class="meter-header">
              <span>${m.label}</span>
              <span style="color: #fff; font-weight: 700;">${m.val !== null ? m.val + m.unit : "--"} <span style="font-weight: 400; color: #8b949e;">(Target: ${m.optLow}-${m.optHigh}${m.unit})</span></span>
            </div>
            <div class="meter-track">
              <div class="meter-optimal" style="left: ${optLeft}%; width: ${optWidth}%;"></div>
              <div class="meter-needle" style="left: ${currentPos}%;"></div>
            </div>
          </div>
        `;
      })
      .join("");
  }
}

// ============================================================================
// 2. TENDRILGROW EXECUTIVE OVERVIEW CARD (<tendrilgrow-overview-card>)
// ============================================================================
class TendrilGrowOverviewCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._config = {};
    this._hass = null;
  }

  setConfig(config) {
    this._config = {
      title: config.title || "Cultivation Network Overview",
      spaces: config.spaces || [],
      ...config,
    };
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._update();
  }

  getCardSize() {
    return 6;
  }

  _callService(domain, service, data = {}) {
    if (!this._hass) return;
    this._hass.callService(domain, service, data);
  }

  _navigate(path) {
    if (!path) return;
    window.history.pushState(null, "", path);
    window.dispatchEvent(new CustomEvent("location-changed"));
  }

  _render() {
    if (!this.shadowRoot) return;

    this.shadowRoot.innerHTML = `
      <style>
        :host {
          display: block;
          font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
          color: #e6edf3;
          --tg-bg: #0b0f17;
          --tg-card-bg: rgba(18, 24, 38, 0.9);
          --tg-border: rgba(255, 255, 255, 0.08);
          --tg-green: #10b981;
          --tg-cyan: #06b6d4;
          --tg-amber: #f59e0b;
          --tg-red: #ef4444;
          --tg-glow-green: 0 0 16px rgba(16, 185, 129, 0.35);
        }

        * {
          box-sizing: border-box;
          margin: 0;
          padding: 0;
        }

        .container {
          background: var(--tg-bg);
          border-radius: 18px;
          border: 1px solid var(--tg-border);
          padding: 18px;
          box-shadow: 0 12px 40px rgba(0, 0, 0, 0.55);
        }

        /* HEADER */
        .header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          margin-bottom: 20px;
          padding-bottom: 14px;
          border-bottom: 1px solid var(--tg-border);
          flex-wrap: wrap;
          gap: 12px;
        }

        .header-title-box {
          display: flex;
          align-items: center;
          gap: 12px;
        }

        .brand-badge {
          width: 34px;
          height: 34px;
          border-radius: 10px;
          background: linear-gradient(135deg, #10b981, #059669);
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 18px;
          box-shadow: var(--tg-glow-green);
        }

        .header h2 {
          font-size: 19px;
          font-weight: 700;
          letter-spacing: -0.3px;
          color: #f0f6fc;
        }

        .header-subtitle {
          font-size: 12px;
          color: #8b949e;
          font-weight: 500;
        }

        .global-alert-badge {
          background: rgba(239, 68, 68, 0.15);
          border: 1px solid rgba(239, 68, 68, 0.4);
          color: #fca5a5;
          padding: 5px 12px;
          border-radius: 20px;
          font-size: 12px;
          font-weight: 700;
          display: flex;
          align-items: center;
          gap: 6px;
          animation: pulse-alert 2s infinite ease-in-out;
        }

        @keyframes pulse-alert {
          0%, 100% { opacity: 0.9; }
          50% { opacity: 1; filter: brightness(1.2); }
        }

        /* SPACES GRID */
        .spaces-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
          gap: 18px;
        }

        /* SPACE CARD */
        .space-card {
          background: var(--tg-card-bg);
          border: 1px solid var(--tg-border);
          border-radius: 16px;
          overflow: hidden;
          cursor: pointer;
          transition: all 0.28s cubic-bezier(0.4, 0, 0.2, 1);
          display: flex;
          flex-direction: column;
          box-shadow: 0 4px 20px rgba(0, 0, 0, 0.35);
          position: relative;
        }

        .space-card:hover {
          border-color: rgba(16, 185, 129, 0.45);
          transform: translateY(-3px);
          box-shadow: 0 10px 32px rgba(16, 185, 129, 0.18), 0 4px 20px rgba(0, 0, 0, 0.5);
        }

        /* HERO VISUAL AREA */
        .space-hero {
          position: relative;
          width: 100%;
          height: 180px;
          background: #0d1117;
          overflow: hidden;
        }

        .space-cam-img {
          width: 100%;
          height: 100%;
          object-fit: cover;
          display: block;
          transition: transform 0.4s ease;
        }

        .space-card:hover .space-cam-img {
          transform: scale(1.03);
        }

        .cam-scrim {
          position: absolute;
          inset: 0;
          background: linear-gradient(180deg, rgba(11, 15, 23, 0.5) 0%, transparent 40%, rgba(18, 24, 38, 0.95) 100%);
          pointer-events: none;
        }

        .schematic-hero {
          height: 120px;
          background: radial-gradient(circle at 50% 40%, #162438 0%, #0d121c 100%);
          display: flex;
          align-items: center;
          justify-content: center;
          gap: 12px;
          position: relative;
        }

        .schematic-icon {
          font-size: 38px;
          filter: drop-shadow(0 0 16px rgba(16, 185, 129, 0.5));
        }

        .live-tag {
          position: absolute;
          top: 10px;
          left: 10px;
          background: rgba(0, 0, 0, 0.7);
          backdrop-filter: blur(6px);
          border: 1px solid rgba(16, 185, 129, 0.5);
          color: #34d399;
          font-size: 10px;
          font-weight: 700;
          padding: 3px 8px;
          border-radius: 12px;
          display: flex;
          align-items: center;
          gap: 5px;
          letter-spacing: 0.5px;
        }

        .pulse-dot {
          width: 6px;
          height: 6px;
          border-radius: 50%;
          background: #10b981;
          box-shadow: 0 0 6px #10b981;
          animation: pulse 1.5s infinite;
        }

        .stage-tag {
          position: absolute;
          top: 10px;
          right: 10px;
          background: rgba(0, 0, 0, 0.75);
          backdrop-filter: blur(6px);
          border: 1px solid rgba(255, 255, 255, 0.15);
          color: #e6edf3;
          font-size: 10px;
          font-weight: 700;
          padding: 3px 8px;
          border-radius: 12px;
          text-transform: uppercase;
          letter-spacing: 0.5px;
        }

        .cam-alert-banner {
          position: absolute;
          bottom: 8px;
          left: 10px;
          right: 10px;
          background: rgba(239, 68, 68, 0.9);
          backdrop-filter: blur(8px);
          color: #fff;
          font-size: 11px;
          font-weight: 700;
          padding: 5px 10px;
          border-radius: 8px;
          display: flex;
          align-items: center;
          gap: 6px;
          box-shadow: 0 4px 12px rgba(239, 68, 68, 0.4);
          animation: pulse-alert 2s infinite ease-in-out;
        }

        /* CARD BODY */
        .card-body {
          padding: 14px 16px 16px;
          display: flex;
          flex-direction: column;
          gap: 12px;
          flex: 1;
        }

        .title-row {
          display: flex;
          align-items: center;
          justify-content: space-between;
        }

        .space-name {
          font-size: 16px;
          font-weight: 700;
          color: #fff;
          letter-spacing: -0.2px;
        }

        /* RADIAL HEALTH DIAL */
        .health-dial-box {
          position: relative;
          width: 44px;
          height: 44px;
          display: flex;
          align-items: center;
          justify-content: center;
        }

        .health-dial-box svg {
          transform: rotate(-90deg);
          width: 44px;
          height: 44px;
        }

        .health-dial-box circle {
          fill: none;
          stroke-width: 3.5;
        }

        .health-track {
          stroke: rgba(255, 255, 255, 0.08);
        }

        .health-ring {
          stroke-linecap: round;
          transition: stroke-dashoffset 0.8s ease, stroke 0.3s ease;
        }

        .health-score-val {
          position: absolute;
          inset: 0;
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 12px;
          font-weight: 800;
          color: #fff;
        }

        /* TELEMETRY CAPSULES */
        .capsules-grid {
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: 8px;
        }

        .telemetry-capsule {
          background: rgba(13, 17, 23, 0.7);
          border: 1px solid rgba(255, 255, 255, 0.06);
          border-radius: 10px;
          padding: 8px 10px;
          display: flex;
          flex-direction: column;
          gap: 4px;
        }

        .capsule-title {
          font-size: 9px;
          font-weight: 700;
          text-transform: uppercase;
          letter-spacing: 0.5px;
          color: #8b949e;
          display: flex;
          align-items: center;
          gap: 4px;
        }

        .capsule-row {
          display: flex;
          justify-content: space-between;
          align-items: baseline;
        }

        .metric-cell {
          display: flex;
          flex-direction: column;
        }

        .metric-label {
          font-size: 8.5px;
          text-transform: uppercase;
          color: #6e7681;
          font-weight: 600;
        }

        .metric-val {
          font-size: 13px;
          font-weight: 700;
          color: #f0f6fc;
        }

        .metric-val.cyan {
          color: #38bdf8;
        }

        .metric-val.green {
          color: #34d399;
        }

        /* CONTROLS & ACTION ROW */
        .controls-row {
          display: flex;
          align-items: center;
          justify-content: space-between;
          margin-top: 4px;
          padding-top: 10px;
          border-top: 1px solid rgba(255, 255, 255, 0.06);
          gap: 8px;
        }

        .quick-toggles {
          display: flex;
          gap: 6px;
        }

        .btn-toggle {
          background: rgba(255, 255, 255, 0.05);
          border: 1px solid var(--tg-border);
          color: #8b949e;
          padding: 5px 9px;
          border-radius: 8px;
          font-size: 11px;
          font-weight: 600;
          cursor: pointer;
          display: flex;
          align-items: center;
          gap: 5px;
          transition: all 0.2s ease;
        }

        .btn-toggle:hover {
          background: rgba(255, 255, 255, 0.1);
          color: #fff;
        }

        .btn-toggle.active {
          background: rgba(16, 185, 129, 0.15);
          border-color: rgba(16, 185, 129, 0.4);
          color: #34d399;
          box-shadow: 0 0 10px rgba(16, 185, 129, 0.2);
        }

        .btn-cockpit {
          background: linear-gradient(135deg, rgba(16, 185, 129, 0.2), rgba(5, 150, 105, 0.2));
          border: 1px solid rgba(16, 185, 129, 0.4);
          color: #34d399;
          padding: 5px 12px;
          border-radius: 8px;
          font-size: 11px;
          font-weight: 700;
          cursor: pointer;
          display: flex;
          align-items: center;
          gap: 4px;
          transition: all 0.2s ease;
          margin-left: auto;
        }

        .btn-cockpit:hover {
          background: #10b981;
          color: #0b0f17;
          border-color: #10b981;
          box-shadow: var(--tg-glow-green);
        }
      </style>

      <div class="container">
        <div class="header">
          <div class="header-title-box">
            <div class="brand-badge">🌿</div>
            <div>
              <h2>${this._config.title}</h2>
              <div class="header-subtitle" id="network-subtitle">Cultivation Network Active</div>
            </div>
          </div>
          <div class="global-alert-badge" id="global-alert-badge" style="display: none;">
            <span>⚠️</span>
            <span id="global-alert-count">Active Alerts</span>
          </div>
        </div>
        <div class="spaces-grid" id="spaces-grid">
          <!-- Dynamically populated -->
        </div>
      </div>
    `;

    this._update();
  }

  _update() {
    if (!this._hass || !this.shadowRoot) return;
    const grid = this.shadowRoot.getElementById("spaces-grid");
    if (!grid) return;

    const spaces = this._config.spaces || [];
    let activeAlertCount = 0;

    grid.innerHTML = spaces
      .map((s, idx) => {
        const temp = getStateStr(this._hass, s.temperature, "--");
        const rh = getStateStr(this._hass, s.humidity, "--");
        const vpd = getStateStr(this._hass, s.leaf_vpd || s.vpd, "--");
        const ph = getStateStr(this._hass, s.ph, "--");
        const ec = getStateStr(this._hass, s.ec, "--");
        const waterTemp = getStateStr(this._hass, s.water_temperature, "--");
        const score = getStateNum(this._hass, s.ai_health_score, 90);
        const stage = getStateStr(this._hass, s.stage, "Grow Space");
        const lightOn = getState(this._hass, s.light)?.state === "on";
        const fanOn = getState(this._hass, s.fan)?.state === "on";

        // Alerts check
        const moldRisk = getState(this._hass, s.mold_risk)?.state === "on";
        const flushDue = getState(this._hass, s.flush_due)?.state === "on";
        const metricsOut = getState(this._hass, s.metrics_out_of_range)?.state === "on";
        const criticalAlert = getState(this._hass, s.ai_critical_alert)?.state === "on";

        let alertMsg = null;
        if (criticalAlert) alertMsg = "Critical AI Alert";
        else if (moldRisk) alertMsg = "High Mold Risk Detected";
        else if (flushDue) alertMsg = "Reservoir Flush Due";
        else if (metricsOut) alertMsg = "Target Bands Out of Range";

        if (alertMsg) activeAlertCount++;

        // Camera image URL with token
        let camUrl = null;
        if (s.camera) {
          const camState = getState(this._hass, s.camera);
          if (camState) {
            const token = camState.attributes?.access_token;
            camUrl = token
              ? `/api/camera_proxy_stream/${s.camera}?token=${token}`
              : (camState.attributes?.entity_picture || `/api/camera_proxy/${s.camera}`);
          }
        }

        // Circular Dial Progress
        const circumference = 2 * Math.PI * 17; // ~106.8
        const validScore = score !== null ? Math.max(0, Math.min(100, score)) : 90;
        const offset = circumference - (validScore / 100) * circumference;
        const ringColor = validScore >= 75 ? "#10b981" : validScore >= 50 ? "#f59e0b" : "#ef4444";

        return `
          <div class="space-card" data-idx="${idx}">
            ${
              camUrl
                ? `
                  <div class="space-hero">
                    <img class="space-cam-img" src="${camUrl}" alt="${s.name}" loading="lazy" />
                    <div class="cam-scrim"></div>
                    <div class="live-tag"><span class="pulse-dot"></span> LIVE</div>
                    <div class="stage-tag">${stage}</div>
                    ${alertMsg ? `<div class="cam-alert-banner">⚠️ ${alertMsg}</div>` : ""}
                  </div>
                `
                : `
                  <div class="schematic-hero">
                    <div class="schematic-icon">🌱</div>
                    <div class="stage-tag">${stage}</div>
                    ${alertMsg ? `<div class="cam-alert-banner">⚠️ ${alertMsg}</div>` : ""}
                  </div>
                `
            }

            <div class="card-body">
              <div class="title-row">
                <div class="space-name">${s.name || `Space ${idx + 1}`}</div>
                <div class="health-dial-box" title="AI Health Score: ${Math.round(validScore)}/100">
                  <svg>
                    <circle class="health-track" cx="22" cy="22" r="17" />
                    <circle class="health-ring" cx="22" cy="22" r="17" style="stroke: ${ringColor}; stroke-dasharray: ${circumference}; stroke-dashoffset: ${offset};" />
                  </svg>
                  <div class="health-score-val" style="color: ${ringColor}">${Math.round(validScore)}%</div>
                </div>
              </div>

              <div class="capsules-grid">
                <!-- Canopy Telemetry -->
                <div class="telemetry-capsule">
                  <div class="capsule-title">🌿 Canopy Air</div>
                  <div class="capsule-row">
                    <div class="metric-cell">
                      <span class="metric-label">Temp</span>
                      <span class="metric-val">${temp}°</span>
                    </div>
                    <div class="metric-cell">
                      <span class="metric-label">RH</span>
                      <span class="metric-val">${rh}%</span>
                    </div>
                    <div class="metric-cell">
                      <span class="metric-label">VPD</span>
                      <span class="metric-val green">${vpd}</span>
                    </div>
                  </div>
                </div>

                <!-- Hydroponic Reservoir -->
                <div class="telemetry-capsule">
                  <div class="capsule-title">💧 Reservoir</div>
                  <div class="capsule-row">
                    <div class="metric-cell">
                      <span class="metric-label">pH</span>
                      <span class="metric-val cyan">${ph}</span>
                    </div>
                    <div class="metric-cell">
                      <span class="metric-label">EC</span>
                      <span class="metric-val">${ec}</span>
                    </div>
                    <div class="metric-cell">
                      <span class="metric-label">Water</span>
                      <span class="metric-val">${waterTemp}°</span>
                    </div>
                  </div>
                </div>
              </div>

              <div class="controls-row">
                <div class="quick-toggles">
                  ${
                    s.light
                      ? `<button class="btn-toggle ${lightOn ? "active" : ""}" data-action="toggle-light" data-idx="${idx}">💡 ${lightOn ? "Light ON" : "Light OFF"}</button>`
                      : ""
                  }
                  ${
                    s.fan
                      ? `<button class="btn-toggle ${fanOn ? "active" : ""}" data-action="toggle-fan" data-idx="${idx}">💨 ${fanOn ? "Fan ON" : "Fan OFF"}</button>`
                      : ""
                  }
                </div>
                <button class="btn-cockpit" data-action="nav" data-idx="${idx}">Cockpit HUD →</button>
              </div>
            </div>
          </div>
        `;
      })
      .join("");

    // Update Global Alerts
    const globalAlertBadge = this.shadowRoot.getElementById("global-alert-badge");
    const globalAlertCount = this.shadowRoot.getElementById("global-alert-count");
    if (globalAlertBadge && globalAlertCount) {
      if (activeAlertCount > 0) {
        globalAlertBadge.style.display = "flex";
        globalAlertCount.textContent = `${activeAlertCount} Alert${activeAlertCount > 1 ? "s" : ""} Active`;
      } else {
        globalAlertBadge.style.display = "none";
      }
    }

    // Bind navigation clicks on the card
    grid.querySelectorAll(".space-card").forEach((card) => {
      card.addEventListener("click", (e) => {
        // If clicking a button, handled separately
        if (e.target.closest("button")) return;
        const idx = parseInt(card.getAttribute("data-idx"), 10);
        const target = spaces[idx];
        if (target && target.path) {
          this._navigate(target.path);
        }
      });
    });

    // Bind button actions
    grid.querySelectorAll("button[data-action]").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        const action = btn.getAttribute("data-action");
        const idx = parseInt(btn.getAttribute("data-idx"), 10);
        const s = spaces[idx];
        if (!s) return;

        if (action === "toggle-light" && s.light) {
          this._callService("homeassistant", "toggle", { entity_id: s.light });
        } else if (action === "toggle-fan" && s.fan) {
          this._callService("homeassistant", "toggle", { entity_id: s.fan });
        } else if (action === "nav" && s.path) {
          this._navigate(s.path);
        }
      });
    });
  }
}

// Register Custom Elements
customElements.define("tendrilgrow-twin-card", TendrilGrowTwinCard);
customElements.define("tendrilgrow-overview-card", TendrilGrowOverviewCard);

// Register in Home Assistant Lovelace Card Picker
window.customCards = window.customCards || [];
window.customCards.push({
  type: "tendrilgrow-twin-card",
  name: "TendrilGrow Digital Twin HUD",
  description: "Interactive 2.5D visual grow tent with live telemetry HUD, equipment controls, and target range meters.",
  preview: true,
  documentationURL: "https://github.com/Trec-TorConsulting/TendrilGrow",
});
window.customCards.push({
  type: "tendrilgrow-overview-card",
  name: "TendrilGrow Executive Overview",
  description: "Multi-space executive dashboard card with live health scores and quick status.",
  preview: true,
  documentationURL: "https://github.com/Trec-TorConsulting/TendrilGrow",
});
