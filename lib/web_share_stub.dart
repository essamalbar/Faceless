/// Stub for non-web platforms (mobile, desktop). The Web Share API
/// is web-only; this fallback always returns false so callers fall
/// through to their alt UI.
Future<bool> tryNativeWebShare({
  required String url,
  required String title,
  String? text,
}) async {
  return false;
}
