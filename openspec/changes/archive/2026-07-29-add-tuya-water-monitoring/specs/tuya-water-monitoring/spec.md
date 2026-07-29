## ADDED Requirements

### Requirement: Optional Tuya cloud polling per grow space
Each grow space SHALL support an optional Tuya cloud polling source that the user
enables and configures with Tuya IoT access id, access secret, region, an optional
user UID, one or more device ids, and a poll interval. When Tuya polling is
disabled the grow space MUST operate normally with no Tuya calls.

#### Scenario: Enable Tuya polling
- **WHEN** the user enables Tuya polling and provides valid credentials and device ids
- **THEN** the integration polls those devices on the configured interval and
  exposes their readings as sensors

#### Scenario: Tuya polling left disabled
- **WHEN** the user does not enable Tuya polling
- **THEN** no Tuya cloud requests are made and the grow space still functions

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
The integration SHALL create one sensor entity per device per available metric and
a per-device diagnostic "last updated" timestamp sensor, each grouped under a Home
Assistant device representing the Tuya probe, and each reporting unavailable when
its metric is absent from the latest reading.

#### Scenario: Metric entities created per device
- **WHEN** a device returns pH, EC, and TDS readings
- **THEN** the integration exposes pH, EC, and TDS sensor entities for that device

#### Scenario: Missing metric is unavailable
- **WHEN** the latest reading omits a metric for a device
- **THEN** that metric's sensor reports unavailable

### Requirement: Automatic role mapping from Tuya entities
When Tuya polling is enabled the integration SHALL hide the manual water-quality
sensor-mapping fields (the camera role remains manual) and SHALL bind each Tuya
metric entity to its matching grow-space sensor role when that role is unmapped,
recording the auto-mapped roles for diagnostics.

#### Scenario: Auto-map an unmapped role
- **WHEN** a Tuya pH entity is added and the grow space has no pH mapping
- **THEN** the integration binds the pH role to that entity id

#### Scenario: Do not override an existing mapping
- **WHEN** a grow-space role is already mapped
- **THEN** the integration leaves the existing mapping unchanged

### Requirement: Rebuild auto-mapping service
The integration SHALL provide a `rebuild_automap` service that reloads a specified
loaded grow-space entry, or all loaded entries when none is specified, to
recompute Tuya role auto-mapping, and MUST error when a requested entry is not
loaded.

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
