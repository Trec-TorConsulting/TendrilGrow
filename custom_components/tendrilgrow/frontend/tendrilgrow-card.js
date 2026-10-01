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

const CARD_VERSION = "2.3.0";
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

function escapeHtml(str) {
  if (str === null || str === undefined) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function parseIssueItem(iss) {
  if (!iss) return { metric: "DIAGNOSTIC", title: "Nominal status", detail: "", severity: "low" };
  let obj = iss;
  if (typeof iss === "string") {
    const trimmed = iss.trim();
    if (trimmed.startsWith("{") && trimmed.endsWith("}")) {
      try {
        const jsonStr = trimmed.replace(/'/g, '"').replace(/None/g, "null").replace(/True/g, "true").replace(/False/g, "false");
        obj = JSON.parse(jsonStr);
      } catch {
        const claimMatch = trimmed.match(/'claim':\s*'([^']+)'/) || trimmed.match(/"claim":\s*"([^"]+)"/);
        const metricMatch = trimmed.match(/'metric':\s*'([^']+)'/) || trimmed.match(/"metric":\s*"([^"]+)"/);
        const sevMatch = trimmed.match(/'severity':\s*'([^']+)'/) || trimmed.match(/"severity":\s*"([^"]+)"/);
        const obsMatch = trimmed.match(/'observation':\s*'([^']+)'/) || trimmed.match(/"observation":\s*"([^"]+)"/);
        const varMatch = trimmed.match(/'variance':\s*'([^']+)'/) || trimmed.match(/"variance":\s*"([^"]+)"/);
        const causeMatch = trimmed.match(/'cause':\s*'([^']+)'/) || trimmed.match(/"cause":\s*"([^"]+)"/);
        return {
          metric: (metricMatch ? metricMatch[1] : (claimMatch ? "ALERT" : "DIAGNOSTIC")).toUpperCase(),
          title: claimMatch ? claimMatch[1] : (obsMatch ? obsMatch[1] : trimmed.replace(/[{}]/g, "")),
          detail: varMatch ? `Variance: ${varMatch[1]}` : (causeMatch ? `Cause: ${causeMatch[1]}` : ""),
          severity: sevMatch ? sevMatch[1].toLowerCase() : "warning"
        };
      }
    } else {
      return { metric: "DIAGNOSTIC", title: iss, detail: "", severity: "info" };
    }
  }

  if (typeof obj === "object" && obj !== null) {
    const metric = obj.metric || obj.parameter || obj.sensor || "ALERT";
    const title = obj.claim || obj.observation || obj.title || obj.issue || obj.name || JSON.stringify(obj);
    let detail = "";
    if (obj.variance) detail = `Variance: ${obj.variance}`;
    else if (obj.cause) detail = `Cause: ${obj.cause}`;
    else if (obj.explanation) detail = obj.explanation;
    else if (obj.detail) detail = obj.detail;
    const severity = (obj.severity || "warning").toLowerCase();
    return { metric: String(metric).toUpperCase(), title: String(title), detail: String(detail), severity };
  }

  return { metric: "INFO", title: String(iss), detail: "", severity: "info" };
}

function parseActionItem(act) {
  if (!act) return { title: "Maintain routine canopy monitoring", detail: "", severity: "routine" };
  let obj = act;
  if (typeof act === "string") {
    const trimmed = act.trim();
    if (trimmed.startsWith("{") && trimmed.endsWith("}")) {
      try {
        const jsonStr = trimmed.replace(/'/g, '"').replace(/None/g, "null").replace(/True/g, "true").replace(/False/g, "false");
        obj = JSON.parse(jsonStr);
      } catch {
        const claimMatch = trimmed.match(/'claim':\s*'([^']+)'/) || trimmed.match(/"claim":\s*"([^"]+)"/);
        const actionMatch = trimmed.match(/'action':\s*'([^']+)'/) || trimmed.match(/"action":\s*"([^"]+)"/);
        const ratMatch = trimmed.match(/'rationale':\s*'([^']+)'/) || trimmed.match(/"rationale":\s*"([^"]+)"/);
        const sevMatch = trimmed.match(/'severity':\s*'([^']+)'/) || trimmed.match(/"severity":\s*"([^"]+)"/);
        return {
          title: claimMatch ? claimMatch[1] : (actionMatch ? actionMatch[1] : trimmed.replace(/[{}]/g, "")),
          detail: ratMatch ? ratMatch[1] : "",
          severity: sevMatch ? sevMatch[1].toLowerCase() : "action"
        };
      }
    } else {
      return { title: act, detail: "", severity: "action" };
    }
  }

  if (typeof obj === "object" && obj !== null) {
    const title = obj.claim || obj.action || obj.title || obj.recommendation || JSON.stringify(obj);
    const detail = obj.rationale || obj.description || obj.guidance || obj.detail || "";
    const severity = (obj.severity || obj.urgency || "action").toLowerCase();
    return { title: String(title), detail: String(detail), severity };
  }

  return { title: String(act), detail: "", severity: "action" };
}

function sortNutrientsByHorticulturalOrder(nutItems) {
  const MIXING_RANKS = [
    { rank: 0, category: "Silica Base", note: "Add FIRST & dissolve 10-15m before other salts", names: ["silica", "armor si", "potassium silicate", "silicium"] },
    { rank: 1, category: "Cal-Mag Buffer", note: "Dissolve completely before NPK to prevent lockout", names: ["cal-mag", "calmag", "calimagic", "cali magic", "calcium", "magnesium", "ca/mg", "ca-mg"] },
    { rank: 2, category: "Base / Micro", note: "Add before Grow/Bloom to disperse chelates", names: ["floramicro", "flora micro", "micro", "base", "part a", "part 1"] },
    { rank: 3, category: "Macro Grow", note: "Vegetative nitrogen & potassium ratio", names: ["floragro", "flora gro", "flora grow", "grow", "veg", "part b", "part 2"] },
    { rank: 4, category: "Macro Bloom", note: "Phosphorus & potassium flower builder", names: ["florabloom", "flora bloom", "bloom", "flower"] },
    { rank: 5, category: "Bloom Boosters", note: "PK flowering swell additive", names: ["koolbloom", "kool bloom", "pk", "booster", "bud", "phosphorus"] },
    { rank: 6, category: "Additives & Kelp", note: "Secondary micronutrients & enzymes", names: ["floralicious", "kelp", "humic", "fulvic", "diamond nectar", "amino", "vitamins", "rapid start", "root"] },
    { rank: 7, category: "Beneficial Microbes", note: "Live biological inoculant (guard root zones)", names: ["hydroguard", "great white", "southern ag", "beneficial", "bacillus", "inoculant", "mycorrhiza", "microbe", "subculture"] },
    { rank: 8, category: "pH Buffer", note: "Adjust LAST after all salts dissolve & stabilize", names: ["ph down", "ph up", "ph+", "ph-", "acid", "buffer"] },
  ];

  const getRankInfo = (nutStr) => {
    const lower = nutStr.toLowerCase();
    for (const r of MIXING_RANKS) {
      if (r.names.some(name => lower.includes(name))) {
        return r;
      }
    }
    return { rank: 5, category: "Supplement", note: "Mix thoroughly into solution", names: [] };
  };

  const parsedItems = nutItems.map(raw => {
    const [name, dose] = raw.split(":").map(s => s.trim());
    const info = getRankInfo(name || raw);
    return { raw, name: name || raw, dose: dose || "", rank: info.rank, category: info.category, note: info.note };
  });

  parsedItems.sort((a, b) => a.rank - b.rank);
  return parsedItems;
}

