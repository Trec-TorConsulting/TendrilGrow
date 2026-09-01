# FAQ

## Is this only for cannabis?

No. It is a generic indoor-cultivation integration. Grow types include `rdwc`,
`dwc`, `aeroponic`, `soil`, `coco`, and `other`, plus custom text.

## Does it control equipment by itself?

No. Switches and services are opt-in. You write automations and you own the
risk. See [Pumps](pumps.md) and [Examples](examples.md).

## Which AI providers work?

Google Gemini, OpenAI, and Ollama. Credentials first, then pick a **vision**
model. [AI health](ai-health.md).

## Do I need Tuya or LocalTuya?

No. Bind LocalTuya/Tuya Local when you have that probe. Or map any pH/EC
entities you already have. Cloud OpenAPI is optional fallback.
[Tuya / LocalTuya](tuya-water.md).

## Does it need internet?

Cloud AI and Tuya cloud polling do. Ollama and LocalTuya can stay on LAN.
Helpers, VPD, flush tracking, and pumps work without a cloud AI.

## Multiple tents?

Yes. One config entry per grow space. Each has its own mappings, helpers, and
AI provider.

## Are API keys stored safely?

They live in the config entry like other HA credentials. Diagnostics redact
them. Never paste keys into GitHub.

## Will AI checks cost money?

Cloud providers bill per usage. Interval default is 12 hours. Ollama is
self-hosted.

## What Home Assistant version?

**2026.2.0** or newer.

## Week In Stage is not editable

Correct. Set **Stage Started** (or change Growth Stage, then backdate).
[Cultivation plan](cultivation.md#stage-started-and-week-in-stage).

## HACS does not show TendrilGrow

Add the **custom repository** first, category **Integration**.
[Installation](installation.md).

## Where is the official docs site?

<https://trec-torconsulting.github.io/TendrilGrow/>

## How do I get help?

[Discussions](https://github.com/Trec-TorConsulting/TendrilGrow/discussions) or
an [issue](https://github.com/Trec-TorConsulting/TendrilGrow/issues/new/choose).
Security: [SECURITY.md](https://github.com/Trec-TorConsulting/TendrilGrow/blob/main/SECURITY.md).
