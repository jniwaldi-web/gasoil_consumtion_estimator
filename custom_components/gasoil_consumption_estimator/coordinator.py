"""Data update coordinator for the Gasoil Consumption Estimator."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant, State
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import (
    ATTR_ACTIVE_RATIO,
    ATTR_CURRENT_ENERGY,
    ATTR_ESTIMATED_PERCENTAGE,
    ATTR_ESTIMATED_REMAINING,
    ATTR_ESTIMATED_SINCE_LAST,
    ATTR_ESTIMATED_TOTAL,
    ATTR_LAST_CUMULATIVE,
    ATTR_LAST_FUEL,
    ATTR_LAST_RAW,
    ATTR_LAST_TIMESTAMP,
    CONF_ENERGY_SENSOR,
    CONF_INITIAL_RATIO,
    CONF_METER_ROLLOVER,
    CONF_TANK_CAPACITY,
    DEFAULT_INITIAL_RATIO,
    DEFAULT_METER_ROLLOVER,
    DOMAIN,
    READING_CUMULATIVE,
    READING_ENERGY,
    READING_RAW,
    READING_TIMESTAMP,
    UPDATE_INTERVAL,
)
from .storage import GasoilStore

_LOGGER = logging.getLogger(__name__)


def _get_option(entry: ConfigEntry, key: str, default: Any = None) -> Any:
    """Return an option preferring options over data."""
    if key in entry.options:
        return entry.options[key]
    return entry.data.get(key, default)


class GasoilCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinate reading the energy sensor and computing the estimation."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{entry.entry_id}",
            update_interval=UPDATE_INTERVAL,
        )
        self.entry = entry
        initial_ratio = float(
            _get_option(entry, CONF_INITIAL_RATIO, DEFAULT_INITIAL_RATIO)
        )
        self.store = GasoilStore(hass, entry.entry_id, initial_ratio)
        self._last_estimate: dict[str, Any] | None = None

    @property
    def energy_sensor(self) -> str:
        """Return the configured energy sensor entity_id."""
        return _get_option(self.entry, CONF_ENERGY_SENSOR)

    @property
    def tank_capacity(self) -> float | None:
        """Return the configured tank capacity in liters, if any."""
        value = _get_option(self.entry, CONF_TANK_CAPACITY)
        if value in (None, ""):
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @property
    def meter_rollover(self) -> float:
        """Return the meter rollover modulus (display wraps back to 0 at it)."""
        value = _get_option(self.entry, CONF_METER_ROLLOVER, DEFAULT_METER_ROLLOVER)
        try:
            rollover = float(value)
        except (TypeError, ValueError):
            return float(DEFAULT_METER_ROLLOVER)
        return rollover if rollover > 0 else float(DEFAULT_METER_ROLLOVER)

    async def async_load(self) -> None:
        """Load persisted data from disk."""
        await self.store.async_load()

    def _read_energy_state(self) -> float | None:
        """Read the current energy sensor value as float kWh, or None."""
        state: State | None = self.hass.states.get(self.energy_sensor)
        if state is None:
            return None
        if state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN, None, ""):
            return None
        try:
            return float(state.state)
        except (TypeError, ValueError):
            _LOGGER.warning(
                "El sensor de energía %s tiene un estado no numérico: %s",
                self.energy_sensor,
                state.state,
            )
            return None

    async def _async_update_data(self) -> dict[str, Any]:
        """Compute the current estimation from the latest energy reading."""
        current_energy = self._read_energy_state()

        # If the sensor is unavailable keep the previous estimate to avoid
        # spurious drops to zero.
        if current_energy is None and self._last_estimate is not None:
            return self._last_estimate

        last = self.store.get_last_reading()
        active_ratio = self.store.active_ratio

        if last is not None:
            last_cumulative = float(last[READING_CUMULATIVE])
            last_raw = float(last[READING_RAW])
            last_energy = float(last[READING_ENERGY])
            last_timestamp = last[READING_TIMESTAMP]
        else:
            last_cumulative = 0.0
            last_raw = 0.0
            last_energy = current_energy if current_energy is not None else 0.0
            last_timestamp = None

        if current_energy is None:
            # No prior estimate and no reading: report the last known total.
            estimated_total = last_cumulative
        else:
            estimated_total = (
                last_cumulative + (current_energy - last_energy) * active_ratio
            )

        since_last = estimated_total - last_cumulative

        data: dict[str, Any] = {
            ATTR_ESTIMATED_TOTAL: round(estimated_total, 3),
            ATTR_ESTIMATED_SINCE_LAST: round(since_last, 3),
            ATTR_ACTIVE_RATIO: round(active_ratio, 6),
            ATTR_LAST_FUEL: round(last_cumulative, 3),
            ATTR_LAST_RAW: round(last_raw, 3),
            ATTR_LAST_CUMULATIVE: round(last_cumulative, 3),
            ATTR_LAST_TIMESTAMP: last_timestamp,
            ATTR_CURRENT_ENERGY: (
                round(current_energy, 3) if current_energy is not None else None
            ),
        }

        capacity = self.tank_capacity
        if capacity is not None and capacity > 0:
            remaining = capacity - estimated_total
            data[ATTR_ESTIMATED_REMAINING] = round(remaining, 3)
            data[ATTR_ESTIMATED_PERCENTAGE] = round(remaining / capacity * 100, 2)

        self._last_estimate = data
        return data

    async def _async_resolve_energy_at(self, when: datetime) -> float:
        """Resolve the energy sensor value (kWh) at a historical timestamp.

        Tries the statistics table first (for sensors with state_class) and
        falls back to the recorder history. Raises HomeAssistantError in Spanish
        when no data can be found.
        """
        from homeassistant.components.recorder import get_instance
        from homeassistant.components.recorder.history import (
            get_last_state_changes,
            state_changes_during_period,
        )
        from homeassistant.components.recorder.statistics import (
            statistics_during_period,
        )

        entity_id = self.energy_sensor
        when_utc = when.astimezone(dt_util.UTC)
        recorder = get_instance(self.hass)

        # 1) Try long-term / short-term statistics around the timestamp.
        start = when_utc - timedelta(hours=2)
        end = when_utc + timedelta(hours=2)

        def _query_statistics() -> dict[str, list[dict[str, Any]]]:
            return statistics_during_period(
                self.hass,
                start,
                end,
                {entity_id},
                "hour",
                None,
                {"state", "sum", "mean"},
            )

        try:
            stats = await recorder.async_add_executor_job(_query_statistics)
        except Exception as err:  # noqa: BLE001 - statistics may be unavailable
            _LOGGER.debug("Fallo consultando statistics para %s: %s", entity_id, err)
            stats = {}

        value = self._closest_statistic(stats.get(entity_id, []), when_utc)
        if value is not None:
            return value

        # 2) Fall back to recorder history state changes in a window.
        hist_start = when_utc - timedelta(days=2)

        def _query_history() -> dict[str, list[State]]:
            return state_changes_during_period(
                self.hass,
                hist_start,
                when_utc,
                entity_id,
                include_start_time_state=True,
            )

        try:
            history = await recorder.async_add_executor_job(_query_history)
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Fallo consultando history para %s: %s", entity_id, err)
            history = {}

        value = self._last_numeric_state(history.get(entity_id, []))
        if value is not None:
            return value

        # 3) Last resort: last recorded state changes overall.
        def _query_last() -> dict[str, list[State]]:
            return get_last_state_changes(self.hass, 1, entity_id)

        try:
            last_changes = await recorder.async_add_executor_job(_query_last)
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Fallo consultando last_state_changes: %s", err)
            last_changes = {}

        value = self._last_numeric_state(last_changes.get(entity_id, []))
        if value is not None:
            return value

        raise HomeAssistantError(
            f"No se encontraron datos históricos del sensor de energía "
            f"'{entity_id}' para la fecha {when.isoformat()}. Asegúrate de que "
            f"el sensor tenía datos registrados en ese momento."
        )

    @staticmethod
    def _closest_statistic(
        rows: list[dict[str, Any]], when_utc: datetime
    ) -> float | None:
        """Return the numeric value of the statistic row closest to when_utc."""
        best: float | None = None
        best_delta: float | None = None
        for row in rows:
            raw = row.get("state")
            if raw is None:
                raw = row.get("mean")
            if raw is None:
                continue
            try:
                candidate = float(raw)
            except (TypeError, ValueError):
                continue
            row_start = row.get("start")
            if isinstance(row_start, (int, float)):
                row_time = dt_util.utc_from_timestamp(float(row_start))
            elif isinstance(row_start, datetime):
                row_time = row_start
            else:
                row_time = when_utc
            delta = abs((row_time - when_utc).total_seconds())
            if best_delta is None or delta < best_delta:
                best = candidate
                best_delta = delta
        return best

    @staticmethod
    def _last_numeric_state(states: list[State]) -> float | None:
        """Return the last numeric state value from a list of states."""
        for state in reversed(states):
            if state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN, None, ""):
                continue
            try:
                return float(state.state)
            except (TypeError, ValueError):
                continue
        return None

    async def add_manual_reading(
        self, liters: float, timestamp: datetime | None = None
    ) -> None:
        """Add a manual fuel reading, resolving historical energy if needed."""
        if timestamp is None:
            energy = self._read_energy_state()
            if energy is None:
                raise HomeAssistantError(
                    f"El sensor de energía '{self.energy_sensor}' no está "
                    f"disponible o su estado no es numérico; no se puede "
                    f"registrar la lectura."
                )
            when = dt_util.utcnow()
        else:
            when = timestamp
            if when.tzinfo is None:
                when = when.replace(tzinfo=dt_util.DEFAULT_TIME_ZONE)
            now = dt_util.utcnow()
            # Treat timestamps within ~2 min of now as "now".
            if abs((when.astimezone(dt_util.UTC) - now).total_seconds()) <= 120:
                energy = self._read_energy_state()
                if energy is None:
                    raise HomeAssistantError(
                        f"El sensor de energía '{self.energy_sensor}' no está "
                        f"disponible; no se puede registrar la lectura."
                    )
            else:
                energy = await self._async_resolve_energy_at(when)

        await self.store.add_reading(when, liters, energy, self.meter_rollover)
        await self.async_request_refresh()

    async def reset_calibration(self) -> None:
        """Clear all readings and reset the ratio."""
        await self.store.async_reset()
        await self.async_request_refresh()

    def update_initial_ratio_from_entry(self) -> None:
        """Refresh the initial ratio from the (possibly updated) config entry."""
        initial_ratio = float(
            _get_option(self.entry, CONF_INITIAL_RATIO, DEFAULT_INITIAL_RATIO)
        )
        self.store.set_initial_ratio(initial_ratio)
