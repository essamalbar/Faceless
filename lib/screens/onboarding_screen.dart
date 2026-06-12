import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../theme.dart';

/// Full-screen welcome carousel shown to first-time visitors immediately
/// after login. Three slides explaining the two modes + the free-draft
/// payment model + a closing CTA.
///
/// "Seen" state is persisted in SharedPreferences under
/// `onboarding_seen_v1`. Bumping the suffix forces a re-show after major
/// product changes (when adding a new mode, for example).
class OnboardingScreen extends StatefulWidget {
  const OnboardingScreen({super.key});

  static const _prefKey = 'onboarding_seen_v1';

  /// Returns true if the user has already completed (or skipped) the
  /// onboarding. Reading is cheap; safe to call on every home-screen
  /// init to decide whether to push the onboarding route.
  static Future<bool> hasSeen() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      return prefs.getBool(_prefKey) ?? false;
    } catch (_) {
      // If SharedPreferences fails (extremely rare), treat as seen so
      // we never block the home screen behind a broken intro.
      return true;
    }
  }

  static Future<void> markSeen() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setBool(_prefKey, true);
    } catch (_) {
      // Best-effort. If this fails the user might see the intro again
      // on next launch — fine.
    }
  }

  @override
  State<OnboardingScreen> createState() => _OnboardingScreenState();
}

class _OnboardingScreenState extends State<OnboardingScreen> {
  final _pageController = PageController();
  int _page = 0;

  // Defined as static records so the widget tree below can map() over
  // them cleanly. Each slide is self-describing (no per-slide branches
  // in build()).
  static const List<_Slide> _slides = [
    _Slide(
      eyebrow: 'WELCOME',
      title: 'An Arabic AI studio that respects your wallet',
      body:
          "Faceless Lab generates cinematic Arabic horror shorts and "
          "original Arabic songs from a single sentence. You'll write the "
          "premise; we'll handle the rest.",
      icon: Icons.auto_awesome_outlined,
    ),
    _Slide(
      eyebrow: 'TWO MODES',
      title: 'Horror shorts. AI songs. One studio.',
      body:
          "Switch between Horror (cinematic Arabic shorts in 6 dialects) "
          "and Songs (full Suno-vocal tracks with AI cover art). Each "
          "render lives in your library and stays sharable forever.",
      icon: Icons.movie_filter_outlined,
    ),
    _Slide(
      eyebrow: 'FAIR PRICING',
      title: 'Free drafts. You only pay when you generate.',
      body:
          "Scripts and lyrics preview at zero cost. Approve when you're "
          "happy. If a render fails, the credits come back automatically — "
          "you never pay for video that didn't deliver.",
      icon: Icons.payments_outlined,
    ),
    _Slide(
      eyebrow: 'LET\'S GO',
      title: 'Your first draft is free.',
      body:
          "Tap below and write a sentence. The system will produce a full "
          "Arabic script or song lyrics for you to review — all before any "
          "credit is spent.",
      icon: Icons.rocket_launch_outlined,
    ),
  ];

  void _next() {
    if (_page < _slides.length - 1) {
      _pageController.nextPage(
        duration: const Duration(milliseconds: 320),
        curve: Curves.easeOutCubic,
      );
    } else {
      _finish();
    }
  }

  Future<void> _finish() async {
    await OnboardingScreen.markSeen();
    if (mounted) Navigator.of(context).pop();
  }

  Future<void> _skip() async {
    await OnboardingScreen.markSeen();
    if (mounted) Navigator.of(context).pop();
  }

  @override
  void dispose() {
    _pageController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final isLast = _page == _slides.length - 1;
    return Scaffold(
      backgroundColor: FacelessTheme.bg,
      body: SafeArea(
        child: Column(
          children: [
            // Top bar: skip button (no logo — slides set their own tone)
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 12, 16, 0),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.end,
                children: [
                  TextButton(
                    onPressed: _skip,
                    style: TextButton.styleFrom(
                      foregroundColor: FacelessTheme.textSecondary,
                    ),
                    child: const Text('Skip'),
                  ),
                ],
              ),
            ),
            Expanded(
              child: PageView.builder(
                controller: _pageController,
                onPageChanged: (i) => setState(() => _page = i),
                itemCount: _slides.length,
                itemBuilder: (ctx, i) => _SlideView(slide: _slides[i]),
              ),
            ),
            // Progress dots
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 16),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: List.generate(_slides.length, (i) {
                  final active = i == _page;
                  return AnimatedContainer(
                    duration: const Duration(milliseconds: 240),
                    margin: const EdgeInsets.symmetric(horizontal: 4),
                    width: active ? 22 : 7,
                    height: 7,
                    decoration: BoxDecoration(
                      color: active
                          ? FacelessTheme.accent
                          : FacelessTheme.textSecondary.withValues(alpha: 0.5),
                      borderRadius: BorderRadius.circular(4),
                    ),
                  );
                }),
              ),
            ),
            // CTA
            Padding(
              padding: const EdgeInsets.fromLTRB(24, 0, 24, 32),
              child: SizedBox(
                width: double.infinity,
                height: 52,
                child: FilledButton(
                  onPressed: _next,
                  style: FilledButton.styleFrom(
                    backgroundColor: FacelessTheme.accent,
                    foregroundColor: const Color(0xFF0F0C06),
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(26),
                    ),
                    textStyle: const TextStyle(
                      fontSize: 16,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                  child: Text(isLast ? "Let's create" : 'Next'),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _Slide {
  final String eyebrow;
  final String title;
  final String body;
  final IconData icon;
  const _Slide({
    required this.eyebrow,
    required this.title,
    required this.body,
    required this.icon,
  });
}

class _SlideView extends StatelessWidget {
  final _Slide slide;
  const _SlideView({required this.slide});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 32),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Big circular icon with accent glow
          Center(
            child: Container(
              width: 120,
              height: 120,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: FacelessTheme.accent.withValues(alpha: 0.10),
                boxShadow: [
                  BoxShadow(
                    color: FacelessTheme.accent.withValues(alpha: 0.18),
                    blurRadius: 40,
                    spreadRadius: 8,
                  ),
                ],
              ),
              child: Icon(slide.icon,
                  color: FacelessTheme.accent, size: 56),
            ),
          ),
          const SizedBox(height: 48),
          Text(
            slide.eyebrow,
            style: TextStyle(
              color: FacelessTheme.accent,
              fontSize: 12,
              letterSpacing: 2,
              fontWeight: FontWeight.w600,
            ),
          ),
          const SizedBox(height: 12),
          Text(
            slide.title,
            style: TextStyle(
              color: FacelessTheme.textPrimary,
              fontSize: 26,
              fontWeight: FontWeight.w700,
              height: 1.25,
              letterSpacing: -0.5,
            ),
          ),
          const SizedBox(height: 16),
          Text(
            slide.body,
            style: TextStyle(
              color: FacelessTheme.textPrimary,
              fontSize: 15,
              height: 1.55,
            ),
          ),
        ],
      ),
    );
  }
}
