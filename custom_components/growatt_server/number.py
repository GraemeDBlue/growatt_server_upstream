"""Number platform for Growatt."""

from __future__ import annotations

from dataclasses import dataclass
import logging

from growattServer import DeviceType, GrowattV1ApiError, OpenApiV1

from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import GrowattConfigEntry, GrowattCoordinator
from .sensor.sensor_entity_description import GrowattRequiredKeysMixin

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = (
    1  # Serialize updates as inverter does not handle concurrent requests
)


@dataclass(frozen=True, kw_only=True)
class GrowattNumberEntityDescription(NumberEntityDescription, GrowattRequiredKeysMixin):
    """Describes Growatt number entity."""

    write_key: str | None = None  # Parameter ID for writing (if different from api_key)


# Note that the Growatt V1 API uses different keys for reading and writing parameters.
# Reading values returns camelCase keys, while writing requires snake_case keys.

MIN_NUMBER_TYPES: tuple[GrowattNumberEntityDescription, ...] = (
    GrowattNumberEntityDescription(
        key="charge_power",
        translation_key="charge_power",
        api_key="chargePowerCommand",  # Key returned by V1 API
        write_key="charge_power",  # Key used to write parameter
        native_step=1,
        native_min_value=0,
        native_max_value=100,
        native_unit_of_measurement=PERCENTAGE,
    ),
    GrowattNumberEntityDescription(
        key="charge_stop_soc",
        translation_key="charge_stop_soc",
        api_key="wchargeSOCLowLimit",  # Key returned by V1 API
        write_key="charge_stop_soc",  # Key used to write parameter
        native_step=1,
        native_min_value=0,
        native_max_value=100,
        native_unit_of_measurement=PERCENTAGE,
    ),
    GrowattNumberEntityDescription(
        key="discharge_power",
        translation_key="discharge_power",
        api_key="disChargePowerCommand",  # Key returned by V1 API
        write_key="discharge_power",  # Key used to write parameter
        native_step=1,
        native_min_value=0,
        native_max_value=100,
        native_unit_of_measurement=PERCENTAGE,
    ),
    GrowattNumberEntityDescription(
        key="discharge_stop_soc",
        translation_key="discharge_stop_soc",
        api_key="wdisChargeSOCLowLimit",  # Key returned by V1 API
        write_key="discharge_stop_soc",  # Key used to write parameter
        native_step=1,
        native_min_value=0,
        native_max_value=100,
        native_unit_of_measurement=PERCENTAGE,
    ),
)

MIX_NUMBER_TYPES: tuple[GrowattNumberEntityDescription, ...] = (
    GrowattNumberEntityDescription(
        key="charge_power",
        translation_key="charge_power",
        api_key="chargePowerCommand",  # Key returned by V1 API
        write_key="charge_power",  # Key used to write parameter
        native_step=1,
        native_min_value=0,
        native_max_value=100,
        native_unit_of_measurement=PERCENTAGE,
    ),
    GrowattNumberEntityDescription(
        key="charge_stop_soc",
        translation_key="charge_stop_soc",
        api_key="wchargeSOCLowLimit1",  # Key for MIX devices (time period 1)
        write_key="charge_stop_soc",  # Key used to write parameter
        native_step=1,
        native_min_value=0,
        native_max_value=100,
        native_unit_of_measurement=PERCENTAGE,
    ),
    GrowattNumberEntityDescription(
        key="discharge_power",
        translation_key="discharge_power",
        api_key="disChargePowerCommand",  # Key returned by V1 API
        write_key="discharge_power",  # Key used to write parameter
        native_step=1,
        native_min_value=0,
        native_max_value=100,
        native_unit_of_measurement=PERCENTAGE,
    ),
    GrowattNumberEntityDescription(
        key="discharge_stop_soc",
        translation_key="discharge_stop_soc",
        api_key="loadFirstStopSocSet",  # Key returned by V1 API for MIX devices
        write_key="discharge_stop_soc",  # Key used to write parameter
        native_step=1,
        native_min_value=0,
        native_max_value=100,
        native_unit_of_measurement=PERCENTAGE,
    ),
)


class GrowattNumber(CoordinatorEntity[GrowattCoordinator], NumberEntity):
    """Representation of a Growatt number."""

    _attr_has_entity_name = True
    entity_description: GrowattNumberEntityDescription

    def __init__(
        self,
        coordinator: GrowattCoordinator,
        description: GrowattNumberEntityDescription,
    ) -> None:
        """Initialize the number."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.device_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.device_id)},
            manufacturer="Growatt",
            name=coordinator.device_id,
        )

    @property
    def native_value(self) -> int | None:
        """Return the current value of the number."""
        value = self.coordinator.get_value(self.entity_description)
        if value is None:
            return None
        return int(value)

    async def async_set_native_value(self, value: float) -> None:
        """Set value (locally only - use Apply button to send to device)."""
        # Convert float to int for storage
        int_value = int(value)

        # Update the local value in coordinator data
        api_key = self.entity_description.api_key
        self.coordinator.data[api_key] = int_value

        # Update the entity state in Home Assistant
        self.async_write_ha_state()


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GrowattConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Growatt number entities."""
    runtime_data = entry.runtime_data

    entities: list[GrowattNumber] = []

    # Add number entities for each device (only supported with V1 API)
    for device_coordinator in runtime_data.devices.values():
        if device_coordinator.api_version == "v1":
            # Use appropriate number types based on device type
            if device_coordinator.device_type == "tlx":
                number_types = MIN_NUMBER_TYPES
            else:  # mix
                number_types = MIX_NUMBER_TYPES

            entities.extend(
                GrowattNumber(
                    coordinator=device_coordinator,
                    description=description,
                )
                for description in number_types
            )

    async_add_entities(entities)
