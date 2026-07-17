"""Sensor platform for the Gasoil Consumption Estimator."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import (
    ATTR_ACTIVE_RATIO,
    ATTR_CURRENT_ENERGY,
    ATTR_ESTIMATED_PERCENTAGE,
    ATTR_ESTIMATED_REMAINING,
    ATTR_ESTIMATED_SINCE_LAST,
    ATTR_ESTIMATED_TOTAL,
    ATTR_LAST_CUMULATIVE,
    ATTR_LAST_RAW,
    ATTR_LAST_TIMESTAMP,
    DOMAIN,
    SENSOR_CONSUMED,
    SENSOR_CURRENT_ENERGY,
    SENSOR_LAST_READING,
    SENSOR_LAST_READING_TIME,
    SENSOR_PERCENTAGE,
    SENSOR_RATIO,
    SENSOR_REMAINING,
    SENSOR_SINCE_LAST,
    SENSOR_TOTAL_MEASURED,
    UNIT_KWH,
    UNIT_LITERS,
    UNIT_PERCENTAGE,
    UNIT_RATIO,
)
from .coordinator import GasoilCoordinator


@dataclass(frozen=True, kw_only=True)
class GasoilSensorDescription(SensorEntityDescription):
    """Describe a gasoil sensor and how to read its value from coordinator data."""

    value_fn: Callable[[dict[str, Any]], Any]


def _as_datetime(value: Any) -> datetime | None:
    """Parse an ISO timestamp string into a datetime for timestamp sensors."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    return dt_util.parse_datetime(value)


SENSOR_DESCRIPTIONS: tuple[GasoilSensorDescription, ...] = (
    GasoilSensorDescription(
        key=SENSOR_CONSUMED,
        translation_key=SENSOR_CONSUMED,
        native_unit_of_measurement=UNIT_LITERS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:barrel",
        value_fn=lambda data: data.get(ATTR_ESTIMATED_TOTAL),
    ),
    GasoilSensorDescription(
        key=SENSOR_SINCE_LAST,
        translation_key=SENSOR_SINCE_LAST,
        native_unit_of_measurement=UNIT_LITERS,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:fuel",
        value_fn=lambda data: data.get(ATTR_ESTIMATED_SINCE_LAST),
    ),
    GasoilSensorDescription(
        key=SENSOR_RATIO,
        translation_key=SENSOR_RATIO,
        native_unit_of_measurement=UNIT_RATIO,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:scale-balance",
        value_fn=lambda data: data.get(ATTR_ACTIVE_RATIO),
    ),
    GasoilSensorDescription(
        key=SENSOR_LAST_READING,
        translation_key=SENSOR_LAST_READING,
        native_unit_of_measurement=UNIT_LITERS,
        icon="mdi:counter",
        value_fn=lambda data: data.get(ATTR_LAST_RAW),
    ),
    GasoilSensorDescription(
        key=SENSOR_TOTAL_MEASURED,
        translation_key=SENSOR_TOTAL_MEASURED,
        native_unit_of_measurement=UNIT_LITERS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:counter",
        value_fn=lambda data: data.get(ATTR_LAST_CUMULATIVE),
    ),
    GasoilSensorDescription(
        key=SENSOR_LAST_READING_TIME,
        translation_key=SENSOR_LAST_READING_TIME,
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:clock-outline",
        value_fn=lambda data: _as_datetime(data.get(ATTR_LAST_TIMESTAMP)),
    ),
    GasoilSensorDescription(
        key=SENSOR_CURRENT_ENERGY,
        translation_key=SENSOR_CURRENT_ENERGY,
        native_unit_of_measurement=UNIT_KWH,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:lightning-bolt",
        value_fn=lambda data: data.get(ATTR_CURRENT_ENERGY),
    ),
)

# Extra descriptions only added when a tank capacity is configured.
TANK_SENSOR_DESCRIPTIONS: tuple[GasoilSensorDescription, ...] = (
    GasoilSensorDescription(
        key=SENSOR_REMAINING,
        translation_key=SENSOR_REMAINING,
        native_unit_of_measurement=UNIT_LITERS,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:gauge",
        value_fn=lambda data: data.get(ATTR_ESTIMATED_REMAINING),
    ),
    GasoilSensorDescription(
        key=SENSOR_PERCENTAGE,
        translation_key=SENSOR_PERCENTAGE,
        native_unit_of_measurement=UNIT_PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:gauge",
        value_fn=lambda data: data.get(ATTR_ESTIMATED_PERCENTAGE),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up gasoil sensors for a config entry."""
    coordinator: GasoilCoordinator = hass.data[DOMAIN][entry.entry_id]

    descriptions = list(SENSOR_DESCRIPTIONS)
    if coordinator.tank_capacity is not None and coordinator.tank_capacity > 0:
        descriptions.extend(TANK_SENSOR_DESCRIPTIONS)

    async_add_entities(
        GasoilSensor(coordinator, entry, description)
        for description in descriptions
    )


class GasoilSensor(CoordinatorEntity[GasoilCoordinator], SensorEntity):
    """A sensor exposing one estimated gasoil value."""

    _attr_has_entity_name = True
    entity_description: GasoilSensorDescription

    def __init__(
        self,
        coordinator: GasoilCoordinator,
        entry: ConfigEntry,
        description: GasoilSensorDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        name = entry.data.get("name") or entry.title
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=name,
            manufacturer="Gasoil Consumption Estimator",
            model="Estimador de consumo de gasoil",
        )

    @property
    def native_value(self) -> Any:
        """Return the current value from the coordinator data."""
        data = self.coordinator.data or {}
        return self.entity_description.value_fn(data)
