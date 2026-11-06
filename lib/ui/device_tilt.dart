/// App-wide device tilt for the 3D cards. On web, the phone's orientation
/// sensor drives [deviceTilt]; everywhere else it stays neutral and TiltCard
/// falls back to pointer hover + the idle sway. Each axis is normalized to
/// -1..1 (0 = flat / held naturally).
library;

import 'package:flutter/widgets.dart';

import '../device_tilt_stub.dart'
    if (dart.library.js_interop) '../device_tilt_web.dart';

/// Shared, read it with a ValueListenableBuilder or addListener.
final ValueNotifier<Offset> deviceTilt = ValueNotifier<Offset>(Offset.zero);

bool _started = false;

/// Begin feeding device-orientation into [deviceTilt]. Safe to call more than
/// once; only the first call wires the sensor. Call it once at app start.
void initDeviceTilt() {
  if (_started) return;
  _started = true;
  startDeviceTilt(deviceTilt);
}
