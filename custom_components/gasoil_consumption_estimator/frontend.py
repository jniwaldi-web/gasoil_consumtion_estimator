"""Auto-register the Lovelace card as a frontend resource."""
from __future__ import annotations
import logging
from pathlib import Path
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_call_later
from .const import CARD_RESOURCE_URL, URL_BASE

_LOGGER = logging.getLogger(__name__)
REGISTER_KEY = "gasoil_card_registered"

async def async_register_frontend(hass: HomeAssistant) -> None:
    """Serve gasoil-card.js and register it as a Lovelace resource (once)."""
    if hass.data.setdefault("gasoil_consumption_estimator", {}).get(REGISTER_KEY):
        return

    # 1) Serve the integration folder over HTTP so the JS is downloadable.
    folder = str(Path(__file__).parent)
    try:
        await hass.http.async_register_static_paths(
            [StaticPathConfig(URL_BASE, folder, False)]
        )
    except RuntimeError:
        # Already registered (e.g. reload).
        _LOGGER.debug("Static path %s already registered", URL_BASE)

    hass.data["gasoil_consumption_estimator"][REGISTER_KEY] = True

    # 2) Auto-add the Lovelace resource (storage mode only).
    hass.async_create_task(_async_register_lovelace_resource(hass))


async def _async_register_lovelace_resource(hass: HomeAssistant) -> None:
    """Add the card to Lovelace resources once they are loaded."""
    # Wait until the lovelace integration has set up its data.
    tries = 0
    while True:
        lovelace = hass.data.get("lovelace")
        if lovelace is not None:
            break
        tries += 1
        if tries > 60:  # ~5 min max
            _LOGGER.info("Lovelace no inicializado; no se autorregistró la tarjeta")
            return
        await asyncio.sleep(5)  # use async_call_later instead if sleep not allowed

    # Only storage mode supports auto-managed resources.
    if getattr(lovelace, "mode", None) != "storage":
        _LOGGER.info(
            "Lovelace no está en modo storage; registra el recurso %s manualmente",
            CARD_RESOURCE_URL,
        )
        return

    resources = getattr(lovelace, "resources", None)
    if resources is None:
        return

    # Wait for the resource collection to be loaded.
    while not getattr(resources, "loaded", False):
        await asyncio.sleep(2)

    existing = [r.get("url") for r in resources.async_items()]
    if CARD_RESOURCE_URL in existing:
        return

    try:
        await resources.async_create_item({"res_type": "module", "url": CARD_RESOURCE_URL})
        _LOGGER.info("Tarjeta gasoil-card registrada como recurso de Lovelace")
    except Exception as err:  # noqa: BLE001
        _LOGGER.warning("No se pudo registrar la tarjeta en Lovelace: %s", err)