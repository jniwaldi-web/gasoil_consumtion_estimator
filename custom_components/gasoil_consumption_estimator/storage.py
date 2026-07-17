"""Persistent storage and calibration logic for the Gasoil Consumption Estimator."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import (
    DATA_ACTIVE_RATIO,
    DATA_INITIAL_RATIO,
    DATA_READINGS,
    DEFAULT_METER_ROLLOVER,
    READING_CUMULATIVE,
    READING_ENERGY,
    READING_FUEL,
    READING_RAW,
    READING_TIMESTAMP,
    STORAGE_KEY_PREFIX,
    STORAGE_VERSION,
)

_LOGGER = logging.getLogger(__name__)


class GasoilStore:
    """Wrapper around Home Assistant's Store for one config entry.

    Keeps a list of manual fuel readings and the calibrated ratio persisted to
    disk, and provides the calibration algorithm on top of them.
    """

    def __init__(
        self, hass: HomeAssistant, entry_id: str, initial_ratio: float
    ) -> None:
        """Initialize the store for a given config entry."""
        self._hass = hass
        self._entry_id = entry_id
        self._initial_ratio = initial_ratio
        self._store: Store[dict[str, Any]] = Store(
            hass, STORAGE_VERSION, f"{STORAGE_KEY_PREFIX}.{entry_id}"
        )
        self._data: dict[str, Any] = {
            DATA_READINGS: [],
            DATA_ACTIVE_RATIO: initial_ratio,
            DATA_INITIAL_RATIO: initial_ratio,
        }

    async def async_load(self) -> dict[str, Any]:
        """Load data from disk, initializing defaults when empty."""
        stored = await self._store.async_load()
        if stored is not None:
            self._data = {
                DATA_READINGS: stored.get(DATA_READINGS, []),
                DATA_ACTIVE_RATIO: stored.get(
                    DATA_ACTIVE_RATIO, self._initial_ratio
                ),
                DATA_INITIAL_RATIO: stored.get(
                    DATA_INITIAL_RATIO, self._initial_ratio
                ),
            }
            self._migrate_readings()
        self._sort_readings()
        return self._data

    def _migrate_readings(self) -> None:
        """Migrate v1 readings (fuel_liters only) to v2 (raw + cumulative).

        Old readings stored a single ``fuel_liters`` value. Treat it as both the
        raw meter value and the cumulative total so calibration keeps working.
        """
        for reading in self._data.get(DATA_READINGS, []):
            if READING_RAW not in reading or READING_CUMULATIVE not in reading:
                base = reading.get(
                    READING_FUEL,
                    reading.get(READING_RAW, reading.get(READING_CUMULATIVE, 0.0)),
                )
                base = float(base)
                reading.setdefault(READING_RAW, base)
                reading.setdefault(READING_CUMULATIVE, base)

    async def async_save(self, data: dict[str, Any] | None = None) -> None:
        """Persist the current (or provided) data to disk."""
        if data is not None:
            self._data = data
        await self._store.async_save(self._data)

    @property
    def data(self) -> dict[str, Any]:
        """Return the in-memory data structure."""
        return self._data

    @property
    def initial_ratio(self) -> float:
        """Return the configured initial ratio."""
        return float(self._data.get(DATA_INITIAL_RATIO, self._initial_ratio))

    @property
    def active_ratio(self) -> float:
        """Return the currently active (calibrated) ratio."""
        return float(self._data.get(DATA_ACTIVE_RATIO, self.initial_ratio))

    @property
    def readings(self) -> list[dict[str, Any]]:
        """Return the list of stored readings ordered by timestamp."""
        return self._data.get(DATA_READINGS, [])

    def set_initial_ratio(self, initial_ratio: float) -> None:
        """Update the initial ratio (e.g. from an options flow change)."""
        self._initial_ratio = initial_ratio
        self._data[DATA_INITIAL_RATIO] = initial_ratio

    def _sort_readings(self) -> None:
        """Sort readings ascending by timestamp string (ISO 8601 sorts well)."""
        self._data[DATA_READINGS] = sorted(
            self._data.get(DATA_READINGS, []),
            key=lambda r: r[READING_TIMESTAMP],
        )

    def get_last_reading(self) -> dict[str, Any] | None:
        """Return the most recent reading, or None if there are none."""
        readings = self.readings
        if not readings:
            return None
        return readings[-1]

    async def add_reading(
        self,
        timestamp: datetime,
        raw_liters: float,
        energy_kwh: float,
        meter_rollover: float = DEFAULT_METER_ROLLOVER,
    ) -> None:
        """Insert or replace a reading, recalibrate and persist.

        ``raw_liters`` is the value shown by the physical meter (0..rollover-1).
        The real cumulative total is derived using rollover-aware deltas so it
        stays monotonically increasing across meter resets. If a reading with
        the same ISO timestamp already exists it is replaced.
        """
        iso = timestamp.astimezone(dt_util.UTC).isoformat()
        raw = float(raw_liters)

        # Cumulative is provisional here; it is recomputed for the whole ordered
        # list below so out-of-order (historical) inserts stay correct.
        reading = {
            READING_TIMESTAMP: iso,
            READING_RAW: raw,
            READING_CUMULATIVE: raw,
            # Keep fuel_liters mirroring cumulative for backwards compatibility.
            READING_FUEL: raw,
            READING_ENERGY: float(energy_kwh),
        }

        readings = self._data.get(DATA_READINGS, [])
        for index, existing in enumerate(readings):
            if existing[READING_TIMESTAMP] == iso:
                readings[index] = reading
                break
        else:
            readings.append(reading)

        self._data[DATA_READINGS] = readings
        self._sort_readings()
        self._recompute_cumulatives(meter_rollover)
        self.recalculate_ratio()
        await self.async_save()

    def _recompute_cumulatives(self, meter_rollover: float) -> None:
        """Recompute cumulative totals for all readings in timestamp order.

        Walks the sorted list from the first reading so that inserting a reading
        with a past timestamp still yields a monotonic cumulative total:
        - readings[0].cumulative = readings[0].raw
        - readings[i].cumulative = readings[i-1].cumulative
              + _rollover_delta(readings[i-1].raw, readings[i].raw, modulus)
        """
        readings = self.readings
        prev_raw: float | None = None
        prev_cumulative = 0.0
        for reading in readings:
            raw = float(reading[READING_RAW])
            if prev_raw is None:
                cumulative = raw
            else:
                cumulative = prev_cumulative + self._rollover_delta(
                    prev_raw, raw, meter_rollover
                )
            reading[READING_CUMULATIVE] = cumulative
            reading[READING_FUEL] = cumulative
            prev_raw = raw
            prev_cumulative = cumulative

    @staticmethod
    def _rollover_delta(prev: float, cur: float, modulus: float) -> float:
        """Return the consumed delta between two meter displays, handling reset.

        If ``cur >= prev`` the meter did not wrap: delta = cur - prev.
        Otherwise it rolled over: delta = (modulus - prev) + cur.
        """
        if cur >= prev:
            return cur - prev
        return (modulus - prev) + cur

    def recalculate_ratio(self) -> float:
        """Recalculate the active ratio as a weighted average over segments.

        ratio = sum(fuel_delta) / sum(energy_delta) over all consecutive
        segments where both fuel and energy strictly increase. Falls back to the
        initial ratio when fewer than two valid readings exist.
        """
        readings = self.readings
        if len(readings) < 2:
            self._data[DATA_ACTIVE_RATIO] = self.initial_ratio
            return self.initial_ratio

        total_fuel_delta = 0.0
        total_energy_delta = 0.0
        for previous, current in zip(readings, readings[1:]):
            fuel_delta = current[READING_CUMULATIVE] - previous[READING_CUMULATIVE]
            energy_delta = current[READING_ENERGY] - previous[READING_ENERGY]
            if fuel_delta > 0 and energy_delta > 0:
                total_fuel_delta += fuel_delta
                total_energy_delta += energy_delta

        if total_energy_delta > 0 and total_fuel_delta > 0:
            ratio = total_fuel_delta / total_energy_delta
        else:
            ratio = self.initial_ratio

        self._data[DATA_ACTIVE_RATIO] = ratio
        return ratio

    async def async_reset(self) -> None:
        """Clear all readings and reset the ratio to the initial value."""
        self._data[DATA_READINGS] = []
        self._data[DATA_ACTIVE_RATIO] = self.initial_ratio
        await self.async_save()

    async def async_remove(self) -> None:
        """Remove the underlying storage file (on entry removal)."""
        await self._store.async_remove()