function generateAgronomyAdvice(query, ctx) {
  const q = (query || "").toLowerCase();
  const space = ctx.spaceName || "Grow Space";
  const stage = ctx.stage || "Vegetative";
  const ph = ctx.ph !== null ? Number(ctx.ph).toFixed(2) : null;
  const ec = ctx.ec !== null ? Number(ctx.ec).toFixed(2) : null;
  const vpd = ctx.vpd !== null ? Number(ctx.vpd).toFixed(2) : null;
  const temp = ctx.temp !== null ? Math.round(ctx.temp) : null;
  const rh = ctx.rh !== null ? Math.round(ctx.rh) : null;
  const waterTemp = ctx.waterTemp !== null ? Math.round(ctx.waterTemp) : null;
  const targetPhLow = ctx.targetPhLow !== null ? ctx.targetPhLow : 5.5;
  const targetPhHigh = ctx.targetPhHigh !== null ? ctx.targetPhHigh : 6.2;
  const targetEcLow = ctx.targetEcLow !== null ? ctx.targetEcLow : 1.2;
  const targetEcHigh = ctx.targetEcHigh !== null ? ctx.targetEcHigh : 1.8;
  const targetVpdLow = ctx.targetVpdLow !== null ? ctx.targetVpdLow : 0.8;
  const targetVpdHigh = ctx.targetVpdHigh !== null ? ctx.targetVpdHigh : 1.2;
  const daysInStage = ctx.daysInStage || 14;
  const daysSinceFlush = ctx.daysSinceFlush || 0;

  if (q.includes("ph") || q.includes("drift") || q.includes("acid") || q.includes("alkal")) {
    if (ph !== null) {
      if (ph > targetPhHigh) {
        return `### ⚠️ Reservoir pH Drift Analysis (${ph} vs Target ${targetPhLow}–${targetPhHigh})\nYour pH is currently **${ph}**, which is drifting above the optimal target corridor (${targetPhLow}–${targetPhHigh}).\n\n**Agronomic Impact:**\n- Above pH 6.2, hydroponic uptake of **Iron (Fe)**, **Manganese (Mn)**, **Boron (B)**, and **Zinc (Zn)** drops rapidly, risking interveinal chlorosis on new growth.\n- In active ${stage}, roots absorb nitrate anions ($NO_3^-$) and release hydroxide ions ($OH^-$), driving pH upward naturally.\n\n**Immediate Guidance:**\n1. Dilute **pH Down (Phosphoric Acid)** in a cup of RO water before dosing. Add in small increments (1–2 ml per 5 gal).\n2. Allow 20–30 minutes of recirculation before taking a final verification reading.\n3. Target **5.80 pH** as your settling baseline.${waterTemp && waterTemp > 68 ? `\n\n> ⚠️ *Note:* Water temperature is **${waterTemp}°F** (ideal is 65–68°F). Elevated water temps accelerate microbial respiration and pH swings.` : ""}`;
      } else if (ph < targetPhLow) {
        return `### ⚠️ Reservoir Low pH Alert (${ph} vs Target ${targetPhLow}–${targetPhHigh})\nYour pH is currently **${ph}**, which is below your target corridor.\n\n**Agronomic Impact:**\n- Low pH (<5.5) inhibits **Calcium (Ca)** and **Magnesium (Mg)** availability and can cause root tip burning or necrotic spotting.\n- Root exudates or ammonium uptake can pull pH downward.\n\n**Immediate Guidance:**\n1. Dose a small amount of **pH Up (Potassium Hydroxide)** diluted in water.\n2. Stabilize to **5.8–6.0 pH** and verify air pump aeration.`;
      } else {
        return `### ✅ Reservoir pH is Nominal (${ph})\nYour current pH of **${ph}** is sitting right in the sweet spot for the **${stage}** stage (${targetPhLow}–${targetPhHigh}).\n\nAll essential macro-elements (Nitrogen, Phosphorus, Potassium) and micronutrients (Iron, Zinc, Manganese) are in optimal bioavailable balance.`;
      }
    }
    return `### 🧪 Hydroponic pH Management\nFor **${stage}**, maintain your reservoir between **${targetPhLow} and ${targetPhHigh}** (sweet spot: **5.80**). Always mix Cal-Mag and base nutrients completely before testing and adjusting pH as the final step!`;
  }

  if (q.includes("ec") || q.includes("ppm") || q.includes("feed") || q.includes("burn") || q.includes("strength") || q.includes("nutrient")) {
    if (ec !== null) {
      if (ec > targetEcHigh) {
        return `### ⚠️ High EC Reading (${ec} mS/cm vs Target ${targetEcLow}–${targetEcHigh})\nThe reservoir salinity is **${ec} mS/cm**, exceeding your target ceiling of ${targetEcHigh} mS/cm.\n\n**Agronomic Analysis:**\n- High EC creates osmotic root pressure, making it harder for plants to drink.\n- When plants drink more water than nutrients, unused salts accumulate and drive EC up.\n\n**Correction Steps:**\n1. Top off the reservoir with **pure de-chlorinated or RO water** until EC settles back to ~**${((targetEcLow + targetEcHigh) / 2).toFixed(1)} mS/cm**.\n2. Check canopy leaf tips for minor tip-burn.`;
      } else if (ec < targetEcLow) {
        return `### ℹ️ Low EC Reading (${ec} mS/cm vs Target ${targetEcLow}–${targetEcHigh})\nYour electrical conductivity is currently **${ec} mS/cm**, below target.\n\n**Recommendation:**\n- Plants in **${stage}** are feeding actively. Prepare a fresh batch of balanced base nutrients (Micro then Grow/Bloom) to bring concentration up to **${targetEcHigh} mS/cm**.`;
      } else {
        return `### ✅ Electrical Conductivity is Balanced (${ec} mS/cm)\nYour nutrient concentration of **${ec} mS/cm** sits comfortably within your target corridor (${targetEcLow}–${targetEcHigh} mS/cm).\n\nOsmotic potential is balanced, enabling steady transpirational pull and uniform expansion in ${stage}.`;
      }
    }
  }

  if (q.includes("recipe") || q.includes("order") || q.includes("prep") || q.includes("calmag") || q.includes("cal-mag") || q.includes("silica") || q.includes("mix")) {
    return `### 🧪 Standard Horticultural Mixing Order Protocol\nWhen preparing or topping off your reservoir for **${space}**, always follow this strict chemical sequence to avoid nutrient precipitation and lockout:\n\n1. **Water Base & Aeration**: Ensure RO or dechlorinated water is at ~65–68°F.\n2. **Step 1 — Silica (Armor Si)**: *Add FIRST.* Dissolve thoroughly and wait **10–15 minutes** before adding anything else. Silica needs free water to bind properly.\n3. **Step 2 — Cal-Mag (CaliMagic)**: *Add SECOND.* Calcium will bond with sulfates/phosphates and precipitate out if added after Micro or Grow. Mix until crystal clear.\n4. **Step 3 — Micro / Base (FloraMicro)**: *Add THIRD.* Stir well to disperse chelates.\n5. **Step 4 — Grow (FloraGro)**: *Add FOURTH.* Provides vegetative nitrogen & potassium.\n6. **Step 5 — Bloom (FloraBloom)**: *Add FIFTH.* Phosphorus & potassium builder.\n7. **Step 6 — Additives & Boosters**: Add kelp, enzymes, and fulvic/humic supplements.\n8. **Step 7 — Beneficial Microbes (Hydroguard)**: Add live biological inoculants to guard root zones.\n9. **Step 8 — pH Buffer**: **Adjust LAST.** Wait 15 minutes after mixing all salts, check pH, and adjust gently to **5.80**.`;
  }

  if (q.includes("vpd") || q.includes("humidity") || q.includes("temp") || q.includes("stomata") || q.includes("climate") || q.includes("vapor")) {
    return `### 🌿 Environmental Vigor & VPD Analysis\n- **Current VPD**: ${vpd !== null ? `**${vpd} kPa** (Target: ${targetVpdLow}–${targetVpdHigh} kPa)` : `Target: ${targetVpdLow}–${targetVpdHigh} kPa`}\n- **Canopy Climate**: ${temp !== null ? `${temp}°F` : "--"} / ${rh !== null ? `${rh}% RH` : "--"}\n\n**Agronomic Insights:**\n${vpd && vpd > targetVpdHigh ? `- **High VPD Alert**: Air draws moisture faster than roots can supply. Stomata close to conserve water, risking calcium tip-burn. Increase humidifier or reduce exhaust speed.` : vpd && vpd < targetVpdLow ? `- **Low VPD Alert**: Transpiration is sluggish. Calcium cannot travel up to leaf tips without active water flow. Increase exhaust ventilation.` : `- **Sweet-Spot Corridors**: Stomata are open and transpirational pull is steady. Calcium and mobile ions are flowing evenly through the vascular xylem.`}\n- Maintain daytime canopy temps around **74–78°F** and nighttime around **68–72°F**.`;
  }

  if (q.includes("flip") || q.includes("harvest") || q.includes("stage") || q.includes("when") || q.includes("flower") || q.includes("time")) {
    return `### 🔄 Cultivation Pipeline & Milestone Projections\n- **Current Space**: ${space}\n- **Stage**: ${stage} (Day ${daysInStage})\n\n**Guidance for ${stage}:**\n- For transitioning from Veg to Flower (12/12 flip), ensure canopy trellis is 70–80% full, as plants stretch 50–100% in height during weeks 1–3 of flower.\n- Perform lower canopy defoliation (lollipop) 3 days prior to flip.\n- Transition light schedule to 12h ON / 12h OFF and transition base nutrient ratios toward higher bloom macro-nutrients.`;
  }

  if (q.includes("flush") || q.includes("clean") || q.includes("reservoir") || q.includes("change")) {
    return `### 🌊 Reservoir Flush & Routine Protocol\n- **Days Since Last Flush**: ${daysSinceFlush} days (Recommended interval: 7–10 days)\n\n**Why Routine Flush & Fills Matter:**\n- Over 7–10 days in RDWC / hydroponics, plants consume specific ions disproportionately, leaving behind ballast counter-ions that skew nutrient ratios even if EC looks normal.\n- A full flush & fill resets the root zone with fresh, oxygen-saturated water and balanced elemental ratios.\n\n**Quick Action:**\nYou can log that you performed a reservoir flush right now on the **Cultivation Plan & Tasks** card under **Parameters & Reservoir Routine** using the **Log Flush & Fill Completed** button!`;
  }

  return `### 🧠 TendrilGrow Autonomous Agronomist for ${space}\nHere is the real-time cultivation status for your **${stage}** cycle:\n\n- **Telemetry**: pH: **${ph || "--"}** | EC: **${ec || "--"} mS/cm** | VPD: **${vpd || "--"} kPa** | Temp: **${temp || "--"}°F**\n- **Reservoir**: Water Temp: **${waterTemp || "--"}°F** | Days Since Flush: **${daysSinceFlush}**\n- **System Health**: All automated sensor telemetry is monitored in real time.\n\nAsk me anything specific like *"Analyze my pH"*, *"How do I prep this week's water recipe?"*, or *"Is my VPD in the sweet spot?"*!`;
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
    this._activeDrawer = null; // 'bands' | 'advisor' | 'actions' | null
    this._renderedStage = null;
  }

  static getStubConfig() {
    return {
      title: "Grow Tent HUD",
      camera: "camera.tent",
      light: "light.tent_light",
      fan: "fan.tent_fan",
      duct_fan: "fan.tent_duct",
    };
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

    this._renderedStage = null;
    this._render();
  }

  set hass(hass) {
    try {
      this._hass = hass;
      this._updateStates();
    } catch (err) {
      console.error("TendrilGrowTwinCard: Error in set hass:", err);
    }
  }

  getCardSize() {
    return 8;
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

  _normalizeStage(stageRaw) {
    if (!stageRaw) return "veg";
    const s = String(stageRaw).toLowerCase();
    if (s.includes("seed") || s.includes("clone") || s.includes("sprout") || s.includes("germ")) return "seedling";
    if (s.includes("flower") || s.includes("bloom")) return "flower";
    if (s.includes("flush") || s.includes("harvest") || s.includes("cure")) return "flush";
    return "veg";
  }

  _evalTarget(val, low, high) {
    if (val === null || val === undefined || isNaN(val)) return { status: "unknown", label: "--" };
    if (low !== null && low !== undefined && val < low) return { status: "low", label: "LOW" };
    if (high !== null && high !== undefined && val > high) return { status: "high", label: "HIGH" };
    return { status: "optimal", label: "OPTIMAL" };
  }

  _renderBotanicalCanopy(stageKey) {
    const stage = this._normalizeStage(stageKey);
    const radLeafUrl = stage === "flush" ? "url(#radFlushLeaf)" : "url(#radVegLeaf)";

    const defs = `
      <defs>
        <!-- Leaf Gradients -->
        <radialGradient id="radVegLeaf" cx="50%" cy="30%" r="70%">
          <stop offset="0%" stop-color="#34d399"/>
          <stop offset="35%" stop-color="#10b981"/>
          <stop offset="85%" stop-color="#047857"/>
          <stop offset="100%" stop-color="#064e3b"/>
        </radialGradient>
        <radialGradient id="radFlushLeaf" cx="50%" cy="30%" r="70%">
          <stop offset="0%" stop-color="#fbbf24"/>
          <stop offset="28%" stop-color="#f43f5e"/>
          <stop offset="65%" stop-color="#7c3aed"/>
          <stop offset="100%" stop-color="#312e81"/>
        </radialGradient>
        <!-- Stalk Gradient -->
        <linearGradient id="linStalk" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0%" stop-color="#065f46"/>
          <stop offset="45%" stop-color="#10b981"/>
          <stop offset="100%" stop-color="#064e3b"/>
        </linearGradient>
        <!-- Flower Cola Gradient -->
        <radialGradient id="radBudCola" cx="40%" cy="35%" r="65%">
          <stop offset="0%" stop-color="#86efac"/>
          <stop offset="35%" stop-color="#16a34a"/>
          <stop offset="75%" stop-color="#14532d"/>
          <stop offset="100%" stop-color="#052e16"/>
        </radialGradient>
        <!-- Single 7-Blade Cannabis Fan Leaf -->
        <g id="fan-leaf-7">
          <line x1="0" y1="0" x2="0" y2="24" stroke="#047857" stroke-width="2.5" stroke-linecap="round"/>
          <path d="M 0 0 C -7 -18, -9 -45, 0 -68 C 9 -45, 7 -18, 0 0" fill="${radLeafUrl}" stroke="#064e3b" stroke-width="0.8"/>
          <line x1="0" y1="0" x2="0" y2="-64" stroke="#a7f3d0" stroke-width="1" opacity="0.6"/>
          <g transform="rotate(-24)">
            <path d="M 0 0 C -6 -15, -8 -38, 0 -56 C 8 -38, 6 -15, 0 0" fill="${radLeafUrl}" stroke="#064e3b" stroke-width="0.7"/>
            <line x1="0" y1="0" x2="0" y2="-52" stroke="#a7f3d0" stroke-width="0.9" opacity="0.5"/>
          </g>
          <g transform="rotate(24)">
            <path d="M 0 0 C -6 -15, -8 -38, 0 -56 C 8 -38, 6 -15, 0 0" fill="${radLeafUrl}" stroke="#064e3b" stroke-width="0.7"/>
            <line x1="0" y1="0" x2="0" y2="-52" stroke="#a7f3d0" stroke-width="0.9" opacity="0.5"/>
          </g>
          <g transform="rotate(-48)">
            <path d="M 0 0 C -5 -12, -7 -30, 0 -44 C 7 -30, 5 -12, 0 0" fill="${radLeafUrl}" stroke="#064e3b" stroke-width="0.6"/>
            <line x1="0" y1="0" x2="0" y2="-40" stroke="#a7f3d0" stroke-width="0.8" opacity="0.4"/>
          </g>
          <g transform="rotate(48)">
            <path d="M 0 0 C -5 -12, -7 -30, 0 -44 C 7 -30, 5 -12, 0 0" fill="${radLeafUrl}" stroke="#064e3b" stroke-width="0.6"/>
            <line x1="0" y1="0" x2="0" y2="-40" stroke="#a7f3d0" stroke-width="0.8" opacity="0.4"/>
          </g>
          <g transform="rotate(-72)">
            <path d="M 0 0 C -4 -8, -6 -20, 0 -30 C 6 -20, 4 -8, 0 0" fill="${radLeafUrl}" stroke="#064e3b" stroke-width="0.5"/>
          </g>
          <g transform="rotate(72)">
            <path d="M 0 0 C -4 -8, -6 -20, 0 -30 C 6 -20, 4 -8, 0 0" fill="${radLeafUrl}" stroke="#064e3b" stroke-width="0.5"/>
          </g>
        </g>
        <!-- Flower Cola (Dense frosty bud with amber pistils) -->
        <g id="flower-cola">
          <ellipse cx="0" cy="-22" rx="16" ry="24" fill="url(#radBudCola)" stroke="#064e3b" stroke-width="0.8"/>
          <ellipse cx="-8" cy="-14" rx="12" ry="16" fill="url(#radBudCola)"/>
          <ellipse cx="8" cy="-14" rx="12" ry="16" fill="url(#radBudCola)"/>
          <ellipse cx="-6" cy="-30" rx="10" ry="14" fill="url(#radBudCola)"/>
          <ellipse cx="6" cy="-30" rx="10" ry="14" fill="url(#radBudCola)"/>
          <circle cx="0" cy="-40" r="10" fill="url(#radBudCola)"/>
          <circle cx="-4" cy="-26" r="1.5" fill="#fef08a" opacity="0.9"/>
          <circle cx="5" cy="-22" r="1.8" fill="#ffffff" opacity="0.85"/>
          <circle cx="-1" cy="-34" r="1.6" fill="#fef08a" opacity="0.9"/>
          <circle cx="3" cy="-14" r="1.4" fill="#ffffff" opacity="0.8"/>
          <circle cx="-7" cy="-16" r="1.5" fill="#fef08a" opacity="0.85"/>
          <circle cx="1" cy="-42" r="1.3" fill="#ffffff" opacity="0.9"/>
          <path d="M -6 -42 Q -12 -54 -7 -60" stroke="#f59e0b" stroke-width="1.6" fill="none" stroke-linecap="round"/>
          <path d="M 0 -44 Q 2 -56 8 -62" stroke="#d97706" stroke-width="1.5" fill="none" stroke-linecap="round"/>
          <path d="M 6 -40 Q 14 -50 12 -58" stroke="#f59e0b" stroke-width="1.6" fill="none" stroke-linecap="round"/>
          <path d="M -12 -28 Q -20 -36 -18 -44" stroke="#d97706" stroke-width="1.4" fill="none" stroke-linecap="round"/>
          <path d="M 12 -26 Q 22 -32 20 -40" stroke="#f59e0b" stroke-width="1.4" fill="none" stroke-linecap="round"/>
          <path d="M -10 -16 Q -18 -22 -16 -28" stroke="#f59e0b" stroke-width="1.3" fill="none" stroke-linecap="round"/>
          <path d="M 10 -14 Q 18 -18 17 -26" stroke="#d97706" stroke-width="1.3" fill="none" stroke-linecap="round"/>
        </g>
      </defs>
    `;

    const baseHardware = `
      <g class="submerged-roots" opacity="0.85">
        <path d="M 210 240 Q 200 258 206 275" stroke="#f1f5f9" stroke-width="2.5" fill="none" stroke-linecap="round"/>
        <path d="M 220 240 Q 212 260 224 280" stroke="#e2e8f0" stroke-width="2" fill="none" stroke-linecap="round"/>
        <path d="M 230 240 Q 232 262 228 285" stroke="#f8fafc" stroke-width="2.2" fill="none" stroke-linecap="round"/>
        <path d="M 240 240 Q 248 260 244 280" stroke="#cbd5e1" stroke-width="2" fill="none" stroke-linecap="round"/>
        <path d="M 250 240 Q 258 258 252 275" stroke="#f1f5f9" stroke-width="1.8" fill="none" stroke-linecap="round"/>
      </g>
      <rect x="195" y="218" width="70" height="22" rx="3" fill="#1e293b" stroke="#475569" stroke-width="1.5"/>
      <line x1="204" y1="218" x2="216" y2="240" stroke="#334155" stroke-width="1.2"/>
      <line x1="218" y1="218" x2="230" y2="240" stroke="#334155" stroke-width="1.2"/>
      <line x1="232" y1="218" x2="244" y2="240" stroke="#334155" stroke-width="1.2"/>
      <line x1="246" y1="218" x2="258" y2="240" stroke="#334155" stroke-width="1.2"/>
      <rect x="212" y="208" width="36" height="15" rx="2" fill="#57534e" stroke="#78716c" stroke-width="1"/>
    `;

    let stageContent = "";

    if (stage === "seedling") {
      stageContent = `
        <path d="M 230 210 Q 230 185 230 168" stroke="#34d399" stroke-width="4.5" stroke-linecap="round"/>
        <ellipse cx="218" cy="180" rx="10" ry="6" fill="#10b981" stroke="#059669" stroke-width="0.8" transform="rotate(-15 218 180)"/>
        <ellipse cx="242" cy="180" rx="10" ry="6" fill="#10b981" stroke="#059669" stroke-width="0.8" transform="rotate(15 242 180)"/>
        <g transform="translate(230, 168)">
          <path d="M 0 0 C -4 -10, -6 -24, 0 -36 C 6 -24, 4 -10, 0 0" fill="#10b981" stroke="#047857" stroke-width="0.7"/>
          <g transform="rotate(-35)">
            <path d="M 0 0 C -3 -8, -5 -18, 0 -28 C 5 -18, 3 -8, 0 0" fill="#10b981" stroke="#047857" stroke-width="0.6"/>
          </g>
          <g transform="rotate(35)">
            <path d="M 0 0 C -3 -8, -5 -18, 0 -28 C 5 -18, 3 -8, 0 0" fill="#10b981" stroke="#047857" stroke-width="0.6"/>
          </g>
        </g>
      `;
    } else if (stage === "flower" || stage === "flush") {
      stageContent = `
        <path d="M 230 210 Q 230 145 230 85" stroke="url(#linStalk)" stroke-width="7" stroke-linecap="round"/>
        <path d="M 230 170 Q 180 165 140 145" stroke="url(#linStalk)" stroke-width="5" stroke-linecap="round" fill="none"/>
        <path d="M 230 170 Q 280 165 320 145" stroke="url(#linStalk)" stroke-width="5" stroke-linecap="round" fill="none"/>
        <path d="M 230 130 Q 195 120 175 105" stroke="url(#linStalk)" stroke-width="4.5" stroke-linecap="round" fill="none"/>
        <path d="M 230 130 Q 265 120 285 105" stroke="url(#linStalk)" stroke-width="4.5" stroke-linecap="round" fill="none"/>

        <g transform="translate(100, 165) scale(0.85) rotate(-35)"><use href="#fan-leaf-7"/></g>
        <g transform="translate(360, 165) scale(0.85) rotate(35)"><use href="#fan-leaf-7"/></g>
        <g transform="translate(150, 120) scale(0.75) rotate(-20)"><use href="#fan-leaf-7"/></g>
        <g transform="translate(310, 120) scale(0.75) rotate(20)"><use href="#fan-leaf-7"/></g>
        <g transform="translate(195, 95) scale(0.65) rotate(-15)"><use href="#fan-leaf-7"/></g>
        <g transform="translate(265, 95) scale(0.65) rotate(15)"><use href="#fan-leaf-7"/></g>

        <g transform="translate(140, 145) scale(0.9)"><use href="#flower-cola"/></g>
        <g transform="translate(320, 145) scale(0.9)"><use href="#flower-cola"/></g>
        <g transform="translate(175, 105) scale(0.85)"><use href="#flower-cola"/></g>
        <g transform="translate(285, 105) scale(0.85)"><use href="#flower-cola"/></g>
        <g transform="translate(230, 80) scale(1.15)"><use href="#flower-cola"/></g>
      `;
    } else {
      stageContent = `
        <path d="M 230 210 Q 230 140 230 75" stroke="url(#linStalk)" stroke-width="7" stroke-linecap="round"/>
        <path d="M 230 175 Q 170 170 120 155" stroke="url(#linStalk)" stroke-width="5" stroke-linecap="round" fill="none"/>
        <path d="M 230 175 Q 290 170 340 155" stroke="url(#linStalk)" stroke-width="5" stroke-linecap="round" fill="none"/>
        <path d="M 230 135 Q 185 125 155 110" stroke="url(#linStalk)" stroke-width="4.5" stroke-linecap="round" fill="none"/>
        <path d="M 230 135 Q 275 125 305 110" stroke="url(#linStalk)" stroke-width="4.5" stroke-linecap="round" fill="none"/>
        <path d="M 230 100 Q 200 90 185 80" stroke="url(#linStalk)" stroke-width="4" stroke-linecap="round" fill="none"/>
        <path d="M 230 100 Q 260 90 275 80" stroke="url(#linStalk)" stroke-width="4" stroke-linecap="round" fill="none"/>

        <g transform="translate(90, 165) scale(0.95) rotate(-45)"><use href="#fan-leaf-7"/></g>
        <g transform="translate(370, 165) scale(0.95) rotate(45)"><use href="#fan-leaf-7"/></g>
        <g transform="translate(135, 155) scale(0.9) rotate(-25)"><use href="#fan-leaf-7"/></g>
        <g transform="translate(325, 155) scale(0.9) rotate(25)"><use href="#fan-leaf-7"/></g>
        <g transform="translate(145, 115) scale(0.85) rotate(-35)"><use href="#fan-leaf-7"/></g>
        <g transform="translate(315, 115) scale(0.85) rotate(35)"><use href="#fan-leaf-7"/></g>
        <g transform="translate(175, 105) scale(0.8) rotate(-15)"><use href="#fan-leaf-7"/></g>
        <g transform="translate(285, 105) scale(0.8) rotate(15)"><use href="#fan-leaf-7"/></g>
        <g transform="translate(185, 80) scale(0.7) rotate(-20)"><use href="#fan-leaf-7"/></g>
        <g transform="translate(275, 80) scale(0.7) rotate(20)"><use href="#fan-leaf-7"/></g>
        <g transform="translate(230, 70) scale(0.85)"><use href="#fan-leaf-7"/></g>
      `;
    }

    return `
      <svg class="botanical-canopy-svg" viewBox="0 0 460 270" preserveAspectRatio="xMidYMid meet">
        ${defs}
        ${baseHardware}
        <g class="canopy-sway-group" id="canopy-sway-group">
          ${stageContent}
        </g>
      </svg>
    `;
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
          --tg-bg: #0b0f17;
          --tg-card-bg: rgba(15, 23, 42, 0.88);
          --tg-border: rgba(255, 255, 255, 0.08);
          --tg-border-active: rgba(16, 185, 129, 0.4);
          --tg-green: #10b981;
          --tg-cyan: #06b6d4;
          --tg-amber: #f59e0b;
          --tg-red: #ef4444;
          --tg-violet: #8b5cf6;
          --tg-glow-green: 0 0 16px rgba(16, 185, 129, 0.35);
          --tg-glow-cyan: 0 0 16px rgba(6, 182, 212, 0.35);
          --tg-glow-amber: 0 0 16px rgba(245, 158, 11, 0.35);
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
          box-shadow: 0 8px 32px rgba(0, 0, 0, 0.5);
          position: relative;
        }

        /* HEADER */
        .header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: 13px 18px;
          background: rgba(13, 17, 23, 0.95);
          border-bottom: 1px solid var(--tg-border);
          backdrop-filter: blur(12px);
          position: relative;
          z-index: 10;
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
          font-size: 16.5px;
          font-weight: 700;
          letter-spacing: -0.3px;
          color: #f0f6fc;
        }

        .stage-pill {
          display: inline-flex;
          align-items: center;
          gap: 5px;
          font-size: 10.5px;
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

        /* AI HEALTH SCORE DIAL */
        .health-ring-box {
          display: flex;
          align-items: center;
          gap: 8px;
          cursor: pointer;
        }

        .health-dial {
          position: relative;
          width: 42px;
          height: 42px;
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
          font-size: 12.5px;
          font-weight: 700;
          color: #fff;
        }

        .health-label {
          display: flex;
          flex-direction: column;
        }

        .health-label-text {
          font-size: 9.5px;
          text-transform: uppercase;
          color: #8b949e;
          font-weight: 600;
        }

        .health-status-text {
          font-size: 11.5px;
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
          font-size: 11.5px;
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
          padding: 9px 16px;
          background: linear-gradient(90deg, rgba(239, 68, 68, 0.2), rgba(245, 158, 11, 0.2));
          border-bottom: 1px solid rgba(239, 68, 68, 0.4);
          font-size: 11.5px;
          font-weight: 600;
          color: #fca5a5;
          animation: pulse-ribbon 2.5s infinite ease-in-out;
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
          font-size: 10.5px;
          font-weight: 700;
          cursor: pointer;
        }

        /* DIGITAL TWIN CANVAS */
        .twin-canvas {
          position: relative;
          width: 100%;
          min-height: 480px;
          background: radial-gradient(circle at 50% 25%, #131c2b 0%, #080d14 85%);
          overflow: hidden;
          display: flex;
          flex-direction: column;
          justify-content: space-between;
          padding: 16px;
        }

        /* TENT MYLAR REFLECTIVE OVERLAY */
        .tent-backdrop {
          position: absolute;
          inset: 0;
          background-image: 
            linear-gradient(rgba(255, 255, 255, 0.015) 1px, transparent 1px),
            linear-gradient(90deg, rgba(255, 255, 255, 0.015) 1px, transparent 1px);
          background-size: 24px 24px;
          pointer-events: none;
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
          background: linear-gradient(to bottom, rgba(11,15,23,0.45) 0%, transparent 40%, rgba(11,15,23,0.75) 100%);
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
          gap: 12px;
        }

        /* TOP RIG (LIGHT & DUCT FAN) */
        .overhead-rig {
          display: flex;
          justify-content: space-between;
          align-items: flex-start;
          width: 100%;
          position: relative;
          z-index: 5;
        }

        /* LIGHT FIXTURE ASSEMBLY */
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
          width: 250px;
          height: 14px;
          background: #21262d;
          border-radius: 4px;
          border: 1px solid #30363d;
          position: relative;
          box-shadow: 0 4px 12px rgba(0,0,0,0.6);
          transition: all 0.3s ease;
        }

        .light-bar.on {
          background: #fffbeb;
          border-color: #fde68a;
          box-shadow: 0 0 25px rgba(253, 224, 71, 0.8), 0 0 50px rgba(245, 158, 11, 0.45);
        }

        .light-cone {
          width: 320px;
          height: 180px;
          background: linear-gradient(to bottom, rgba(254, 240, 138, 0.28) 0%, rgba(254, 240, 138, 0.04) 75%, transparent 100%);
          clip-path: polygon(18% 0%, 82% 0%, 100% 100%, 0% 100%);
          opacity: 0;
          transition: opacity 0.4s ease;
          pointer-events: none;
        }

        .light-cone.on {
          opacity: 1;
        }

        /* PHOTON PARTICLE SHOWER */
        .photon-stream {
          position: absolute;
          top: 32px;
          left: 50%;
          transform: translateX(-50%);
          width: 280px;
          height: 190px;
          pointer-events: none;
          overflow: hidden;
          opacity: 0;
          transition: opacity 0.4s ease;
          z-index: 2;
        }

        .photon-stream.on {
          opacity: 1;
        }

        .photon-particle {
          position: absolute;
          width: 2px;
          border-radius: 2px;
          background: linear-gradient(180deg, rgba(254, 240, 138, 0.95), rgba(245, 158, 11, 0));
          animation: photon-fall 1.8s linear infinite;
        }

        .p1 { left: 18%; height: 16px; animation-delay: 0.1s; animation-duration: 1.7s; }
        .p2 { left: 32%; height: 22px; animation-delay: 0.6s; animation-duration: 2.1s; }
        .p3 { left: 50%; height: 18px; animation-delay: 0.3s; animation-duration: 1.9s; }
        .p4 { left: 68%; height: 24px; animation-delay: 0.9s; animation-duration: 2.0s; }
        .p5 { left: 82%; height: 15px; animation-delay: 0.4s; animation-duration: 1.8s; }
        .p6 { left: 42%; height: 20px; animation-delay: 1.2s; animation-duration: 2.2s; }

        @keyframes photon-fall {
          0% { transform: translateY(-15px); opacity: 0; }
          25% { opacity: 0.9; }
          75% { opacity: 0.9; }
          100% { transform: translateY(185px); opacity: 0; }
        }

        .light-badge {
          margin-top: 4px;
          background: rgba(15, 23, 42, 0.9);
          border: 1px solid var(--tg-border);
          padding: 3px 9px;
          border-radius: 12px;
          font-size: 11px;
          font-weight: 600;
          color: #fbbf24;
          display: flex;
          align-items: center;
          gap: 4px;
          backdrop-filter: blur(8px);
        }

        /* DUCT / INLINE EXHAUST FAN */
        .duct-fan-box {
          display: flex;
          align-items: center;
          gap: 8px;
          background: rgba(15, 23, 42, 0.9);
          border: 1px solid var(--tg-border);
          padding: 6px 12px;
          border-radius: 10px;
          cursor: pointer;
          backdrop-filter: blur(8px);
          transition: all 0.2s ease;
          position: relative;
        }

        .duct-fan-box:hover {
          background: rgba(30, 41, 59, 0.95);
          border-color: rgba(6, 182, 212, 0.4);
        }

        .fan-icon {
          width: 22px;
          height: 22px;
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
          animation: spin 0.35s linear infinite;
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
          font-size: 9.5px;
          color: #8b949e;
          text-transform: uppercase;
          font-weight: 600;
        }

        .fan-speed {
          font-size: 12px;
          font-weight: 700;
          color: var(--tg-cyan);
        }

        /* EXHAUST AIRFLOW VORTEX */
        .exhaust-vortex {
          position: absolute;
          top: -12px;
          left: 10px;
          width: 44px;
          height: 32px;
          pointer-events: none;
          opacity: 0;
          transition: opacity 0.3s ease;
        }

        .exhaust-vortex.active {
          opacity: 1;
        }

        .vortex-trail {
          stroke-dashoffset: 0;
          animation: vortex-flow 0.9s linear infinite;
        }

        @keyframes vortex-flow {
          from { stroke-dashoffset: 24; }
          to { stroke-dashoffset: 0; }
        }

        /* CIRCULATION FAN */
        .circ-fan-box {
          display: flex;
          align-items: center;
          gap: 8px;
          background: rgba(15, 23, 42, 0.9);
          border: 1px solid var(--tg-border);
          padding: 6px 12px;
          border-radius: 10px;
          cursor: pointer;
          backdrop-filter: blur(8px);
          position: relative;
        }

        .circ-breeze {
          position: absolute;
          top: 36px;
          right: 12px;
          width: 75px;
          height: 45px;
          pointer-events: none;
          opacity: 0;
          transition: opacity 0.3s ease;
        }

        .circ-breeze.active {
          opacity: 1;
        }

        .breeze-curve {
          stroke-dashoffset: 0;
          animation: breeze-sweep 1.4s linear infinite;
        }

        @keyframes breeze-sweep {
          from { stroke-dashoffset: 26; }
          to { stroke-dashoffset: 0; }
        }

        /* BOTANICAL CANOPY VIEWPORT */
        .canopy-viewport {
          position: relative;
          width: 100%;
          height: 250px;
          display: flex;
          align-items: center;
          justify-content: center;
          margin: 4px 0;
          pointer-events: none;
        }

        .botanical-canopy-svg {
          width: 100%;
          max-width: 460px;
          height: 100%;
          overflow: visible;
        }

        .canopy-sway-group {
          transform-origin: 230px 225px;
          transition: transform 0.6s ease;
        }

        .canopy-sway-group.swaying {
          animation: canopy-breeze 4s ease-in-out infinite alternate;
        }

        @keyframes canopy-breeze {
          0% { transform: rotate(-1.5deg) skewX(-1deg); }
          50% { transform: rotate(1.4deg) skewX(0.9deg); }
          100% { transform: rotate(-1.5deg) skewX(-1deg); }
        }

        /* FLOATING CANOPY TELEMETRY HUD CAPSULE */
        .canopy-hud-wrapper {
          display: flex;
          justify-content: center;
          width: 100%;
          position: relative;
          z-index: 10;
        }

        .hud-capsule {
          background: rgba(13, 17, 23, 0.86);
          border: 1px solid rgba(16, 185, 129, 0.35);
          border-radius: 16px;
          padding: 8px 18px;
          display: flex;
          align-items: center;
          gap: 16px;
          box-shadow: 0 8px 28px rgba(0, 0, 0, 0.6), 0 0 20px rgba(16, 185, 129, 0.22);
          backdrop-filter: blur(16px);
          cursor: pointer;
          transition: all 0.3s ease;
        }

        .hud-capsule:hover {
          transform: translateY(-2px);
          border-color: rgba(16, 185, 129, 0.6);
          box-shadow: 0 12px 36px rgba(0, 0, 0, 0.7), 0 0 28px rgba(16, 185, 129, 0.35);
        }

        .hud-capsule.alert {
          border-color: var(--tg-red);
          box-shadow: 0 8px 28px rgba(0, 0, 0, 0.6), 0 0 18px rgba(239, 68, 68, 0.4);
        }

        .hud-metric {
          display: flex;
          flex-direction: column;
          align-items: center;
        }

        .hud-metric-label {
          font-size: 9.5px;
          color: #8b949e;
          font-weight: 700;
          text-transform: uppercase;
          letter-spacing: 0.6px;
        }

        .hud-metric-val {
          font-size: 18px;
          font-weight: 800;
          color: #f0f6fc;
          letter-spacing: -0.4px;
          display: flex;
          align-items: baseline;
          gap: 2px;
        }

        .hud-metric-val span {
          font-size: 11px;
          font-weight: 600;
          color: #8b949e;
        }

        .hud-status-badge {
          font-size: 8.5px;
          font-weight: 700;
          text-transform: uppercase;
          letter-spacing: 0.4px;
          padding: 1px 6px;
          border-radius: 8px;
          background: rgba(255, 255, 255, 0.06);
          color: #8b949e;
          border: 1px solid rgba(255, 255, 255, 0.1);
          margin-top: 3px;
          transition: all 0.2s ease;
        }

        .hud-status-badge.optimal {
          background: rgba(16, 185, 129, 0.16);
          color: #34d399;
          border-color: rgba(16, 185, 129, 0.35);
          box-shadow: 0 0 8px rgba(16, 185, 129, 0.25);
        }

        .hud-status-badge.low {
          background: rgba(6, 182, 212, 0.16);
          color: #22d3ee;
          border-color: rgba(6, 182, 212, 0.35);
        }

        .hud-status-badge.high {
          background: rgba(245, 158, 11, 0.16);
          color: #fbbf24;
          border-color: rgba(245, 158, 11, 0.35);
        }

        .hud-status-badge.critical {
          background: rgba(239, 68, 68, 0.18);
          color: #f87171;
          border-color: rgba(239, 68, 68, 0.4);
          box-shadow: 0 0 8px rgba(239, 68, 68, 0.3);
        }

        .hud-divider {
          width: 1px;
          height: 28px;
          background: rgba(255, 255, 255, 0.1);
        }

        /* TRANSLUCENT RESERVOIR & PUMP DOCK (BOTTOM) */
        .reservoir-dock {
          width: 100%;
          background: linear-gradient(180deg, rgba(13, 17, 23, 0.95) 0%, rgba(8, 47, 73, 0.88) 100%);
          border: 1px solid rgba(6, 182, 212, 0.35);
          border-radius: 16px;
          padding: 12px 18px;
          display: flex;
          flex-wrap: wrap;
          align-items: center;
          justify-content: space-between;
          gap: 12px;
          box-shadow: 0 8px 30px rgba(0, 0, 0, 0.6), 0 0 20px rgba(6, 182, 212, 0.25);
          backdrop-filter: blur(14px);
          position: relative;
          overflow: hidden;
          z-index: 10;
        }

        .reservoir-dock.chiller-active {
          border-color: rgba(56, 189, 248, 0.65);
          box-shadow: 0 8px 30px rgba(0, 0, 0, 0.6), 0 0 25px rgba(56, 189, 248, 0.35);
        }

        .water-wave-bg {
          position: absolute;
          inset: 0;
          background: linear-gradient(180deg, transparent 40%, rgba(6, 182, 212, 0.08) 100%);
          pointer-events: none;
        }

        /* RESERVOIR AERATION BUBBLES */
        .aeration-bubbles {
          position: absolute;
          inset: 0;
          pointer-events: none;
          overflow: hidden;
          opacity: 0;
          transition: opacity 0.4s ease;
        }

        .aeration-bubbles.active {
          opacity: 1;
        }

        .bubble-dot {
          position: absolute;
          bottom: -8px;
          border-radius: 50%;
          background: radial-gradient(circle at 30% 30%, #ffffff, rgba(6, 182, 212, 0.5));
          box-shadow: 0 0 4px rgba(6, 182, 212, 0.6);
          animation: bubble-rise 2.4s ease-in infinite;
        }

        .b1 { left: 12%; width: 5px; height: 5px; animation-delay: 0.1s; }
        .b2 { left: 24%; width: 7px; height: 7px; animation-delay: 0.5s; }
        .b3 { left: 38%; width: 6px; height: 6px; animation-delay: 1.1s; }
        .b4 { left: 52%; width: 8px; height: 8px; animation-delay: 0.3s; }
        .b5 { left: 68%; width: 5px; height: 5px; animation-delay: 0.8s; }
        .b6 { left: 82%; width: 7px; height: 7px; animation-delay: 1.4s; }

        @keyframes bubble-rise {
          0% { transform: translateY(0) scale(0.6); opacity: 0; }
          20% { opacity: 0.8; }
          80% { opacity: 0.8; }
          100% { transform: translateY(-65px) scale(1.2); opacity: 0; }
        }

        /* RDWC FLUID RECIRCULATION STREAM */
        .res-flow-stream {
          position: absolute;
          left: 0;
          right: 0;
          bottom: 0;
          height: 4px;
          background: linear-gradient(90deg, transparent, rgba(6, 182, 212, 0.6), transparent);
          background-size: 200% 100%;
          opacity: 0;
          transition: opacity 0.4s ease;
        }

        .res-flow-stream.active {
          opacity: 1;
          animation: flow-shimmer 2s linear infinite;
        }

        @keyframes flow-shimmer {
          from { background-position: 200% 0; }
          to { background-position: -200% 0; }
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
          border-radius: 9px;
          padding: 6px 11px;
          display: flex;
          align-items: center;
          gap: 6px;
          font-size: 11px;
          font-weight: 600;
          color: #8b949e;
          cursor: pointer;
          transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1);
        }

        .pump-btn:hover {
          background: rgba(255, 255, 255, 0.1);
          color: #fff;
          transform: translateY(-1px);
        }

        .pump-btn:active {
          transform: translateY(1px);
        }

        .pump-btn.active {
          background: rgba(6, 182, 212, 0.2);
          border-color: var(--tg-cyan);
          color: #e0f2fe;
          box-shadow: 0 0 12px rgba(6, 182, 212, 0.35);
        }

        .pump-btn.active.chiller {
          background: rgba(56, 189, 248, 0.22);
          border-color: #38bdf8;
          color: #f0f9ff;
          box-shadow: 0 0 12px rgba(56, 189, 248, 0.4);
        }

        .pump-dot {
          width: 7px;
          height: 7px;
          border-radius: 50%;
          background: #484f58;
          transition: all 0.2s ease;
        }

        .pump-btn.active .pump-dot {
          background: var(--tg-cyan);
          box-shadow: 0 0 7px var(--tg-cyan);
        }

        .pump-btn.active.chiller .pump-dot {
          background: #38bdf8;
          box-shadow: 0 0 7px #38bdf8;
        }

        .pump-status-text {
          font-size: 9px;
          font-weight: 700;
          text-transform: uppercase;
          color: #6e7681;
        }

        .pump-btn.active .pump-status-text {
          color: #a5f3fc;
        }

        /* BOTTOM DRAWER / TABS */
        .drawer-bar {
          display: flex;
          border-top: 1px solid var(--tg-border);
          background: rgba(13, 17, 23, 0.95);
          position: relative;
          z-index: 10;
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
          margin-top: 8px;
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
            padding: 7px 12px;
            gap: 10px;
          }
          .hud-metric-val {
            font-size: 15px;
          }
          .light-bar {
            width: 170px;
          }
          .light-cone {
            width: 220px;
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
                <svg width="42" height="42">
                  <circle class="dial-track" cx="21" cy="21" r="16" />
                  <circle class="dial-progress" id="dial-bar" cx="21" cy="21" r="16" stroke-dasharray="100.5" stroke-dashoffset="100.5" />
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
          <div class="tent-backdrop"></div>

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
                <div class="exhaust-vortex" id="exhaust-vortex">
                  <svg viewBox="0 0 50 36" fill="none">
                    <path class="vortex-trail" d="M 8 32 C 14 20, 26 16, 24 8 C 22 2, 34 0, 42 2" stroke="#06b6d4" stroke-width="1.5" stroke-dasharray="4 3" />
                    <path class="vortex-trail" d="M 16 34 C 20 22, 32 18, 30 10 C 28 4, 38 2, 46 4" stroke="#22d3ee" stroke-width="1.2" stroke-dasharray="3 3" />
                  </svg>
                </div>
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
                <!-- Photon Particles -->
                <div class="photon-stream" id="photon-stream">
                  <div class="photon-particle p1"></div>
                  <div class="photon-particle p2"></div>
                  <div class="photon-particle p3"></div>
                  <div class="photon-particle p4"></div>
                  <div class="photon-particle p5"></div>
                  <div class="photon-particle p6"></div>
                </div>
                <div class="light-badge">
                  <span>💡</span>
                  <span id="light-power-text">OFF</span>
                </div>
              </div>

              <!-- CIRCULATION FAN -->
              <div class="circ-fan-box" id="circ-fan-box" title="Circulation Fan">
                <div class="circ-breeze" id="circ-breeze">
                  <svg viewBox="0 0 80 40" fill="none">
                    <path class="breeze-curve" d="M 75 5 C 50 15, 25 15, 5 30" stroke="rgba(16, 185, 129, 0.6)" stroke-width="1.5" stroke-dasharray="6 4" stroke-linecap="round" />
                    <path class="breeze-curve" d="M 70 18 C 45 28, 20 25, 8 36" stroke="rgba(52, 211, 153, 0.45)" stroke-width="1.2" stroke-dasharray="5 5" stroke-linecap="round" />
                  </svg>
                </div>
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

            <!-- BOTANICAL PLANT CANOPY VIEWPORT -->
            <div class="canopy-viewport" id="canopy-viewport">
              <!-- Rendered dynamically by _renderBotanicalCanopy -->
            </div>

            <!-- FLOATING CANOPY TELEMETRY HUD CAPSULE -->
            <div class="canopy-hud-wrapper">
              <div class="hud-capsule" id="canopy-hud" title="Click to view Sweet-Spot Range Meters">
                <div class="hud-metric">
                  <span class="hud-metric-label">Temp</span>
                  <div class="hud-metric-val" id="canopy-temp">--<span>°F</span></div>
                  <span class="hud-status-badge optimal" id="temp-badge">OPT</span>
                </div>
                <div class="hud-divider"></div>
                <div class="hud-metric">
                  <span class="hud-metric-label">Humidity</span>
                  <div class="hud-metric-val" id="canopy-rh">--<span>%</span></div>
                  <span class="hud-status-badge optimal" id="rh-badge">OPT</span>
                </div>
                <div class="hud-divider"></div>
                <div class="hud-metric">
                  <span class="hud-metric-label">Leaf VPD</span>
                  <div class="hud-metric-val" id="canopy-vpd" style="color: #34d399;">--<span> kPa</span></div>
                  <span class="hud-status-badge optimal" id="vpd-badge">OPT</span>
                </div>
                <div class="hud-divider"></div>
                <div class="hud-metric">
                  <span class="hud-metric-label">Dew Point</span>
                  <div class="hud-metric-val" id="canopy-dew">--<span>°F</span></div>
                  <span class="hud-status-badge" id="dew-badge" style="color: #94a3b8;">AIR</span>
                </div>
              </div>
            </div>

            <!-- TRANSLUCENT RESERVOIR BASE DOCK -->
            <div class="reservoir-dock" id="res-dock">
              <div class="water-wave-bg"></div>
              <!-- Bubbler Aeration -->
              <div class="aeration-bubbles" id="res-bubbles">
                <div class="bubble-dot b1"></div>
                <div class="bubble-dot b2"></div>
                <div class="bubble-dot b3"></div>
                <div class="bubble-dot b4"></div>
                <div class="bubble-dot b5"></div>
                <div class="bubble-dot b6"></div>
              </div>
              <!-- Recirculation Flow Shimmer -->
              <div class="res-flow-stream" id="res-flow"></div>

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
                <button class="pump-btn" id="btn-rdwc" title="Toggle RDWC Recirculation Pump">
                  <span class="pump-dot"></span>
                  <span>RDWC</span>
                  <span class="pump-status-text" id="status-rdwc">OFF</span>
                </button>
                <button class="pump-btn" id="btn-air" title="Toggle Aeration Bubbler">
                  <span class="pump-dot"></span>
                  <span>Air</span>
                  <span class="pump-status-text" id="status-air">OFF</span>
                </button>
                <button class="pump-btn chiller" id="btn-chiller" title="Toggle Water Chiller Pump">
                  <span class="pump-dot"></span>
                  <span>Chiller</span>
                  <span class="pump-status-text" id="status-chiller">OFF</span>
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
            <button class="alert-action-btn" id="btn-run-ai" style="background: var(--tg-violet); font-size: 11.5px; padding: 6px 12px;">🧠 Run AI Health Check Now</button>
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

    // Click on HUD capsule opens Target Bands
    const hudCapsule = root.getElementById("canopy-hud");
    if (hudCapsule) hudCapsule.onclick = () => this._toggleDrawer("bands");

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

    // Stage & Week
    const stage = getStateStr(this._hass, this._config.stage, "Vegetative");
    const week = getStateStr(this._hass, this._config.week, "1");
    const stageBadge = root.getElementById("stage-badge");
    if (stageBadge) {
      stageBadge.textContent = `${stage.toUpperCase()} • WEEK ${week}`;
    }

    // Render Botanical Canopy SVG if stage changed or not yet rendered
    const normalizedStage = this._normalizeStage(stage);
    if (this._renderedStage !== normalizedStage) {
      const viewport = root.getElementById("canopy-viewport");
      if (viewport) {
        viewport.innerHTML = this._renderBotanicalCanopy(normalizedStage);
        this._renderedStage = normalizedStage;
      }
    }

    // AI Health Dial
    const score = getStateNum(this._hass, this._config.ai_health_score, 90);
    const dialVal = root.getElementById("dial-val");
    const dialBar = root.getElementById("dial-bar");
    const healthStatus = root.getElementById("health-status");
    if (dialVal && dialBar) {
      dialVal.textContent = score !== null ? Math.round(score) : "--";
      const circumference = 2 * Math.PI * 16; // ~100.5
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
    const photonStream = root.getElementById("photon-stream");
    const lightPower = root.getElementById("light-power-text");
    if (lightState && lightBar && lightCone && lightPower) {
      const isOn = lightState.state === "on";
      const brightness = lightState.attributes?.brightness
        ? Math.round((lightState.attributes.brightness / 255) * 100)
        : null;
      if (isOn) {
        lightBar.classList.add("on");
        lightCone.classList.add("on");
        if (photonStream) photonStream.classList.add("on");
        lightPower.textContent = brightness !== null ? `${brightness}%` : "ON";
      } else {
        lightBar.classList.remove("on");
        lightCone.classList.remove("on");
        if (photonStream) photonStream.classList.remove("on");
        lightPower.textContent = "OFF";
      }
    }

    // Duct Fan
    const ductState = getState(this._hass, this._config.duct_fan);
    const ductRotor = root.getElementById("duct-rotor");
    const ductSpeed = root.getElementById("duct-speed-text");
    const exhaustVortex = root.getElementById("exhaust-vortex");
    if (ductState && ductRotor && ductSpeed) {
      const isFanOn = ductState.state === "on";
      const pct = ductState.attributes?.percentage || (isFanOn ? 100 : 0);
      ductSpeed.textContent = isFanOn ? `${pct}%` : "OFF";
      if (isFanOn) {
        ductRotor.classList.add(pct > 60 ? "spinning-fast" : "spinning");
        if (exhaustVortex) exhaustVortex.classList.add("active");
      } else {
        ductRotor.classList.remove("spinning", "spinning-fast");
        if (exhaustVortex) exhaustVortex.classList.remove("active");
      }
    }

    // Circulation Fan & Canopy Breeze
    const circState = getState(this._hass, this._config.fan);
    const circRotor = root.getElementById("circ-rotor");
    const circText = root.getElementById("circ-fan-text");
    const circBreeze = root.getElementById("circ-breeze");
    const swayGroup = root.getElementById("canopy-sway-group");
    if (circState && circRotor && circText) {
      const isOn = circState.state === "on";
      circText.textContent = isOn ? "ON" : "OFF";
      if (isOn) {
        circRotor.classList.add("spinning");
        if (circBreeze) circBreeze.classList.add("active");
        if (swayGroup) swayGroup.classList.add("swaying");
      } else {
        circRotor.classList.remove("spinning");
        if (circBreeze) circBreeze.classList.remove("active");
        if (swayGroup) swayGroup.classList.remove("swaying");
      }
    }

    // Target Bands definitions
    const targetVpdLow = getStateNum(this._hass, this._config.target_vpd_low, 0.9);
    const targetVpdHigh = getStateNum(this._hass, this._config.target_vpd_high, 1.3);
    const targetPhLow = getStateNum(this._hass, this._config.target_ph_low, 5.7);
    const targetPhHigh = getStateNum(this._hass, this._config.target_ph_high, 6.2);
    const targetEcLow = getStateNum(this._hass, this._config.target_ec_low, 1.4);
    const targetEcHigh = getStateNum(this._hass, this._config.target_ec_high, 2.2);

    // Canopy Climate Telemetry & Status Badges
    const tempNum = getStateNum(this._hass, this._config.temperature, null);
    const rhNum = getStateNum(this._hass, this._config.humidity, null);
    const vpdNum = getStateNum(this._hass, this._config.leaf_vpd || this._config.vpd, null);
    const dewNum = getStateNum(this._hass, this._config.dew_point, null);

    const tempStr = tempNum !== null ? tempNum.toFixed(1) : "--";
    const rhStr = rhNum !== null ? Math.round(rhNum) : "--";
    const vpdStr = vpdNum !== null ? vpdNum.toFixed(2) : "--";
    const dewStr = dewNum !== null ? dewNum.toFixed(1) : "--";

    const elTemp = root.getElementById("canopy-temp");
    const elRh = root.getElementById("canopy-rh");
    const elVpd = root.getElementById("canopy-vpd");
    const elDew = root.getElementById("canopy-dew");

    if (elTemp) elTemp.innerHTML = `${tempStr}<span>°F</span>`;
    if (elRh) elRh.innerHTML = `${rhStr}<span>%</span>`;
    if (elVpd) elVpd.innerHTML = `${vpdStr}<span> kPa</span>`;
    if (elDew) elDew.innerHTML = `${dewStr}<span>°F</span>`;

    // Dynamic Target Badges
    const tempTarget = this._evalTarget(tempNum, 72, 82);
    const rhTarget = this._evalTarget(rhNum, 55, 68);
    const vpdTarget = this._evalTarget(vpdNum, targetVpdLow, targetVpdHigh);

    const bTemp = root.getElementById("temp-badge");
    const bRh = root.getElementById("rh-badge");
    const bVpd = root.getElementById("vpd-badge");

    if (bTemp) {
      bTemp.className = `hud-status-badge ${tempTarget.status}`;
      bTemp.textContent = tempTarget.label;
    }
    if (bRh) {
      bRh.className = `hud-status-badge ${rhTarget.status}`;
      bRh.textContent = rhTarget.label;
    }
    if (bVpd) {
      bVpd.className = `hud-status-badge ${vpdTarget.status}`;
      bVpd.textContent = vpdTarget.label;
    }

    // Hydro Reservoir
    const phNum = getStateNum(this._hass, this._config.ph, null);
    const ecNum = getStateNum(this._hass, this._config.ec, null);
    const wtemp = getStateStr(this._hass, this._config.water_temperature, "--");
    const tds = getStateStr(this._hass, this._config.tds, "--");

    const elPh = root.getElementById("res-ph");
    const elEc = root.getElementById("res-ec");
    const elWtemp = root.getElementById("res-temp");
    const elTds = root.getElementById("res-tds");

    if (elPh) elPh.textContent = phNum !== null ? phNum.toFixed(2) : "--";
    if (elEc) elEc.textContent = ecNum !== null ? ecNum.toFixed(2) : "--";
    if (elWtemp) elWtemp.textContent = `${wtemp}°F`;
    if (elTds) elTds.textContent = tds;

    // Pumps & Equipment
    const rdwcState = getState(this._hass, this._config.rdwc_pump);
    const airState = getState(this._hass, this._config.air_pump);
    const chillerState = getState(this._hass, this._config.chiller_pump);

    const btnRdwc = root.getElementById("btn-rdwc");
    const btnAir = root.getElementById("btn-air");
    const btnChiller = root.getElementById("btn-chiller");
    const statRdwc = root.getElementById("status-rdwc");
    const statAir = root.getElementById("status-air");
    const statChiller = root.getElementById("status-chiller");

    const resDock = root.getElementById("res-dock");
    const resBubbles = root.getElementById("res-bubbles");
    const resFlow = root.getElementById("res-flow");

    if (btnRdwc && rdwcState) {
      const isOn = rdwcState.state === "on";
      btnRdwc.classList.toggle("active", isOn);
      if (statRdwc) statRdwc.textContent = isOn ? "ON" : "OFF";
      if (resFlow) resFlow.classList.toggle("active", isOn);
    }
    if (btnAir && airState) {
      const isOn = airState.state === "on";
      btnAir.classList.toggle("active", isOn);
      if (statAir) statAir.textContent = isOn ? "ON" : "OFF";
      if (resBubbles) resBubbles.classList.toggle("active", isOn);
    }
    if (btnChiller && chillerState) {
      const isOn = chillerState.state === "on";
      btnChiller.classList.toggle("active", isOn);
      if (statChiller) statChiller.textContent = isOn ? "ON" : "OFF";
      if (resDock) resDock.classList.toggle("chiller-active", isOn);
    }

    // Alerts Ribbon
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
        optLow: getStateNum(this._hass, this._config.target_vpd_low, 0.9),
        optHigh: getStateNum(this._hass, this._config.target_vpd_high, 1.3),
      },
      {
        label: "Hydroponic pH",
        val: getStateNum(this._hass, this._config.ph, 5.9),
        unit: "",
        min: 4.5,
        max: 7.5,
        optLow: getStateNum(this._hass, this._config.target_ph_low, 5.7),
        optHigh: getStateNum(this._hass, this._config.target_ph_high, 6.2),
      },
      {
        label: "Electrical Conductivity (EC)",
        val: getStateNum(this._hass, this._config.ec, 1.8),
        unit: "mS",
        min: 0.5,
        max: 3.5,
        optLow: getStateNum(this._hass, this._config.target_ec_low, 1.4),
        optHigh: getStateNum(this._hass, this._config.target_ec_high, 2.2),
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
          transition: border-color 0.25s ease, box-shadow 0.25s ease, background 0.25s ease;
          display: flex;
          flex-direction: column;
          box-shadow: 0 4px 20px rgba(0, 0, 0, 0.35);
          position: relative;
        }

        .space-card:hover {
          border-color: rgba(16, 185, 129, 0.55);
          box-shadow: 0 0 24px rgba(16, 185, 129, 0.2), 0 8px 32px rgba(0, 0, 0, 0.6);
          background: rgba(22, 30, 48, 0.95);
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
          transition: opacity 0.3s ease;
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

    // Check if we need to build the card DOM nodes
    const existingCards = grid.querySelectorAll(".space-card");
    if (existingCards.length !== spaces.length) {
      this._buildCardSkeletons(grid, spaces);
    }

    // Update in-place to prevent DOM recreation and eliminate mouse hover jitter
    spaces.forEach((s, idx) => {
      const card = grid.querySelector(`.space-card[data-idx="${idx}"]`);
      if (!card) return;

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

      // Update stage
      const stageEl = card.querySelector(".stage-tag");
      if (stageEl && stageEl.textContent !== stage) stageEl.textContent = stage;

      // Update alert banner
      const alertBanner = card.querySelector(".cam-alert-banner");
      if (alertBanner) {
        if (alertMsg) {
          alertBanner.style.display = "flex";
          alertBanner.textContent = `⚠️ ${alertMsg}`;
        } else {
          alertBanner.style.display = "none";
        }
      }

      // Update camera image URL with token
      if (s.camera) {
        const camImg = card.querySelector(".space-cam-img");
        if (camImg) {
          const camState = getState(this._hass, s.camera);
          if (camState) {
            const token = camState.attributes?.access_token;
            const targetUrl = token
              ? `/api/camera_proxy_stream/${s.camera}?token=${token}`
              : (camState.attributes?.entity_picture || `/api/camera_proxy/${s.camera}`);
            if (targetUrl && camImg.src !== targetUrl && !camImg.src.endsWith(targetUrl)) {
              camImg.src = targetUrl;
            }
          }
        }
      }

      // Circular Dial Progress
      const circumference = 2 * Math.PI * 17; // ~106.8
      const validScore = score !== null ? Math.max(0, Math.min(100, score)) : 90;
      const offset = circumference - (validScore / 100) * circumference;
      const ringColor = validScore >= 75 ? "#10b981" : validScore >= 50 ? "#f59e0b" : "#ef4444";

      const scoreEl = card.querySelector(".health-score-val");
      if (scoreEl) {
        scoreEl.textContent = `${Math.round(validScore)}%`;
        scoreEl.style.color = ringColor;
      }
      const ringEl = card.querySelector(".health-ring");
      if (ringEl) {
        ringEl.style.stroke = ringColor;
        ringEl.style.strokeDashoffset = offset;
      }

      // Telemetry metrics
      const tempEl = card.querySelector(".metric-temp");
      if (tempEl && tempEl.textContent !== `${temp}°`) tempEl.textContent = `${temp}°`;
      const rhEl = card.querySelector(".metric-rh");
      if (rhEl && rhEl.textContent !== `${rh}%`) rhEl.textContent = `${rh}%`;
      const vpdEl = card.querySelector(".metric-vpd");
      if (vpdEl && vpdEl.textContent !== `${vpd}`) vpdEl.textContent = `${vpd}`;

      const phEl = card.querySelector(".metric-ph");
      if (phEl && phEl.textContent !== `${ph}`) phEl.textContent = `${ph}`;
      const ecEl = card.querySelector(".metric-ec");
      if (ecEl && ecEl.textContent !== `${ec}`) ecEl.textContent = `${ec}`;
      const waterEl = card.querySelector(".metric-water");
      if (waterEl && waterEl.textContent !== `${waterTemp}°`) waterEl.textContent = `${waterTemp}°`;

      // Buttons
      const btnLight = card.querySelector('button[data-action="toggle-light"]');
      if (btnLight) {
        if (lightOn) {
          btnLight.classList.add("active");
          btnLight.textContent = "💡 Light ON";
        } else {
          btnLight.classList.remove("active");
          btnLight.textContent = "💡 Light OFF";
        }
      }
      const btnFan = card.querySelector('button[data-action="toggle-fan"]');
      if (btnFan) {
        if (fanOn) {
          btnFan.classList.add("active");
          btnFan.textContent = "💨 Fan ON";
        } else {
          btnFan.classList.remove("active");
          btnFan.textContent = "💨 Fan OFF";
        }
      }
    });

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
  }

  _buildCardSkeletons(grid, spaces) {
    grid.innerHTML = spaces
      .map((s, idx) => {
        const hasCamera = Boolean(s.camera);
        return `
          <div class="space-card" data-idx="${idx}">
            ${
              hasCamera
                ? `
                  <div class="space-hero">
                    <img class="space-cam-img" src="" alt="${s.name}" loading="lazy" />
                    <div class="cam-scrim"></div>
                    <div class="live-tag"><span class="pulse-dot"></span> LIVE</div>
                    <div class="stage-tag">...</div>
                    <div class="cam-alert-banner" style="display: none;"></div>
                  </div>
                `
                : `
                  <div class="schematic-hero">
                    <div class="schematic-icon">🌱</div>
                    <div class="stage-tag">...</div>
                    <div class="cam-alert-banner" style="display: none;"></div>
                  </div>
                `
            }

            <div class="card-body">
              <div class="title-row">
                <div class="space-name">${s.name || `Space ${idx + 1}`}</div>
                <div class="health-dial-box" title="AI Health Score">
                  <svg>
                    <circle class="health-track" cx="22" cy="22" r="17" />
                    <circle class="health-ring" cx="22" cy="22" r="17" style="stroke: #10b981; stroke-dasharray: 106.8; stroke-dashoffset: 0;" />
                  </svg>
                  <div class="health-score-val" style="color: #10b981">--%</div>
                </div>
              </div>

              <div class="capsules-grid">
                <!-- Canopy Telemetry -->
                <div class="telemetry-capsule">
                  <div class="capsule-title">🌿 Canopy Air</div>
                  <div class="capsule-row">
                    <div class="metric-cell">
                      <span class="metric-label">Temp</span>
                      <span class="metric-val metric-temp">--°</span>
                    </div>
                    <div class="metric-cell">
                      <span class="metric-label">RH</span>
                      <span class="metric-val metric-rh">--%</span>
                    </div>
                    <div class="metric-cell">
                      <span class="metric-label">VPD</span>
                      <span class="metric-val green metric-vpd">--</span>
                    </div>
                  </div>
                </div>

                <!-- Hydroponic Reservoir -->
                <div class="telemetry-capsule">
                  <div class="capsule-title">💧 Reservoir</div>
                  <div class="capsule-row">
                    <div class="metric-cell">
                      <span class="metric-label">pH</span>
                      <span class="metric-val cyan metric-ph">--</span>
                    </div>
                    <div class="metric-cell">
                      <span class="metric-label">EC</span>
                      <span class="metric-val metric-ec">--</span>
                    </div>
                    <div class="metric-cell">
                      <span class="metric-label">Water</span>
                      <span class="metric-val metric-water">--°</span>
                    </div>
                  </div>
                </div>
              </div>

              <div class="controls-row">
                <div class="quick-toggles">
                  ${
                    s.light
                      ? `<button class="btn-toggle" data-action="toggle-light" data-idx="${idx}">💡 Light</button>`
                      : ""
                  }
                  ${
                    s.fan
                      ? `<button class="btn-toggle" data-action="toggle-fan" data-idx="${idx}">💨 Fan</button>`
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

    // Bind navigation clicks on the card
    grid.querySelectorAll(".space-card").forEach((card) => {
      card.addEventListener("click", (e) => {
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

// ============================================================================
// 3. TENDRILGROW TELEMETRY TRENDS CARD (<tendrilgrow-trends-card>)
// ============================================================================
class TendrilGrowTrendsCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._config = {};
    this._hass = null;
    this._mode = "canopy"; // 'canopy' | 'hydro'
    this._hours = 24; // 6 | 12 | 24
    this._historyData = {}; // entityId -> [{val, time}]
    this._lastFetchTime = 0;
    this._hoverData = null;
    this._spaceChartData = {};
  }

  static getStubConfig() {
    return {
      title: "Cultivation Telemetry Curves",
      hours_to_show: 24,
      spaces: [],
    };
  }

  setConfig(config) {
    if (!config) throw new Error("Invalid configuration");
    this._config = {
      title: config.title || "Cultivation Telemetry Curves",
      hours_to_show: config.hours_to_show || 24,
      spaces: Array.isArray(config.spaces) ? config.spaces : [],
      ...config,
    };
    this._hours = this._config.hours_to_show;
    this._spaceChartData = {};
    this._render();
  }

  set hass(hass) {
    try {
      const oldHass = this._hass;
      this._hass = hass;
      if (!oldHass || Date.now() - this._lastFetchTime > 60000) {
        this._fetchHistory();
      } else {
        this._updateStats();
      }
    } catch (err) {
      console.error("TendrilGrowTrendsCard: Error in set hass:", err);
    }
  }

  getCardSize() {
    return 6;
  }

  _getAllEntityIds() {
    const ids = new Set();
    (this._config.spaces || []).forEach((s) => {
      [s.temperature, s.humidity, s.vpd, s.leaf_vpd, s.ph, s.ec, s.water_temperature].forEach(
        (id) => {
          if (id) ids.add(id);
        }
      );
    });
    return Array.from(ids);
  }

  async _fetchHistory(force = false) {
    if (!this._hass) return;
    const now = Date.now();
    if (!force && now - this._lastFetchTime < 45000 && Object.keys(this._historyData).length > 0) {
      return;
    }
    this._lastFetchTime = now;
    const hours = this._hours || 24;
    const startTime = new Date(now - hours * 3600 * 1000).toISOString();
    const entityIds = this._getAllEntityIds();
    if (entityIds.length === 0) return;

    try {
      if (typeof this._hass.callApi === "function") {
        const path = `history/period/${encodeURIComponent(startTime)}?filter_entity_id=${encodeURIComponent(
          entityIds.join(",")
        )}&minimal_response&significant_changes_only=1`;
        const data = await this._hass.callApi("GET", path);
        if (Array.isArray(data)) {
          data.forEach((entityList) => {
            if (Array.isArray(entityList) && entityList.length > 0) {
              const entityId = entityList[0].entity_id;
              const points = entityList
                .map((item) => {
                  const val = parseFloat(item.state);
                  const time = new Date(item.last_changed || item.last_updated).getTime();
                  return isNaN(val) ? null : { val, time };
                })
                .filter(Boolean);
              this._historyData[entityId] = points;
            }
          });
        }
      }
    } catch (err) {
      console.debug("TendrilGrow: Could not fetch history period:", err);
    }
    this._renderCharts();
  }

  _render() {
    try {
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
            --tg-blue: #38bdf8;
            --tg-violet: #8b5cf6;
            --tg-amber: #f59e0b;
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
            margin-bottom: 18px;
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
            background: linear-gradient(135deg, #06b6d4, #0891b2);
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 18px;
            box-shadow: 0 0 16px rgba(6, 182, 212, 0.35);
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

          /* CONTROLS (TABS & TIME WINDOW) */
          .header-controls {
            display: flex;
            align-items: center;
            gap: 10px;
            flex-wrap: wrap;
          }

          .tabs-pill-box {
            background: rgba(13, 17, 23, 0.85);
            border: 1px solid var(--tg-border);
            border-radius: 10px;
            padding: 3px;
            display: flex;
            gap: 4px;
          }

          .tab-btn {
            background: transparent;
            border: none;
            color: #8b949e;
            font-size: 12px;
            font-weight: 600;
            padding: 5px 12px;
            border-radius: 8px;
            cursor: pointer;
            transition: all 0.2s ease;
          }

          .tab-btn:hover {
            color: #fff;
          }

          .tab-btn.active {
            background: rgba(16, 185, 129, 0.18);
            color: #34d399;
            font-weight: 700;
            box-shadow: 0 0 10px rgba(16, 185, 129, 0.2);
          }

          .tab-btn.active.hydro {
            background: rgba(6, 182, 212, 0.18);
            color: #38bdf8;
            box-shadow: 0 0 10px rgba(6, 182, 212, 0.2);
          }

          .time-box {
            background: rgba(13, 17, 23, 0.85);
            border: 1px solid var(--tg-border);
            border-radius: 10px;
            padding: 3px;
            display: flex;
            gap: 2px;
          }

          .time-btn {
            background: transparent;
            border: none;
            color: #8b949e;
            font-size: 11px;
            font-weight: 600;
            padding: 5px 8px;
            border-radius: 6px;
            cursor: pointer;
            transition: all 0.2s ease;
          }

          .time-btn:hover {
            color: #fff;
          }

          .time-btn.active {
            background: rgba(255, 255, 255, 0.1);
            color: #fff;
            font-weight: 700;
          }

          /* SPACES PANELS */
          .trends-grid {
            display: grid;
            grid-template-columns: 1fr;
            gap: 16px;
          }

          .trend-space-panel {
            background: var(--tg-card-bg);
            border: 1px solid var(--tg-border);
            border-radius: 14px;
            padding: 16px;
            display: flex;
            flex-direction: column;
            gap: 12px;
            box-shadow: 0 4px 16px rgba(0, 0, 0, 0.3);
            transition: border-color 0.25s ease;
          }

          .trend-space-panel:hover {
            border-color: rgba(6, 182, 212, 0.4);
          }

          .panel-top {
            display: flex;
            align-items: center;
            justify-content: space-between;
            flex-wrap: wrap;
            gap: 10px;
          }

          .space-title-row {
            display: flex;
            align-items: center;
            gap: 10px;
          }

          .panel-space-name {
            font-size: 16px;
            font-weight: 700;
            color: #fff;
          }

          .target-corridor-badge {
            background: rgba(16, 185, 129, 0.12);
            border: 1px solid rgba(16, 185, 129, 0.3);
            color: #34d399;
            font-size: 11px;
            font-weight: 600;
            padding: 2px 8px;
            border-radius: 10px;
          }

          /* STATS PILLS */
          .stats-pills-row {
            display: flex;
            align-items: center;
            gap: 8px;
            flex-wrap: wrap;
          }

          .stat-pill {
            background: rgba(13, 17, 23, 0.7);
            border: 1px solid rgba(255, 255, 255, 0.06);
            border-radius: 8px;
            padding: 4px 10px;
            font-size: 11px;
            display: flex;
            align-items: center;
            gap: 6px;
          }

          .stat-pill-label {
            color: #8b949e;
            text-transform: uppercase;
            font-size: 9px;
            font-weight: 700;
          }

          .stat-pill-val {
            color: #fff;
            font-weight: 700;
            font-size: 12px;
          }

          .stat-pill-range {
            color: #6e7681;
            font-size: 10px;
          }

          /* SVG CHART CONTAINER */
          .chart-container {
            position: relative;
            width: 100%;
            height: 140px;
            background: rgba(10, 14, 22, 0.6);
            border-radius: 10px;
            border: 1px solid rgba(255, 255, 255, 0.04);
            overflow: hidden;
          }

          .chart-svg {
            width: 100%;
            height: 100%;
            display: block;
          }

          /* TOOLTIP */
          .chart-tooltip {
            position: absolute;
            display: none;
            background: rgba(13, 17, 23, 0.95);
            backdrop-filter: blur(8px);
            border: 1px solid rgba(255, 255, 255, 0.2);
            color: #fff;
            padding: 4px 10px;
            border-radius: 6px;
            font-size: 11px;
            pointer-events: none;
            white-space: nowrap;
            z-index: 10;
            box-shadow: 0 4px 16px rgba(0, 0, 0, 0.6);
          }
        </style>

        <div class="container">
          <div class="header">
            <div class="header-title-box">
              <div class="brand-badge">📈</div>
              <div>
                <h2>${this._config.title}</h2>
                <div class="header-subtitle">24-Hour Telemetry Intelligence & Environmental Trends</div>
              </div>
            </div>

            <div class="header-controls">
              <div class="tabs-pill-box">
                <button class="tab-btn ${this._mode === "canopy" ? "active" : ""}" data-mode="canopy">🌿 Canopy Climate</button>
                <button class="tab-btn ${this._mode === "hydro" ? "active hydro" : ""}" data-mode="hydro">💧 Reservoir Chemistry</button>
              </div>
              <div class="time-box">
                <button class="time-btn ${this._hours === 6 ? "active" : ""}" data-hours="6">6h</button>
                <button class="time-btn ${this._hours === 12 ? "active" : ""}" data-hours="12">12h</button>
                <button class="time-btn ${this._hours === 24 ? "active" : ""}" data-hours="24">24h</button>
              </div>
            </div>
          </div>

          <div class="trends-grid" id="trends-grid">
            <!-- Populated dynamically -->
          </div>
        </div>
      `;

      this._bindHeaderEvents();
      this._renderCharts();
    } catch (err) {
      console.error("TendrilGrowTrendsCard: Error in _render:", err);
    }
  }

  _bindHeaderEvents() {
    const root = this.shadowRoot;
    root.querySelectorAll("button[data-mode]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const mode = btn.getAttribute("data-mode");
        if (mode && this._mode !== mode) {
          this._mode = mode;
          this._render();
        }
      });
    });

    root.querySelectorAll("button[data-hours]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const hours = parseInt(btn.getAttribute("data-hours"), 10);
        if (hours && this._hours !== hours) {
          this._hours = hours;
          this._fetchHistory(true);
          this._render();
        }
      });
    });
  }

  _updateStats() {
    this._renderCharts();
  }

  _renderCharts() {
    try {
      if (!this._hass || !this.shadowRoot) return;
      const grid = this.shadowRoot.getElementById("trends-grid");
      if (!grid) return;

      const spaces = this._config.spaces || [];
      const mode = this._mode;
      const hours = this._hours || 24;
      const now = Date.now();
      const windowStart = now - hours * 3600 * 1000;

      this._spaceChartData = {};
      grid.innerHTML = spaces
        .map((s, sIdx) => {
          let primaryEntity = null;
          let secondaryEntity = null;
          let primaryLabel = "";
          let secondaryLabel = "";
          let primaryUnit = "";
          let targetLow = null;
          let targetHigh = null;
          let strokeColor = "#10b981";
          let secondaryStroke = "#38bdf8";

          if (mode === "canopy") {
            primaryEntity = s.leaf_vpd || s.vpd;
            secondaryEntity = s.temperature;
            primaryLabel = "Leaf VPD";
            secondaryLabel = "Temp";
            primaryUnit = "kPa";
            targetLow = 0.9;
            targetHigh = 1.3;
            strokeColor = "#10b981";
            secondaryStroke = "#38bdf8";
          } else {
            primaryEntity = s.ph;
            secondaryEntity = s.water_temperature;
            primaryLabel = "Hydro pH";
            secondaryLabel = "Water Temp";
            primaryUnit = "";
            targetLow = 5.7;
            targetHigh = 6.2;
            strokeColor = "#06b6d4";
            secondaryStroke = "#2dd4bf";
          }

          // Live values
          const primaryCurrent = getStateNum(this._hass, primaryEntity, null);
          const secondaryCurrent = getStateNum(this._hass, secondaryEntity, null);
          const humidityCurrent = getStateNum(this._hass, s.humidity, null);
          const ecCurrent = getStateNum(this._hass, s.ec, null);

          // History points for primary entity
          const rawPoints = (this._historyData[primaryEntity] || []).filter((p) => p.time >= windowStart);
          let minVal = targetLow !== null ? targetLow * 0.9 : 0;
          let maxVal = targetHigh !== null ? targetHigh * 1.1 : 100;
          let avgVal = primaryCurrent;

          if (rawPoints.length > 0) {
            const vals = rawPoints
              .map((p) => p.val)
              .filter((v) => typeof v === "number" && !isNaN(v));
            if (vals.length > 0) {
              minVal = Math.min(...vals);
              maxVal = Math.max(...vals);
              avgVal = vals.reduce((a, b) => a + b, 0) / vals.length;
            }
          }

          if (!isFinite(minVal)) minVal = 0;
          if (!isFinite(maxVal)) maxVal = 10;
          if (maxVal <= minVal) {
            minVal -= 0.5;
            maxVal += 0.5;
          }
          const valSpan = maxVal - minVal || 1;
          const padMin = minVal - valSpan * 0.1;
          const padMax = maxVal + valSpan * 0.1;
          const totalSpan = padMax - padMin || 1;

          // SVG Layout constants
          const svgW = 600;
          const svgH = 130;
          const padLeft = 40;
          const padRight = 15;
          const padTop = 15;
          const padBottom = 25;
          const plotW = svgW - padLeft - padRight;
          const plotH = svgH - padTop - padBottom;

          // Points mapping
          let plottedPoints = [];
          if (rawPoints.length >= 2) {
            plottedPoints = rawPoints.map((p) => {
              const x = padLeft + ((p.time - windowStart) / (now - windowStart)) * plotW;
              const y = padTop + plotH - ((p.val - padMin) / totalSpan) * plotH;
              return { x, y, val: p.val, time: p.time };
            });
          } else {
            // Fallback smooth sparkline curve if history is pending
            const base = primaryCurrent !== null ? primaryCurrent : ((targetLow ?? 1.0) + (targetHigh ?? 1.2)) / 2;
            for (let step = 0; step <= 10; step++) {
              const ratio = step / 10;
              const x = padLeft + ratio * plotW;
              const wave = Math.sin(ratio * Math.PI * 2) * (valSpan * 0.15);
              const val = base + wave;
              const y = padTop + plotH - ((val - padMin) / totalSpan) * plotH;
              plottedPoints.push({ x, y, val, time: windowStart + ratio * (now - windowStart) });
            }
          }

        // Generate smooth cubic bezier spline
        let splinePath = "";
        let areaPath = "";
        if (plottedPoints.length > 0) {
          splinePath = `M ${plottedPoints[0].x.toFixed(1)} ${plottedPoints[0].y.toFixed(1)}`;
          for (let i = 0; i < plottedPoints.length - 1; i++) {
            const p0 = plottedPoints[Math.max(i - 1, 0)];
            const p1 = plottedPoints[i];
            const p2 = plottedPoints[i + 1];
            const p3 = plottedPoints[Math.min(i + 2, plottedPoints.length - 1)];
            const cp1x = p1.x + (p2.x - p0.x) / 6;
            const cp1y = p1.y + (p2.y - p0.y) / 6;
            const cp2x = p2.x - (p3.x - p1.x) / 6;
            const cp2y = p2.y - (p3.y - p1.y) / 6;
            splinePath += ` C ${cp1x.toFixed(1)} ${cp1y.toFixed(1)}, ${cp2x.toFixed(1)} ${cp2y.toFixed(1)}, ${p2.x.toFixed(1)} ${p2.y.toFixed(1)}`;
          }
          const lastP = plottedPoints[plottedPoints.length - 1];
          const firstP = plottedPoints[0];
          const groundY = padTop + plotH;
          areaPath = `${splinePath} L ${lastP.x.toFixed(1)} ${groundY} L ${firstP.x.toFixed(1)} ${groundY} Z`;
        }

        // Target band corridor rect
        let targetRectSvg = "";
        if (targetLow !== null && targetHigh !== null) {
          const corridorTop = padTop + plotH - ((targetHigh - padMin) / totalSpan) * plotH;
          const corridorBottom = padTop + plotH - ((targetLow - padMin) / totalSpan) * plotH;
          const corridorH = Math.max(2, corridorBottom - corridorTop);
          targetRectSvg = `
            <rect x="${padLeft}" y="${corridorTop.toFixed(1)}" width="${plotW}" height="${corridorH.toFixed(1)}" fill="${mode === "canopy" ? "rgba(16, 185, 129, 0.08)" : "rgba(6, 182, 212, 0.08)"}" rx="3" />
            <line x1="${padLeft}" y1="${corridorTop.toFixed(1)}" x2="${padLeft + plotW}" y2="${corridorTop.toFixed(1)}" stroke="${strokeColor}" stroke-dasharray="3,3" stroke-opacity="0.35" />
            <line x1="${padLeft}" y1="${corridorBottom.toFixed(1)}" x2="${padLeft + plotW}" y2="${corridorBottom.toFixed(1)}" stroke="${strokeColor}" stroke-dasharray="3,3" stroke-opacity="0.35" />
          `;
        }

        const gradId = `area-grad-${sIdx}-${mode}`;
        this._spaceChartData[sIdx] = { plottedPoints, primaryLabel, primaryUnit, svgW, svgH };

        return `
          <div class="trend-space-panel" data-space="${sIdx}">
            <div class="panel-top">
              <div class="space-title-row">
                <span class="panel-space-name">${s.name || `Space ${sIdx + 1}`}</span>
                ${
                  targetLow !== null
                    ? `<span class="target-corridor-badge">Target: ${targetLow}–${targetHigh} ${primaryUnit}</span>`
                    : ""
                }
              </div>

              <div class="stats-pills-row">
                <div class="stat-pill">
                  <span class="stat-pill-label">${primaryLabel}</span>
                  <span class="stat-pill-val" style="color: ${strokeColor}">${primaryCurrent !== null ? primaryCurrent + primaryUnit : "--"}</span>
                  <span class="stat-pill-range">Low: ${minVal.toFixed(2)} • High: ${maxVal.toFixed(2)}</span>
                </div>

                ${
                  mode === "canopy" && secondaryCurrent !== null
                    ? `
                      <div class="stat-pill">
                        <span class="stat-pill-label">Temp</span>
                        <span class="stat-pill-val" style="color: #38bdf8">${secondaryCurrent}°F</span>
                      </div>
                      ${
                        humidityCurrent !== null
                          ? `
                            <div class="stat-pill">
                              <span class="stat-pill-label">RH</span>
                              <span class="stat-pill-val" style="color: #60a5fa">${humidityCurrent}%</span>
                            </div>
                          `
                          : ""
                      }
                    `
                    : ""
                }

                ${
                  mode === "hydro" && secondaryCurrent !== null
                    ? `
                      <div class="stat-pill">
                        <span class="stat-pill-label">Water</span>
                        <span class="stat-pill-val" style="color: #2dd4bf">${secondaryCurrent}°F</span>
                      </div>
                      ${
                        ecCurrent !== null
                          ? `
                            <div class="stat-pill">
                              <span class="stat-pill-label">EC</span>
                              <span class="stat-pill-val" style="color: #a78bfa">${ecCurrent}</span>
                            </div>
                          `
                          : ""
                      }
                    `
                    : ""
                }
              </div>
            </div>

            <div class="chart-container" id="chart-box-${sIdx}">
              <div class="chart-tooltip" id="tooltip-${sIdx}"></div>
              <svg class="chart-svg" viewBox="0 0 ${svgW} ${svgH}" preserveAspectRatio="none">
                <defs>
                  <linearGradient id="${gradId}" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stop-color="${strokeColor}" stop-opacity="0.35" />
                    <stop offset="100%" stop-color="${strokeColor}" stop-opacity="0.0" />
                  </linearGradient>
                </defs>

                <!-- Grid Background -->
                <line x1="${padLeft}" y1="${padTop}" x2="${padLeft + plotW}" y2="${padTop}" stroke="rgba(255,255,255,0.05)" />
                <line x1="${padLeft}" y1="${padTop + plotH * 0.5}" x2="${padLeft + plotW}" y2="${padTop + plotH * 0.5}" stroke="rgba(255,255,255,0.05)" />
                <line x1="${padLeft}" y1="${padTop + plotH}" x2="${padLeft + plotW}" y2="${padTop + plotH}" stroke="rgba(255,255,255,0.08)" />

                <!-- Target Corridor -->
                ${targetRectSvg}

                <!-- Filled Area -->
                <path d="${areaPath}" fill="url(#${gradId})" />

                <!-- Main Spline -->
                <path d="${splinePath}" fill="none" stroke="${strokeColor}" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" />

                <!-- End Node Pulsing Circle -->
                ${
                  plottedPoints.length > 0
                    ? `
                      <circle cx="${plottedPoints[plottedPoints.length - 1].x}" cy="${plottedPoints[plottedPoints.length - 1].y}" r="4" fill="${strokeColor}" stroke="#fff" stroke-width="1.5" />
                    `
                    : ""
                }

                <!-- Y Axis Labels -->
                <text x="${padLeft - 6}" y="${padTop + 4}" fill="#6e7681" font-size="9" text-anchor="end" font-weight="600">${maxVal.toFixed(1)}</text>
                <text x="${padLeft - 6}" y="${padTop + plotH}" fill="#6e7681" font-size="9" text-anchor="end" font-weight="600">${minVal.toFixed(1)}</text>

                <!-- X Axis Time Labels -->
                <text x="${padLeft}" y="${svgH - 6}" fill="#6e7681" font-size="9" text-anchor="start">-${hours}h</text>
                <text x="${padLeft + plotW * 0.5}" y="${svgH - 6}" fill="#6e7681" font-size="9" text-anchor="middle">-${Math.round(hours / 2)}h</text>
                <text x="${padLeft + plotW}" y="${svgH - 6}" fill="#6e7681" font-size="9" text-anchor="end">Now</text>
              </svg>
            </div>
          </div>
        `;
      })
      .join("");

    spaces.forEach((_, sIdx) => {
      const box = this.shadowRoot.getElementById(`chart-box-${sIdx}`);
      const tooltip = this.shadowRoot.getElementById(`tooltip-${sIdx}`);
      if (!box || !tooltip) return;

      box.addEventListener("mousemove", (e) => {
        const info = this._spaceChartData?.[sIdx];
        if (!info || !info.plottedPoints || info.plottedPoints.length === 0) return;
        const rect = box.getBoundingClientRect();
        const mouseX = e.clientX - rect.left;
        const scaleX = info.svgW / rect.width;
        const targetSvgX = mouseX * scaleX;

        let closest = info.plottedPoints[0];
        let minDiff = Math.abs(closest.x - targetSvgX);
        for (let i = 1; i < info.plottedPoints.length; i++) {
          const diff = Math.abs(info.plottedPoints[i].x - targetSvgX);
          if (diff < minDiff) {
            minDiff = diff;
            closest = info.plottedPoints[i];
          }
        }

        if (closest) {
          const timeStr = new Date(closest.time).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
          tooltip.style.display = "block";
          const leftPos = (closest.x / info.svgW) * rect.width;
          const clampedLeft = Math.max(10, Math.min(rect.width - 150, leftPos - 50));
          tooltip.style.left = `${clampedLeft}px`;
          tooltip.style.top = "10px";
          tooltip.innerHTML = `<strong>${closest.val.toFixed(2)} ${info.primaryUnit}</strong> <span style="color:#8b949e">(${timeStr})</span>`;
        }
      });

      box.addEventListener("mouseleave", () => {
        tooltip.style.display = "none";
      });
    });
    } catch (err) {
      console.error("TendrilGrowTrendsCard: Error in _renderCharts:", err);
    }
  }
}


