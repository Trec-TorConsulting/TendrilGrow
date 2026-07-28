"""Grow space domain models."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from math import exp
from typing import Any
from uuid import uuid4

from ..const import CONTROL_ROLES, SENSOR_ROLE_EC_TDS_LEGACY, SENSOR_ROLE_TDS, SENSOR_ROLES


@dataclass(slots=True)
class GrowSite:
    """A plant site or position within a grow space."""

    site_id: str
    name: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class GrowSpace:
    """Configuration and mappings for one grow space."""

    space_id: str
    name: str
    grow_type: str
    descriptor: str = ""
    sites: list[GrowSite] = field(default_factory=list)
    sensor_mappings: dict[str, str] = field(default_factory=dict)
    control_mappings: dict[str, str] = field(default_factory=dict)
    targets: dict[str, Any] = field(default_factory=dict)
    schedules: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def new(
        cls,
        name: str,
        grow_type: str,
        descriptor: str = "",
        *,
        sites: list[GrowSite] | None = None,
    ) -> "GrowSpace":
        """Build a new grow space with a stable generated id."""
        return cls(
            space_id=str(uuid4()),
            name=name,
            grow_type=grow_type,
            descriptor=descriptor,
            sites=sites or [],
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize the model into config-entry-safe data."""
        return {
            "space_id": self.space_id,
            "name": self.name,
            "grow_type": self.grow_type,
            "grow_size": self.descriptor,
            "descriptor": self.descriptor,
            "sites": [asdict(site) for site in self.sites],
            "sensor_mappings": self.sensor_mappings,
            "control_mappings": self.control_mappings,
            "targets": self.targets,
            "schedules": self.schedules,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "GrowSpace":
        """Deserialize a grow space from config-entry data."""
        sensor_mappings = dict(value.get("sensor_mappings", {}))
        # Migrate legacy combined EC/TDS role to a dedicated TDS role.
        if SENSOR_ROLE_EC_TDS_LEGACY in sensor_mappings and SENSOR_ROLE_TDS not in sensor_mappings:
            sensor_mappings[SENSOR_ROLE_TDS] = sensor_mappings[SENSOR_ROLE_EC_TDS_LEGACY]

        return cls(
            space_id=value["space_id"],
            name=value["name"],
            grow_type=value["grow_type"],
            descriptor=value.get("grow_size", value.get("descriptor", "")),
            sites=[GrowSite(**site) for site in value.get("sites", [])],
            sensor_mappings=sensor_mappings,
            control_mappings=dict(value.get("control_mappings", {})),
            targets=dict(value.get("targets", {})),
            schedules=dict(value.get("schedules", {})),
        )

    def bind_sensor(self, role: str, entity_id: str) -> None:
        """Bind a configured sensor role to an entity id."""
        if role not in SENSOR_ROLES:
            raise ValueError(f"Unsupported sensor role: {role}")
        self.sensor_mappings[role] = entity_id

    def bind_control(self, role: str, entity_id: str) -> None:
        """Bind a configured control role to an entity id."""
        if role not in CONTROL_ROLES:
            raise ValueError(f"Unsupported control role: {role}")
        self.control_mappings[role] = entity_id

    @staticmethod
    def compute_vpd_c_kpa(temperature_c: float | None, humidity_pct: float | None) -> float | None:
        """Compute vapor pressure deficit in kPa from C and relative humidity.

        Returns None when inputs are missing or out of reasonable range.
        """
        if temperature_c is None or humidity_pct is None:
            return None
        if humidity_pct <= 0 or humidity_pct > 100:
            return None

        sat_vapor_pressure = 0.6108 * exp((17.27 * temperature_c) / (temperature_c + 237.3))
        return sat_vapor_pressure * (1 - (humidity_pct / 100.0))
