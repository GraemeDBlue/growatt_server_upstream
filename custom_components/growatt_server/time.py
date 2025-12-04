"""Time platform for Growatt."""

from __future__ import annotations

from datetime import time
import logging
from typing import Any

from homeassistant.components.time import TimeEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import GrowattConfigEntry, GrowattCoordinator

_LOGGER = logging.getLogger(__name__)

# Field name templates for different device types
# MIN/TLX devices use numbered time segment fields
MIN_TLX_FIELD_TEMPLATES = {
    "start_time": "timeSegmentStart{segment_id}",
    "stop_time": "timeSegmentStop{segment_id}",
    "enabled": "timeSegmentEnabled{segment_id}",
}

# MIX/SPH devices use different field names for charge and discharge
SPH_MIX_CHARGE_FIELD_TEMPLATES = {
    "start_time": "forcedChargeTimeStart{segment_id}",
    "stop_time": "forcedChargeTimeStop{segment_id}",
    "enabled": "forcedChargeStopSwitch{segment_id}",
}

SPH_MIX_DISCHARGE_FIELD_TEMPLATES = {
    "start_time": "forcedDischargeTimeStart{segment_id}",
    "stop_time": "forcedDischargeTimeStop{segment_id}",
    "enabled": "forcedDischargeStopSwitch{segment_id}",
}


class GrowattChargeStartTimeEntity(CoordinatorEntity[GrowattCoordinator], TimeEntity):
    """Representation of charge start time."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG
    _attr_translation_key = "charge_start_time"

    def __init__(self, coordinator: GrowattCoordinator, segment_id: int = 1) -> None:
        """Initialize the time entity."""
        super().__init__(coordinator)
        self._segment_id = segment_id
        self._attr_unique_id = f"{coordinator.device_id}_charge_start_time_{segment_id}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.device_id)},
            manufacturer="Growatt",
            name=coordinator.device_id,
        )

    def _get_field_name(self, field_type: str) -> str:
        """Get the appropriate field name based on device type."""
        if self.coordinator.device_type == "tlx":
            template = MIN_TLX_FIELD_TEMPLATES[field_type]
        else:  # mix
            template = SPH_MIX_CHARGE_FIELD_TEMPLATES[field_type]
        return template.format(segment_id=self._segment_id)

    @property
    def native_value(self) -> time | None:
        """Return the current time value."""
        # Get from coordinator data using correct field name
        start_field = self._get_field_name("start_time")
        start_time_str = self.coordinator.data.get(start_field, "14:00")
        try:
            parts = start_time_str.split(":")
            return time(hour=int(parts[0]), minute=int(parts[1]))
        except (ValueError, IndexError):
            return time(14, 0)

    async def async_set_value(self, value: time) -> None:
        """Update the time (locally only - use Apply button to send to device)."""
        # Update the local state in coordinator data
        start_field = self._get_field_name("start_time")
        time_str = f"{value.hour:02d}:{value.minute:02d}"
        self.coordinator.data[start_field] = time_str

        # Update the entity state in Home Assistant
        self.async_write_ha_state()


class GrowattChargeEndTimeEntity(CoordinatorEntity[GrowattCoordinator], TimeEntity):
    """Representation of charge end time."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG
    _attr_translation_key = "charge_end_time"

    def __init__(self, coordinator: GrowattCoordinator, segment_id: int = 1) -> None:
        """Initialize the time entity."""
        super().__init__(coordinator)
        self._segment_id = segment_id
        self._attr_unique_id = f"{coordinator.device_id}_charge_end_time_{segment_id}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.device_id)},
            manufacturer="Growatt",
            name=coordinator.device_id,
        )

    def _get_field_name(self, field_type: str) -> str:
        """Get the appropriate field name based on device type."""
        if self.coordinator.device_type == "tlx":
            template = MIN_TLX_FIELD_TEMPLATES[field_type]
        else:  # mix
            template = SPH_MIX_CHARGE_FIELD_TEMPLATES[field_type]
        return template.format(segment_id=self._segment_id)

    @property
    def native_value(self) -> time | None:
        """Return the current time value."""
        stop_field = self._get_field_name("stop_time")
        end_time_str = self.coordinator.data.get(stop_field, "16:00")
        try:
            parts = end_time_str.split(":")
            return time(hour=int(parts[0]), minute=int(parts[1]))
        except (ValueError, IndexError):
            return time(16, 0)

    async def async_set_value(self, value: time) -> None:
        """Update the time (locally only - use Apply button to send to device)."""
        # Update the local state in coordinator data
        stop_field = self._get_field_name("stop_time")
        time_str = f"{value.hour:02d}:{value.minute:02d}"
        self.coordinator.data[stop_field] = time_str

        # Update the entity state in Home Assistant
        self.async_write_ha_state()


