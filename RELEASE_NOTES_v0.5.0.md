## v0.5.0

Per-remote fan entities, new main-fan preset buttons, a setup-wizard step to pick which remotes to expose, and an RF-dispatch fix that stops the main fan from accidentally spoofing a receive-only remote. Requires firmware **3.1.0-beta4** or newer for accurate per-remote-type preset lists.

### New Features

#### Per-remote fan entities

Every configured virtual or RF SEND remote on the add-on can be exposed as its own Home Assistant `fan` entity that routes commands to that specific remote index. Intended primarily for **DemandFlow** users (where each zone is controlled by its own remote and there is no single "main fan"), and available as an opt-in for CVE / HRU / QualityFlow users with multiple virtual remotes.

- **`IthoRemoteFan`**: one `fan` entity per configured `(virtual|rf, index)` pair. Friendly name `Virtual Remote: <name>` or `RF Remote: <name>`, taken live from the remote's `name` field.
- **Preset list is per-remote-type.** An RFT CVE remote sees `away, low, medium, high, timer1/2/3`. An RFT CO2 remote sees `low, medium, high, auto, autonight, timer1/2/3`. Populated dynamically from the firmware's new `presets` field on each remote, which mirrors the actual RF command maps in `IthoCC1101.cpp` — no more dropdown entries for presets the remote doesn't physically support.
- **`preset_mode` state** reflects the last command dispatched via the remote (firmware-side `last_cmd` field). For persistent presets (low/medium/high/auto/autonight/away) the state is shown directly. For timer/cook presets, the state is gated on `ithostatus.RemainingTime (min)` — while the timer is still running the preset stays visible; once it expires (or if the device doesn't report RemainingTime at all), it clears.
- **`percentage`** maps low/medium/high → 33/66/100, `away` → 0, and `auto`/`autonight`/timer/cook → `None` (they aren't meaningfully representable as a percentage).
- **Supported features**: `PRESET_MODE | TURN_ON | TURN_OFF`. No `SET_SPEED` — per-remote commands are preset-only.
- **`turn_off`** prefers `away` if the remote type exposes it, falls back to `low` otherwise. For remote types with neither, turn-off is a safe no-op.
- **`turn_on`** with a target percentage picks the nearest preset the remote type actually supports. Bare "turn on" prefers `medium`, falls through `auto` / `high` / `low`.
- **`extra_state_attributes`** exposes `remote_kind`, `remote_index`, `remote_name`, `remote_type`, `remote_function`, and `last_cmd` for debugging.
- **Dispatch**: virtual → `POST /api/v2/vremote {"command":..., "index": N}`. RF SEND → `POST /api/v2/rfremote/command {"command":..., "index": N}`.

#### New setup wizard step: RF and Virtual Remote devices

After the sensor selection step, the setup wizard now shows a new **"RF and Virtual Remote devices"** form listing every configured remote on the device with a checkbox labelled `Virtual Remote N — <name> (<type>)` / `RF Remote N — <name> (<type>)`. Tick the ones you want to expose as individual fan entities.

- **DemandFlow devices**: all configured remotes are pre-selected.
- **Other fan devices**: empty list by default (opt-in).
- **Devices with no configured remotes**: the step is silently skipped.
- Same multi-select also appears in **Settings → Devices & Services → IthoWiFi → Configure** for changes after setup.

#### New main-fan preset buttons

For every fan-capable device (not just QualityFlow/DemandFlow), the main fan now gets dedicated one-press button entities:

- `Low` (`mdi:fan-speed-1`)
- `Medium` (`mdi:fan-speed-2`)
- `High` (`mdi:fan-speed-3`)
- `Auto` (`mdi:fan-auto`)
- `Auto night` (`mdi:weather-night`)

These sit alongside the existing `Timer 1` / `Timer 2` / `Timer 3` buttons (and `Cook 30` / `Cook 60` for QF/DF). The buttons dispatch through the same path as the main fan entity's `set_preset_mode` — the firmware's `ithoExecCommand` handles the routing (vremote 0 dispatch when `itho_vremoteapi=1`, PWM2I2C speed otherwise), so the same command semantics apply.

#### RF dispatch fix for the main fan

Previously the main fan entity and its buttons dispatched RF commands to remote index 0 unconditionally. On setups where index 0 is a RECEIVE remote (e.g. RF standalone with a SEND remote configured at index 1), this sent packets spoofing the RX remote's ID rather than using the configured SEND remote. The integration now picks the **first non-empty SEND remote** from the remotes coordinator on every RF dispatch, falling back to index 0 only when no SEND remote is configured. Fix applies to all four main-fan RF code paths: `set_preset_mode`, `set_percentage`, `turn_on`, `turn_off`, plus the new main-fan preset buttons.

#### Rescan remotes button

New `button` entity (`mdi:refresh`, config category) that forces an immediate refresh of the remotes coordinator. Use after renaming/adding/removing a remote in the device's web UI so HA picks up the change without waiting for the 30s polling interval or reloading the integration.

#### Translations

All new UI strings added to `strings.json` and `translations/en.json` + `translations/nl.json`:

- New `remote_fans` step title: **"RF and Virtual Remote devices"** / "RF- en Virtuele-afstandsbedieningen"
- Options flow `init` step retitled "Configure IthoWiFi" / "IthoWiFi configureren" to reflect its broader scope.

### Internal

- **New `IthoRemotesCoordinator`** polling `/api/v2/remotes` and `/api/v2/vremotes` on a 30 second interval. Tolerates a missing `/api/v2/vremotes` endpoint (older firmware) by stopping vremote polls and falling back to RF-only remote data.
- **New API client methods** in `api.py`: `get_remotes()` and `get_vremotes()`.
- **New `CONF_REMOTE_FANS` option key** storing a list of `vr:<index>` / `rf:<index>` strings.
- **New `is_demandflow_device(itho_devtype)` helper** in `const.py` (substring match on `"DemandFlow"`).
- **New module helper `pick_main_fan_rf_index(remotes_coordinator)`** in `fan.py`, used by both `IthoFan` and `IthoCommandButton` for RF dispatch.
- **`IthoFan`** constructor now takes the remotes coordinator alongside the status + device-info coordinators.
- **`IthoCommandButton`** optionally takes the remotes coordinator for RF dispatch routing.
- **`IthoRemoteFan`** inherits directly from `CoordinatorEntity[IthoRemotesCoordinator]` + `FanEntity` rather than via `IthoEntity`, so it can bind to the dedicated remotes coordinator while still reporting itself as part of the main device via `device_info`. Holds a reference to the status coordinator for `RemainingTime` lookups.
- **Entity name is recomputed on every coordinator update**, so renaming a remote in the device web UI is reflected after the next refresh.

### Compatibility

- **Requires firmware [3.1.0-beta4](https://github.com/arjenhiemstra/ithowifi/releases/tag/Version-3.1.0-beta4) or newer** for the per-remote-type preset list. On `3.1.0-beta3`, per-remote fans fall back to a conservative `low / medium / high` preset set instead of the accurate per-remote list — commands still dispatch correctly but users may see presets their remote doesn't actually support. `last_cmd` state display works on `3.1.0-beta3` and newer.
- **On firmware `3.1.0-beta2` or older**, `/api/v2/vremotes` returned an empty object (fixed in beta3), so no per-remote fans will be offered for virtual remotes until the firmware is upgraded.
- **Existing users on non-DemandFlow devices** see the main fan entity unchanged. New per-remote fans appear only if the user explicitly picks some in the setup wizard or options flow.
- **Existing users on DemandFlow devices** lose their main fan entity (which wasn't meaningful anyway) and gain per-remote fan entities for every configured remote.
- **All existing entities** (main fan, sensors, number, update, reboot) work as before. `Low` / `Medium` / `High` / `Auto` / `Auto night` are new button entities that appear alongside the existing timer/cook buttons.

### Known Limitations

- Per-remote `percentage` buckets are fixed at 33/66/100 (low/medium/high). There is no fine-grained 0-100% control because per-remote commands are preset-only.
- Multiple remotes each dispatching `timer1` will all show `timer1` as their current preset for the duration of the device's timer, even though technically only the last-dispatched remote "owns" it. The device only tracks a single timer at a time so there's no way to attribute it to one remote.
- When a remote is removed via the device web UI and you click Rescan, the fan entity becomes unavailable but isn't automatically deleted from HA. To fully remove it, go to Devices & Services → IthoWiFi → Configure, uncheck the removed remote, and save.
