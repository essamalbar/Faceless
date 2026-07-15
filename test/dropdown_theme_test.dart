import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:faceless/theme.dart';

void main() {
  testWidgets('open dropdown menu has a SOLID background (drop.png bug)',
      (t) async {
    await t.pumpWidget(MaterialApp(
      theme: FacelessTheme.build(),
      home: Scaffold(
        body: Center(
          child: DropdownButton<String>(
            key: const Key('dd'),
            value: 'a',
            items: const [
              DropdownMenuItem(value: 'a', child: Text('Option A')),
              DropdownMenuItem(value: 'b', child: Text('Option B')),
            ],
            onChanged: (_) {},
          ),
        ),
      ),
    ));
    await t.tap(find.byKey(const Key('dd')));
    await t.pumpAndSettle();
    // The open menu paints on theme.canvasColor — it must be opaque.
    final theme = FacelessTheme.build();
    expect(theme.canvasColor.a, 1.0,
        reason: 'canvasColor must be opaque or dropdown menus are see-through');
    expect(find.text('Option B'), findsOneWidget); // menu actually open
  });
}
