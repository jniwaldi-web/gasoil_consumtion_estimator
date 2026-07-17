"""Constants for the Gasoil Consumption Estimator integration."""

from __future__ import annotations

from datetime import timedelta
from typing import Final

DOMAIN: Final = "gasoil_consumption_estimator"

# Config / options keys
CONF_ENERGY_SENSOR: Final = "energy_sensor"
CONF_TANK_CAPACITY: Final = "tank_capacity"
CONF_INITIAL_LITERS: Final = "initial_liters"
CONF_INITIAL_TIMESTAMP: Final = "initial_timestamp"
CONF_INITIAL_RATIO: Final = "initial_ratio"
CONF_NAME: Final = "name"
CONF_METER_ROLLOVER: Final = "meter_rollover"

URL_BASE: Final = "/gasoil_consumption_estimator"
CARD_FILENAME: Final = "gasoil-card.js"

CARD_RESOURCE_URL: Final = f"{URL_BASE}/{CARD_FILENAME}"

# Defaults
DEFAULT_NAME: Final = "Estimador gasoil"
DEFAULT_INITIAL_RATIO: Final = 0.1
DEFAULT_METER_ROLLOVER: Final = 10000

# Update interval for the coordinator
UPDATE_INTERVAL: Final = timedelta(seconds=30)

# Storage
STORAGE_VERSION: Final = 2
STORAGE_KEY_PREFIX: Final = DOMAIN

# Storage data keys
DATA_READINGS: Final = "readings"
DATA_ACTIVE_RATIO: Final = "active_ratio"
DATA_INITIAL_RATIO: Final = "initial_ratio"

# Reading fields
READING_TIMESTAMP: Final = "timestamp"
READING_FUEL: Final = "fuel_liters"
READING_ENERGY: Final = "energy_kwh"
READING_RAW: Final = "raw_liters"
READING_CUMULATIVE: Final = "cumulative_liters"

# Coordinator data keys
ATTR_ESTIMATED_TOTAL: Final = "estimated_total"
ATTR_ESTIMATED_SINCE_LAST: Final = "estimated_since_last"
ATTR_ACTIVE_RATIO: Final = "active_ratio"
ATTR_LAST_FUEL: Final = "last_fuel_liters"
ATTR_LAST_RAW: Final = "last_raw_liters"
ATTR_LAST_CUMULATIVE: Final = "last_cumulative_liters"
ATTR_LAST_TIMESTAMP: Final = "last_reading_time"
ATTR_CURRENT_ENERGY: Final = "current_energy_kwh"
ATTR_ESTIMATED_REMAINING: Final = "estimated_remaining"
ATTR_ESTIMATED_PERCENTAGE: Final = "estimated_percentage"

# Sensor keys
SENSOR_CONSUMED: Final = "estimated_gasoil_consumed"
SENSOR_SINCE_LAST: Final = "estimated_gasoil_since_last_reading"
SENSOR_RATIO: Final = "gasoil_liters_per_kwh"
SENSOR_LAST_READING: Final = "last_gasoil_manual_reading"
SENSOR_LAST_READING_TIME: Final = "last_gasoil_reading_time"
SENSOR_CURRENT_ENERGY: Final = "current_energy_kwh"
SENSOR_TOTAL_MEASURED: Final = "total_gasoil_measured"
SENSOR_REMAINING: Final = "estimated_gasoil_remaining"
SENSOR_PERCENTAGE: Final = "estimated_tank_percentage"

# Services
SERVICE_ADD_MANUAL_READING: Final = "add_manual_reading"
SERVICE_RESET_CALIBRATION: Final = "reset_calibration"

ATTR_LITERS: Final = "liters"
ATTR_TIMESTAMP: Final = "timestamp"
ATTR_CONFIG_ENTRY_ID: Final = "config_entry_id"

# Units
UNIT_LITERS: Final = "L"
UNIT_KWH: Final = "kWh"
UNIT_RATIO: Final = "L/kWh"
UNIT_PERCENTAGE: Final = "%"
