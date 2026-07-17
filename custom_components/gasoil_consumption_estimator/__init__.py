"""The Gasoil Consumption Estimator integration."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.util import dt as dt_util

from .const import (
    ATTR_CONFIG_ENTRY_ID,
    ATTR_LITERS,
    ATTR_TIMESTAMP,
    CONF_INITIAL_LITERS,
    CONF_INITIAL_TIMESTAMP,
    DOMAIN,
    SERVICE_ADD_MANUAL_READING,
    SERVICE_RESET_CALIBRATION,
)
from .frontend import async_register_frontend 
from .coordinator import GasoilCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]

ADD_MANUAL_READING_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_LITERS): vol.Coerce(float),
        vol.Optional(ATTR_TIMESTAMP): cv.datetime,
        vol.Optional(ATTR_CONFIG_ENTRY_ID): cv.string,
    }
)

RESET_CALIBRATION_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_CONFIG_ENTRY_ID): cv.string,
    }
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Gasoil Consumption Estimator from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    coordinator = GasoilCoordinator(hass, entry)
    await coordinator.async_load()

    # Seed an initial reading if provided and no readings exist yet.
    if coordinator.store.get_last_reading() is None:
        await _maybe_seed_initial_reading(hass, entry, coordinator)



    await async_register_frontend(hass)
 
    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    _async_register_services(hass)

    return True


async def _maybe_seed_initial_reading(
    hass: HomeAssistant, entry: ConfigEntry, coordinator: GasoilCoordinator
) -> None:
    """Create the first reading from the config data, if provided."""
    initial_liters = entry.data.get(CONF_INITIAL_LITERS)
    if initial_liters in (None, ""):
        return

    raw_ts = entry.data.get(CONF_INITIAL_TIMESTAMP)
    timestamp: datetime | None = None
    if raw_ts not in (None, ""):
        timestamp = (
            raw_ts if isinstance(raw_ts, datetime) else dt_util.parse_datetime(raw_ts)
        )

    try:
        await coordinator.add_manual_reading(float(initial_liters), timestamp)
    except HomeAssistantError as err:
        _LOGGER.warning(
            "No se pudo registrar la lectura inicial de gasoil: %s", err
        )


def _resolve_coordinator(
    hass: HomeAssistant, entry_id: str | None
) -> GasoilCoordinator:
    """Resolve the target coordinator from a service call."""
    entries: dict[str, GasoilCoordinator] = hass.data.get(DOMAIN, {})
    if not entries:
        raise HomeAssistantError(
            "No hay ninguna instancia del Estimador de gasoil configurada."
        )

    if entry_id:
        coordinator = entries.get(entry_id)
        if coordinator is None:
            raise HomeAssistantError(
                f"No se encontró la instancia con config_entry_id '{entry_id}'."
            )
        return coordinator

    if len(entries) == 1:
        return next(iter(entries.values()))

    raise HomeAssistantError(
        "Hay varias instancias configuradas; especifica 'config_entry_id' "
        "en la llamada al servicio."
    )


def _async_register_services(hass: HomeAssistant) -> None:
    """Register domain services once (shared across all config entries)."""
    if hass.services.has_service(DOMAIN, SERVICE_ADD_MANUAL_READING):
        return

    async def _handle_add_manual_reading(call: ServiceCall) -> None:
        """Handle the add_manual_reading service call."""
        coordinator = _resolve_coordinator(
            hass, call.data.get(ATTR_CONFIG_ENTRY_ID)
        )
        liters: float = call.data[ATTR_LITERS]
        timestamp: datetime | None = call.data.get(ATTR_TIMESTAMP)
        await coordinator.add_manual_reading(liters, timestamp)

    async def _handle_reset_calibration(call: ServiceCall) -> None:
        """Handle the reset_calibration service call."""
        coordinator = _resolve_coordinator(
            hass, call.data.get(ATTR_CONFIG_ENTRY_ID)
        )
        await coordinator.reset_calibration()

    hass.services.async_register(
        DOMAIN,
        SERVICE_ADD_MANUAL_READING,
        _handle_add_manual_reading,
        schema=ADD_MANUAL_READING_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_RESET_CALIBRATION,
        _handle_reset_calibration,
        schema=RESET_CALIBRATION_SCHEMA,
    )


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the entry when options change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)

        # Remove services only when the last entry is unloaded.
        if not hass.data[DOMAIN]:
            hass.services.async_remove(DOMAIN, SERVICE_ADD_MANUAL_READING)
            hass.services.async_remove(DOMAIN, SERVICE_RESET_CALIBRATION)

    return unload_ok


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Remove the persisted storage when the entry is deleted."""
    from .storage import GasoilStore

    store = GasoilStore(hass, entry.entry_id, 0.0)
    await store.async_remove()
