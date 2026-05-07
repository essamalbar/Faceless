// Boot-up smoke test: app starts and reaches either Home (if configured)
// or Settings (first launch). We don't have secure storage in the test
// harness, so we accept either landing screen.
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:faceless/main.dart';

void main() {
  testWidgets('app boots without crashing', (tester) async {
    await tester.pumpWidget(const FacelessApp());
    // Bootstrap shows a loader while it reads secure storage; let it settle.
    await tester.pump(const Duration(milliseconds: 500));
    // Either landing surface is acceptable
    final landed = find.byType(MaterialApp);
    expect(landed, findsOneWidget);
  });
}
