# Troubleshooting

## AI health entities are missing

AI health entities are only created when AI is fully configured:

1. Map a `camera` entity for the grow space.
2. Select a provider (`Gemini`, `OpenAI`, or `Ollama`) — not `None`.
3. Choose a **vision-capable** model.

Re-open **Options** and confirm all three, then reload the integration.

## Model discovery failed

If the provider's model list cannot be fetched (network, credentials, or
endpoint issues), you can enter a model name manually on the model-selection
step. Verify the API key/endpoint and that the account has access to a
vision-capable model.

## VPD looks wrong

VPD is computed from the **air** temperature and humidity (canopy), not the
water probe. If VPD is off:

- Confirm `temperature`/`humidity` are mapped to **air/canopy** sensors.
- Confirm the water probe is mapped to `water_temperature`, not the air role.

See [Configuration](configuration.md#sensor-roles).

## Tuya / LocalTuya sensors are missing

1. Prefer LocalTuya (or Tuya Local): confirm the probe device exists in HA and
   is selected as this grow space’s **Local water monitor**.
2. For cloud fallback only: confirm Tuya is enabled and the access ID, access
   secret, region, and device IDs are correct; keep the poll interval at least
   600s on Trial projects.
3. Call [`tendrilgrow.rebuild_automap`](services.md#tendrilgrowrebuild_automap)
   to reload and rebuild auto-mapped roles.
4. Check the logs for the `custom_components.tendrilgrow` logger.
5. If you just left cloud polling, dashboard entity ids may still point at
   `sensor.*_tuya_*` — regenerate with `scripts/generate_dashboard.py`.

## Entities are unavailable after an update

Custom integrations require a Home Assistant **restart** to load new code.
After updating in HACS, restart Home Assistant.

## Dashboards reference old entity IDs

If you renamed grow spaces or updated across a version that changed entity IDs,
storage-mode (UI-managed) dashboards keep the old IDs. Update the affected cards,
or regenerate the dashboard from live entities with
`scripts/generate_dashboard.py` (see [Dashboards](dashboards.md)).

## Collecting diagnostics

Download redacted diagnostics from **Settings → Devices & Services →
TendrilGrow → the entry → ⋯ → Download diagnostics**. API keys and the Tuya
access secret are redacted, so it is safe to attach to a discussion or issue.

## Still stuck?

- Ask in [Discussions](https://github.com/Trec-TorConsulting/TendrilGrow/discussions).
- File a [bug report](https://github.com/Trec-TorConsulting/TendrilGrow/issues/new/choose)
  with your Home Assistant version, TendrilGrow version, and sanitized logs.
