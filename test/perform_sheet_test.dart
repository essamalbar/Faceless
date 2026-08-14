import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:image_picker/image_picker.dart';

import 'package:faceless/api/client.dart';
import 'package:faceless/api/settings.dart';
import 'package:faceless/theme.dart';
import 'package:faceless/ui/brand.dart';
import 'package:faceless/widgets/perform_sheet.dart';

class _FixedSettings extends FacelessSettings {
  @override
  Future<String?> baseUrl() async => 'http://localhost:9999';
  @override
  Future<String?> tokenForLegacyMode() async => 'fake-dev-token';
}

Widget _host(Widget child) => MaterialApp(
      theme: FacelessTheme.build(),
      home: Scaffold(body: child),
    );

GradientButton _approveButton(WidgetTester tester) =>
    tester.widget<GradientButton>(find.byType(GradientButton));

// A real (if tiny) 1x1 transparent PNG so Image.memory can actually decode
// it — arbitrary bytes throw an image-codec exception that fails the test
// even though it has nothing to do with the enable/disable logic under test.
final _fakePhotoBytes = base64Decode(
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk'
  '+A8AAQUBAScY42YAAAAASUVORK5CYII=',
);

void main() {
  testWidgets(
      'Approve is disabled until a photo is picked AND attestation is checked',
      (tester) async {
    final client = FacelessApiClient(_FixedSettings());
    await tester.pumpWidget(_host(PerformSheet(
      client: client,
      runId: 'run-1',
      pickImage: (source) async =>
          XFile.fromData(_fakePhotoBytes, name: 'me.jpg'),
    )));
    await tester.pumpAndSettle();

    // Nothing picked, nothing checked — disabled.
    expect(_approveButton(tester).onPressed, isNull);

    // Attestation alone isn't enough.
    await tester.tap(find.byType(Checkbox));
    await tester.pumpAndSettle();
    expect(_approveButton(tester).onPressed, isNull);

    // Picking a photo (attestation already checked) enables it.
    await tester.tap(find.text('Gallery'));
    await tester.pumpAndSettle();
    expect(_approveButton(tester).onPressed, isNotNull);
    // Thumbnail should now be showing instead of the placeholder icon.
    expect(find.byType(Image), findsOneWidget);

    // Unchecking attestation disables it again even with a photo picked.
    await tester.tap(find.byType(Checkbox));
    await tester.pumpAndSettle();
    expect(_approveButton(tester).onPressed, isNull);
  });

  testWidgets('a canceled picker (null result) leaves Approve disabled',
      (tester) async {
    final client = FacelessApiClient(_FixedSettings());
    await tester.pumpWidget(_host(PerformSheet(
      client: client,
      runId: 'run-1',
      pickImage: (source) async => null,
    )));
    await tester.pumpAndSettle();

    await tester.tap(find.byType(Checkbox));
    await tester.tap(find.text('Camera'));
    await tester.pumpAndSettle();

    expect(_approveButton(tester).onPressed, isNull);
  });

  testWidgets('cost card shows the real credit price, not a hardcoded figure',
      (tester) async {
    // Finding 4: the disclosed price must equal what's charged
    // (perform_credits from the backend), never a stale hardcoded string.
    final client = FacelessApiClient(_FixedSettings());
    await tester.pumpWidget(_host(PerformSheet(
      client: client,
      runId: 'run-1',
      performCredits: 7,
      pickImage: (source) async => null,
    )));
    await tester.pumpAndSettle();

    expect(find.textContaining('7 credits'), findsOneWidget);
    expect(find.textContaining(r'$2.40'), findsNothing);
  });
}
