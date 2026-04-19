"""Number platform for IthoWiFi integration."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import DOMAIN, is_fan_device
from .coordinator import (
    IthoDeviceInfoCoordinator,
    IthoStatusCoordinator,
)
from .entity import IthoEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up IthoWiFi number entities."""
    data = hass.data[DOMAIN][entry.entry_id]
    status_coord: IthoStatusCoordinator = data["status_coordinator"]
    device_coord: IthoDeviceInfoCoordinator = data["device_coordinator"]

    devtype = (device_coord.data or {}).get("itho_devtype")
    entities: list[NumberEntity] = []

    if is_fan_device(devtype):
        entities.append(IthoFanDemandNumber(status_coord, device_coord))

    if status_coord.use_rf_commands:
        entities.append(
            IthoCO2LevelNumber(status_coord, device_coord, entry.entry_id)
        )

    if not entities:
        return

    async_add_entities(entities)


class IthoFanDemandNumber(IthoEntity, NumberEntity):
    """Number entity for setting fan demand percentage."""

    _attr_name = "Fan demand"
    _attr_icon = "mdi:fan"
    _attr_native_min_value = 0
    _attr_native_max_value = 100
    _attr_native_step = 1
    _attr_native_unit_of_measurement = "%"
    _attr_mode = NumberMode.SLIDER

    def __init__(
        self,
        coordinator: IthoStatusCoordinator,
        device_info_coordinator: IthoDeviceInfoCoordinator,
    ) -> None:
        """Initialize the number entity."""
        super().__init__(coordinator, device_info_coordinator)
        info = device_info_coordinator.data or {}
        self._attr_unique_id = (
            f"{info.get('add-on_hwid', 'itho')}_fan_demand"
        )

    @property
    def native_value(self) -> float | None:
        """Return the current fan speed as percentage."""
        if self.coordinator.data is None:
            return None
        # Prefer Speed status from ithostatus (works when PWM2I2C is off)
        status = self.coordinator.data.get("status", {})
        val = status.get("Speed status")
        if val is not None and val != "not available":
            return min(round(float(val)), 100)
        # Fall back to currentspeed
        speed = self.coordinator.data.get("speed", {}).get("currentspeed")
        if speed is None:
            return None
        return min(round(speed / 2.55), 100)

    async def async_set_native_value(self, value: float) -> None:
        """Set the fan demand. Tries RF demand first, falls back to speed."""
        try:
            await self.coordinator.api.send_rf_command("auto")
            demand = int(value * 2)  # 0-100% → 0-200 demand
            await self.coordinator.api.send_rf_demand(demand)
        except Exception:
            import math
            speed = math.ceil(value * 2.55)
            await self.coordinator.api.set_speed(speed)
        await self.coordinator.async_request_refresh()


class IthoCO2LevelNumber(IthoEntity, NumberEntity, RestoreEntity):
    """Number entity for staging a CO2 value for RF send."""

    _attr_name = "CO2 send value"
    _attr_translation_key = "co2_send_value"
    _attr_icon = "mdi:molecule-co2"
    _attr_native_min_value = 400
    _attr_native_max_value = 5000
    _attr_native_step = 1
    _attr_native_unit_of_measurement = "ppm"
    _attr_mode = NumberMode.BOX

    def __init__(
        self,
        coordinator: IthoStatusCoordinator,
        device_info_coordinator: IthoDeviceInfoCoordinator,
        entry_id: str,
    ) -> None:
        """Initialize the CO2 number entity."""
        super().__init__(coordinator, device_info_coordinator)
        self._entry_id = entry_id
        info = device_info_coordinator.data or {}
        self._attr_unique_id = f"{info.get('add-on_hwid', 'itho')}_co2_level"
        self._attr_native_value = 400

    @property
    def native_value(self) -> float | None:
        """Return the staged CO2 send value."""
        return self._attr_native_value

    async def async_added_to_hass(self) -> None:
        """Restore the last staged CO2 value."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state is None:
            return
        try:
            self._attr_native_value = float(last_state.state)
        except (TypeError, ValueError):
            return
        self.hass.data[DOMAIN][self._entry_id]["rf_co2_value"] = int(
            self._attr_native_value
        )

    async def async_set_native_value(self, value: float) -> None:
        """Stage a CO2 value without sending it immediately."""
        self._attr_native_value = value
        self.hass.data[DOMAIN][self._entry_id]["rf_co2_value"] = int(value)
        self.async_write_ha_state()
