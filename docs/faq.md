# FAQ

## Is TendrilGrow only for one type of plant?

No. It is a generic indoor-cultivation integration. Grow types include `rdwc`,
`dwc`, `aeroponic`, `soil`, `coco`, and `other`, and you can type a custom value.

## Does it control my equipment automatically?

No. Control (pumps, and any actuation) is manual and opt-in. TendrilGrow exposes
switches and services; you build automations yourself and are responsible for
validating them. See [Pump control and monitoring](pumps.md).

## Which AI providers are supported?

Google Gemini, OpenAI, and Ollama. After you enter credentials, TendrilGrow
discovers available models so you can pick one. See
[AI health checks](ai-health.md).

## Do I need Tuya / LocalTuya?

No. Prefer LocalTuya (or Tuya Local) when you have a Tuya Wi-Fi water probe —
TendrilGrow binds that HA device and skips cloud polling. Cloud OpenAPI
polling is optional fallback only. If you already have water sensors in Home
Assistant, map them directly. See
[Tuya / LocalTuya water monitoring](tuya-water.md).

## Does it require internet access?

Cloud AI providers (Gemini, OpenAI) and Tuya cloud polling require internet.
Ollama can run locally on your network. The rest of the integration works
locally.

## Can I run multiple tents or rooms?

Yes. Add one config entry per grow space; each has its own mappings, settings,
and AI provider.

## Are my API keys safe?

Keys and the Tuya access secret are treated as sensitive and are redacted in
diagnostics and logs. Never paste real keys into issues or discussions.

## Will AI checks cost money?

That depends on your provider. Cloud providers bill per usage according to their
own pricing; Ollama is self-hosted. Tune the check interval to control frequency.

## What Home Assistant version is required?

Home Assistant **2026.2.0** or newer.

## How do I get help?

Start a thread in
[Discussions](https://github.com/Trec-TorConsulting/TendrilGrow/discussions), or
open an [issue](https://github.com/Trec-TorConsulting/TendrilGrow/issues/new/choose).
