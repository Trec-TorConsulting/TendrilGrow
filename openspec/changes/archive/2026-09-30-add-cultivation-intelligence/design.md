# Technical Design: add-cultivation-intelligence

## Context

TendrilGrow monitors indoor cultivation environments and hydroponic systems within Home Assistant. While basic ambient sensors (air temperature, air relative humidity, pH, EC, and light) are supported, advanced cultivation intelligence requires contextual synthesis:
- In RDWC, the delta of EC and pH over time directly reflects plant transpiration vs. nutrient absorption.
- High-efficiency LED lights emit minimal radiant heat, making leaf surface temperature typically 2°F–4°F (1.1°C–2.2°C) cooler than ambient air. Evaluating VPD purely on air temperature underestimates the true drying potential on leaves.
- High humidity and narrow dew point margins during flowering and curing are the primary catalysts for *Botrytis cinerea* (bud rot) and powdery mildew.
- Transitioning photoperiod to 12/12 triggers flowering ("the flip"); cultivation calendars and feeding schedules are universally indexed from the flip date.
- Stalled daily water uptake in RDWC is an early indicator of root pathogen infection (Pythium) and dissolved oxygen starvation before visible foliar symptoms appear.
- Post-harvest drying and curing requires preserving volatile terpenes by adhering to the industry gold-standard "60/60 rule" (60°F ± 2°F and 60% RH ± 3%).

## Goals / Non-Goals

**Goals:**
- Provide a deterministic, robust RDWC drift diagnostic sensor classifying conditions into `equilibrium`, `dilute_recommended`, `feed_recommended`, and `root_health_check`.
- Provide true Leaf VPD calculation using either mapped infrared leaf temperature sensors or configurable LED offsets.
- Provide a Dew Point Margin sensor and an automated Mold Risk binary sensor with stage-aware thresholds.
- Provide dynamic Photoperiod Hours tracking, Days Since Flip calculation, and integrated DLI calculation.
- Support water level sensor mapping to compute daily transpiration rate and alert on stalled consumption.
- Automatically seed 60/60 target bands for `dry` and `cure` growth stages.

**Non-Goals:**
- Automated chemical dosing or motorized valve control (remains monitoring and advisory only).
- Hardcoding specific third-party hardware or cloud vendor protocols (all entities connect via Home Assistant entity IDs).
- Heavy machine learning models inside the local integration (insights are deterministic mathematical models; qualitative analysis is handled by the pluggable AI advisor).

## Decisions

### Decision 1: Pure Functions in `insights.py`
All mathematical algorithms (VPD, dew point margin, linear regression / slope delta, transpiration rate, flip duration) are implemented as pure, side-effect-free functions in `insights.py`.
- *Rationale*: Allows exhaustive unit testing without Home Assistant mocking, zero dependencies, and high execution speed.
- *Alternatives considered*: Embedding math directly into sensor entity classes (rejected: tightly couples calculation logic to Home Assistant lifecycle).

### Decision 2: In-Memory Rolling History with Resilient Fallbacks
Reservoir drift and daily transpiration analyze trends across a 12h–24h rolling window. Samples `(timestamp, ec, ph, water_level)` are buffered in memory within `RuntimeData` / sensor instance, pruning samples older than 24 hours.
- *Rationale*: Does not require the Home Assistant recorder component or SQL queries, works seamlessly in containerized and ephemeral environments, and has near-zero overhead (< 100 tuples in memory).
- *Alternatives considered*: Querying the Home Assistant `recorder` history API (rejected: fails when recorder is excluded, delayed, or on ephemeral test fixtures).

### Decision 3: Leaf Temperature Priority Cascade
Leaf VPD evaluates leaf temperature in order of priority:
1. Mapped `SENSOR_ROLE_LEAF_TEMPERATURE` entity state (if mapped and valid).
2. Ambient air temperature minus `CONF_LEAF_TEMP_OFFSET` (default `-3.0°F` / `-1.67°C`).
- *Rationale*: Most hobbyist and boutique growers lack expensive thermal IR canopy probes; supplying an agronomic default offset ensures all growers benefit from realistic Leaf VPD immediately.

### Decision 4: Stage-Aware Mold Risk Evaluation
`TendrilGrowMoldRiskBinarySensor` activates when:
- Dew Point Margin $\le 2.0^\circ\text{C}$ ($3.6^\circ\text{F}$) regardless of stage, OR
- Relative Humidity $\ge 65\%$ while in vulnerable stages (`mid_flower`, `late_flower`, `dry`, `cure`).
- *Rationale*: Mold spores require moisture condensation or high localized humidity; dense colas in late flower or drying racks are vulnerable even before full condensation occurs.

## Risks / Trade-offs

- [Risk]: Reservoir sensor noise or intermittent calibration spikes producing false drift diagnoses.
  → *Mitigation*: Require sustained slope thresholds ($\Delta EC \ge 0.1$, $\Delta pH \ge 0.2$) over at least 12 hours before triggering recommendations, and provide an `equilibrium` fallback.
- [Risk]: Water level sensor fluctuating due to aeration bubbles or wave action.
  → *Mitigation*: Transpiration rate aggregates delta across a rolling window rather than instantaneous differentiation.
- [Risk]: Operator changing stage back and forth corrupting `days_since_flip`.
  → *Mitigation*: `days_since_flip` tracks the `stage_started` date associated with the initial flowering transition (`early_flower`).
