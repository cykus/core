"""InfluxDB."""
from __future__ import annotations

from datetime import datetime
import logging

from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.statistics import (
    async_import_statistics,
    get_last_statistics,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util.dt import get_time_zone

_LOGGER = logging.getLogger(__name__)


class InfluxDB:
    """InfluxDB."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize."""
        self.hass = hass
        self.influx = hass.data["influxdb"].influx
        self.entry = entry

    async def fetch(self) -> None:
        """Fetch data."""
        entity_registry = er.async_get(self.hass)
        if registry_entry := entity_registry.async_get(self.entry.data["entity_id"]):
            # self.import_all(
            #     registry_entry.entity_id, registry_entry.unit_of_measurement
            # )
            statistic_id = self.entry.data["entity_id"]
            get_instance(self.hass).async_clear_statistics([statistic_id])

            data = await get_instance(self.hass).async_add_executor_job(
                get_last_statistics, self.hass, 1, statistic_id, True, {"state", "sum"}
            )
            if not data:
                await self.hass.async_add_executor_job(
                    self.import_all,
                    statistic_id,
                    registry_entry,
                )

    def import_all(self, statistic_id, registry) -> None:
        """import_all."""
        if (
            registry.capabilities["state_class"] == "total"
            or registry.capabilities["state_class"] == "total_increasing"
        ):
            query = (
                'SELECT max("value") AS "value", time FROM "home_assistant"."autogen"."'  # noqa: S608
                + registry.unit_of_measurement
                + '" WHERE "entity_id"=\''  # noqa: S608
                + statistic_id.replace("sensor.", "")
                + "' GROUP BY time(1h) FILL(null)"
            )
        elif registry.capabilities["state_class"] == "measurement":
            query = (
                'SELECT max("value") AS "max", min("value") AS "min", mean("value") AS "value", time FROM "home_assistant"."autogen"."'  # noqa: S608
                + registry.unit_of_measurement
                + '" WHERE "entity_id"=\''  # noqa: S608
                + statistic_id.replace("sensor.", "")
                + "' GROUP BY time(1h) FILL(null)"
            )
        else:
            return None
        rs = self.influx.query(query)
        self.update_stats(statistic_id, registry, rs)

    def update_stats(self, statistic_id, registry, raw_data):
        """update_stats."""
        metadata = {
            "has_mean": registry.capabilities["state_class"] == "measurement",
            "has_sum": registry.capabilities["state_class"] == "total"
            or registry.capabilities["state_class"] == "total_increasing",
            "source": "recorder",
            "statistic_id": statistic_id,
            "unit_of_measurement": registry.unit_of_measurement,
        }
        statistic_data = []
        for prev_raw_hour, raw_hour in zip(raw_data, raw_data[1:]):
            if raw_hour.get("value") is not None:
                current_sum = 0
                start = self.get_time(raw_hour.get("time"))
                start = start.replace(minute=0, second=0, microsecond=0)
                usage = float(raw_hour.get("value"))
                if registry.capabilities["state_class"] == "measurement":
                    stats = {
                        "start": start,
                        "mean": raw_hour.get("value"),
                        "min": raw_hour.get("min"),
                        "max": raw_hour.get("max"),
                    }
                elif registry.capabilities["state_class"] == "total_increasing":
                    if (
                        prev_raw_hour is not None
                        and prev_raw_hour.get("value") is not None
                    ):
                        current_sum = raw_hour.get("value") - prev_raw_hour.get("value")
                    stats = {"start": start, "state": usage, "sum": current_sum}
                elif registry.capabilities["state_class"] == "total":
                    stats = {
                        "start": start,
                        "state": usage,
                        "sum": raw_hour.get("value"),
                    }
                self.log(stats)
                statistic_data.append(stats)
        self.log(metadata)
        async_import_statistics(self.hass, metadata, statistic_data)
        self.log(
            f"Updated {len(statistic_data)} entries for statistic: {statistic_id} "
        )

    def get_time(self, raw_hour):
        """get_time."""
        zone = get_time_zone("Europe/Warsaw")
        return datetime.strptime(raw_hour, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=zone)

    def log(self, msg):
        """log."""
        _LOGGER.info(msg)
