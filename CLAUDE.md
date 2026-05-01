# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project status

`faceless` is a Flutter application scaffolded via `flutter create`. As of now the codebase is essentially the default counter-app template (`lib/main.dart`, `test/widget_test.dart`) — there is no custom architecture, state management, routing, or feature code yet. Treat anything beyond the scaffold as new work.

Dart SDK constraint: `^3.11.0` (see `pubspec.yaml`). Supported platforms have been generated for Android, iOS, macOS, Linux, Windows, and Web (folders all present).

Note: `lib/main.dart` currently contains invalid Dart at lines 31 and 105 — `colorScheme: .fromSeed(...)` and `mainAxisAlignment: .center` are missing their leading type names (`ColorScheme` and `MainAxisAlignment`). Fix these before expecting `flutter run` / `flutter analyze` to succeed.

## Common commands

```bash
flutter pub get               # install dependencies
flutter run                   # run on the default connected device
flutter run -d chrome         # run on web
flutter run -d macos          # run on macOS desktop
flutter analyze               # static analysis (uses analysis_options.yaml)
flutter test                  # run all tests
flutter test test/widget_test.dart                                  # single file
flutter test test/widget_test.dart --plain-name "Counter increments"  # single test by name
flutter build apk             # release build (substitute ios / web / macos / linux / windows)
```

## Lints

`analysis_options.yaml` includes `package:flutter_lints/flutter.yaml` (flutter_lints ^6.0.0) with no project-specific rule overrides. Run `flutter analyze` before considering work done.
