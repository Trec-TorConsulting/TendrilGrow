# tuya-water-monitoring Specification

## Purpose
Optional per-grow-space Tuya cloud polling: signed OpenAPI access, datapoint
normalization into stable water-quality metrics, a per-entry update coordinator,
metric and last-updated sensors, sensor-role auto-mapping, and the rebuild_automap
service.
## Requirements
### Requirement: Optional Tuya cloud polling per grow space
Each grow space SHALL support an optional Tuya cloud polling source that the user
enables and configures with Tuya IoT access id, access secret, region, an optional
user UID, one or more device ids, and a poll interval. Cloud polling is a
fallback: the grow space MUST NOT make Tuya cloud requests when a local
water-monitor device is bound, even if cloud polling is still enabled in stored
options. When Tuya polling is disabled and no local device is bound, the grow
space MUST operate normally with no Tuya calls.

#### Scenario: Enable Tuya polling
- **WHEN** the user enables Tuya polling, no local water-monitor device is bound,
  and the user provides valid credentials and device ids
- **THEN** the integration polls those devices on the configured interval and
  exposes their readings as sensors

#### Scenario: Tuya polling left disabled
- **WHEN** the user does not enable Tuya polling and no local water-monitor
  device is bound
- **THEN** no Tuya cloud requests are made and the grow space still functions

#### Scenario: Local bind skips cloud polling
- **WHEN** a local water-monitor device is bound and stored options still have
  Tuya cloud polling enabled
- **THEN** no Tuya cloud requests are made for that grow space

### Requirement: Signed Tuya OpenAPI access
The integration SHALL authenticate to the Tuya OpenAPI using HMAC-SHA256 request
signing with a cached access token, selecting the regional endpoint (us, eu, cn,
or in), and SHALL fetch device readings from the shadow-properties endpoint when
available and fall back to the device status endpoint otherwise.

#### Scenario: Token is cached and reused
- **WHEN** multiple polls occur before the access token expires
- **THEN** the integration reuses the cached token rather than re-authenticating

#### Scenario: Status fallback
- **WHEN** a device does not return shadow properties
- **THEN** the integration reads the device status endpoint and normalizes it

### Requirement: Datapoint normalization
The integration SHALL normalize heterogeneous Tuya datapoint codes into a stable
metric set (pH, EC, CF, ORP, TDS, water temperature, ambient temperature, ambient
humidity, battery), applying the reported scale and deriving related conductivity
metrics when only one is present (TDS from EC, EC from TDS, CF mirroring EC).

#### Scenario: Normalize scaled properties
- **WHEN** a probe reports scaled pH/EC/temperature datapoints
- **THEN** the integration converts them to correctly scaled metric values

#### Scenario: Derive EC and CF from TDS only
- **WHEN** a probe reports only TDS
- **THEN** the integration derives EC and CF values from the TDS reading

### Requirement: Coordinated polling with partial-failure tolerance
The integration SHALL poll Tuya devices through a per-grow-space update coordinator
that records each device's last-updated timestamp and display name, and SHALL fail
the update only when every device fails; partial failures MUST be logged while
successful readings are still published.

#### Scenario: One device fails, others succeed
- **WHEN** one device errors during a poll but others return data
- **THEN** the coordinator publishes the successful readings and logs the failure

#### Scenario: All devices fail
- **WHEN** every device fails during a poll
- **THEN** the coordinator reports the update as failed

### Requirement: Tuya-backed sensor entities
When the effective water source is Tuya cloud polling, the integration SHALL
create one sensor entity per device per available metric and a per-device
diagnostic "last updated" timestamp sensor, each grouped under a Home Assistant
device representing the Tuya probe, and each reporting unavailable when its
metric is absent from the latest reading. When the effective source is a local
device, the integration MUST NOT create those cloud-backed metric entities.

#### Scenario: Metric entities created per device
- **WHEN** cloud polling is the effective source and a device returns pH, EC, and
  TDS readings
- **THEN** the integration exposes pH, EC, and TDS sensor entities for that device

#### Scenario: Missing metric is unavailable
- **WHEN** the latest cloud reading omits a metric for a device
- **THEN** that metric's sensor reports unavailable

#### Scenario: Local source does not create cloud metric entities
- **WHEN** a local water-monitor device is bound
- **THEN** the integration does not create Tuya cloud metric or last-updated
  sensors for that grow space

### Requirement: Automatic role mapping from Tuya entities
When Tuya cloud polling is the effective water source the integration SHALL hide
the manual water-quality sensor-mapping fields (the camera role remains manual)
and SHALL bind each Tuya metric entity to its matching grow-space water-quality
sensor role when that role is unmapped, recording the auto-mapped roles for
diagnostics. Cloud-backed probe humidity and ambient temperature MUST NOT be
auto-mapped onto the canopy `humidity` or `temperature` roles. When a local
water-monitor device is bound, water-quality mapping fields MUST remain visible
so the operator can override a datapoint.

