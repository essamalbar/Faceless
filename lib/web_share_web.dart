/// Web Share API binding (web build only).
///
/// `navigator.share({url, title, text})` is supported on:
///   • Safari (iOS + macOS)
///   • Chrome / Edge on Android, Windows, ChromeOS
///   • Chrome on macOS (>= 89)
///
/// Returns `false` when:
///   • The API is missing (Firefox, older browsers)
///   • The user cancels the share sheet
///   • The page isn't served over HTTPS
///   • Any other browser-side error
///
/// On false, callers should fall back to a copy-link dialog or
/// platform-specific share path.

import 'dart:js_interop';

@JS('navigator.share')
external JSPromise<JSAny?>? _share(_ShareData data);

extension type _ShareData._(JSObject _) implements JSObject {
  external factory _ShareData({String? url, String? title, String? text});
}

Future<bool> tryNativeWebShare({
  required String url,
  required String title,
  String? text,
}) async {
  try {
    final promise = _share(_ShareData(url: url, title: title, text: text));
    if (promise == null) return false;
    await promise.toDart;
    return true;
  } catch (_) {
    // User cancelled, API not present, or browser rejected the call.
    // Caller falls back to its alt UI.
    return false;
  }
}
