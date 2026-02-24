from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN, PLATFORMS
from .coordinator import NodeEnergyCoordinator

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    coordinator = NodeEnergyCoordinator(hass, entry)
    # Keep entry load resilient even if recorder/weather is not ready yet.
    await coordinator.async_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    if not hass.services.has_service(DOMAIN, "refresh"):
        async def _refresh_service(call):
            target = call.data.get("entry_id")
            entries = hass.data.get(DOMAIN, {})
            if target:
                coord = entries.get(target)
                if coord:
                    await coord.async_request_refresh()
                return
            for coord in entries.values():
                if not isinstance(coord, NodeEnergyCoordinator):
                    continue
                await coord.async_request_refresh()

        hass.services.async_register(DOMAIN, "refresh", _refresh_service)

    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        domain_data = hass.data.get(DOMAIN)
        if isinstance(domain_data, dict):
            domain_data.pop(entry.entry_id, None)
        if isinstance(domain_data, dict) and (not domain_data) and hass.services.has_service(DOMAIN, "refresh"):
            hass.services.async_remove(DOMAIN, "refresh")
    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    unload_ok = await async_unload_entry(hass, entry)
    if unload_ok:
        await async_setup_entry(hass, entry)
