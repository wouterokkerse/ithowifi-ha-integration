## v0.4.1

Bug fix release: skip fan/preset/fan-demand entities for Heatpump (WPU) and AutoTemp devices.

### Bug Fixes

- **No more phantom fan entity for Heatpump (WPU) and AutoTemp devices.** Previously the integration unconditionally created `fan`, `number` (fan demand), and timer/cook preset button entities regardless of the connected Itho device type. For users with a WPU heatpump or AutoTemp device this produced a non-functional fan entity and meaningless preset buttons. The integration now registers these fan-related entities only for ventilation/fan devices. The reboot button and all sensors remain available for every device type.

  Closes [#351](https://github.com/arjenhiemstra/ithowifi/issues/351) (follow-up: user reported the integration also created a phantom fan entity for their WPU5G).

### Known Limitation

DemandFlow devices still get the (single) main fan entity even though their natural model is one fan-controller per configured remote. Per-remote fan entities for DemandFlow are planned for v0.5.0.

### Internal

- New `is_fan_device(itho_devtype)` helper in `const.py` with `NON_FAN_DEVICE_TYPES` constant (`Heatpump`, `AutoTemp`). Used by `fan.py`, `number.py`, and `button.py` to gate setup. Substring matching so "AutoTemp Basic" is also recognised. Unknown / empty / "Generic Itho device" types are treated as fan-like (RF standalone setups land in this bucket).

### Compatibility

No breaking changes. Users with fan devices see no difference. Users with WPU or AutoTemp devices will see the phantom fan/preset entities disappear after reload — Home Assistant will mark them as orphaned.

### Migration

After upgrading and restarting Home Assistant, the orphaned fan entity (e.g. `fan.itho_heatpump`) and preset buttons can be safely deleted from the device page.
