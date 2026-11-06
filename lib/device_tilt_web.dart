/// Device-orientation tilt (web build only). Feeds the phone's physical tilt
/// into [target] as an Offset with each axis normalized to -1..1, so TiltCard
/// can lean toward however the device is held.
///
///   gamma  (left/right, -90..90)  -> x
///   beta   (front/back, -180..180, ~45 = a natural hold) -> y
///
/// iOS 13+ gates motion behind a permission prompt that must be triggered by a
/// user gesture, so there we request permission on the first tap. Android and
/// desktop browsers deliver the events without a prompt. All of it is
/// best-effort: any failure just leaves the tilt at neutral (hover + idle still
/// work).
library;

import 'dart:js_interop';
import 'dart:js_interop_unsafe';

import 'package:flutter/widgets.dart';
import 'package:web/web.dart' as web;

void startDeviceTilt(ValueNotifier<Offset> target) {
  void attach() {
    web.window.addEventListener(
      'deviceorientation',
      ((web.Event e) {
        final doe = e as web.DeviceOrientationEvent;
        final g = (doe.gamma ?? 0).toDouble();
        final b = (doe.beta ?? 0).toDouble();
        target.value = Offset(
          (g / 30).clamp(-1.0, 1.0).toDouble(),
          ((b - 45) / 30).clamp(-1.0, 1.0).toDouble(),
        );
      }).toJS,
    );
  }

  // Does this browser (iOS 13+ Safari) require an explicit permission grant?
  JSObject? gated;
  try {
    final doe = globalContext.getProperty('DeviceOrientationEvent'.toJS);
    if (doe != null && !doe.isUndefinedOrNull) {
      final fn = (doe as JSObject).getProperty('requestPermission'.toJS);
      if (fn.typeofEquals('function')) gated = doe;
    }
  } catch (_) {}

  if (gated == null) {
    attach();
    return;
  }

  // Request on the first tap, then stop listening for taps.
  final JSObject doe = gated;
  late final JSFunction onFirstTap;
  onFirstTap = ((web.Event _) {
    try {
      final p =
          doe.callMethod('requestPermission'.toJS) as JSPromise<JSString>?;
      p?.toDart.then((state) {
        if (state.toDart == 'granted') attach();
      });
    } catch (_) {}
    web.window.removeEventListener('pointerdown', onFirstTap);
  }).toJS;
  web.window.addEventListener('pointerdown', onFirstTap);
}
