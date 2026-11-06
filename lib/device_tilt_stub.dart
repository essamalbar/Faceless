/// Stub for non-web platforms. Device-orientation tilt is wired up through the
/// browser's DeviceOrientationEvent (web build only); a native iOS/Android app
/// would use a sensor plugin instead. Here it's a no-op, so TiltCard falls back
/// to pointer hover + the idle sway.
library;

import 'package:flutter/widgets.dart';

void startDeviceTilt(ValueNotifier<Offset> target) {}