// ============================================================================
// 4. TENDRILGROW CONTROLLER SCHEDULES & AMBIENT CARD (<tendrilgrow-schedules-card>)
// ============================================================================
class TendrilGrowSchedulesCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._config = {};
    this._hass = null;
  }

  static getStubConfig() {
    return {
      title: "Controller Schedules & Ambient",
      ambient: {},
      tent: {},
      schedules: [],
    };
  }

  setConfig(config) {
    if (!config) throw new Error("Invalid configuration");
    this._config = {
      title: config.title || "Controller Schedules & Ambient",
      ambient: config.ambient || {},
      tent: config.tent || {},
      schedules: Array.isArray(config.schedules) ? config.schedules : [],
      ...config,
    };
    this._render();
  }

  set hass(hass) {
    try {
      this._hass = hass;
      this._updateStates();
    } catch (err) {
      console.error("TendrilGrowSchedulesCard: Error in set hass:", err);
    }
  }

  getCardSize() {
    return 4;
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

  _render() {
    if (!this.shadowRoot) return;
    const title = this._config.title;

    this.shadowRoot.innerHTML = `
      <style>
        :host {
          display: block;
          font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
          color: #e6edf3;
          --tg-bg: #0b0f17;
          --tg-card-bg: rgba(15, 23, 42, 0.88);
          --tg-border: rgba(255, 255, 255, 0.08);
          --tg-green: #10b981;
          --tg-cyan: #06b6d4;
          --tg-amber: #f59e0b;
          --tg-violet: #8b5cf6;
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
          box-shadow: 0 10px 32px rgba(0, 0, 0, 0.5);
        }

        /* HEADER */
        .header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          margin-bottom: 16px;
          padding-bottom: 12px;
          border-bottom: 1px solid var(--tg-border);
          flex-wrap: wrap;
          gap: 10px;
        }

        .header-left {
          display: flex;
          align-items: center;
          gap: 12px;
        }

        .brand-badge {
          width: 32px;
          height: 32px;
          border-radius: 8px;
          background: linear-gradient(135deg, #06b6d4, #0891b2);
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 16px;
          box-shadow: 0 0 14px rgba(6, 182, 212, 0.35);
        }

        .header h2 {
          font-size: 16.5px;
          font-weight: 700;
          letter-spacing: -0.3px;
          color: #f0f6fc;
        }

        .subtitle {
          font-size: 11.5px;
          color: #8b949e;
          font-weight: 500;
        }

        .header-status-badge {
          font-size: 10px;
          font-weight: 700;
          text-transform: uppercase;
          letter-spacing: 0.5px;
          color: #38bdf8;
          background: rgba(56, 189, 248, 0.12);
          padding: 3px 9px;
          border-radius: 12px;
          border: 1px solid rgba(56, 189, 248, 0.3);
        }

        /* AMBIENT LUNG ROOM BUFFER BAR */
        .ambient-bar {
          display: flex;
          align-items: center;
          justify-content: space-between;
          background: rgba(13, 17, 23, 0.9);
          border: 1px solid rgba(6, 182, 212, 0.25);
          border-radius: 12px;
          padding: 10px 16px;
          margin-bottom: 16px;
          flex-wrap: wrap;
          gap: 14px;
        }

        .ambient-title-box {
          display: flex;
          align-items: center;
          gap: 10px;
        }

        .ambient-icon {
          font-size: 20px;
        }

        .ambient-title-text {
          display: flex;
          flex-direction: column;
        }

        .ambient-label {
          font-size: 11.5px;
          font-weight: 700;
          color: #f0f6fc;
        }

        .ambient-status {
          font-size: 9.5px;
          font-weight: 600;
          color: var(--tg-cyan);
          text-transform: uppercase;
        }

        .ambient-kpis {
          display: flex;
          align-items: center;
          gap: 18px;
          flex-wrap: wrap;
        }

        .kpi-item {
          display: flex;
          flex-direction: column;
        }

        .kpi-label {
          font-size: 9.5px;
          color: #8b949e;
          text-transform: uppercase;
          font-weight: 700;
          letter-spacing: 0.5px;
        }

        .kpi-val {
          font-size: 14px;
          font-weight: 700;
          color: #f0f6fc;
          display: flex;
          align-items: baseline;
          gap: 5px;
        }

        .kpi-delta {
          font-size: 10.5px;
          font-weight: 600;
          padding: 1px 5px;
          border-radius: 5px;
        }

        .kpi-delta.pos { color: #f87171; background: rgba(239, 68, 68, 0.15); }
        .kpi-delta.neg { color: #38bdf8; background: rgba(56, 189, 248, 0.15); }
        .kpi-delta.zero { color: #34d399; background: rgba(16, 185, 129, 0.15); }

        /* SCHEDULES GRID */
        .schedules-grid {
          display: grid;
          grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
          gap: 12px;
        }

        .schedule-card {
          background: rgba(15, 23, 42, 0.7);
          border: 1px solid var(--tg-border);
          border-radius: 12px;
          padding: 12px 14px;
          display: flex;
          align-items: center;
          gap: 12px;
          cursor: pointer;
          transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1);
        }

        .schedule-card:hover {
          background: rgba(30, 41, 59, 0.85);
          border-color: rgba(6, 182, 212, 0.4);
          transform: translateY(-2px);
          box-shadow: 0 6px 20px rgba(0, 0, 0, 0.4);
        }

        .sched-icon-box {
          width: 38px;
          height: 38px;
          border-radius: 10px;
          background: rgba(255, 255, 255, 0.05);
          border: 1px solid var(--tg-border);
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 18px;
          flex-shrink: 0;
        }

        .sched-details {
          display: flex;
          flex-direction: column;
          min-width: 0;
          flex: 1;
        }

        .sched-title-row {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 6px;
          margin-bottom: 2px;
        }

        .sched-name {
          font-size: 13px;
          font-weight: 700;
          color: #f0f6fc;
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }

        .sched-pill {
          font-size: 9px;
          font-weight: 700;
          text-transform: uppercase;
          padding: 2px 6px;
          border-radius: 6px;
          background: rgba(255, 255, 255, 0.08);
          color: #8b949e;
        }

        .sched-pill.active {
          background: rgba(16, 185, 129, 0.18);
          color: #34d399;
          border: 1px solid rgba(16, 185, 129, 0.35);
        }

        .sched-pill.auto {
          background: rgba(6, 182, 212, 0.18);
          color: #22d3ee;
          border: 1px solid rgba(6, 182, 212, 0.35);
        }

        .sched-pill.cycle {
          background: rgba(139, 92, 246, 0.18);
          color: #c084fc;
          border: 1px solid rgba(139, 92, 246, 0.35);
        }

        .sched-state-text {
          font-size: 11.5px;
          color: #94a3b8;
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }
      </style>

      <div class="container">
        <div class="header">
          <div class="header-left">
            <div class="brand-badge">⏱️</div>
            <div>
              <h2>${title}</h2>
              <div class="subtitle">Smart Controller Cycles & Environmental Buffers</div>
            </div>
          </div>
          <div class="header-status-badge">Auto Synchronized</div>
        </div>

        <!-- Ambient Lung Room Bar -->
        <div class="ambient-bar" id="ambient-box" style="display: none;">
          <div class="ambient-title-box">
            <span class="ambient-icon">🌬️</span>
            <div class="ambient-title-text">
              <span class="ambient-label">Lung Room (Ambient)</span>
              <span class="ambient-status" id="ambient-status-text">Buffer Stable</span>
            </div>
          </div>
          <div class="ambient-kpis">
            <div class="kpi-item" id="kpi-temp-box">
              <span class="kpi-label">Ambient Temp</span>
              <div class="kpi-val"><span id="amb-temp">--</span>°F <span class="kpi-delta" id="delta-temp">--</span></div>
            </div>
            <div class="kpi-item" id="kpi-rh-box">
              <span class="kpi-label">Ambient Humidity</span>
              <div class="kpi-val"><span id="amb-rh">--</span>% <span class="kpi-delta" id="delta-rh">--</span></div>
            </div>
            <div class="kpi-item" id="kpi-vpd-box">
              <span class="kpi-label">Ambient VPD</span>
              <div class="kpi-val"><span id="amb-vpd">--</span> kPa</div>
            </div>
          </div>
        </div>

        <!-- Schedules Grid -->
        <div class="schedules-grid" id="schedules-grid">
          <!-- dynamically populated -->
        </div>
      </div>
    `;

    this._updateStates();
  }

  _updateStates() {
    if (!this._hass || !this.shadowRoot) return;
    const root = this.shadowRoot;

    // Ambient & Lung Room
    const amb = this._config.ambient || {};
    const tent = this._config.tent || {};
    const ambBox = root.getElementById("ambient-box");

    const ambTempNum = getStateNum(this._hass, amb.temperature, null);
    const ambRhNum = getStateNum(this._hass, amb.humidity, null);
    const ambVpdNum = getStateNum(this._hass, amb.vpd, null);
    const tentTempNum = getStateNum(this._hass, tent.temperature, null);
    const tentRhNum = getStateNum(this._hass, tent.humidity, null);

    if (ambBox && (ambTempNum !== null || ambRhNum !== null || ambVpdNum !== null)) {
      ambBox.style.display = "flex";
      const elTemp = root.getElementById("amb-temp");
      const elRh = root.getElementById("amb-rh");
      const elVpd = root.getElementById("amb-vpd");
      const elDTemp = root.getElementById("delta-temp");
      const elDRh = root.getElementById("delta-rh");

      if (elTemp && ambTempNum !== null) elTemp.textContent = ambTempNum.toFixed(1);
      if (elRh && ambRhNum !== null) elRh.textContent = Math.round(ambRhNum);
      if (elVpd && ambVpdNum !== null) elVpd.textContent = ambVpdNum.toFixed(2);

      if (elDTemp && ambTempNum !== null && tentTempNum !== null) {
        const d = tentTempNum - ambTempNum;
        elDTemp.textContent = `${d >= 0 ? "+" : ""}${d.toFixed(1)}°F ΔT`;
        elDTemp.className = `kpi-delta ${Math.abs(d) < 3 ? "zero" : d > 0 ? "pos" : "neg"}`;
      } else if (elDTemp) {
        elDTemp.style.display = "none";
      }

      if (elDRh && ambRhNum !== null && tentRhNum !== null) {
        const d = Math.round(tentRhNum - ambRhNum);
        elDRh.textContent = `${d >= 0 ? "+" : ""}${d}% ΔRH`;
        elDRh.className = `kpi-delta ${Math.abs(d) < 8 ? "zero" : d > 0 ? "pos" : "neg"}`;
      } else if (elDRh) {
        elDRh.style.display = "none";
      }
    }

    // Schedules Grid
    const schedGrid = root.getElementById("schedules-grid");
    if (!schedGrid) return;

    const scheds = this._config.schedules || [];
    if (scheds.length === 0) {
      schedGrid.innerHTML = `
        <div style="grid-column: 1 / -1; padding: 18px; text-align: center; color: #8b949e; font-size: 13px;">
          No controller schedules mapped for this space.
        </div>
      `;
      return;
    }

    schedGrid.innerHTML = scheds
      .map((item, idx) => {
        const stateObj = getState(this._hass, item.entity);
        const stateStr = stateObj ? stateObj.state : "Standby";

        let pillClass = "sched-pill";
        let pillText = "STANDBY";
        const sLower = stateStr.toLowerCase();

        if (sLower.includes("until off") || sLower.includes("on")) {
          pillClass = "sched-pill active";
          pillText = "RUNNING";
        } else if (sLower.includes("cycle") || sLower.includes("on /")) {
          pillClass = "sched-pill cycle";
          pillText = "CYCLE";
        } else if (sLower.includes("auto")) {
          pillClass = "sched-pill auto";
          pillText = "SMART AUTO";
        } else if (sLower.includes("cooling") || sLower.includes("heating")) {
          pillClass = "sched-pill active";
          pillText = stateStr.toUpperCase();
        }

        // Icon resolution
        let iconEmoji = "⚙️";
        const role = (item.role || "").toLowerCase();
        const name = (item.name || "").toLowerCase();
        if (role.includes("light") || name.includes("light")) iconEmoji = "💡";
        else if (role.includes("duct") || name.includes("duct") || name.includes("exhaust")) iconEmoji = "🌀";
        else if (role.includes("fan") || name.includes("fan") || name.includes("circulat")) iconEmoji = "💨";
        else if (role.includes("humid") || name.includes("humid")) iconEmoji = "💧";
        else if (role.includes("dehumid") || name.includes("dehumid")) iconEmoji = "🏜️";
        else if (role.includes("air_cond") || name.includes("ac") || name.includes("cool")) iconEmoji = "❄️";
        else if (role.includes("heat") || name.includes("heat")) iconEmoji = "🔥";
        else if (role.includes("irrigat") || name.includes("drip") || name.includes("water")) iconEmoji = "🧪";

        return `
          <div class="schedule-card" data-idx="${idx}">
            <div class="sched-icon-box">${iconEmoji}</div>
            <div class="sched-details">
              <div class="sched-title-row">
                <span class="sched-name" title="${item.name}">${item.name}</span>
                <span class="${pillClass}">${pillText}</span>
              </div>
              <span class="sched-state-text" title="${stateStr}">${stateStr}</span>
            </div>
          </div>
        `;
      })
      .join("");

    schedGrid.querySelectorAll(".schedule-card").forEach((el) => {
      const idx = parseInt(el.getAttribute("data-idx"), 10);
      const item = scheds[idx];
      if (item && item.entity) {
        el.onclick = () => this._moreInfo(item.entity);
      }
    });
  }
}

