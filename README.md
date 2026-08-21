# Abfallkalender RTK

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![Validate](https://github.com/sourcesoldier/Abfallkalender-RTK/actions/workflows/validate.yml/badge.svg)](https://github.com/sourcesoldier/Abfallkalender-RTK/actions/workflows/validate.yml)
[![Test](https://github.com/sourcesoldier/Abfallkalender-RTK/actions/workflows/test.yml/badge.svg)](https://github.com/sourcesoldier/Abfallkalender-RTK/actions/workflows/test.yml)

A Home Assistant custom integration that reads the yearly waste-collection
calendar PDF for the Eltville / Rheingau-Taunus-Kreis (RTK) area, parses the
collection dates per bin type, and exposes them as a calendar plus per-bin
sensors. It refreshes on a schedule and can automatically pick up next year's
PDF when it is published.

Supported bins: Biomüll (BM), Gelbe Tonne (GT), Papiermüll (PM), Restmüll (RM),
Sondermüll (SM).

> Scope: tuned to the Eltville/RTK grid-PDF layout. Other municipalities use
> different PDFs and are not supported.

## Features

- Configuration entirely through the Home Assistant UI (no YAML).
- Calendar entity with one all-day event per collection day.
- Per-bin "next pickup" sensors plus a combined next-pickup sensor
  (`days_to`, `weekday`, `is_today`, `is_tomorrow`, bin `labels`).
- Automatic year rollover: when next year's PDF appears at the predictable URL,
  it is verified against the PDF's internal year and merged automatically.
- Failure handling: a Repairs issue and a diagnostic `problem` binary sensor,
  with an optional notification banner.
- Importable German automation blueprints for pickup reminders and problem
  alerts.

## Installation (HACS)

1. In HACS, add this repository as a custom repository (type: Integration).
2. Install "Abfallkalender RTK".
3. Restart Home Assistant.
4. Go to Settings > Devices & Services > Add Integration > "Abfallkalender RTK".
5. Enter the PDF URL for your area (the 2026 Erbach/Hattenheim/Rauenthal URL is
   the default), pick an update interval and the bins to track.

## Configuration

| Option | Description |
| --- | --- |
| PDF URL | Link to the yearly area PDF. The year in the URL is detected automatically. |
| Update interval | Daily or weekly refresh. |
| Tracked bins | Which waste types to expose. |
| Coverage lookahead (days) | How far ahead events must reach before probing next year. |
| Earliest next-year probe (MM-DD) | Earliest date in the year to look for the next PDF. |
| Notification banner on failure | Show a persistent notification in addition to the Repairs issue. |

## Automations

Two blueprints are provided under
`blueprints/automation/abfallkalender_rtk/`:

- `pickup_reminder.yaml` - notify the evening before a collection.
- `integration_problem_alert.yaml` - notify when the integration reports a
  problem.

### Example: remind everyone the night before at 19:00

If you prefer a plain YAML automation over the blueprint, this reminds all
household members the evening before any collection. It uses a calendar trigger:
all-day events start at midnight, so an offset of `-5:00:00` fires at 19:00 the
previous day.

```yaml
- id: abfallkalender_rtk_reminder_vorabend
  alias: Abfallkalender RTK – Erinnerung am Vorabend (19 Uhr)
  triggers:
  - trigger: calendar
    entity_id: calendar.abfallkalender_rtk_abfuhr
    event: start
    offset: '-5:00:00'
  conditions: []
  actions:
  - action: notify.household
    data:
      title: Abfallabholung morgen
      message: >-
        Morgen wird abgeholt: {{ trigger.calendar_event.summary
        if trigger is mapping and 'calendar_event' in trigger
        else 'Testbenachrichtigung' }}
      data:
        tag: abfallkalender-rtk
  mode: single
```

Notes:

- Replace `calendar.abfallkalender_rtk_abfuhr` with your calendar entity id
  (Settings > Devices & Services > Entities) and `notify.household` with your
  notify service. A [notify group](https://www.home-assistant.io/integrations/group/#notify-groups)
  named `household` is a convenient way to reach every companion app at once.
- The `if trigger is mapping ...` guard keeps a manual **Run** from failing when
  no calendar trigger context is present.
- `{{ trigger.calendar_event.summary }}` expands to the bins due, e.g.
  "Biomüll, Gelbe Tonne, Restmüll".

## Development

Pure-logic tests (parser and URL handling) run without Home Assistant:

```bash
python3.14 -m venv .venv
.venv/bin/pip install pdfplumber pytest
.venv/bin/python -m pytest tests/test_parser.py tests/test_rollover.py
```

Full integration tests (config flow, coordinator, entities) need the Home
Assistant test harness on Python 3.13:

```bash
python3.13 -m venv .venv-ha
.venv-ha/bin/pip install -r requirements-test.txt
.venv-ha/bin/python -m pytest
```

Deploy to a mounted HAOS config for on-device testing:

```bash
./deploy.sh /Volumes/config
# then restart Home Assistant
```

## License

MIT
