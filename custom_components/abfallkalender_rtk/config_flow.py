"""Config and options flow for Abfallkalender RTK."""

from __future__ import annotations

import logging
from typing import Any

import aiohttp
import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    BooleanSelector,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
)

from .const import (
    CONF_ACTIVE_YEAR,
    CONF_DISCOVERY_START,
    CONF_ENABLE_PERSISTENT_NOTIFICATION,
    CONF_LOOKAHEAD_DAYS,
    CONF_NAME,
    CONF_PDF_URL,
    CONF_SCAN_INTERVAL_DAYS,
    CONF_TRACKED_TYPES,
    CONF_URL_TEMPLATE,
    DEFAULT_DISCOVERY_START,
    DEFAULT_ENABLE_PERSISTENT_NOTIFICATION,
    DEFAULT_LOOKAHEAD_DAYS,
    DEFAULT_NAME,
    DEFAULT_PDF_URL,
    DEFAULT_SCAN_INTERVAL_DAYS,
    DOMAIN,
    HTTP_TIMEOUT_SECONDS,
    USER_AGENT,
    WASTE_TYPES,
)
from .parser import ParseError, parse_pdf
from .url import UrlError, build_url, normalize_url

_LOGGER = logging.getLogger(__name__)

_TYPE_OPTIONS = [
    SelectOptionDict(value=code, label=meta["label"])
    for code, meta in WASTE_TYPES.items()
]
_INTERVAL_OPTIONS = [
    SelectOptionDict(value="1", label="daily"),
    SelectOptionDict(value="7", label="weekly"),
]


async def _validate_pdf(hass, url: str) -> tuple[str, int]:
    """Download and parse a URL, returning (url_template, year).

    Raises vol.Invalid-compatible error strings via the returned error key.
    """
    template, _ = normalize_url(url)
    # Probe the entered URL directly so validation matches the user's input.
    session = async_get_clientsession(hass)
    async with session.get(
        url,
        headers={"User-Agent": USER_AGENT},
        timeout=aiohttp.ClientTimeout(total=HTTP_TIMEOUT_SECONDS),
        allow_redirects=True,
    ) as response:
        response.raise_for_status()
        raw = await response.read()
    parsed = await hass.async_add_executor_job(parse_pdf, raw)
    return template, parsed.year


class AbfallkalenderConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the initial setup."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                template, year = await _validate_pdf(
                    self.hass, user_input[CONF_PDF_URL]
                )
            except UrlError:
                errors["base"] = "invalid_url"
            except ParseError:
                errors["base"] = "parse_error"
            except (aiohttp.ClientError, TimeoutError):
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(template)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=user_input[CONF_NAME],
                    data={
                        CONF_URL_TEMPLATE: template,
                        CONF_ACTIVE_YEAR: year,
                    },
                    options={
                        CONF_SCAN_INTERVAL_DAYS: int(
                            user_input[CONF_SCAN_INTERVAL_DAYS]
                        ),
                        CONF_TRACKED_TYPES: user_input[CONF_TRACKED_TYPES],
                    },
                )

        schema = vol.Schema(
            {
                vol.Required(CONF_NAME, default=DEFAULT_NAME): TextSelector(),
                vol.Required(CONF_PDF_URL, default=DEFAULT_PDF_URL): TextSelector(),
                vol.Required(
                    CONF_SCAN_INTERVAL_DAYS,
                    default=str(DEFAULT_SCAN_INTERVAL_DAYS),
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=_INTERVAL_OPTIONS,
                        translation_key="scan_interval_days",
                    )
                ),
                vol.Required(
                    CONF_TRACKED_TYPES, default=list(WASTE_TYPES.keys())
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=_TYPE_OPTIONS,
                        multiple=True,
                        mode=SelectSelectorMode.LIST,
                    )
                ),
            }
        )
        return self.async_show_form(
            step_id="user", data_schema=schema, errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(entry: ConfigEntry) -> OptionsFlow:
        return AbfallkalenderOptionsFlow()


class AbfallkalenderOptionsFlow(OptionsFlow):
    """Handle options: URL, interval, tracked types, rollover and alerts."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        options = self.config_entry.options
        current_url = build_url(
            self.config_entry.data[CONF_URL_TEMPLATE],
            self.config_entry.data[CONF_ACTIVE_YEAR],
        )

        if user_input is not None:
            new_url = user_input[CONF_PDF_URL]
            try:
                template, year = await _validate_pdf(self.hass, new_url)
            except UrlError:
                errors["base"] = "invalid_url"
            except ParseError:
                errors["base"] = "parse_error"
            except (aiohttp.ClientError, TimeoutError):
                errors["base"] = "cannot_connect"
            else:
                # Persist a possibly changed URL/year on the entry data.
                self.hass.config_entries.async_update_entry(
                    self.config_entry,
                    data={
                        **self.config_entry.data,
                        CONF_URL_TEMPLATE: template,
                        CONF_ACTIVE_YEAR: year,
                    },
                )
                return self.async_create_entry(
                    data={
                        CONF_SCAN_INTERVAL_DAYS: int(
                            user_input[CONF_SCAN_INTERVAL_DAYS]
                        ),
                        CONF_TRACKED_TYPES: user_input[CONF_TRACKED_TYPES],
                        CONF_LOOKAHEAD_DAYS: user_input[CONF_LOOKAHEAD_DAYS],
                        CONF_DISCOVERY_START: user_input[CONF_DISCOVERY_START],
                        CONF_ENABLE_PERSISTENT_NOTIFICATION: user_input[
                            CONF_ENABLE_PERSISTENT_NOTIFICATION
                        ],
                    }
                )

        schema = vol.Schema(
            {
                vol.Required(CONF_PDF_URL, default=current_url): TextSelector(),
                vol.Required(
                    CONF_SCAN_INTERVAL_DAYS,
                    default=str(
                        options.get(
                            CONF_SCAN_INTERVAL_DAYS, DEFAULT_SCAN_INTERVAL_DAYS
                        )
                    ),
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=_INTERVAL_OPTIONS,
                        translation_key="scan_interval_days",
                    )
                ),
                vol.Required(
                    CONF_TRACKED_TYPES,
                    default=options.get(
                        CONF_TRACKED_TYPES, list(WASTE_TYPES.keys())
                    ),
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=_TYPE_OPTIONS,
                        multiple=True,
                        mode=SelectSelectorMode.LIST,
                    )
                ),
                vol.Required(
                    CONF_LOOKAHEAD_DAYS,
                    default=options.get(
                        CONF_LOOKAHEAD_DAYS, DEFAULT_LOOKAHEAD_DAYS
                    ),
                ): vol.All(vol.Coerce(int), vol.Range(min=7, max=180)),
                vol.Required(
                    CONF_DISCOVERY_START,
                    default=options.get(
                        CONF_DISCOVERY_START, DEFAULT_DISCOVERY_START
                    ),
                ): TextSelector(),
                vol.Required(
                    CONF_ENABLE_PERSISTENT_NOTIFICATION,
                    default=options.get(
                        CONF_ENABLE_PERSISTENT_NOTIFICATION,
                        DEFAULT_ENABLE_PERSISTENT_NOTIFICATION,
                    ),
                ): BooleanSelector(),
            }
        )
        return self.async_show_form(
            step_id="init", data_schema=schema, errors=errors
        )