#### Scenario: Auto-map an unmapped role
- **WHEN** a Tuya pH entity is added, cloud polling is the effective source, and
  the grow space has no pH mapping
- **THEN** the integration binds the pH role to that entity id

#### Scenario: Do not override an existing mapping
- **WHEN** a grow-space role is already mapped
- **THEN** the integration leaves the existing mapping unchanged

#### Scenario: Cloud probe humidity is not canopy humidity
- **WHEN** a Tuya cloud humidity metric entity is added
- **THEN** the integration does not bind it onto the canopy `humidity` role

### Requirement: Rebuild auto-mapping service
The integration SHALL provide a `rebuild_automap` service that reloads a specified
loaded grow-space entry, or all loaded entries when none is specified, to
recompute local-device and Tuya cloud role auto-mapping, and MUST error when a
requested entry is not loaded.

#### Scenario: Rebuild all entries
- **WHEN** the service is called without an entry id
- **THEN** all loaded TendrilGrow entries are reloaded to rebuild auto-mapping

#### Scenario: Unknown entry id
- **WHEN** the service is called with an entry id that is not loaded
- **THEN** the service raises an error identifying the missing entry

### Requirement: Tuya secret redaction
The integration MUST treat the Tuya access secret as sensitive: it SHALL store it
in config-entry data and redact it from logs and diagnostics.

#### Scenario: Secret redacted in diagnostics
- **WHEN** diagnostics are generated for a grow space using Tuya polling
- **THEN** the Tuya access secret is redacted from the output

### Requirement: Prefer local Tuya water source
Each grow space SHALL prefer a bound Home Assistant device from LocalTuya
(`localtuya`) over Tuya Local (`tuya_local`) over Tuya cloud polling as the
water-metric source. The bound device SHALL be stored as a Home Assistant device
registry id. When no local device is bound, the grow space MAY use cloud polling
or manual role mappings. The integration MUST NOT pick an arbitrary LocalTuya
sensor from the instance when more than one water monitor exists.

#### Scenario: LocalTuya device is bound
- **WHEN** a grow space has a bound `localtuya` water-monitor device
- **THEN** the integration uses that device's sensors for water roles and makes
  no Tuya cloud requests for that grow space

#### Scenario: Tuya Local used when LocalTuya is absent
- **WHEN** a grow space has a bound `tuya_local` device and no `localtuya` device
- **THEN** the integration uses that `tuya_local` device as the water-metric source

#### Scenario: Cloud fallback when no local device
- **WHEN** a grow space has no bound local water-monitor device and Tuya cloud
  polling is enabled with valid credentials and device ids
- **THEN** the integration polls the Tuya cloud as today

#### Scenario: Do not guess among multiple probes
- **WHEN** two LocalTuya water monitors exist and a grow space has no bound
  device id and no unique Tuya device-id match
- **THEN** the integration does not auto-bind either device

### Requirement: Match stored Tuya device ids to a local HA device
The integration SHALL attempt to bind a `localtuya` (then `tuya_local`) device whose
registry identifiers contain one of the stored Tuya device ids when a grow space
has stored Tuya device ids and no bound local device. It MUST bind only when
the match is unique for that grow space.

#### Scenario: Unique match auto-binds
- **WHEN** a grow space stores a Tuya device id that matches exactly one
  `localtuya` device in the registry
- **THEN** the integration binds that HA device and uses it as the local source

#### Scenario: Ambiguous match is left unbound
- **WHEN** a stored Tuya device id matches more than one local device or none
- **THEN** the integration leaves the local device unbound

### Requirement: Auto-map water roles from the bound local device
When a local water-monitor device is bound, the integration SHALL bind that
device's sensor entities to unmapped water-quality roles (`ph`, `ec`, `cf`,
`orp`, `tds`, `water_temperature`) using device class, unit of measurement, and
entity name, SHALL record those bindings in auto-mapped roles for diagnostics,
and MUST NOT bind the probe's ambient humidity or temperature onto the canopy
`humidity` or `temperature` roles. An already-mapped role MUST be left unchanged.

#### Scenario: Auto-map pH from the bound device
- **WHEN** the bound local device has a pH sensor and the grow space has no pH
  mapping
- **THEN** the integration binds the pH role to that entity id

#### Scenario: Do not override an existing mapping
- **WHEN** a grow-space water role is already mapped
- **THEN** the integration leaves the existing mapping unchanged

#### Scenario: Probe humidity is not canopy humidity
- **WHEN** the bound local device exposes a humidity sensor
- **THEN** the integration does not auto-map it onto the canopy `humidity` role

### Requirement: Diagnostics report the effective water source
Diagnostics for a grow space SHALL include the effective water source
(`localtuya`, `tuya_local`, `cloud`, or `none`) and the bound Home Assistant
device id when one is set.

#### Scenario: Local source in diagnostics
- **WHEN** diagnostics are generated for a grow space bound to a LocalTuya device
- **THEN** the payload reports water source `localtuya` and the bound device id

