"""Platform for sensor integration."""

from homeassistant.components.button import ButtonEntity
from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN


# See cover.py for more details.
# Note how both entities for each roller sensor (battry and illuminance) are added at
# the same time to the same list. This way only a single async_add_devices call is
# required.
async def async_setup_entry(hass, config_entry, async_add_entities):
    """Add sensors for passed config_entry in HA."""
    hub = hass.data[DOMAIN][config_entry.entry_id]

    async_add_entities([ConfigFlowSensor(hub)])


class Sensor(ButtonEntity):
    """Representation of a Sensor entity."""

    def __init__(self, hub):
        """Initialize the sensor."""
        self.hub = hub

    async def async_press(self) -> None:
        """Fetch data."""
        await self.hub.fetch()


class ConfigFlowSensor(Sensor):
    """Config flow."""

    @property
    def device_info(self) -> DeviceInfo:
        """device_info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.hub.entry.entry_id + "_sensor")},
            name=self.hub.entry.entry_id,
            manufacturer="InfluxDB",
            model=self.hub.entry.entry_id,
            sw_version="1.0.0",
        )

    @property
    def name(self):
        """name."""
        return self.hub.entry.data["entity_id"]

    @property
    def unique_id(self):
        """Return a unique ID."""
        return self.hub.entry.entry_id + "_uu"
