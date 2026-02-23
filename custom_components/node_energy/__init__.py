from __future__ import annotations

from pathlib import Path

from homeassistant.components.http import StaticPathConfig
from homeassistant.components.panel_custom import async_register_panel
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN, PLATFORMS
from .coordinator import NodeEnergyCoordinator

PANEL_COMPONENT = "node-energy-setup-panel"
PANEL_URL_PATH = "node-energy-setup"
PANEL_STATIC_DIR_URL = "/api/node_energy_panel"
PANEL_MODULE = "node-energy-setup-panel.js"
PANEL_MODULE_VERSION = "0.1.5"
DATA_PANEL_REGISTERED = f"{DOMAIN}_panel_registered"


async def _async_register_panel(hass: HomeAssistant) -> None:
    if hass.data.get(DATA_PANEL_REGISTERED):
        return

    module_path = Path(__file__).parent / "frontend" / PANEL_MODULE
    await hass.http.async_register_static_paths(
        [StaticPathConfig(f"{PANEL_STATIC_DIR_URL}/{PANEL_MODULE}", str(module_path), True)]
    )
    async_register_panel(
        hass,
        webcomponent_name=PANEL_COMPONENT,
        frontend_url_path=PANEL_URL_PATH,
        sidebar_title="Node Energy Setup",
        sidebar_icon="mdi:chart-line",
        module_url=f"{PANEL_STATIC_DIR_URL}/{PANEL_MODULE}?v={PANEL_MODULE_VERSION}",
        require_admin=False,
    )
    hass.data[DATA_PANEL_REGISTERED] = True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    coordinator = NodeEnergyCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await _async_register_panel(hass)

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
        hass.data[DOMAIN].pop(entry.entry_id, None)
        if not hass.data[DOMAIN] and hass.services.has_service(DOMAIN, "refresh"):
            hass.services.async_remove(DOMAIN, "refresh")
    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)
