"""Data update coordinator: download, parse, cache, rollover and failure handling."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

import aiohttp
from homeassistant.components import persistent_notification
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_ACTIVE_YEAR,
    CONF_DISCOVERY_START,
    CONF_ENABLE_PERSISTENT_NOTIFICATION,
    CONF_LOOKAHEAD_DAYS,
    CONF_SCAN_INTERVAL_DAYS,
    CONF_TRACKED_TYPES,
    CONF_URL_TEMPLATE,
    DEFAULT_DISCOVERY_START,
    DEFAULT_ENABLE_PERSISTENT_NOTIFICATION,
    DEFAULT_LOOKAHEAD_DAYS,
    DEFAULT_SCAN_INTERVAL_DAYS,
    DOMAIN,
    HTTP_TIMEOUT_SECONDS,
    NETWORK_FAILURE_THRESHOLD,
    REASON_NETWORK,
    REASON_NOT_FOUND,
    REASON_PARSE_ERROR,
    REASON_ROLLOVER_OVERDUE,
    USER_AGENT,
    WASTE_TYPES,
)
from .parser import ParseError, parse_pdf
from .url import build_url

_LOGGER = logging.getLogger(__name__)


@dataclass
class CalendarData:
    """Merged, cached view of parsed calendar data across years."""

    events: dict[date, set[str]] = field(default_factory=dict)
    loaded_years: set[int] = field(default_factory=set)
    problem_reason: str | None = None
    last_error: str | None = None
    last_success: datetime | None = None

    def coverage_until(self) -> date | None:
        """Latest date with a collection event."""
        return max(self.events) if self.events else None


class AbfallkalenderCoordinator(DataUpdateCoordinator[CalendarData]):
    """Fetches and parses the Abfallkalender PDF on a schedule."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        interval_days = entry.options.get(
            CONF_SCAN_INTERVAL_DAYS, DEFAULT_SCAN_INTERVAL_DAYS
        )
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(days=interval_days),
        )
        self.entry = entry
        self._data = CalendarData()
        self._consecutive_network_failures = 0

    @property
    def tracked_types(self) -> list[str]:
        """Waste codes the user opted to track."""
        return self.entry.options.get(
            CONF_TRACKED_TYPES, list(WASTE_TYPES.keys())
        )

    @property
    def _active_year(self) -> int:
        return self.entry.data[CONF_ACTIVE_YEAR]

    @property
    def _url_template(self) -> str:
        return self.entry.data[CONF_URL_TEMPLATE]

    async def _async_update_data(self) -> CalendarData:
        """Refresh the configured year and attempt rollover when needed."""
        try:
            await self._async_load_year(self._active_year, required=True)

            if self._should_probe_next_year():
                await self._async_try_rollover()

            self._evaluate_rollover_overdue()
        finally:
            self._sync_alerts()
        return self._data

    async def _async_load_year(self, year: int, *, required: bool) -> bool:
        """Download and parse one year; merge into cache on success.

        Returns True if the year was loaded. When required and the load fails,
        raises UpdateFailed but keeps previously cached data intact.
        """
        url = build_url(self._url_template, year)
        try:
            raw = await self._async_download(url)
        except _NotFound:
            self._record_problem(
                REASON_NOT_FOUND if required else None,
                f"PDF not found for {year}: {url}",
            )
            if required:
                raise UpdateFailed(f"PDF not found: {url}")
            return False
        except _NetworkError as err:
            self._consecutive_network_failures += 1
            reason = (
                REASON_NETWORK
                if self._consecutive_network_failures >= NETWORK_FAILURE_THRESHOLD
                else None
            )
            self._record_problem(reason, str(err))
            if required:
                raise UpdateFailed(str(err))
            return False

        try:
            parsed = await self.hass.async_add_executor_job(parse_pdf, raw)
        except ParseError as err:
            self._record_problem(REASON_PARSE_ERROR, str(err))
            if required:
                raise UpdateFailed(f"parse error: {err}")
            return False

        if parsed.year != year:
            # Do not trust a document whose internal year differs.
            _LOGGER.warning(
                "Expected calendar year %s but PDF reports %s", year, parsed.year
            )
            if required:
                raise UpdateFailed(
                    f"year mismatch: expected {year}, got {parsed.year}"
                )
            return False

        self._merge_year(parsed.year, parsed.events)
        self._consecutive_network_failures = 0
        self._clear_problem()
        return True

    def _merge_year(self, year: int, events: dict[date, set[str]]) -> None:
        """Replace a year's events in the cache, keeping other years."""
        self._data.events = {
            d: t for d, t in self._data.events.items() if d.year != year
        }
        self._data.events.update(events)
        self._data.loaded_years.add(year)

    def _should_probe_next_year(self) -> bool:
        """Whether to look for next year's PDF now."""
        next_year = self._active_year + 1
        if next_year in self._data.loaded_years:
            return False

        today = datetime.now().date()
        lookahead = self.entry.options.get(
            CONF_LOOKAHEAD_DAYS, DEFAULT_LOOKAHEAD_DAYS
        )
        coverage = self._data.coverage_until()
        low_on_coverage = coverage is not None and coverage <= today + timedelta(
            days=lookahead
        )
        return low_on_coverage or today >= self._discovery_start_date()

    async def _async_try_rollover(self) -> None:
        """Probe next year's URL; adopt and persist it on success."""
        next_year = self._active_year + 1
        loaded = await self._async_load_year(next_year, required=False)
        if not loaded:
            return

        new_data = {**self.entry.data, CONF_ACTIVE_YEAR: next_year}
        self.hass.config_entries.async_update_entry(self.entry, data=new_data)
        _LOGGER.info("Automatically adopted Abfallkalender for %s", next_year)

    def _evaluate_rollover_overdue(self) -> None:
        """Flag when next year is due but still unavailable."""
        today = datetime.now().date()
        next_year = self._active_year + 1
        coverage = self._data.coverage_until()
        lookahead = self.entry.options.get(
            CONF_LOOKAHEAD_DAYS, DEFAULT_LOOKAHEAD_DAYS
        )
        running_out = coverage is not None and coverage <= today + timedelta(
            days=lookahead
        )
        if (
            today >= self._discovery_start_date()
            and next_year not in self._data.loaded_years
            and running_out
            and self._data.problem_reason is None
        ):
            self._record_problem(
                REASON_ROLLOVER_OVERDUE,
                f"calendar for {next_year} not yet available",
            )

    def _discovery_start_date(self) -> date:
        raw = self.entry.options.get(CONF_DISCOVERY_START, DEFAULT_DISCOVERY_START)
        month, day = (int(p) for p in raw.split("-"))
        return date(datetime.now().year, month, day)

    async def _async_download(self, url: str) -> bytes:
        """Download a PDF, following redirects. Raises typed errors."""
        session = async_get_clientsession(self.hass)
        try:
            async with session.get(
                url,
                headers={"User-Agent": USER_AGENT},
                timeout=aiohttp.ClientTimeout(total=HTTP_TIMEOUT_SECONDS),
                allow_redirects=True,
            ) as response:
                if response.status == 404:
                    raise _NotFound(url)
                if response.status != 200:
                    raise _NetworkError(f"HTTP {response.status} for {url}")
                return await response.read()
        except aiohttp.ClientError as err:
            raise _NetworkError(str(err)) from err

    def _record_problem(self, reason: str | None, message: str) -> None:
        self._data.last_error = message
        if reason is not None:
            self._data.problem_reason = reason
            _LOGGER.warning("Abfallkalender problem (%s): %s", reason, message)

    def _clear_problem(self) -> None:
        self._data.problem_reason = None
        self._data.last_error = None
        self._data.last_success = datetime.now()

    def _sync_alerts(self) -> None:
        """Create or clear the Repairs issue and optional notification."""
        issue_id = f"{self.entry.entry_id}_problem"
        reason = self._data.problem_reason

        if reason is None:
            ir.async_delete_issue(self.hass, DOMAIN, issue_id)
            self._dismiss_notification()
            return

        severity = (
            ir.IssueSeverity.ERROR
            if reason == REASON_PARSE_ERROR
            else ir.IssueSeverity.WARNING
        )
        ir.async_create_issue(
            self.hass,
            DOMAIN,
            issue_id,
            is_fixable=False,
            severity=severity,
            translation_key=reason,
            translation_placeholders={
                "name": self.entry.title,
                "error": self._data.last_error or "",
            },
        )
        self._maybe_notify(reason)

    def _maybe_notify(self, reason: str) -> None:
        if not self.entry.options.get(
            CONF_ENABLE_PERSISTENT_NOTIFICATION,
            DEFAULT_ENABLE_PERSISTENT_NOTIFICATION,
        ):
            return
        persistent_notification.async_create(
            self.hass,
            f"Abfallkalender '{self.entry.title}': {self._data.last_error}",
            title="Abfallkalender RTK",
            notification_id=f"{DOMAIN}_{self.entry.entry_id}",
        )

    def _dismiss_notification(self) -> None:
        persistent_notification.async_dismiss(
            self.hass, f"{DOMAIN}_{self.entry.entry_id}"
        )


class _NotFound(Exception):
    """Internal: PDF returned HTTP 404."""


class _NetworkError(Exception):
    """Internal: transient download failure."""