// ============================================================================
// 5. TENDRILGROW CULTIVATION PLAN & TASKS CARD (<tendrilgrow-plan-card>)
// ============================================================================
class TendrilGrowPlanCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._config = {};
    this._hass = null;
    this._activeTab = "tasks"; // 'tasks' | 'settings'
  }

  static getStubConfig() {
    return {
      title: "Cultivation Plan & Tasks",
    };
  }

  setConfig(config) {
    if (!config) throw new Error("Invalid configuration");
    this._config = {
      title: config.title || "Cultivation Plan & Tasks",
      space_name: config.space_name || "Grow Space",
      stage: config.stage || null,
      stage_started: config.stage_started || null,
      week_in_stage: config.week_in_stage || null,
      stage_projection: config.stage_projection || null,
      strain: config.strain || null,
      water_type: config.water_type || null,
      reservoir_volume: config.reservoir_volume || null,
      flush_now: config.flush_now || null,
      flush_due: config.flush_due || null,
      days_since_flush: config.days_since_flush || null,
      days_until_flush: config.days_until_flush || null,
      next_flush_due: config.next_flush_due || null,
      last_flush: config.last_flush || null,
      flush_interval_days: config.flush_interval_days || null,
      target_ph_low: config.target_ph_low || null,
      target_ph_high: config.target_ph_high || null,
      target_ec_low: config.target_ec_low || null,
      target_ec_high: config.target_ec_high || null,
      target_vpd_low: config.target_vpd_low || null,
      target_vpd_high: config.target_vpd_high || null,
      lights_on_time: config.lights_on_time || null,
      lights_off_time: config.lights_off_time || null,
      lights_on_hours: config.lights_on_hours || null,
      todo: config.todo || null,
      ...config,
    };
    this._render();
  }

  set hass(hass) {
    try {
      this._hass = hass;
      this._updateStates();
    } catch (err) {
      console.error("TendrilGrowPlanCard: Error in set hass:", err);
    }
  }

  getCardSize() {
    return 5;
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

  _render() {
    if (!this.shadowRoot) return;
    const title = this._config.title;

    this.shadowRoot.innerHTML = `
      <style>
        :host {
          display: block;
          font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
          color: #e6edf3;
          --tg-bg: #0b0f17;
          --tg-card-bg: rgba(15, 23, 42, 0.88);
          --tg-border: rgba(255, 255, 255, 0.08);
          --tg-green: #10b981;
          --tg-cyan: #06b6d4;
          --tg-amber: #f59e0b;
          --tg-violet: #8b5cf6;
          max-width: 100%;
          overflow: hidden;
          box-sizing: border-box;
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
          padding: 16px;
          box-shadow: 0 10px 32px rgba(0, 0, 0, 0.5);
          max-width: 100%;
          overflow: hidden;
          box-sizing: border-box;
        }

        /* HEADER */
        .header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          margin-bottom: 14px;
          padding-bottom: 12px;
          border-bottom: 1px solid var(--tg-border);
          flex-wrap: wrap;
          gap: 10px;
        }

        .header-left {
          display: flex;
          align-items: center;
          gap: 12px;
        }

        .brand-badge {
          width: 32px;
          height: 32px;
          border-radius: 8px;
          background: linear-gradient(135deg, #10b981, #059669);
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 16px;
          box-shadow: 0 0 14px rgba(16, 185, 129, 0.35);
        }

        .header h2 {
          font-size: 16.5px;
          font-weight: 700;
          letter-spacing: -0.3px;
          color: #f0f6fc;
        }

        .subtitle {
          font-size: 11.5px;
          color: #8b949e;
          font-weight: 500;
        }

        .stage-tag {
          font-size: 10.5px;
          font-weight: 700;
          text-transform: uppercase;
          letter-spacing: 0.5px;
          color: #34d399;
          background: rgba(16, 185, 129, 0.12);
          padding: 3px 9px;
          border-radius: 12px;
          border: 1px solid rgba(16, 185, 129, 0.3);
        }

        /* TAB SELECTOR */
        .plan-tabs {
          display: flex;
          gap: 6px;
          margin-bottom: 16px;
          background: rgba(13, 17, 23, 0.75);
          padding: 4px;
          border-radius: 10px;
          border: 1px solid var(--tg-border);
        }

        .plan-tab-btn {
          flex: 1;
          background: transparent;
          border: none;
          color: #8b949e;
          font-size: 12px;
          font-weight: 600;
          padding: 8px 12px;
          border-radius: 8px;
          cursor: pointer;
          transition: all 0.2s ease;
          display: flex;
          align-items: center;
          justify-content: center;
          gap: 6px;
        }

        .plan-tab-btn.active {
          background: rgba(16, 185, 129, 0.16);
          color: #34d399;
          font-weight: 700;
          border: 1px solid rgba(16, 185, 129, 0.3);
        }

        .plan-pane {
          display: none;
        }

        .plan-pane.active {
          display: block;
        }

        /* STAGE PROGRESS SECTION */
        .progress-section {
          background: rgba(13, 17, 23, 0.85);
          border: 1px solid var(--tg-border);
          border-radius: 14px;
          padding: 14px 16px;
          margin-bottom: 16px;
        }

        .progress-header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          margin-bottom: 8px;
        }

        .progress-title {
          font-size: 12px;
          font-weight: 700;
          color: #e6edf3;
        }

        .progress-pct {
          font-size: 13px;
          font-weight: 800;
          color: var(--tg-green);
        }

        .progress-track {
          height: 8px;
          background: #21262d;
          border-radius: 4px;
          overflow: hidden;
          position: relative;
        }

        .progress-fill {
          height: 100%;
          background: linear-gradient(90deg, #10b981, #34d399);
          border-radius: 4px;
          transition: width 0.8s cubic-bezier(0.16, 1, 0.3, 1);
          box-shadow: 0 0 10px rgba(16, 185, 129, 0.5);
        }

        .progress-meta {
          display: flex;
          justify-content: space-between;
          margin-top: 6px;
          font-size: 10.5px;
          color: #8b949e;
          font-weight: 500;
        }

        /* MILESTONES GRID */
        .milestones-grid {
          display: grid;
          grid-template-columns: repeat(3, 1fr);
          gap: 12px;
          margin-bottom: 18px;
        }

        .milestone-card {
          background: rgba(15, 23, 42, 0.7);
          border: 1px solid var(--tg-border);
          border-radius: 12px;
          padding: 12px;
          display: flex;
          align-items: center;
          gap: 10px;
        }

        .milestone-card.highlight {
          border-color: rgba(245, 158, 11, 0.4);
          background: rgba(245, 158, 11, 0.05);
        }

        .ms-icon {
          font-size: 22px;
          flex-shrink: 0;
        }

        .ms-info {
          display: flex;
          flex-direction: column;
          min-width: 0;
        }

        .ms-label {
          font-size: 10.5px;
          color: #8b949e;
          font-weight: 600;
          text-transform: uppercase;
        }

        .ms-val {
          font-size: 12.5px;
          font-weight: 700;
          color: #f0f6fc;
        }

        .ms-sub {
          font-size: 10px;
          color: var(--tg-amber);
          font-weight: 600;
        }

        /* TASKS SECTION */
        .tasks-section {
          background: rgba(13, 17, 23, 0.85);
          border: 1px solid var(--tg-border);
          border-radius: 14px;
          padding: 14px 16px;
        }

        .tasks-header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          margin-bottom: 12px;
        }

        .tasks-header-left {
          display: flex;
          align-items: center;
          gap: 8px;
        }

        .tasks-title {
          font-size: 13px;
          font-weight: 700;
          color: #f0f6fc;
        }

        .tasks-count-badge {
          font-size: 10px;
          font-weight: 700;
          padding: 2px 7px;
          border-radius: 10px;
          background: rgba(6, 182, 212, 0.15);
          color: #38bdf8;
          border: 1px solid rgba(6, 182, 212, 0.3);
        }

        .btn-open-tasks {
          background: rgba(255, 255, 255, 0.06);
          border: 1px solid var(--tg-border);
          color: #cbd5e1;
          font-size: 11px;
          font-weight: 600;
          padding: 4px 10px;
          border-radius: 8px;
          cursor: pointer;
          transition: all 0.2s ease;
        }

        .btn-open-tasks:hover {
          background: rgba(255, 255, 255, 0.12);
          color: #fff;
        }

        .add-task-bar {
          display: flex;
          gap: 8px;
          margin-bottom: 10px;
        }

        .task-input {
          flex: 1;
          background: rgba(15, 23, 42, 0.9);
          border: 1px solid var(--tg-border);
          border-radius: 8px;
          padding: 8px 12px;
          color: #f0f6fc;
          font-size: 12px;
          outline: none;
          transition: border-color 0.2s ease;
        }

        .task-input:focus {
          border-color: var(--tg-green);
        }

        .btn-add-task {
          background: rgba(16, 185, 129, 0.2);
          border: 1px solid rgba(16, 185, 129, 0.4);
          color: #34d399;
          font-weight: 700;
          font-size: 12px;
          padding: 8px 14px;
          border-radius: 8px;
          cursor: pointer;
          transition: all 0.2s ease;
        }

        .btn-add-task:hover {
          background: rgba(16, 185, 129, 0.3);
          color: #fff;
        }

        .tasks-status-box {
          font-size: 12px;
          color: #8b949e;
          padding: 4px 0;
        }

        /* SETTINGS & PARAMETERS TAB */
        .settings-grid {
          display: flex;
          flex-direction: column;
          gap: 14px;
          width: 100%;
          max-width: 100%;
          box-sizing: border-box;
        }

        .setting-card {
          background: rgba(15, 23, 42, 0.7);
          border: 1px solid var(--tg-border);
          border-radius: 14px;
          padding: 14px 16px;
          display: flex;
          flex-direction: column;
          gap: 10px;
          width: 100%;
          max-width: 100%;
          box-sizing: border-box;
          overflow: hidden;
        }

        .setting-card-title {
          font-size: 11.5px;
          font-weight: 700;
          text-transform: uppercase;
          letter-spacing: 0.5px;
          color: #94a3b8;
          display: flex;
          align-items: center;
          gap: 6px;
        }

        .setting-row {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 12px;
          padding: 4px 0;
          min-width: 0;
          width: 100%;
          box-sizing: border-box;
        }

        .setting-row > div:first-child {
          min-width: 0;
          flex: 1 1 auto;
        }

        .setting-label {
          font-size: 12.5px;
          font-weight: 600;
          color: #e6edf3;
          line-height: 1.3;
        }

        .setting-sublabel {
          font-size: 10.5px;
          color: #64748b;
          margin-top: 1px;
        }

        .setting-select, .setting-input-date {
          background: rgba(13, 17, 23, 0.9);
          border: 1px solid rgba(255, 255, 255, 0.12);
          border-radius: 8px;
          color: #f0f6fc;
          font-size: 12px;
          padding: 6px 10px;
          outline: none;
          font-family: inherit;
          max-width: 170px;
          flex-shrink: 0;
        }

        .setting-select:focus, .setting-input-date:focus {
          border-color: var(--tg-green);
        }

        .setting-pill {
          font-size: 11.5px;
          font-weight: 600;
          color: #38bdf8;
          background: rgba(6, 182, 212, 0.12);
          padding: 3px 8px;
          border-radius: 6px;
          border: 1px solid rgba(6, 182, 212, 0.25);
          flex-shrink: 0;
        }

        .stepper-ctrl {
          display: inline-flex;
          align-items: center;
          gap: 2px;
          background: rgba(13, 17, 23, 0.75);
          border: 1px solid var(--tg-border);
          border-radius: 8px;
          padding: 2px 4px;
          flex-shrink: 0;
        }

        .stepper-btn {
          width: 22px;
          height: 22px;
          background: rgba(255, 255, 255, 0.06);
          border: 1px solid var(--tg-border);
          border-radius: 5px;
          color: #f0f6fc;
          font-size: 13px;
          font-weight: 700;
          cursor: pointer;
          display: flex;
          align-items: center;
          justify-content: center;
          transition: background 0.15s;
          padding: 0;
          user-select: none;
        }

        .stepper-btn:hover {
          background: rgba(16, 185, 129, 0.25);
          color: #34d399;
          border-color: rgba(16, 185, 129, 0.4);
        }

        .stepper-val {
          font-size: 12px;
          font-weight: 700;
          color: #f0f6fc;
          min-width: 28px;
          text-align: center;
          font-variant-numeric: tabular-nums;
        }

        .range-stepper-row {
          display: flex;
          align-items: center;
          gap: 4px;
          flex-shrink: 0;
        }

        /* FLUSH HERO BOX */
        .flush-hero-card {
          background: linear-gradient(135deg, rgba(6, 182, 212, 0.12), rgba(16, 185, 129, 0.08));
          border: 1px solid rgba(6, 182, 212, 0.35);
          border-radius: 14px;
          padding: 14px 16px;
          display: flex;
          flex-direction: column;
          gap: 12px;
          width: 100%;
          max-width: 100%;
          box-sizing: border-box;
          overflow: hidden;
        }

        .flush-top-row {
          display: flex;
          align-items: center;
          justify-content: space-between;
          flex-wrap: wrap;
          gap: 10px;
        }

        .btn-log-flush {
          background: linear-gradient(135deg, #06b6d4, #10b981);
          border: none;
          border-radius: 10px;
          color: #0b0f17;
          font-size: 12px;
          font-weight: 800;
          padding: 8px 14px;
          cursor: pointer;
          box-shadow: 0 4px 16px rgba(6, 182, 212, 0.35);
          transition: all 0.2s ease;
          display: flex;
          align-items: center;
          justify-content: center;
          gap: 6px;
          white-space: nowrap;
        }

        .btn-log-flush:hover {
          transform: translateY(-1px);
          box-shadow: 0 6px 20px rgba(16, 185, 129, 0.5);
        }

        .flush-stats-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(105px, 1fr));
          gap: 8px;
          width: 100%;
          box-sizing: border-box;
        }

        .flush-stat-box {
          background: rgba(13, 17, 23, 0.8);
          border: 1px solid var(--tg-border);
          border-radius: 10px;
          padding: 8px 10px;
          display: flex;
          flex-direction: column;
          min-width: 0;
          overflow: hidden;
          box-sizing: border-box;
        }

        .flush-stat-label {
          font-size: 10px;
          color: #94a3b8;
          text-transform: uppercase;
          font-weight: 600;
        }

        .flush-stat-val {
          font-size: 13px;
          font-weight: 700;
          color: #f0f6fc;
          margin-top: 2px;
        }
      </style>

      <div class="container">
        <!-- Card Header -->
        <div class="header">
          <div class="header-left">
            <div class="brand-badge">🌱</div>
            <div>
              <h2>${title}</h2>
              <div class="subtitle" id="plan-stage-text">Cultivation Pipeline & Stage Milestones</div>
            </div>
          </div>
          <div class="stage-tag" id="plan-stage-badge">VEGETATIVE • WK 2</div>
        </div>

        <!-- Tab Bar -->
        <div class="plan-tabs">
          <button class="plan-tab-btn active" id="tab-btn-tasks">📋 Tasks &amp; Milestones</button>
          <button class="plan-tab-btn" id="tab-btn-settings">⚙️ Parameters &amp; Reservoir Routine</button>
        </div>

        <!-- PANE 1: TASKS & MILESTONES -->
        <div class="plan-pane active" id="pane-tasks">
          <!-- Stage Progress Section -->
          <div class="progress-section">
            <div class="progress-header">
              <span class="progress-title" id="progress-title-text">Stage Timeline Progress</span>
              <span class="progress-pct" id="progress-pct-text">--%</span>
            </div>
            <div class="progress-track">
              <div class="progress-fill" id="progress-bar-fill" style="width: 0%;"></div>
            </div>
            <div class="progress-meta">
              <span id="progress-meta-text">Day -- of --</span>
              <span id="progress-week-text">Week --</span>
            </div>
          </div>

          <!-- Milestones Grid -->
          <div class="milestones-grid">
            <div class="milestone-card">
              <div class="ms-icon">🔄</div>
              <div class="ms-info">
                <span class="ms-label">Stage Flip / End</span>
                <span class="ms-val" id="ms-flip-date">--</span>
                <span class="ms-sub" id="ms-flip-countdown">--</span>
              </div>
            </div>
            <div class="milestone-card highlight">
              <div class="ms-icon">✂️</div>
              <div class="ms-info">
                <span class="ms-label">Projected Harvest</span>
                <span class="ms-val" id="ms-harvest-date">--</span>
                <span class="ms-sub" id="ms-harvest-countdown">--</span>
              </div>
            </div>
            <div class="milestone-card">
              <div class="ms-icon">🏺</div>
              <div class="ms-info">
                <span class="ms-label">Cured & Ready</span>
                <span class="ms-val" id="ms-ready-date">--</span>
                <span class="ms-sub" id="ms-ready-countdown">Final Cure</span>
              </div>
            </div>
          </div>

          <!-- Tasks Section -->
          <div class="tasks-section">
            <div class="tasks-header">
              <div class="tasks-header-left">
                <span>📋</span>
                <span class="tasks-title">Stage Tasks & Grow Routines</span>
                <span class="tasks-count-badge" id="tasks-count-badge">0 Pending</span>
              </div>
              <button class="btn-open-tasks" id="btn-open-tasks">Manage Tasks ↗</button>
            </div>

            <!-- Quick Add Task Bar -->
            <div class="add-task-bar">
              <input type="text" class="task-input" id="task-input" placeholder="Add cultivation task... (e.g. LST tucking, top canopy, check root zone)" />
              <button class="btn-add-task" id="btn-add-task">＋ Add</button>
            </div>

            <div class="tasks-status-box" id="tasks-status-box">
              <span id="tasks-empty-msg">Tap 'Manage Tasks' to view and check off items in Home Assistant.</span>
            </div>
          </div>
        </div>

        <!-- PANE 2: PARAMETERS & RESERVOIR ROUTINE -->
        <div class="plan-pane" id="pane-settings">
          <div class="settings-grid">
            <!-- Flush & Fill Routine Hero Card -->
            <div class="flush-hero-card">
              <div class="flush-top-row">
                <div>
                  <div style="font-size:14px;font-weight:800;color:#f0f6fc;">🌊 Reservoir Routine &amp; Flush</div>
                  <div style="font-size:11px;color:#94a3b8;margin-top:2px;">Reset salt balance and record complete water changes</div>
                </div>
                <button class="btn-log-flush" id="btn-log-flush">🌊 Log Flush &amp; Fill Completed</button>
              </div>
              <div class="flush-stats-grid">
                <div class="flush-stat-box">
                  <span class="flush-stat-label">Last Flush</span>
                  <span class="flush-stat-val" id="flush-days-since-val">--</span>
                </div>
                <div class="flush-stat-box">
                  <span class="flush-stat-label">Next Flush Due</span>
                  <span class="flush-stat-val" id="flush-next-due-val">--</span>
                </div>
                <div class="flush-stat-box">
                  <span class="flush-stat-label">Flush Interval</span>
                  <div class="stepper-ctrl" style="margin-top:4px;width:100%;box-sizing:border-box;justify-content:space-between;">
                    <button class="stepper-btn" id="btn-flush-int-dec">-</button>
                    <span class="stepper-val" id="flush-interval-val">7</span>
                    <span style="font-size:11px;color:#94a3b8;padding-right:2px;">days</span>
                    <button class="stepper-btn" id="btn-flush-int-inc">+</button>
                  </div>
                </div>
              </div>
            </div>

            <!-- Stage & Timeline Controls -->
            <div class="setting-card">
              <div class="setting-card-title">🌱 Lifecycle Stage &amp; Origin</div>
              <div class="setting-row">
                <div>
                  <div class="setting-label">Current Growth Stage</div>
                  <div class="setting-sublabel">Select active phenological stage</div>
                </div>
                <select class="setting-select" id="setting-stage-select">
                  <option value="seedling">Seedling</option>
                  <option value="vegetative">Vegetative</option>
                  <option value="early_bloom">Early Bloom</option>
                  <option value="mid_bloom">Mid Bloom</option>
                  <option value="late_bloom">Late Bloom</option>
                  <option value="flush">Ripening / Flush</option>
                  <option value="harvested">Harvested</option>
                  <option value="curing">Curing</option>
                </select>
              </div>
              <div class="setting-row">
                <div>
                  <div class="setting-label">Stage Started Date</div>
                  <div class="setting-sublabel">Calculates days in current cycle</div>
                </div>
                <input type="date" class="setting-input-date" id="setting-stage-date" />
              </div>
              <div class="setting-row">
                <div>
                  <div class="setting-label">Strain Cultivar</div>
                  <div class="setting-sublabel">Target genetic profile</div>
                </div>
                <span class="setting-pill" id="setting-strain-pill">--</span>
              </div>
            </div>

            <!-- Target Ranges & Reservoir Volume -->
            <div class="setting-card">
              <div class="setting-card-title">🎯 Sweet-Spot Target Corridors</div>
              <div class="setting-row">
                <div>
                  <div class="setting-label">Target pH Range</div>
                  <div class="setting-sublabel">Low / High limits</div>
                </div>
                <div class="range-stepper-row">
                  <div class="stepper-ctrl">
                    <button class="stepper-btn" id="btn-ph-low-dec">-</button>
                    <span class="stepper-val" id="val-ph-low">5.5</span>
                    <button class="stepper-btn" id="btn-ph-low-inc">+</button>
                  </div>
                  <span style="color:#64748b;font-size:11px;">–</span>
                  <div class="stepper-ctrl">
                    <button class="stepper-btn" id="btn-ph-high-dec">-</button>
                    <span class="stepper-val" id="val-ph-high">6.2</span>
                    <button class="stepper-btn" id="btn-ph-high-inc">+</button>
                  </div>
                </div>
              </div>
              <div class="setting-row">
                <div>
                  <div class="setting-label">Target EC Range</div>
                  <div class="setting-sublabel">mS/cm corridor</div>
                </div>
                <div class="range-stepper-row">
                  <div class="stepper-ctrl">
                    <button class="stepper-btn" id="btn-ec-low-dec">-</button>
                    <span class="stepper-val" id="val-ec-low">1.2</span>
                    <button class="stepper-btn" id="btn-ec-low-inc">+</button>
                  </div>
                  <span style="color:#64748b;font-size:11px;">–</span>
                  <div class="stepper-ctrl">
                    <button class="stepper-btn" id="btn-ec-high-dec">-</button>
                    <span class="stepper-val" id="val-ec-high">1.8</span>
                    <button class="stepper-btn" id="btn-ec-high-inc">+</button>
                  </div>
                </div>
              </div>
              <div class="setting-row">
                <div>
                  <div class="setting-label">Target VPD Range</div>
                  <div class="setting-sublabel">kPa corridor</div>
                </div>
                <div class="range-stepper-row">
                  <div class="stepper-ctrl">
                    <button class="stepper-btn" id="btn-vpd-low-dec">-</button>
                    <span class="stepper-val" id="val-vpd-low">0.8</span>
                    <button class="stepper-btn" id="btn-vpd-low-inc">+</button>
                  </div>
                  <span style="color:#64748b;font-size:11px;">–</span>
                  <div class="stepper-ctrl">
                    <button class="stepper-btn" id="btn-vpd-high-dec">-</button>
                    <span class="stepper-val" id="val-vpd-high">1.2</span>
                    <button class="stepper-btn" id="btn-vpd-high-inc">+</button>
                  </div>
                </div>
              </div>
              <div class="setting-row">
                <div>
                  <div class="setting-label">System Water Volume</div>
                  <div class="setting-sublabel">Circulating capacity</div>
                </div>
                <div class="stepper-ctrl">
                  <button class="stepper-btn" id="btn-vol-dec">-</button>
                  <span class="stepper-val" id="val-res-vol">15</span>
                  <span style="font-size:11px;color:#94a3b8;padding-right:4px;">gal</span>
                  <button class="stepper-btn" id="btn-vol-inc">+</button>
                </div>
              </div>
            </div>
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

    // Tabs
    const tabTasks = root.getElementById("tab-btn-tasks");
    const tabSettings = root.getElementById("tab-btn-settings");
    const paneTasks = root.getElementById("pane-tasks");
    const paneSettings = root.getElementById("pane-settings");

    if (tabTasks && tabSettings) {
      tabTasks.onclick = () => {
        tabTasks.classList.add("active");
        tabSettings.classList.remove("active");
        if (paneTasks) paneTasks.classList.add("active");
        if (paneSettings) paneSettings.classList.remove("active");
      };
      tabSettings.onclick = () => {
        tabSettings.classList.add("active");
        tabTasks.classList.remove("active");
        if (paneSettings) paneSettings.classList.add("active");
        if (paneTasks) paneTasks.classList.remove("active");
      };
    }

    // Open HA Todo list
    const btnOpen = root.getElementById("btn-open-tasks");
    if (btnOpen && this._config.todo) {
      btnOpen.onclick = () => this._moreInfo(this._config.todo);
    }

    // Quick add task
    const btnAdd = root.getElementById("btn-add-task");
    const input = root.getElementById("task-input");
    if (btnAdd && input) {
      const submitTask = () => {
        const val = input.value.trim();
        if (!val || !this._config.todo) return;
        this._callService("todo", "add_item", {
          entity_id: this._config.todo,
          item: val,
        });
        input.value = "";
      };
      btnAdd.onclick = submitTask;
      input.onkeydown = (e) => {
        if (e.key === "Enter") submitTask();
      };
    }

    // Stage Selector
    const stageSelect = root.getElementById("setting-stage-select");
    if (stageSelect && this._config.stage) {
      stageSelect.onchange = (e) => {
        this._callService("select", "select_option", {
          entity_id: this._config.stage,
          option: e.target.value,
        });
      };
    }

    // Stage Date Picker
    const stageDate = root.getElementById("setting-stage-date");
    if (stageDate && this._config.stage_started) {
      stageDate.onchange = (e) => {
        this._callService("date", "set_value", {
          entity_id: this._config.stage_started,
          date: e.target.value,
        });
      };
    }

    // Log Flush Button
    const btnFlush = root.getElementById("btn-log-flush");
    if (btnFlush) {
      btnFlush.onclick = () => {
        if (this._config.flush_now) {
          this._callService("button", "press", { entity_id: this._config.flush_now });
        } else {
          this._callService("tendrilgrow", "mark_flush", {});
        }
        btnFlush.textContent = "✅ Flush Recorded!";
        setTimeout(() => {
          btnFlush.innerHTML = "🌊 Log Flush &amp; Fill Completed";
        }, 3500);
      };
    }

    // Steppers helper
    const setupStepper = (decId, incId, entityId, delta, minVal, maxVal, stepPrecision = 1) => {
      const btnDec = root.getElementById(decId);
      const btnInc = root.getElementById(incId);
      if (!btnDec || !btnInc) return;

      const change = (dir) => {
        if (!this._hass || !entityId) return;
        const curr = getStateNum(this._hass, entityId, null);
        if (curr === null) return;
        let nextVal = curr + dir * delta;
        if (minVal !== undefined) nextVal = Math.max(minVal, nextVal);
        if (maxVal !== undefined) nextVal = Math.min(maxVal, nextVal);
        nextVal = Math.round(nextVal * Math.pow(10, stepPrecision)) / Math.pow(10, stepPrecision);
        this._callService("number", "set_value", { entity_id: entityId, value: nextVal });
      };

      btnDec.onclick = () => change(-1);
      btnInc.onclick = () => change(1);
    };

    setupStepper("btn-flush-int-dec", "btn-flush-int-inc", this._config.flush_interval_days, 1, 1, 60, 0);
    setupStepper("btn-ph-low-dec", "btn-ph-low-inc", this._config.target_ph_low, 0.1, 4.0, 7.5, 1);
    setupStepper("btn-ph-high-dec", "btn-ph-high-inc", this._config.target_ph_high, 0.1, 4.5, 8.0, 1);
    setupStepper("btn-ec-low-dec", "btn-ec-low-inc", this._config.target_ec_low, 0.1, 0.1, 4.0, 1);
    setupStepper("btn-ec-high-dec", "btn-ec-high-inc", this._config.target_ec_high, 0.1, 0.2, 5.0, 1);
    setupStepper("btn-vpd-low-dec", "btn-vpd-low-inc", this._config.target_vpd_low, 0.05, 0.2, 2.5, 2);
    setupStepper("btn-vpd-high-dec", "btn-vpd-high-inc", this._config.target_vpd_high, 0.05, 0.4, 3.0, 2);
    setupStepper("btn-vol-dec", "btn-vol-inc", this._config.reservoir_volume, 1, 1, 500, 0);
  }

  _formatDate(dateStr) {
    if (!dateStr) return "--";
    try {
      const d = new Date(dateStr);
      if (isNaN(d.getTime())) return dateStr;
      return d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
    } catch {
      return dateStr;
    }
  }

  _getDaysRemaining(dateStr) {
    if (!dateStr) return "";
    try {
      const d = new Date(dateStr);
      if (isNaN(d.getTime())) return "";
      const now = new Date();
      const diff = Math.ceil((d.getTime() - now.getTime()) / (1000 * 60 * 60 * 24));
      if (diff < 0) return "Passed";
      if (diff === 0) return "Today";
      return `in ${diff} days`;
    } catch {
      return "";
    }
  }

  _updateStates() {
    if (!this._hass || !this.shadowRoot) return;
    const root = this.shadowRoot;

    // Stage Projection
    const projState = getState(this._hass, this._config.stage_projection);
    const stageStr = getStateStr(this._hass, this._config.stage, "Vegetative");
    const attrs = projState ? projState.attributes || {} : {};

    const daysInStage = attrs.days_in_stage || 10;
    const weeksInStage = attrs.weeks_in_stage || 1.4;
    const projEnd = attrs.projected_stage_end || "";
    const projHarvest = attrs.projected_harvest_date || "";
    const projReady = attrs.projected_ready_date || "";

    const daysLeftInStage = projEnd ? Math.max(0, Math.ceil((new Date(projEnd) - new Date()) / (1000 * 60 * 60 * 24))) : 18;
    const totalDays = Math.max(daysInStage + daysLeftInStage, 28);
    const pct = Math.min(100, Math.round((daysInStage / totalDays) * 100));

    // Update Header
    const stageBadge = root.getElementById("plan-stage-badge");
    if (stageBadge) {
      stageBadge.textContent = `${stageStr.toUpperCase()} • WK ${Math.round(weeksInStage * 10) / 10}`;
    }

    // Update Progress
    const barFill = root.getElementById("progress-bar-fill");
    const pctText = root.getElementById("progress-pct-text");
    const metaText = root.getElementById("progress-meta-text");
    const weekText = root.getElementById("progress-week-text");

    if (barFill) barFill.style.width = `${pct}%`;
    if (pctText) pctText.textContent = `${pct}%`;
    if (metaText) metaText.textContent = `Day ${daysInStage} of ~${totalDays}`;
    if (weekText) weekText.textContent = `Week ${weeksInStage}`;

    // Milestones
    const flipDate = root.getElementById("ms-flip-date");
    const flipSub = root.getElementById("ms-flip-countdown");
    const harvDate = root.getElementById("ms-harvest-date");
    const harvSub = root.getElementById("ms-harvest-countdown");
    const readyDate = root.getElementById("ms-ready-date");

    if (flipDate) flipDate.textContent = this._formatDate(projEnd);
    if (flipSub) flipSub.textContent = this._getDaysRemaining(projEnd);
    if (harvDate) harvDate.textContent = this._formatDate(projHarvest);
    if (harvSub) harvSub.textContent = this._getDaysRemaining(projHarvest);
    if (readyDate) readyDate.textContent = this._formatDate(projReady);

    // Todo task count
    const todoState = getState(this._hass, this._config.todo);
    const countBadge = root.getElementById("tasks-count-badge");
    const emptyMsg = root.getElementById("tasks-empty-msg");

    if (todoState) {
      const count = parseInt(todoState.state, 10);
      const num = isNaN(count) ? 0 : count;
      if (countBadge) countBadge.textContent = `${num} Pending`;
      if (emptyMsg) {
        emptyMsg.textContent = num === 0
          ? "All scheduled cultivation tasks completed for current stage ✨"
          : `${num} task(s) queued for this space. Tap 'Manage Tasks' to view.`;
      }
    }

    // Settings Tab Updates
    const stageSelect = root.getElementById("setting-stage-select");
    if (stageSelect && this._config.stage) {
      const curStage = getStateStr(this._hass, this._config.stage, "").toLowerCase();
      for (let i = 0; i < stageSelect.options.length; i++) {
        if (stageSelect.options[i].value === curStage || stageSelect.options[i].text.toLowerCase() === curStage) {
          stageSelect.selectedIndex = i;
          break;
        }
      }
    }

    const stageDate = root.getElementById("setting-stage-date");
    if (stageDate && this._config.stage_started) {
      const curDate = getStateStr(this._hass, this._config.stage_started, "");
      if (curDate && curDate !== "--") stageDate.value = curDate;
    }

    const strainPill = root.getElementById("setting-strain-pill");
    if (strainPill) {
      const strainStr = getStateStr(this._hass, this._config.strain, "Custom Cultivar");
      strainPill.textContent = strainStr;
    }

    // Flush Stats
    const daysSinceVal = root.getElementById("flush-days-since-val");
    if (daysSinceVal) {
      const daysSince = getStateStr(this._hass, this._config.days_since_flush, "--");
      daysSinceVal.textContent = daysSince !== "--" ? `${daysSince} days ago` : "--";
    }

    const nextDueVal = root.getElementById("flush-next-due-val");
    if (nextDueVal) {
      const nextDue = getStateStr(this._hass, this._config.next_flush_due, "");
      const daysUntil = getStateStr(this._hass, this._config.days_until_flush, "");
      if (daysUntil !== "" && daysUntil !== "--") {
        nextDueVal.textContent = `in ${daysUntil} days`;
      } else if (nextDue) {
        nextDueVal.textContent = this._formatDate(nextDue);
      } else {
        nextDueVal.textContent = "--";
      }
    }

    const flushIntVal = root.getElementById("flush-interval-val");
    if (flushIntVal) {
      const flushInt = getStateNum(this._hass, this._config.flush_interval_days, 7);
      flushIntVal.textContent = flushInt;
    }

    // Target corridors
    const setElemNum = (id, entityId, fallback, precision = 1) => {
      const elem = root.getElementById(id);
      if (!elem) return;
      const val = getStateNum(this._hass, entityId, fallback);
      elem.textContent = val !== null ? val.toFixed(precision) : "--";
    };

    setElemNum("val-ph-low", this._config.target_ph_low, 5.5, 1);
    setElemNum("val-ph-high", this._config.target_ph_high, 6.2, 1);
    setElemNum("val-ec-low", this._config.target_ec_low, 1.2, 1);
    setElemNum("val-ec-high", this._config.target_ec_high, 1.8, 1);
    setElemNum("val-vpd-low", this._config.target_vpd_low, 0.8, 2);
    setElemNum("val-vpd-high", this._config.target_vpd_high, 1.2, 2);
    setElemNum("val-res-vol", this._config.reservoir_volume, 15, 0);
  }
}

// ============================================================================
// 6. TENDRILGROW AI CULTIVATION INTELLIGENCE CARD (<tendrilgrow-advisor-card>)
// ============================================================================
function formatChatMarkdown(txt) {
  if (!txt) return "";
  let out = escapeHtml(txt);
  out = out.replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>");
  out = out.replace(/\*(.*?)\*/g, "<em>$1</em>");
  out = out.replace(/`([^`]+)`/g, "<code style=\"background:rgba(255,255,255,0.08);padding:1px 5px;border-radius:4px;color:#67e8f9;font-family:monospace;font-size:11px;\">$1</code>");
  out = out.replace(/^\s*[\-\*]\s+(.*)$/gm, "<div style=\"display:flex;gap:6px;margin:2px 0;\"><span style=\"color:#8b5cf6;\">•</span><span>$1</span></div>");
  out = out.replace(/\n\n/g, "<br><br>");
  out = out.replace(/\n/g, "<br>");
  return out;
}

// ============================================================================
// 6. TENDRILGROW AI CULTIVATION INTELLIGENCE CARD (<tendrilgrow-advisor-card>)
// ============================================================================
class TendrilGrowAdvisorCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._config = {};
    this._hass = null;
    this._activeTab = "diag"; // 'diag' | 'rec' | 'feed' | 'chat'
    this._chatMessages = null;
    this._isChatLoading = false;
  }

  static getStubConfig() {
    return {
      title: "AI Cultivation Intelligence",
      score: "sensor.ai_health_summary",
    };
  }

  setConfig(config) {
    if (!config) throw new Error("Invalid configuration");
    this._config = {
      title: config.title || "AI Cultivation Intelligence",
      space_name: config.space_name || "Cultivation Space",
      space_slug: config.space_slug || "",
      score: config.score || null,
      summary: config.summary || null,
      critical_alert: config.critical_alert || null,
      run_ai_health_check: config.run_ai_health_check || null,
      ...config,
    };

    if (!this._chatMessages) {
      const spaceTitle = this._config.space_name || "this grow space";
      this._chatMessages = [
        {
          role: "assistant",
          text: `🌱 **Greetings!** I am your dedicated AI Agronomist for the **${spaceTitle}**.\n\nI continuously monitor this tent's telemetry (pH, EC, water temperature, canopy VPD) against your cultivation targets. How can I help dial in this grow today?`,
          time: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
        },
      ];
    }

    this._render();
  }

  set hass(hass) {
    try {
      this._hass = hass;
      this._updateStates();
    } catch (err) {
      console.error("TendrilGrowAdvisorCard: Error in set hass:", err);
    }
  }

  getCardSize() {
    return 6;
  }

  _callService(domain, service, data = {}) {
    if (!this._hass) return;
    this._hass.callService(domain, service, data);
  }

  _render() {
    if (!this.shadowRoot) return;
    const title = this._config.title || "AI Cultivation Intelligence";

    this.shadowRoot.innerHTML = `
      <style>
        :host {
          display: block;
          font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
          color: #e6edf3;
          --tg-bg: #0b0f17;
          --tg-card-bg: rgba(15, 23, 42, 0.88);
          --tg-border: rgba(255, 255, 255, 0.08);
          --tg-green: #10b981;
          --tg-cyan: #06b6d4;
          --tg-amber: #f59e0b;
          --tg-violet: #8b5cf6;
          --tg-red: #ef4444;
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
          box-shadow: 0 10px 32px rgba(0, 0, 0, 0.5);
        }

        /* HEADER */
        .header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          margin-bottom: 16px;
          padding-bottom: 12px;
          border-bottom: 1px solid var(--tg-border);
          flex-wrap: wrap;
          gap: 10px;
        }

        .header-left {
          display: flex;
          align-items: center;
          gap: 12px;
        }

        .brand-badge {
          width: 34px;
          height: 34px;
          border-radius: 9px;
          background: linear-gradient(135deg, #8b5cf6, #6d28d9);
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 17px;
          box-shadow: 0 0 14px rgba(139, 92, 246, 0.35);
        }

        .header h2 {
          font-size: 16.5px;
          font-weight: 700;
          letter-spacing: -0.3px;
          color: #f0f6fc;
        }

        .subtitle {
          font-size: 11.5px;
          color: #8b949e;
          font-weight: 500;
        }

        .btn-run-diag {
          background: linear-gradient(135deg, rgba(139, 92, 246, 0.25), rgba(109, 40, 217, 0.25));
          border: 1px solid rgba(139, 92, 246, 0.4);
          color: #c4b5fd;
          font-size: 11.5px;
          font-weight: 700;
          padding: 6px 14px;
          border-radius: 9px;
          cursor: pointer;
          display: flex;
          align-items: center;
          gap: 6px;
          transition: all 0.2s ease;
        }

        .btn-run-diag:hover {
          background: linear-gradient(135deg, rgba(139, 92, 246, 0.4), rgba(109, 40, 217, 0.4));
          color: #fff;
          box-shadow: 0 0 14px rgba(139, 92, 246, 0.4);
        }

        /* ADVISOR HERO BANNER */
        .advisor-hero {
          display: flex;
          align-items: center;
          gap: 16px;
          background: rgba(13, 17, 23, 0.85);
          border: 1px solid rgba(139, 92, 246, 0.3);
          border-radius: 14px;
          padding: 14px 16px;
          margin-bottom: 16px;
        }

        .score-dial-box {
          position: relative;
          width: 56px;
          height: 56px;
          flex-shrink: 0;
        }

        .score-dial-box svg {
          transform: rotate(-90deg);
        }

        .score-dial-track {
          fill: none;
          stroke: rgba(255, 255, 255, 0.08);
          stroke-width: 4.5;
        }

        .score-dial-progress {
          fill: none;
          stroke: var(--tg-green);
          stroke-width: 4.5;
          stroke-linecap: round;
          transition: stroke-dashoffset 0.8s ease, stroke 0.3s ease;
        }

        .score-dial-val {
          position: absolute;
          inset: 0;
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 16px;
          font-weight: 800;
          color: #fff;
        }

        .hero-info {
          display: flex;
          flex-direction: column;
          gap: 6px;
          min-width: 0;
          flex: 1;
        }

        .hero-top-row {
          display: flex;
          align-items: center;
          gap: 10px;
          flex-wrap: wrap;
        }

        .severity-pill {
          font-size: 10.5px;
          font-weight: 700;
          text-transform: uppercase;
          padding: 2px 8px;
          border-radius: 10px;
          background: rgba(16, 185, 129, 0.15);
          color: #34d399;
          border: 1px solid rgba(16, 185, 129, 0.3);
        }

        .severity-pill.amber {
          background: rgba(245, 158, 11, 0.15);
          color: #fbbf24;
          border-color: rgba(245, 158, 11, 0.3);
        }

        .severity-pill.red {
          background: rgba(239, 68, 68, 0.15);
          color: #f87171;
          border-color: rgba(239, 68, 68, 0.3);
        }

        .model-tag {
          font-size: 11px;
          color: #94a3b8;
          font-weight: 500;
        }

        .summary-text {
          font-size: 12.5px;
          line-height: 1.5;
          color: #c9d1d9;
        }

        /* NAVIGATION TABS */
        .advisor-tabs {
          display: flex;
          gap: 6px;
          background: rgba(13, 17, 23, 0.9);
          border: 1px solid var(--tg-border);
          border-radius: 10px;
          padding: 4px;
          margin-bottom: 14px;
          flex-wrap: wrap;
        }

        .adv-tab-btn {
          flex: 1;
          min-width: 110px;
          background: transparent;
          border: none;
          color: #8b949e;
          font-size: 11.5px;
          font-weight: 600;
          padding: 7px 10px;
          border-radius: 8px;
          cursor: pointer;
          transition: all 0.2s ease;
          display: flex;
          align-items: center;
          justify-content: center;
          gap: 6px;
        }

        .adv-tab-btn.active {
          background: rgba(139, 92, 246, 0.2);
          color: #ddd6fe;
          font-weight: 700;
          border: 1px solid rgba(139, 92, 246, 0.35);
        }

        /* TAB PANES */
        .tab-pane {
          display: none;
        }

        .tab-pane.active {
          display: block;
        }

        .diag-section-title {
          font-size: 11.5px;
          font-weight: 700;
          color: #8b949e;
          text-transform: uppercase;
          letter-spacing: 0.5px;
          margin-bottom: 8px;
        }

        .nominal-box {
          display: flex;
          align-items: center;
          gap: 12px;
          background: rgba(16, 185, 129, 0.08);
          border: 1px solid rgba(16, 185, 129, 0.25);
          border-radius: 10px;
          padding: 12px 14px;
          margin-bottom: 10px;
        }

        .nominal-icon {
          font-size: 20px;
          flex-shrink: 0;
        }

        .nominal-title {
          font-size: 12.5px;
          font-weight: 700;
          color: #34d399;
        }

        .nominal-sub {
          font-size: 11.5px;
          color: #8b949e;
          margin-top: 2px;
        }

        /* OBSERVATIONS */
        .item-card {
          background: rgba(15, 23, 42, 0.65);
          border: 1px solid var(--tg-border);
          border-radius: 10px;
          padding: 10px 14px;
          margin-bottom: 8px;
          font-size: 12.5px;
          line-height: 1.45;
          color: #e6edf3;
          display: flex;
          align-items: flex-start;
          gap: 10px;
        }

        .item-icon {
          font-size: 15px;
          flex-shrink: 0;
          margin-top: 1px;
        }

        /* FORMATTED DETECTED ISSUES */
        .issue-card {
          background: rgba(245, 158, 11, 0.06);
          border: 1px solid rgba(245, 158, 11, 0.35);
          border-radius: 10px;
          padding: 10px 14px;
          margin-bottom: 8px;
          display: flex;
          flex-direction: column;
          gap: 4px;
          transition: all 0.2s ease;
        }

        .issue-card.critical {
          background: rgba(239, 68, 68, 0.08);
          border-color: rgba(239, 68, 68, 0.4);
        }

        .issue-card-top {
          display: flex;
          align-items: center;
          gap: 8px;
          flex-wrap: wrap;
        }

        .issue-badge {
          font-size: 10px;
          font-weight: 800;
          padding: 2px 7px;
          border-radius: 6px;
          text-transform: uppercase;
          background: rgba(245, 158, 11, 0.2);
          color: #fbbf24;
          border: 1px solid rgba(245, 158, 11, 0.35);
        }

        .issue-badge.critical {
          background: rgba(239, 68, 68, 0.2);
          color: #f87171;
          border-color: rgba(239, 68, 68, 0.4);
        }

        .issue-title {
          font-size: 12.5px;
          font-weight: 700;
          color: #f0f6fc;
          flex: 1;
        }

        .issue-detail {
          font-size: 11.5px;
          color: #94a3b8;
          line-height: 1.4;
          padding-left: 2px;
        }

        /* FORMATTED RECOMMENDED ACTIONS */
        .action-card {
          background: rgba(15, 23, 42, 0.7);
          border: 1px solid var(--tg-border);
          border-radius: 10px;
          padding: 10px 14px;
          margin-bottom: 8px;
          display: flex;
          align-items: flex-start;
          gap: 12px;
          transition: all 0.2s ease;
        }

        .action-card.immediate {
          background: rgba(239, 68, 68, 0.06);
          border-color: rgba(239, 68, 68, 0.35);
        }

        .action-card:hover {
          border-color: rgba(139, 92, 246, 0.4);
        }

        .action-num-badge {
          width: 24px;
          height: 24px;
          border-radius: 50%;
          background: rgba(16, 185, 129, 0.2);
          color: #34d399;
          font-weight: 800;
          font-size: 11.5px;
          display: flex;
          align-items: center;
          justify-content: center;
          flex-shrink: 0;
          margin-top: 1px;
        }

        .action-num-badge.immediate {
          background: rgba(239, 68, 68, 0.2);
          color: #f87171;
        }

        .action-content {
          display: flex;
          flex-direction: column;
          gap: 3px;
          flex: 1;
        }

        .action-top-row {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 8px;
        }

        .action-title {
          font-size: 12.5px;
          font-weight: 700;
          color: #f0f6fc;
        }

        .action-urgency-tag {
          font-size: 9.5px;
          font-weight: 800;
          padding: 1px 6px;
          border-radius: 5px;
          text-transform: uppercase;
          background: rgba(239, 68, 68, 0.2);
          color: #f87171;
          border: 1px solid rgba(239, 68, 68, 0.3);
        }

        .action-detail {
          font-size: 11.5px;
          color: #94a3b8;
          line-height: 1.4;
        }

        /* WATER PREPARATION SEQUENCE */
        .feed-order-banner {
          display: flex;
          align-items: center;
          gap: 10px;
          background: linear-gradient(135deg, rgba(6, 182, 212, 0.12), rgba(16, 185, 129, 0.1));
          border: 1px solid rgba(6, 182, 212, 0.3);
          border-radius: 10px;
          padding: 10px 14px;
          margin-bottom: 12px;
          font-size: 12px;
          color: #67e8f9;
        }

        .feed-order-banner-icon {
          font-size: 18px;
          flex-shrink: 0;
        }

        .recipe-timeline {
          display: flex;
          flex-direction: column;
          gap: 8px;
          margin-bottom: 14px;
        }

        .recipe-step-card {
          background: rgba(15, 23, 42, 0.75);
          border: 1px solid var(--tg-border);
          border-radius: 10px;
          padding: 10px 14px;
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 12px;
        }

        .recipe-step-left {
          display: flex;
          align-items: center;
          gap: 12px;
          min-width: 0;
        }

        .recipe-order-badge {
          width: 26px;
          height: 26px;
          border-radius: 8px;
          background: rgba(139, 92, 246, 0.2);
          color: #c4b5fd;
          font-weight: 800;
          font-size: 12px;
          display: flex;
          align-items: center;
          justify-content: center;
          flex-shrink: 0;
          border: 1px solid rgba(139, 92, 246, 0.3);
        }

        .recipe-nut-details {
          display: flex;
          flex-direction: column;
          min-width: 0;
        }

        .recipe-nut-name {
          font-size: 13px;
          font-weight: 700;
          color: #f0f6fc;
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }

        .recipe-nut-hint {
          font-size: 11px;
          color: #8b949e;
        }

        .recipe-nut-dose {
          font-size: 12.5px;
          font-weight: 800;
          color: #34d399;
          background: rgba(16, 185, 129, 0.12);
          padding: 4px 10px;
          border-radius: 7px;
          border: 1px solid rgba(16, 185, 129, 0.25);
          white-space: nowrap;
          flex-shrink: 0;
        }

        .recipe-corridor-box {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
          gap: 8px;
          background: rgba(13, 17, 23, 0.85);
          border: 1px solid var(--tg-border);
          border-radius: 10px;
          padding: 10px 14px;
        }

        .corridor-item {
          display: flex;
          flex-direction: column;
          gap: 2px;
        }

        .corridor-item-label {
          font-size: 10px;
          color: #8b949e;
          text-transform: uppercase;
          font-weight: 600;
        }

        .corridor-item-val {
          font-size: 12.5px;
          font-weight: 700;
          color: #e6edf3;
        }

        /* TAB 4: AI AGRONOMIST CHAT */
        .chat-context-bar {
          display: flex;
          align-items: center;
          justify-content: space-between;
          background: rgba(13, 17, 23, 0.85);
          border: 1px solid rgba(6, 182, 212, 0.25);
          border-radius: 10px;
          padding: 8px 12px;
          margin-bottom: 10px;
          font-size: 11.5px;
          color: #94a3b8;
          flex-wrap: wrap;
          gap: 6px;
        }

        .chat-context-pills {
          display: flex;
          align-items: center;
          gap: 6px;
          flex-wrap: wrap;
        }

        .ctx-pill {
          background: rgba(255, 255, 255, 0.05);
          border: 1px solid rgba(255, 255, 255, 0.08);
          border-radius: 6px;
          padding: 2px 7px;
          font-size: 10.5px;
          color: #e6edf3;
          font-weight: 600;
        }

        .ctx-pill.cyan {
          color: #67e8f9;
          border-color: rgba(6, 182, 212, 0.3);
          background: rgba(6, 182, 212, 0.1);
        }

        .chat-suggestions {
          display: flex;
          gap: 6px;
          overflow-x: auto;
          padding-bottom: 6px;
          margin-bottom: 10px;
        }

        .suggestion-chip {
          background: rgba(139, 92, 246, 0.12);
          border: 1px solid rgba(139, 92, 246, 0.3);
          color: #c4b5fd;
          font-size: 11px;
          font-weight: 600;
          padding: 5px 10px;
          border-radius: 14px;
          cursor: pointer;
          white-space: nowrap;
          transition: all 0.2s ease;
        }

        .suggestion-chip:hover {
          background: rgba(139, 92, 246, 0.25);
          color: #fff;
          border-color: rgba(139, 92, 246, 0.5);
        }

        .chat-stream {
          height: 250px;
          overflow-y: auto;
          background: rgba(11, 15, 23, 0.95);
          border: 1px solid var(--tg-border);
          border-radius: 12px;
          padding: 12px;
          display: flex;
          flex-direction: column;
          gap: 12px;
          margin-bottom: 12px;
          scroll-behavior: smooth;
        }

        .chat-bubble {
          display: flex;
          gap: 10px;
          max-width: 92%;
        }

        .chat-bubble.assistant {
          align-self: flex-start;
        }

        .chat-bubble.user {
          align-self: flex-end;
          flex-direction: row-reverse;
        }

        .chat-avatar {
          width: 28px;
          height: 28px;
          border-radius: 8px;
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 14px;
          flex-shrink: 0;
        }

        .chat-bubble.assistant .chat-avatar {
          background: linear-gradient(135deg, #8b5cf6, #6d28d9);
        }

        .chat-bubble.user .chat-avatar {
          background: linear-gradient(135deg, #06b6d4, #0284c7);
        }

        .chat-msg-body {
          background: rgba(15, 23, 42, 0.9);
          border: 1px solid rgba(255, 255, 255, 0.08);
          border-radius: 12px;
          padding: 10px 13px;
          font-size: 12px;
          line-height: 1.5;
          color: #e6edf3;
        }

        .chat-bubble.assistant .chat-msg-body {
          border-color: rgba(139, 92, 246, 0.3);
        }

        .chat-bubble.user .chat-msg-body {
          background: linear-gradient(135deg, rgba(6, 182, 212, 0.18), rgba(2, 132, 199, 0.15));
          border-color: rgba(6, 182, 212, 0.35);
        }

        .chat-time {
          font-size: 9.5px;
          color: #64748b;
          margin-top: 4px;
          text-align: right;
        }

        .chat-typing {
          display: flex;
          align-items: center;
          gap: 8px;
          font-size: 11.5px;
          color: #c4b5fd;
          font-style: italic;
          padding: 4px 8px;
        }

        .chat-input-row {
          display: flex;
          gap: 8px;
        }

        .chat-input {
          flex: 1;
          background: rgba(15, 23, 42, 0.9);
          border: 1px solid var(--tg-border);
          border-radius: 10px;
          padding: 9px 14px;
          font-size: 12.5px;
          color: #fff;
          outline: none;
          transition: border-color 0.2s ease;
        }

        .chat-input:focus {
          border-color: var(--tg-cyan);
        }

        .chat-send-btn {
          background: linear-gradient(135deg, #06b6d4, #0284c7);
          border: none;
          color: #fff;
          font-weight: 700;
          font-size: 12px;
          padding: 0 16px;
          border-radius: 10px;
          cursor: pointer;
          transition: all 0.2s ease;
        }

        .chat-send-btn:hover {
          box-shadow: 0 0 14px rgba(6, 182, 212, 0.4);
          transform: translateY(-1px);
        }
      </style>

      <div class="container">
        <!-- Header -->
        <div class="header">
          <div class="header-left">
            <div class="brand-badge">🧠</div>
            <div>
              <h2>${title}</h2>
              <div class="subtitle">Autonomous Agronomy Diagnostics & Guidance</div>
            </div>
          </div>
          <button class="btn-run-diag" id="btn-run-diag">⚡ Run AI Check</button>
        </div>

        <!-- Executive Hero Banner -->
        <div class="advisor-hero">
          <div class="score-dial-box">
            <svg width="56" height="56">
              <circle class="score-dial-track" cx="28" cy="28" r="22" />
              <circle class="score-dial-progress" id="adv-dial-bar" cx="28" cy="28" r="22" stroke-dasharray="138.2" stroke-dashoffset="138.2" />
            </svg>
            <div class="score-dial-val" id="adv-score-val">--</div>
          </div>
          <div class="hero-info">
            <div class="hero-top-row">
              <span class="severity-pill" id="adv-sev-pill">Optimal Vigor</span>
              <span class="model-tag" id="adv-model-tag">Gemini 2.5 Flash • 95% Conf</span>
            </div>
            <p class="summary-text" id="adv-summary-text">Analyzing cultivation telemetry and visual canopy vigor...</p>
          </div>
        </div>

        <!-- Navigation Tabs -->
        <div class="advisor-tabs">
          <button class="adv-tab-btn active" id="tab-btn-diag">🔍 Observations & Issues</button>
          <button class="adv-tab-btn" id="tab-btn-rec">⚡ Recommended Actions</button>
          <button class="adv-tab-btn" id="tab-btn-feed">🧪 Feeding Recipe</button>
          <button class="adv-tab-btn" id="tab-btn-chat">💬 Agronomist Chat</button>
        </div>

        <!-- Tab 1: Observations & Issues -->
        <div class="tab-pane active" id="pane-diag">
          <div class="diag-section-title">Canopy Observations</div>
          <div class="obs-list" id="obs-list-container">
            <div class="item-card"><span class="item-icon">👁️</span><span>Healthy green foliage with active transpiration.</span></div>
          </div>
          <div class="diag-section-title" style="margin-top: 14px;">Detected Issues & Variances</div>
          <div class="issues-list" id="issues-list-container">
            <div class="nominal-box">
              <span class="nominal-icon">✅</span>
              <div>
                <div class="nominal-title">All Parameters Nominal</div>
                <div class="nominal-sub">No nutrient burn, pH lockout, or environmental variances detected.</div>
              </div>
            </div>
          </div>
        </div>

        <!-- Tab 2: Recommended Actions -->
        <div class="tab-pane" id="pane-rec">
          <div class="diag-section-title">Agronomy Action Plan</div>
          <div class="rec-list" id="rec-list-container">
            <div class="action-card">
              <div class="action-num-badge">1</div>
              <div class="action-content">
                <div class="action-top-row">
                  <span class="action-title">Maintain optimal target VPD band</span>
                  <span class="action-urgency-tag">ROUTINE</span>
                </div>
                <div class="action-detail">Keep canopy transpiration balanced for current vegetative growth cycle.</div>
              </div>
            </div>
          </div>
        </div>

        <!-- Tab 3: Feeding Recipe (Strict Horticultural Order) -->
        <div class="tab-pane" id="pane-feed">
          <div class="feed-order-banner">
            <span class="feed-order-banner-icon">💧</span>
            <span><strong>Strict Water Preparation Sequence:</strong> Add nutrients one by one in exact order. Dissolve thoroughly before adding next to avoid nutrient lockout/precipitation. Buffer pH LAST.</span>
          </div>
          <div class="recipe-timeline" id="feed-recipe-container">
            <!-- Dynamically populated -->
          </div>
          <div class="recipe-corridor-box" id="recipe-corridor-box">
            <div class="corridor-item">
              <span class="corridor-item-label">Target pH Buffer</span>
              <span class="corridor-item-val" id="adv-feed-target-ph">5.8 (5.5 - 6.2)</span>
            </div>
            <div class="corridor-item">
              <span class="corridor-item-label">Target EC Corridor</span>
              <span class="corridor-item-val" id="adv-feed-target-ec">1.2 - 1.6 mS/cm</span>
            </div>
            <div class="corridor-item">
              <span class="corridor-item-label">Reservoir Water Temp</span>
              <span class="corridor-item-val" id="adv-feed-target-temp">65°F - 68°F (Optimal DO)</span>
            </div>
          </div>
        </div>

        <!-- Tab 4: AI Agronomist Chat Window -->
        <div class="tab-pane" id="pane-chat">
          <div class="chat-context-bar">
            <span>Cockpit: <strong id="chat-ctx-space">${escapeHtml(this._config.space_name || "Cultivation Space")}</strong></span>
            <div class="chat-context-pills" id="chat-ctx-pills">
              <span class="ctx-pill cyan" id="chat-pill-stage">Stage: Vegetative</span>
              <span class="ctx-pill" id="chat-pill-ph">pH: --</span>
              <span class="ctx-pill" id="chat-pill-ec">EC: --</span>
              <span class="ctx-pill" id="chat-pill-vpd">VPD: --</span>
            </div>
          </div>

          <div class="chat-suggestions">
            <button class="suggestion-chip" data-query="How healthy is my canopy right now based on telemetry?">Canopy Health Check</button>
            <button class="suggestion-chip" data-query="Is my VPD dialed in for my current stage?">Check VPD Corridor</button>
            <button class="suggestion-chip" data-query="What is the proper order to mix my water and nutrients?">Water Prep Sequence</button>
            <button class="suggestion-chip" data-query="When should I do my next reservoir flush and fill?">Flush & Fill Routine</button>
            <button class="suggestion-chip" data-query="What should my target EC and pH corridor be?">Target Corridor Advice</button>
          </div>

          <div class="chat-stream" id="chat-stream">
            <!-- Messages rendered dynamically -->
          </div>

          <div class="chat-input-row">
            <input type="text" class="chat-input" id="chat-input" placeholder="Ask AI agronomist about this grow..." />
            <button class="chat-send-btn" id="chat-send-btn">Send 🚀</button>
          </div>
        </div>
      </div>
    `;

    this._bindEvents();
    this._renderChatMessages();
    this._updateStates();
  }

  _bindEvents() {
    const root = this.shadowRoot;
    if (!root) return;

    const tDiag = root.getElementById("tab-btn-diag");
    const tRec = root.getElementById("tab-btn-rec");
    const tFeed = root.getElementById("tab-btn-feed");
    const tChat = root.getElementById("tab-btn-chat");

    const pDiag = root.getElementById("pane-diag");
    const pRec = root.getElementById("pane-rec");
    const pFeed = root.getElementById("pane-feed");
    const pChat = root.getElementById("pane-chat");

    const setTab = (tab) => {
      this._activeTab = tab;
      [tDiag, tRec, tFeed, tChat].forEach((b) => b && b.classList.remove("active"));
      [pDiag, pRec, pFeed, pChat].forEach((p) => p && p.classList.remove("active"));

      if (tab === "diag") {
        if (tDiag) tDiag.classList.add("active");
        if (pDiag) pDiag.classList.add("active");
      } else if (tab === "rec") {
        if (tRec) tRec.classList.add("active");
        if (pRec) pRec.classList.add("active");
      } else if (tab === "feed") {
        if (tFeed) tFeed.classList.add("active");
        if (pFeed) pFeed.classList.add("active");
      } else if (tab === "chat") {
        if (tChat) tChat.classList.add("active");
        if (pChat) pChat.classList.add("active");
        this._scrollChatToBottom();
      }
    };

    if (tDiag) tDiag.onclick = () => setTab("diag");
    if (tRec) tRec.onclick = () => setTab("rec");
    if (tFeed) tFeed.onclick = () => setTab("feed");
    if (tChat) tChat.onclick = () => setTab("chat");

    // Re-apply active tab if changed
    if (this._activeTab) setTab(this._activeTab);

    // AI Health Check Button
    const btnDiag = root.getElementById("btn-run-diag");
    if (btnDiag) {
      btnDiag.onclick = () => {
        btnDiag.textContent = "⏳ Running Diagnostic...";
        const runBtn = this._config.run_ai_health_check || this._config.run_button;
        if (runBtn) {
          this._callService("button", "press", { entity_id: runBtn });
        } else {
          this._callService("tendrilgrow", "run_ai_health_check", {});
        }
        setTimeout(() => {
          btnDiag.textContent = "⚡ Run AI Check";
        }, 4000);
      };
    }

    // Chat Input & Send
    const chatInput = root.getElementById("chat-input");
    const chatSendBtn = root.getElementById("chat-send-btn");

    const handleSend = () => {
      if (!chatInput) return;
      const text = chatInput.value.trim();
      if (!text || this._isChatLoading) return;
      chatInput.value = "";
      this._sendUserChatMessage(text);
    };

    if (chatSendBtn) chatSendBtn.onclick = handleSend;
    if (chatInput) {
      chatInput.onkeydown = (e) => {
        if (e.key === "Enter") {
          e.preventDefault();
          handleSend();
        }
      };
    }

    // Suggestion Chips
    const chips = root.querySelectorAll(".suggestion-chip");
    chips.forEach((chip) => {
      chip.onclick = () => {
        const query = chip.getAttribute("data-query");
        if (query && !this._isChatLoading) {
          this._sendUserChatMessage(query);
        }
      };
    });
  }

  _renderChatMessages() {
    const root = this.shadowRoot;
    if (!root) return;
    const stream = root.getElementById("chat-stream");
    if (!stream) return;

    const msgs = this._chatMessages || [];
    let html = msgs
      .map((msg) => {
        const isUser = msg.role === "user";
        return `
          <div class="chat-bubble ${isUser ? "user" : "assistant"}">
            <div class="chat-avatar">${isUser ? "🧑‍🌾" : "🧠"}</div>
            <div class="chat-msg-body">
              <div>${isUser ? escapeHtml(msg.text) : formatChatMarkdown(msg.text)}</div>
              <div class="chat-time">${escapeHtml(msg.time || "")}</div>
            </div>
          </div>
        `;
      })
      .join("");

    if (this._isChatLoading) {
      html += `
        <div class="chat-bubble assistant">
          <div class="chat-avatar">🧠</div>
          <div class="chat-msg-body chat-typing">
            <span>Analyzing ${escapeHtml(this._config.space_name || "grow space")} telemetry...</span>
          </div>
        </div>
      `;
    }

    stream.innerHTML = html;
    this._scrollChatToBottom();
  }

  _scrollChatToBottom() {
    const root = this.shadowRoot;
    if (!root) return;
    const stream = root.getElementById("chat-stream");
    if (stream) {
      setTimeout(() => {
        stream.scrollTop = stream.scrollHeight;
      }, 50);
    }
  }

  async _sendUserChatMessage(query) {
    if (!query) return;
    const timeStr = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    this._chatMessages.push({
      role: "user",
      text: query,
      time: timeStr,
    });
    this._isChatLoading = true;
    this._renderChatMessages();

    // Prepare context bundle
    const phVal = getStateNum(this._hass, this._config.ph, 5.85);
    const ecVal = getStateNum(this._hass, this._config.ec, 1.35);
    const vpdVal = getStateNum(this._hass, this._config.vpd, 1.15);
    const tempVal = getStateNum(this._hass, this._config.temperature, 75);
    const rhVal = getStateNum(this._hass, this._config.humidity, 60);
    const waterTempVal = getStateNum(this._hass, this._config.water_temperature, 67.5);
    const stageVal = getStateStr(this._hass, this._config.stage, "Vegetative");
    const daysSinceFlush = getStateNum(this._hass, this._config.days_since_flush, 5);

    const agronomyContext = {
      space_name: this._config.space_name || "Cultivation Space",
      space_slug: this._config.space_slug || "",
      stage: stageVal,
      ph: phVal,
      ec: ecVal,
      vpd: vpdVal,
      air_temp: tempVal,
      humidity: rhVal,
      water_temp: waterTempVal,
      days_since_flush: daysSinceFlush,
      reservoir_volume: this._config.reservoir_volume || 15,
      target_ph_low: this._config.target_ph_low || 5.5,
      target_ph_high: this._config.target_ph_high || 6.2,
      target_ec_low: this._config.target_ec_low || 1.2,
      target_ec_high: this._config.target_ec_high || 1.6,
      target_vpd_low: this._config.target_vpd_low || 0.8,
      target_vpd_high: this._config.target_vpd_high || 1.2,
    };

    let reply = "";

    // 1. Try Home Assistant Conversation WebSocket if available
    if (this._hass && typeof this._hass.callWS === "function") {
      try {
        const res = await Promise.race([
          this._hass.callWS({
            type: "conversation/process",
            text: `[Space: ${agronomyContext.space_name} | Stage: ${agronomyContext.stage} | pH: ${agronomyContext.ph} | EC: ${agronomyContext.ec} | VPD: ${agronomyContext.vpd} kPa | Water Temp: ${agronomyContext.water_temp}°F] ${query}`,
          }),
          new Promise((_, reject) => setTimeout(() => reject(new Error("Timeout")), 2500)),
        ]);
        if (res && res.response && res.response.speech && res.response.speech.plain && res.response.speech.plain.speech) {
          reply = res.response.speech.plain.speech;
        }
      } catch (e) {
        // Fallback to autonomous agronomy advice generator
      }
    }

    // 2. Fallback to our grounded agronomy knowledge engine
    if (!reply) {
      await new Promise((resolve) => setTimeout(resolve, 400));
      reply = generateAgronomyAdvice(query, agronomyContext);
    }

    this._isChatLoading = false;
    this._chatMessages.push({
      role: "assistant",
      text: reply,
      time: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
    });

    this._renderChatMessages();
  }

  _updateStates() {
    if (!this._hass || !this.shadowRoot) return;
    const root = this.shadowRoot;

    const summaryEntity = this._config.summary || this._config.ai_health_summary || this._config.score;
    const summaryState = getState(this._hass, summaryEntity);
    const scoreEntity = this._config.score || summaryEntity;
    const scoreState = getState(this._hass, scoreEntity);
    const attrs = {
      ...(scoreState ? scoreState.attributes || {} : {}),
      ...(summaryState ? summaryState.attributes || {} : {}),
    };

    const score = attrs.score !== undefined ? attrs.score : getStateNum(this._hass, scoreEntity, 92);
    const severity = (attrs.severity || "low").toLowerCase();
    const confidence = attrs.confidence || 95;
    const model = attrs.model || "gemini-2.5-flash";
    const summary = attrs.summary || summaryState?.state || scoreState?.state || "Vigor nominal across all environmental metrics.";
    const observations = Array.isArray(attrs.observations) ? attrs.observations : [];
    const issues = Array.isArray(attrs.issues) ? attrs.issues : [];
    const actions = Array.isArray(attrs.recommended_actions) ? attrs.recommended_actions : [];
    const feedSchedule = Array.isArray(attrs.feeding_schedule) ? attrs.feeding_schedule : [];

    // Health Score Dial
    const dialVal = root.getElementById("adv-score-val");
    const dialBar = root.getElementById("adv-dial-bar");
    if (dialVal && dialBar) {
      dialVal.textContent = score !== null ? Math.round(score) : "--";
      const circ = 2 * Math.PI * 22; // ~138.2
      const offset = circ - ((score || 0) / 100) * circ;
      dialBar.style.strokeDashoffset = offset;
      if (score >= 75) {
        dialBar.style.stroke = "var(--tg-green)";
      } else if (score >= 50) {
        dialBar.style.stroke = "var(--tg-amber)";
      } else {
        dialBar.style.stroke = "var(--tg-red)";
      }
    }

    // Severity & Model
    const sevPill = root.getElementById("adv-sev-pill");
    const modelTag = root.getElementById("adv-model-tag");
    const sumText = root.getElementById("adv-summary-text");

    if (sevPill) {
      sevPill.textContent = severity === "low" ? "Nominal Vigor" : severity === "medium" ? "Moderate Variance" : "Attention Required";
      sevPill.className = `severity-pill ${severity === "low" ? "" : severity === "medium" ? "amber" : "red"}`;
    }
    if (modelTag) {
      modelTag.textContent = `${model} • ${confidence}% Confidence`;
    }
    if (sumText) {
      sumText.textContent = summary;
    }

    // Observations
    const obsContainer = root.getElementById("obs-list-container");
    if (obsContainer && observations.length > 0) {
      obsContainer.innerHTML = observations
        .map((obs) => `<div class="item-card"><span class="item-icon">👁️</span><span>${escapeHtml(String(obs))}</span></div>`)
        .join("");
    }

    // Tab 1: Formatted Detected Issues (No Raw JSON)
    const issuesContainer = root.getElementById("issues-list-container");
    if (issuesContainer) {
      if (issues.length > 0) {
        issuesContainer.innerHTML = issues
          .map((iss) => {
            const item = parseIssueItem(iss);
            const isCrit = item.severity === "critical" || item.severity === "high";
            const tagText = item.metric ? item.metric.toUpperCase() : isCrit ? "CRITICAL" : "VARIANCE";
            return `
              <div class="issue-card ${isCrit ? "critical" : ""}">
                <div class="issue-card-top">
                  <span class="issue-badge ${isCrit ? "critical" : ""}">${escapeHtml(tagText)}</span>
                  <span class="issue-title">${escapeHtml(item.title)}</span>
                </div>
                ${item.detail ? `<div class="issue-detail">${escapeHtml(item.detail)}</div>` : ""}
              </div>
            `;
          })
          .join("");
      } else {
        issuesContainer.innerHTML = `
          <div class="nominal-box">
            <span class="nominal-icon">✅</span>
            <div>
              <div class="nominal-title">All Parameters Nominal</div>
              <div class="nominal-sub">No nutrient burn, pH lockout, or environmental variances detected.</div>
            </div>
          </div>
        `;
      }
    }

    // Tab 2: Formatted Recommended Actions (No Raw JSON)
    const recContainer = root.getElementById("rec-list-container");
    if (recContainer) {
      if (actions.length > 0) {
        recContainer.innerHTML = actions
          .map((act, i) => {
            const item = parseActionItem(act);
            const isImmediate = item.severity === "immediate" || item.severity === "critical" || item.severity === "high";
            return `
              <div class="action-card ${isImmediate ? "immediate" : ""}">
                <div class="action-num-badge ${isImmediate ? "immediate" : ""}">${i + 1}</div>
                <div class="action-content">
                  <div class="action-top-row">
                    <span class="action-title">${escapeHtml(item.title)}</span>
                    ${isImmediate ? `<span class="action-urgency-tag">IMMEDIATE</span>` : ""}
                  </div>
                  ${item.detail ? `<div class="action-detail">${escapeHtml(item.detail)}</div>` : ""}
                </div>
              </div>
            `;
          })
          .join("");
      } else {
        recContainer.innerHTML = `
          <div class="nominal-box">
            <span class="nominal-icon">🌱</span>
            <div>
              <div class="nominal-title">Standard Cultivation Plan</div>
              <div class="nominal-sub">Maintain current target bands and monitor root zone transpiration.</div>
            </div>
          </div>
        `;
      }
    }

    // Tab 3: Feeding Recipe (Strict Horticultural Order)
    const feedContainer = root.getElementById("feed-recipe-container");
    if (feedContainer) {
      let rawItems = [];
      if (feedSchedule.length > 0) {
        const schedStr = feedSchedule[0] || "";
        const parts = schedStr.split("|");
        const nutPart = parts.length > 1 ? parts[1] : schedStr;
        rawItems = nutPart
          .replace(/ADD IN ORDER:/i, "")
          .split(";")
          .map((s) => s.trim())
          .filter(Boolean);
      }

      let parsedNuts = [];
      if (rawItems.length > 0) {
        parsedNuts = rawItems.map((item) => {
          const splitIdx = item.indexOf(":");
          if (splitIdx > -1) {
            return {
              name: item.slice(0, splitIdx).trim(),
              dose: item.slice(splitIdx + 1).trim(),
            };
          }
          return { name: item, dose: "" };
        });
      } else {
        // Stage-appropriate standard nutrient sequence
        parsedNuts = [
          { name: "Armor Si (Silica)", dose: "12.5 ml (2.5 ml/gal)" },
          { name: "CaliMagic (Cal-Mag)", dose: "15.0 ml (3.0 ml/gal)" },
          { name: "FloraMicro (Base)", dose: "25.0 ml (5.0 ml/gal)" },
          { name: "FloraGro (Vegetative)", dose: "25.0 ml (5.0 ml/gal)" },
          { name: "FloraBloom (Flowering)", dose: "10.0 ml (2.0 ml/gal)" },
          { name: "Hydroguard (Beneficial Microbes)", dose: "10.0 ml (2.0 ml/gal)" },
          { name: "General Hydroponics pH Down", dose: "Buffer LAST to 5.8" },
        ];
      }

      // Sort by strict horticultural water preparation order
      const sortedNuts = sortNutrientsByHorticulturalOrder(parsedNuts);

      const getNutrientHint = (name) => {
        const low = name.toLowerCase();
        if (low.includes("silica") || low.includes("armor si") || low.includes("rhino")) {
          return "Add first. Dissolve & let stand 10-15m before adding salts.";
        }
        if (low.includes("cal-mag") || low.includes("calimagic") || low.includes("calmag")) {
          return "Dissolve completely before base NPK to avoid gypsum precipitation.";
        }
        if (low.includes("micro") || low.includes("base")) {
          return "Add chelated micro-nutrients first before Grow/Bloom.";
        }
        if (low.includes("gro") || low.includes("grow") || low.includes("veg")) {
          return "Primary vegetative nitrogen & potassium builder.";
        }
        if (low.includes("bloom")) {
          return "Phosphorus & potassium builder for floral structure.";
        }
        if (low.includes("hydroguard") || low.includes("microbe") || low.includes("voodoo") || low.includes("tarantula")) {
          return "Root inoculant. Add after macro salts are completely dissolved.";
        }
        if (low.includes("ph down") || low.includes("ph up") || low.includes("ph adjust")) {
          return "Buffer LAST once all salts stabilize and EC stabilizes.";
        }
        return "Mix thoroughly into reservoir before proceeding.";
      };

      feedContainer.innerHTML = sortedNuts
        .map((nut, idx) => {
          const hint = getNutrientHint(nut.name);
          return `
            <div class="recipe-step-card">
              <div class="recipe-step-left">
                <div class="recipe-order-badge">${idx + 1}</div>
                <div class="recipe-nut-details">
                  <span class="recipe-nut-name">${escapeHtml(nut.name)}</span>
                  <span class="recipe-nut-hint">${escapeHtml(hint)}</span>
                </div>
              </div>
              <div class="recipe-nut-dose">${escapeHtml(nut.dose || "As Directed")}</div>
            </div>
          `;
        })
        .join("");
    }

    // Corridor Targets in Recipe Tab
    const feedTargetPh = root.getElementById("adv-feed-target-ph");
    const feedTargetEc = root.getElementById("adv-feed-target-ec");
    if (feedTargetPh) {
      feedTargetPh.textContent = `5.8 (${this._config.target_ph_low || 5.5} - ${this._config.target_ph_high || 6.2})`;
    }
    if (feedTargetEc) {
      feedTargetEc.textContent = `${this._config.target_ec_low || 1.2} - ${this._config.target_ec_high || 1.6} mS/cm`;
    }

    // Tab 4: Live Telemetry Context Pills
    const stagePill = root.getElementById("chat-pill-stage");
    const phPill = root.getElementById("chat-pill-ph");
    const ecPill = root.getElementById("chat-pill-ec");
    const vpdPill = root.getElementById("chat-pill-vpd");

    if (stagePill) {
      const curStage = getStateStr(this._hass, this._config.stage, "Vegetative");
      stagePill.textContent = `Stage: ${curStage}`;
    }
    if (phPill) {
      const phVal = getStateNum(this._hass, this._config.ph, 5.85);
      phPill.textContent = `pH: ${phVal.toFixed(2)}`;
    }
    if (ecPill) {
      const ecVal = getStateNum(this._hass, this._config.ec, 1.35);
      ecPill.textContent = `EC: ${ecVal.toFixed(2)}`;
    }
    if (vpdPill) {
      const vpdVal = getStateNum(this._hass, this._config.vpd, 1.15);
      vpdPill.textContent = `VPD: ${vpdVal.toFixed(2)} kPa`;
    }
  }
}

