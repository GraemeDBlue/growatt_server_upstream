"""Button platform for Growatt."""

from __future__ import annotations

from datetime import time as dt_time
import logging

from growattServer import DeviceType, GrowattV1ApiError, OpenApiV1

from homeassistant.components.button import ButtonEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import GrowattConfigEntry, GrowattCoordinator

_LOGGER = logging.getLogger(__name__)


class GrowattApplySettingsButton(CoordinatorEntity[GrowattCoordinator], ButtonEntity):
    """Button to apply charge/discharge settings."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        coordinator: GrowattCoordinator,
        setting_type: str,  # "charge" or "discharge"
    ) -> None:
        """Initialize the button."""
        super().__init__(coordinator)
        self._setting_type = setting_type
        self._attr_unique_id = f"{coordinator.device_id}_apply_{setting_type}_settings"
        self._attr_translation_key = f"apply_{setting_type}_settings"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.device_id)},
            manufacturer="Growatt",
            name=coordinator.device_id,
        )

    async def async_press(self) -> None:
        """Handle the button press."""
        try:
            if self._setting_type == "charge":
                await self._apply_charge_settings()
            else:
                await self._apply_discharge_settings()

            # Refresh coordinator after successful update
            await self.coordinator.async_request_refresh()

        except GrowattV1ApiError as err:
            msg = f"Error applying {self._setting_type} settings: {err}"
            _LOGGER.exception(msg)
            raise HomeAssistantError(msg) from err

    async def _apply_charge_settings(self) -> None:
        """Apply charge settings."""
        device_id = self.coordinator.device_id

        # Get all entity IDs for this device from the entity registry
        from homeassistant.helpers import entity_registry as er

        entity_reg = er.async_get(self.hass)

        # Find entities by their unique_id pattern
        charge_power_entity = None
        charge_stop_soc_entity = None

        # For MIX devices, also need time and enable entities
        charge_start_entity = None
        charge_end_entity = None
        charge_enabled_entity = None

        for entity in entity_reg.entities.values():
            if entity.platform == "growatt_server" and device_id in entity.unique_id:
                if entity.unique_id.endswith("_charge_power"):
                    charge_power_entity = self.hass.states.get(entity.entity_id)
                elif entity.unique_id.endswith("_charge_stop_soc"):
                    charge_stop_soc_entity = self.hass.states.get(entity.entity_id)
                elif entity.unique_id.endswith("_charge_start_time_1"):
                    charge_start_entity = self.hass.states.get(entity.entity_id)
                elif entity.unique_id.endswith("_charge_end_time_1"):
                    charge_end_entity = self.hass.states.get(entity.entity_id)
                elif entity.unique_id.endswith("_charge_period_1_enabled"):
                    charge_enabled_entity = self.hass.states.get(entity.entity_id)

        # Determine device type
        if self.coordinator.device_type == "tlx":
            device_type = DeviceType.MIN_TLX
        else:
            device_type = DeviceType.SPH_MIX

        # TLX and MIX devices handle charge settings differently
        if isinstance(self.coordinator.api, OpenApiV1):
            if self.coordinator.device_type == "tlx":
                # TLX devices use individual ChargeDischargeParams
                if not all([charge_power_entity, charge_stop_soc_entity]):
                    missing = []
                    if not charge_power_entity:
                        missing.append(
                            f"number.{self.coordinator.device_id}_charge_power"
                        )
                    if not charge_stop_soc_entity:
                        missing.append(
                            f"number.{self.coordinator.device_id}_charge_stop_soc"
                        )
                    msg = f"Could not find all charge setting entities. Missing: {', '.join(missing)}"
                    _LOGGER.error(msg)
                    raise HomeAssistantError(msg)

                charge_power = int(float(charge_power_entity.state))
                charge_stop_soc = int(float(charge_stop_soc_entity.state))

                # TLX uses separate commands for charge power and charge SOC
                _LOGGER.info(
                    "Applying TLX charge settings: power=%s, soc=%s",
                    charge_power,
                    charge_stop_soc,
                )

                # Send charge power
                params_power = OpenApiV1.ChargeDischargeParams(
                    charge_power=charge_power,
                    charge_stop_soc=0,
                    discharge_power=0,
                    discharge_stop_soc=0,
                    ac_charge_enabled=False,
                )
                await self.hass.async_add_executor_job(
                    self.coordinator.api.write_parameter,
                    self.coordinator.device_id,
                    device_type,
                    "charge_power",
                    params_power,
                )

                # Send charge stop SOC
                params_soc = OpenApiV1.ChargeDischargeParams(
                    charge_power=0,
                    charge_stop_soc=charge_stop_soc,
                    discharge_power=0,
                    discharge_stop_soc=0,
                    ac_charge_enabled=False,
                )
                await self.hass.async_add_executor_job(
                    self.coordinator.api.write_parameter,
                    self.coordinator.device_id,
                    device_type,
                    "charge_stop_soc",
                    params_soc,
                )

            else:
                # MIX devices bundle charge settings with time periods
                if not all(
                    [
                        charge_start_entity,
                        charge_end_entity,
                        charge_enabled_entity,
                        charge_power_entity,
                        charge_stop_soc_entity,
                    ]
                ):
                    missing = []
                    if not charge_start_entity:
                        missing.append(
                            f"time.{self.coordinator.device_id}_charge_start_time"
                        )
                    if not charge_end_entity:
                        missing.append(
                            f"time.{self.coordinator.device_id}_charge_end_time"
                        )
                    if not charge_enabled_entity:
                        missing.append(
                            f"switch.{self.coordinator.device_id}_charge_period_1_enabled"
                        )
                    if not charge_power_entity:
                        missing.append(
                            f"number.{self.coordinator.device_id}_charge_power"
                        )
                    if not charge_stop_soc_entity:
                        missing.append(
                            f"number.{self.coordinator.device_id}_charge_stop_soc"
                        )

                    msg = f"Could not find all charge setting entities. Missing: {', '.join(missing)}"
                    _LOGGER.error(msg)
                    raise HomeAssistantError(msg)

                # Parse values
                start_time = dt_time.fromisoformat(charge_start_entity.state)
                end_time = dt_time.fromisoformat(charge_end_entity.state)
                enabled = charge_enabled_entity.state == "on"
                charge_power = int(float(charge_power_entity.state))
                charge_stop_soc = int(float(charge_stop_soc_entity.state))

                # Get mains enabled from coordinator data
                mains_enabled = bool(
                    int(self.coordinator.data.get("acChargeEnable", 0))
                )

                params = OpenApiV1.MixAcChargeTimeParams(
                    charge_power=charge_power,
                    charge_stop_soc=charge_stop_soc,
                    mains_enabled=mains_enabled,
                    start_hour=start_time.hour,
                    start_minute=start_time.minute,
                    end_hour=end_time.hour,
                    end_minute=end_time.minute,
                    enabled=enabled,
                    segment_id=1,
                )

                _LOGGER.info(
                    "Applying MIX charge settings: power=%s, soc=%s, mains=%s, "
                    "times=%02d:%02d-%02d:%02d, enabled=%s",
                    charge_power,
                    charge_stop_soc,
                    mains_enabled,
                    start_time.hour,
                    start_time.minute,
                    end_time.hour,
                    end_time.minute,
                    enabled,
                )

                await self.hass.async_add_executor_job(
                    self.coordinator.api.write_time_segment,
                    self.coordinator.device_id,
                    device_type,
                    "mix_ac_charge_time_period",
                    params,
                )

    async def _apply_discharge_settings(self) -> None:
        """Apply discharge settings."""
        device_id = self.coordinator.device_id

        # Get all entity IDs for this device from the entity registry
        from homeassistant.helpers import entity_registry as er

        entity_reg = er.async_get(self.hass)

        # Find entities by their unique_id pattern
        discharge_power_entity = None
        discharge_stop_soc_entity = None

        # For MIX devices, also need time and enable entities
        discharge_start_entity = None
        discharge_end_entity = None
        discharge_enabled_entity = None

        for entity in entity_reg.entities.values():
            if entity.platform == "growatt_server" and device_id in entity.unique_id:
                if entity.unique_id.endswith("_discharge_power"):
                    discharge_power_entity = self.hass.states.get(entity.entity_id)
                elif entity.unique_id.endswith("_discharge_stop_soc"):
                    discharge_stop_soc_entity = self.hass.states.get(entity.entity_id)
                elif entity.unique_id.endswith("_discharge_start_time_1"):
                    discharge_start_entity = self.hass.states.get(entity.entity_id)
                elif entity.unique_id.endswith("_discharge_end_time_1"):
                    discharge_end_entity = self.hass.states.get(entity.entity_id)
                elif entity.unique_id.endswith("_discharge_period_1_enabled"):
                    discharge_enabled_entity = self.hass.states.get(entity.entity_id)

        # Determine device type
        if self.coordinator.device_type == "tlx":
            device_type = DeviceType.MIN_TLX
        else:
            device_type = DeviceType.SPH_MIX

        # TLX and MIX devices handle discharge settings differently
        if isinstance(self.coordinator.api, OpenApiV1):
            if self.coordinator.device_type == "tlx":
                # TLX devices use individual ChargeDischargeParams
                if not all([discharge_power_entity, discharge_stop_soc_entity]):
                    missing = []
                    if not discharge_power_entity:
                        missing.append(
                            f"number.{self.coordinator.device_id}_discharge_power"
                        )
                    if not discharge_stop_soc_entity:
                        missing.append(
                            f"number.{self.coordinator.device_id}_discharge_stop_soc"
                        )
                    msg = f"Could not find all discharge setting entities. Missing: {', '.join(missing)}"
                    _LOGGER.error(msg)
                    raise HomeAssistantError(msg)

                discharge_power = int(float(discharge_power_entity.state))
                discharge_stop_soc = int(float(discharge_stop_soc_entity.state))

                # TLX uses separate commands for discharge power and discharge SOC
                _LOGGER.info(
                    "Applying TLX discharge settings: power=%s, soc=%s",
                    discharge_power,
                    discharge_stop_soc,
                )

                # Send discharge power
                params_power = OpenApiV1.ChargeDischargeParams(
                    charge_power=0,
                    charge_stop_soc=0,
                    discharge_power=discharge_power,
                    discharge_stop_soc=0,
                    ac_charge_enabled=False,
                )
                await self.hass.async_add_executor_job(
                    self.coordinator.api.write_parameter,
                    self.coordinator.device_id,
                    device_type,
                    "discharge_power",
                    params_power,
                )

                # Send discharge stop SOC
                params_soc = OpenApiV1.ChargeDischargeParams(
                    charge_power=0,
                    charge_stop_soc=0,
                    discharge_power=0,
                    discharge_stop_soc=discharge_stop_soc,
                    ac_charge_enabled=False,
                )
                await self.hass.async_add_executor_job(
                    self.coordinator.api.write_parameter,
                    self.coordinator.device_id,
                    device_type,
                    "discharge_stop_soc",
                    params_soc,
                )

            else:
                # MIX devices bundle discharge settings with time periods
                if not all(
                    [
                        discharge_start_entity,
                        discharge_end_entity,
                        discharge_enabled_entity,
                        discharge_power_entity,
                        discharge_stop_soc_entity,
                    ]
                ):
                    missing = []
                    if not discharge_start_entity:
                        missing.append(
                            f"time.{self.coordinator.device_id}_discharge_start_time"
                        )
                    if not discharge_end_entity:
                        missing.append(
                            f"time.{self.coordinator.device_id}_discharge_end_time"
                        )
                    if not discharge_enabled_entity:
                        missing.append(
                            f"switch.{self.coordinator.device_id}_discharge_period_1_enabled"
                        )
                    if not discharge_power_entity:
                        missing.append(
                            f"number.{self.coordinator.device_id}_discharge_power"
                        )
                    if not discharge_stop_soc_entity:
                        missing.append(
                            f"number.{self.coordinator.device_id}_discharge_stop_soc"
                        )

                    msg = f"Could not find all discharge setting entities. Missing: {', '.join(missing)}"
                    _LOGGER.error(msg)
                    raise HomeAssistantError(msg)

                # Parse values
                start_time = dt_time.fromisoformat(discharge_start_entity.state)
                end_time = dt_time.fromisoformat(discharge_end_entity.state)
                enabled = discharge_enabled_entity.state == "on"
                discharge_power = int(float(discharge_power_entity.state))
                discharge_stop_soc = int(float(discharge_stop_soc_entity.state))

                params = OpenApiV1.MixAcDischargeTimeParams(
                    discharge_power=discharge_power,
                    discharge_stop_soc=discharge_stop_soc,
                    start_hour=start_time.hour,
                    start_minute=start_time.minute,
                    end_hour=end_time.hour,
                    end_minute=end_time.minute,
                    enabled=enabled,
                    segment_id=1,
                )

                _LOGGER.info(
                    "Applying MIX discharge settings: power=%s, soc=%s, "
                    "times=%02d:%02d-%02d:%02d, enabled=%s",
                    discharge_power,
                    discharge_stop_soc,
                    start_time.hour,
                    start_time.minute,
                    end_time.hour,
                    end_time.minute,
                    enabled,
                )

                await self.hass.async_add_executor_job(
                    self.coordinator.api.write_time_segment,
                    self.coordinator.device_id,
                    device_type,
                    "mix_ac_discharge_time_period",
                    params,
                )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GrowattConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Growatt button entities."""
    runtime_data = entry.runtime_data
    entities: list[ButtonEntity] = []

    for device_coordinator in runtime_data.devices.values():
        if (
            device_coordinator.device_type in ["mix", "tlx"]
            and device_coordinator.api_version == "v1"
        ):
            # Add apply settings buttons
            entities.extend(
                [
                    GrowattApplySettingsButton(device_coordinator, "charge"),
                    GrowattApplySettingsButton(device_coordinator, "discharge"),
                ]
            )

    async_add_entities(entities)
