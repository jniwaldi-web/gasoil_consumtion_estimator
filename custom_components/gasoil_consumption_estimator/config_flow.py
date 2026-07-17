"""Config and options flow for the Gasoil Consumption Estimator."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers import selector
from homeassistant.util import dt as dt_util

from .const import (
    CONF_ENERGY_SENSOR,
    CONF_INITIAL_LITERS,
    CONF_INITIAL_RATIO,
    CONF_INITIAL_TIMESTAMP,
    CONF_METER_ROLLOVER,
    CONF_NAME,
    CONF_TANK_CAPACITY,
    DEFAULT_INITIAL_RATIO,
    DEFAULT_METER_ROLLOVER,
    DEFAULT_NAME,
    DOMAIN,
)


def _energy_sensor_selector() -> selector.EntitySelector:
    """Return a selector limited to energy sensors."""
    return selector.EntitySelector(
        selector.EntitySelectorConfig(
            domain="sensor", device_class="energy"
        )
    )


def _liters_number_selector() -> selector.NumberSelector:
    """Return a number selector for liter values."""
    return selector.NumberSelector(
        selector.NumberSelectorConfig(
            min=0, step=0.1, unit_of_measurement="L", mode=selector.NumberSelectorMode.BOX
        )
    )


def _ratio_number_selector() -> selector.NumberSelector:
    """Return a number selector for the liters/kWh ratio."""
    return selector.NumberSelector(
        selector.NumberSelectorConfig(
            min=0,
            step=0.001,
            unit_of_measurement="L/kWh",
            mode=selector.NumberSelectorMode.BOX,
        )
    )


def _rollover_number_selector() -> selector.NumberSelector:
    """Return a number selector for the meter rollover modulus."""
    return selector.NumberSelector(
        selector.NumberSelectorConfig(
            min=0,
            step=1,
            unit_of_measurement="L",
            mode=selector.NumberSelectorMode.BOX,
        )
    )


class GasoilConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the initial configuration flow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the user step of the config flow."""
        errors: dict[str, str] = {}

        if user_input is not None:
            name = user_input.get(CONF_NAME) or DEFAULT_NAME
            data = {
                CONF_ENERGY_SENSOR: user_input[CONF_ENERGY_SENSOR],
                CONF_NAME: name,
                CONF_INITIAL_RATIO: user_input.get(
                    CONF_INITIAL_RATIO, DEFAULT_INITIAL_RATIO
                ),
            }
            if user_input.get(CONF_TANK_CAPACITY) not in (None, ""):
                data[CONF_TANK_CAPACITY] = user_input[CONF_TANK_CAPACITY]
            if user_input.get(CONF_INITIAL_LITERS) not in (None, ""):
                data[CONF_INITIAL_LITERS] = user_input[CONF_INITIAL_LITERS]
            if user_input.get(CONF_INITIAL_TIMESTAMP) not in (None, ""):
                data[CONF_INITIAL_TIMESTAMP] = user_input[CONF_INITIAL_TIMESTAMP]
            data[CONF_METER_ROLLOVER] = user_input.get(
                CONF_METER_ROLLOVER, DEFAULT_METER_ROLLOVER
            )

            return self.async_create_entry(title=name, data=data)

        schema = vol.Schema(
            {
                vol.Required(CONF_ENERGY_SENSOR): _energy_sensor_selector(),
                vol.Optional(CONF_NAME, default=DEFAULT_NAME): selector.TextSelector(),
                vol.Optional(CONF_TANK_CAPACITY): _liters_number_selector(),
                vol.Optional(CONF_INITIAL_LITERS): _liters_number_selector(),
                vol.Optional(CONF_INITIAL_TIMESTAMP): selector.DateTimeSelector(),
                vol.Optional(
                    CONF_INITIAL_RATIO, default=DEFAULT_INITIAL_RATIO
                ): _ratio_number_selector(),
                vol.Optional(
                    CONF_METER_ROLLOVER, default=DEFAULT_METER_ROLLOVER
                ): _rollover_number_selector(),
            }
        )

        return self.async_show_form(
            step_id="user", data_schema=schema, errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> GasoilOptionsFlow:
        """Return the options flow handler."""
        return GasoilOptionsFlow(config_entry)


class GasoilOptionsFlow(OptionsFlow):
    """Handle editing options after setup."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Store the config entry."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the editable options."""
        if user_input is not None:
            options = {
                CONF_ENERGY_SENSOR: user_input[CONF_ENERGY_SENSOR],
                CONF_NAME: user_input.get(CONF_NAME) or DEFAULT_NAME,
                CONF_INITIAL_RATIO: user_input.get(
                    CONF_INITIAL_RATIO, DEFAULT_INITIAL_RATIO
                ),
            }
            if user_input.get(CONF_TANK_CAPACITY) not in (None, ""):
                options[CONF_TANK_CAPACITY] = user_input[CONF_TANK_CAPACITY]
            options[CONF_METER_ROLLOVER] = user_input.get(
                CONF_METER_ROLLOVER, DEFAULT_METER_ROLLOVER
            )
            return self.async_create_entry(title="", data=options)

        current = {**self.config_entry.data, **self.config_entry.options}

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_ENERGY_SENSOR,
                    default=current.get(CONF_ENERGY_SENSOR),
                ): _energy_sensor_selector(),
                vol.Optional(
                    CONF_NAME,
                    default=current.get(CONF_NAME, DEFAULT_NAME),
                ): selector.TextSelector(),
                vol.Optional(
                    CONF_TANK_CAPACITY,
                    description={
                        "suggested_value": current.get(CONF_TANK_CAPACITY)
                    },
                ): _liters_number_selector(),
                vol.Optional(
                    CONF_INITIAL_RATIO,
                    default=current.get(CONF_INITIAL_RATIO, DEFAULT_INITIAL_RATIO),
                ): _ratio_number_selector(),
                vol.Optional(
                    CONF_METER_ROLLOVER,
                    description={
                        "suggested_value": current.get(
                            CONF_METER_ROLLOVER, DEFAULT_METER_ROLLOVER
                        )
                    },
                ): _rollover_number_selector(),
            }
        )

        return self.async_show_form(step_id="init", data_schema=schema)
