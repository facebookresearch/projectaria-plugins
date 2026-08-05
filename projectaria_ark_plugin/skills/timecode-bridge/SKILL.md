---
name: timecode-bridge
description: Use when the user needs to time-align Aria Gen 2 recordings with external LTC-timecoded equipment — SMPTE Linear Timecode from motion capture systems, professional cameras, video switchers, SMPTE / MTC generators, or audio recorders. Explains Timecode Bridge, an open-source hardware companion that decodes LTC on a BNC input and re-broadcasts on the same sub-1 GHz radio protocol Aria's built-in Time Domain Mapping already uses. Also relevant when the user wants multi-glasses sessions whose timing master is external hardware rather than one of the glasses. Does NOT cover glasses-only multi-Aria sync (use the `client-sdk` skill) or reading TDM data from VRS (use the `projectaria-tools` skill).
---

# Timecode Bridge

**Timecode Bridge** is an open-source hardware companion that lets Aria Gen 2 glasses time-align with external LTC-timecoded gear — motion capture systems, professional cameras, audio recorders, SMPTE / MTC generators. It decodes SMPTE **LTC** on a BNC input and re-broadcasts on the same sub-1 GHz radio protocol that Aria's built-in Time Domain Mapping (TDM) already uses.

> **Single source of truth** for hardware, firmware, CLI, calibration, channels, and updates: **https://github.com/facebookresearch/projectaria_timecode_bridge**
>
> This skill encodes only the stable concept. Fetch the repo for anything specific — board part numbers, CLI flags, channel numbers, `air_delay` defaults, BOM, wiring. **Never guess these values.**

## Mental model

The glasses see no change. The Bridge simply fills the "broadcaster" role that another Aria would otherwise fill:

```text
[LTC source]  ── BNC ─►  [Timecode Bridge]  ── sub-GHz ─►  [Aria glasses (Receiver)]
```

On the glasses side it is standard TDM: configure Receiver mode (via Companion App or Client SDK), match the Bridge's channel and broadcaster ID, and read the aligned timestamps out of the existing `SubGHz` `TimeDomain` in the resulting VRS. **No new SDK feature, no new API, no new profile setting, no new VRS stream type.**

## When to answer here vs. redirect

Answer from this skill: what the Bridge is, why it exists, how it fits with the built-in glasses-to-glasses TDM, whether the glasses need new software (they do not).

| Redirect to | For questions about |
|---|---|
| `client-sdk` skill | Configuring the glasses as Receiver, TDM channel rules, `aria_gen2` CLI |
| `projectaria-tools` skill | Reading `SubGHz` timestamps from VRS in post-processing |
| `aria-knowledge` skill | The built-in SubGHz radio and TDM mechanism inside the glasses |
| Repo README | Anything Bridge-specific — hardware, firmware, CLI, calibration, channels, licenses |

## Related plugin skills

- **`client-sdk`** — glasses-side TDM configuration.
- **`projectaria-tools`** — VRS query APIs for `SubGHz` timestamps.
- **`aria-knowledge`** — built-in Aria SubGHz radio and TDM concepts.