class GrowattDischargeStartTimeEntity(
    CoordinatorEntity[GrowattCoordinator], TimeEntity
):
    """Representation of discharge start time."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG
    _attr_translation_key = "discharge_start_time"

    def __init__(self, coordinator: GrowattCoordinator, segment_id: int = 1) -> None:
        """Initialize the time entity."""
        super().__init__(coordinator)
        self._segment_id = segment_id
        self._attr_unique_id = (
            f"{coordinator.device_id}_discharge_start_time_{segment_id}"
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.device_id)},
            manufacturer="Growatt",
            name=coordinator.device_id,
        )

    def _get_field_name(self, field_type: str) -> str:
        """Get the appropriate field name based on device type."""
        if self.coordinator.device_type == "tlx":
            template = MIN_TLX_FIELD_TEMPLATES[field_type]
        else:  # mix
            template = SPH_MIX_DISCHARGE_FIELD_TEMPLATES[field_type]
        return template.format(segment_id=self._segment_id)

    @property
    def native_value(self) -> time | None:
        """Return the current time value."""
        start_field = self._get_field_name("start_time")
        start_time_str = self.coordinator.data.get(start_field, "00:00")
        try:
            parts = start_time_str.split(":")
            return time(hour=int(parts[0]), minute=int(parts[1]))
        except (ValueError, IndexError):
            return time(0, 0)

    async def async_set_value(self, value: time) -> None:
        """Update the time (locally only - use Apply button to send to device)."""
        # Update the local state in coordinator data
        start_field = self._get_field_name("start_time")
        time_str = f"{value.hour:02d}:{value.minute:02d}"
        self.coordinator.data[start_field] = time_str

        # Update the entity state in Home Assistant
        self.async_write_ha_state()


class GrowattDischargeEndTimeEntity(CoordinatorEntity[GrowattCoordinator], TimeEntity):
    """Representation of discharge end time."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG
    _attr_translation_key = "discharge_end_time"

    def __init__(self, coordinator: GrowattCoordinator, segment_id: int = 1) -> None:
        """Initialize the time entity."""
        super().__init__(coordinator)
        self._segment_id = segment_id
        self._attr_unique_id = (
            f"{coordinator.device_id}_discharge_end_time_{segment_id}"
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.device_id)},
            manufacturer="Growatt",
            name=coordinator.device_id,
        )

    def _get_field_name(self, field_type: str) -> str:
        """Get the appropriate field name based on device type."""
        if self.coordinator.device_type == "tlx":
            template = MIN_TLX_FIELD_TEMPLATES[field_type]
        else:  # mix
            template = SPH_MIX_DISCHARGE_FIELD_TEMPLATES[field_type]
        return template.format(segment_id=self._segment_id)

    @property
    def native_value(self) -> time | None:
        """Return the current time value."""
        stop_field = self._get_field_name("stop_time")
        end_time_str = self.coordinator.data.get(stop_field, "00:00")
        try:
            parts = end_time_str.split(":")
            return time(hour=int(parts[0]), minute=int(parts[1]))
        except (ValueError, IndexError):
            return time(0, 0)

    async def async_set_value(self, value: time) -> None:
        """Update the time (locally only - use Apply button to send to device)."""
        # Update the local state in coordinator data
        stop_field = self._get_field_name("stop_time")
        time_str = f"{value.hour:02d}:{value.minute:02d}"
        self.coordinator.data[stop_field] = time_str

        # Update the entity state in Home Assistant
        self.async_write_ha_state()


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GrowattConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Growatt time entities."""
    runtime_data = entry.runtime_data
    entities: list[TimeEntity] = []

    for device_coordinator in runtime_data.devices.values():
        if device_coordinator.api_version == "v1":
            if device_coordinator.device_type == "mix":
                # Add time entities for MIX devices (first charge/discharge segment)
                # Order: charge start/end, then discharge start/end
                entities.extend(
                    [
                        GrowattChargeStartTimeEntity(device_coordinator, segment_id=1),
                        GrowattChargeEndTimeEntity(device_coordinator, segment_id=1),
                        GrowattDischargeStartTimeEntity(
                            device_coordinator, segment_id=1
                        ),
                        GrowattDischargeEndTimeEntity(device_coordinator, segment_id=1),
                    ]
                )
            elif device_coordinator.device_type == "tlx":
                # Add time entities for TLX devices (first segment)
                # Order: charge start/end, then discharge start/end
                entities.extend(
                    [
                        GrowattChargeStartTimeEntity(device_coordinator, segment_id=1),
                        GrowattChargeEndTimeEntity(device_coordinator, segment_id=1),
                        GrowattDischargeStartTimeEntity(
                            device_coordinator, segment_id=1
                        ),
                        GrowattDischargeEndTimeEntity(device_coordinator, segment_id=1),
                    ]
                )

    async_add_entities(entities)