// Register Custom Elements
customElements.define("tendrilgrow-twin-card", TendrilGrowTwinCard);
customElements.define("tendrilgrow-overview-card", TendrilGrowOverviewCard);
customElements.define("tendrilgrow-trends-card", TendrilGrowTrendsCard);
customElements.define("tendrilgrow-schedules-card", TendrilGrowSchedulesCard);
customElements.define("tendrilgrow-plan-card", TendrilGrowPlanCard);
customElements.define("tendrilgrow-advisor-card", TendrilGrowAdvisorCard);

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
window.customCards.push({
  type: "tendrilgrow-trends-card",
  name: "TendrilGrow Telemetry Trends Card",
  description: "High-resolution 24h environmental & hydroponic trendlines with sweet-spot target corridors.",
  preview: true,
  documentationURL: "https://github.com/Trec-TorConsulting/TendrilGrow",
});
window.customCards.push({
  type: "tendrilgrow-schedules-card",
  name: "TendrilGrow Controller Schedules & Ambient Card",
  description: "Smart controller schedule cycles, timer countdowns, and lung room ambient buffer telemetry.",
  preview: true,
  documentationURL: "https://github.com/Trec-TorConsulting/TendrilGrow",
});
window.customCards.push({
  type: "tendrilgrow-plan-card",
  name: "TendrilGrow Cultivation Plan & Tasks Card",
  description: "Stage timeline progress, flip/harvest milestones, and interactive grow tasks checklist.",
  preview: true,
  documentationURL: "https://github.com/Trec-TorConsulting/TendrilGrow",
});
window.customCards.push({
  type: "tendrilgrow-advisor-card",
  name: "TendrilGrow AI Cultivation Intelligence Card",
  description: "AI agronomy diagnostics, visual observations, anomaly analysis, and nutrient mixing recipes.",
  preview: true,
  documentationURL: "https://github.com/Trec-TorConsulting/TendrilGrow",
});


