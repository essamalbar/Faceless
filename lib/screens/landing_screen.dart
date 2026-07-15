import 'package:flutter/material.dart';

import '../l10n/l10n.dart';
import '../theme.dart';
import '../ui/brand.dart';
import '../widgets/faceless_logo.dart';
import 'login_screen.dart';

/// Public marketing page — shown to unauthenticated visitors before they
/// hit the login wall. Mission: convince a stranger landing here from
/// social media that this app is worth signing up for.
///
/// Sections, top-to-bottom:
///   1. Hero (logo + tagline + CTAs)
///   2. How it works (3 steps)
///   3. Showcase (3 sample reels)
///   4. Pricing (3 tiers, same as BillingScreen)
///   5. Footer
class LandingScreen extends StatelessWidget {
  const LandingScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.transparent,
      body: SafeArea(
        child: CustomScrollView(
          slivers: [
            SliverToBoxAdapter(child: _TopNav()),
            SliverToBoxAdapter(child: _Hero()),
            SliverToBoxAdapter(child: _HowItWorks()),
            SliverToBoxAdapter(child: _Showcase()),
            SliverToBoxAdapter(child: _Pricing()),
            SliverToBoxAdapter(child: _Footer()),
          ],
        ),
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// Top nav — small wordmark on the left, sign-in link on the right
// ---------------------------------------------------------------------------

class _TopNav extends StatelessWidget {
  const _TopNav();
  @override
  Widget build(BuildContext context) {
    return Center(
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 1120),
        child: Padding(
          padding: const EdgeInsets.fromLTRB(20, 18, 20, 0),
          child: Row(
            children: [
              const FacelessLogo(size: 30),
              const SizedBox(width: 10),
              Text('Faceless',
                  style: FacelessTheme.display(size: 18, weight: FontWeight.w700)),
              Text('Lab',
                  style: FacelessTheme.display(
                      size: 18, weight: FontWeight.w400, color: FacelessTheme.faint)),
              const Spacer(),
              // AR ⇄ EN toggle for pre-auth visitors; label shows the
              // language you'd switch TO.
              TextButton.icon(
                icon: const Icon(Icons.language, size: 18),
                label: Text(
                    Localizations.localeOf(context).languageCode == 'ar'
                        ? 'EN'
                        : 'العربية'),
                onPressed: () {
                  final cur = Localizations.localeOf(context).languageCode;
                  LocaleController.instance
                      .set(Locale(cur == 'ar' ? 'en' : 'ar'));
                },
              ),
              TextButton(
                onPressed: () => _goLogin(context, signUp: false),
                child: Text(context.l10n.commonSignIn),
              ),
              const SizedBox(width: 10),
              GradientButton(
                label: context.l10n.commonGetStarted,
                icon: Icons.arrow_forward,
                padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 12),
                onPressed: () => _goLogin(context, signUp: true),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// Hero — large logo, tagline, primary CTA
// ---------------------------------------------------------------------------

class _Hero extends StatelessWidget {
  const _Hero();

  @override
  Widget build(BuildContext context) {
    final wide = MediaQuery.sizeOf(context).width >= 900;
    final l10n = context.l10n;
    final copy = Column(
      crossAxisAlignment:
          wide ? CrossAxisAlignment.start : CrossAxisAlignment.center,
      children: [
        BrandPill(l10n.landingHeroPill, dot: true),
        const SizedBox(height: 22),
        DefaultTextStyle(
          style: FacelessTheme.display(size: wide ? 56 : 40, height: 1.04),
          textAlign: wide ? TextAlign.start : TextAlign.center,
          child: Wrap(
            alignment: wide ? WrapAlignment.start : WrapAlignment.center,
            children: [
              Text(l10n.landingHeroTitlePart1,
                  textAlign: wide ? TextAlign.start : TextAlign.center,
                  style: FacelessTheme.display(size: wide ? 56 : 40, height: 1.04)),
              GradientText(l10n.landingHeroTitlePart2Accent,
                  style: FacelessTheme.display(size: wide ? 56 : 40, height: 1.04)),
            ],
          ),
        ),
        const SizedBox(height: 20),
        ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 520),
          child: Text(
            l10n.landingHeroSubtitle,
            textAlign: wide ? TextAlign.start : TextAlign.center,
            style: const TextStyle(
                color: FacelessTheme.textSecondary, fontSize: 17, height: 1.6),
          ),
        ),
        const SizedBox(height: 30),
        Wrap(
          spacing: 14,
          runSpacing: 12,
          alignment: wide ? WrapAlignment.start : WrapAlignment.center,
          children: [
            GradientButton(
              label: l10n.landingStartCreating,
              icon: Icons.auto_awesome,
              onPressed: () => _goLogin(context, signUp: true),
            ),
            OutlinedButton.icon(
              onPressed: () => _goLogin(context, signUp: false),
              icon: const Icon(Icons.play_arrow_rounded),
              label: Text(l10n.commonSignIn),
            ),
          ],
        ),
        const SizedBox(height: 22),
        Text(l10n.landingTrustLine,
            style: TextStyle(color: FacelessTheme.faint, fontSize: 13)),
      ],
    );

    final card = ConstrainedBox(
      constraints: const BoxConstraints(maxWidth: 420),
      child: const _NowPlayingCard(),
    );

    return Center(
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 1120),
        child: Padding(
          padding: const EdgeInsets.fromLTRB(24, 56, 24, 48),
          child: wide
              ? Row(
                  crossAxisAlignment: CrossAxisAlignment.center,
                  children: [
                    Expanded(flex: 6, child: copy),
                    const SizedBox(width: 44),
                    Expanded(flex: 5, child: card),
                  ],
                )
              : Column(children: [copy, const SizedBox(height: 40), card]),
        ),
      ),
    );
  }
}

/// Hero showpiece — a glassy "now generating" song card with a waveform.
class _NowPlayingCard extends StatelessWidget {
  const _NowPlayingCard();
  @override
  Widget build(BuildContext context) {
    return GlassCard(
      padding: const EdgeInsets.all(22),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            height: 200,
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(16),
              gradient: coverGradient('حلم في الليل'),
            ),
            child: Stack(
              children: [
                Positioned(
                    top: 12,
                    left: 12,
                    child:
                        BrandPill(context.l10n.landingNowGenerating, dot: true)),
                const Center(child: Text('🌙', style: TextStyle(fontSize: 64))),
              ],
            ),
          ),
          const SizedBox(height: 18),
          Row(
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('حلم في الليل',
                        style: FacelessTheme.display(size: 20, weight: FontWeight.w600)),
                    const SizedBox(height: 3),
                    Text(context.l10n.landingSampleTagline,
                        style: TextStyle(color: FacelessTheme.textSecondary, fontSize: 13)),
                  ],
                ),
              ),
              Container(
                width: 50,
                height: 50,
                decoration: const BoxDecoration(
                    gradient: FacelessTheme.brandGradient, shape: BoxShape.circle),
                child: const Icon(Icons.play_arrow_rounded, color: Colors.white),
              ),
            ],
          ),
          const SizedBox(height: 18),
          const _Waveform(),
        ],
      ),
    );
  }
}

class _Waveform extends StatelessWidget {
  const _Waveform();
  @override
  Widget build(BuildContext context) {
    const heights = [0.4, 0.7, 0.95, 0.55, 0.8, 0.35, 0.65, 1.0, 0.5, 0.75,
      0.45, 0.85, 0.6, 0.3, 0.9, 0.55, 0.7, 0.4];
    return SizedBox(
      height: 40,
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.end,
        children: [
          for (final h in heights)
            Expanded(
              child: Container(
                margin: const EdgeInsets.symmetric(horizontal: 2),
                height: 40 * h,
                decoration: BoxDecoration(
                  borderRadius: BorderRadius.circular(3),
                  gradient: const LinearGradient(
                    begin: Alignment.bottomCenter,
                    end: Alignment.topCenter,
                    colors: [FacelessTheme.accent, FacelessTheme.accent2],
                  ),
                ),
              ),
            ),
        ],
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// How it works — 3 numbered steps
// ---------------------------------------------------------------------------

class _HowItWorks extends StatelessWidget {
  const _HowItWorks();
  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    return Center(
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 960),
        child: Padding(
          padding: const EdgeInsets.fromLTRB(20, 32, 20, 32),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              _SectionHeading(title: l10n.landingSectionHowItWorks),
              const SizedBox(height: 24),
              LayoutBuilder(
                builder: (ctx, c) {
                  // Two-column on wide screens, stacked on narrow.
                  final wide = c.maxWidth >= 720;
                  final cards = [
                    _StepCard(
                      number: '1',
                      title: l10n.landingStep1Title,
                      body: l10n.landingStep1Body,
                    ),
                    _StepCard(
                      number: '2',
                      title: l10n.landingStep2Title,
                      body: l10n.landingStep2Body,
                    ),
                    _StepCard(
                      number: '3',
                      title: l10n.landingStep3Title,
                      body: l10n.landingStep3Body,
                    ),
                  ];
                  if (wide) {
                    return Row(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        for (var i = 0; i < cards.length; i++) ...[
                          if (i > 0) const SizedBox(width: 16),
                          Expanded(child: cards[i]),
                        ],
                      ],
                    );
                  }
                  return Column(
                    children: [
                      for (var i = 0; i < cards.length; i++) ...[
                        if (i > 0) const SizedBox(height: 12),
                        cards[i],
                      ],
                    ],
                  );
                },
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _StepCard extends StatelessWidget {
  final String number;
  final String title;
  final String body;
  const _StepCard({
    required this.number,
    required this.title,
    required this.body,
  });
  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: FacelessTheme.surface,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(
          color: FacelessTheme.textSecondary.withValues(alpha: 0.12),
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            width: 36,
            height: 36,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              color: FacelessTheme.accent.withValues(alpha: 0.18),
              border: Border.all(
                color: FacelessTheme.accent.withValues(alpha: 0.5),
              ),
            ),
            alignment: Alignment.center,
            child: Text(number,
                style: const TextStyle(
                  color: FacelessTheme.accent,
                  fontWeight: FontWeight.w700,
                  fontSize: 16,
                )),
          ),
          const SizedBox(height: 14),
          Text(title,
              style: const TextStyle(
                color: FacelessTheme.textPrimary,
                fontWeight: FontWeight.w700,
                fontSize: 17,
              )),
          const SizedBox(height: 6),
          Text(body,
              style: const TextStyle(
                color: FacelessTheme.textSecondary,
                fontSize: 13,
                height: 1.5,
              )),
        ],
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// Showcase — 3 sample reels. Drop the real thumbnails + links here.
// ---------------------------------------------------------------------------

class _ShowcaseItem {
  final String title;
  final String tagline;
  final List<Color> gradient;
  final String? videoUrl;     // when null: card is a teaser, not playable
  final String? thumbnailUrl;
  const _ShowcaseItem({
    required this.title,
    required this.tagline,
    required this.gradient,
    // Placeholder slots — wired into _ShowcaseCard so swapping in real
    // demos is a one-line edit per entry. Empty for now until the
    // user uploads thumbnails / public video URLs.
    // ignore: unused_element_parameter
    this.videoUrl,
    // ignore: unused_element_parameter
    this.thumbnailUrl,
  });
}

// Edit this list to swap in your real demos. Each entry needs:
//   - thumbnailUrl: a public JPG/PNG URL (or null → falls back to the
//     gradient block, which still looks polished)
//   - videoUrl: a public mp4 / YouTube / Vimeo link to open on tap
//     (null → card is non-interactive, just visual)
//
// Mix horror + songs so visitors see both modes work. First two are
// horror, third is a song so the gallery doesn't read as a one-genre
// product.
List<_ShowcaseItem> _showcase(AppLocalizations l10n) => [
      _ShowcaseItem(
        title: 'البئر المهجور',
        tagline: l10n.landingShowcaseTagline1,
        gradient: const [Color(0xFFB07F1F), Color(0xFFE7B53C)],
      ),
      _ShowcaseItem(
        title: 'صوت من الجدار',
        tagline: l10n.landingShowcaseTagline2,
        gradient: const [Color(0xFF8B5CF6), Color(0xFF5B21B6)],
      ),
      _ShowcaseItem(
        title: 'تحت حراسة القمر',
        tagline: l10n.landingShowcaseTagline3,
        gradient: const [Color(0xFF1E3A8A), Color(0xFF312E81)],
      ),
    ];

class _Showcase extends StatelessWidget {
  const _Showcase();
  @override
  Widget build(BuildContext context) {
    return Center(
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 960),
        child: Padding(
          padding: const EdgeInsets.fromLTRB(20, 32, 20, 32),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              _SectionHeading(title: context.l10n.landingSectionShowcase),
              const SizedBox(height: 24),
              LayoutBuilder(builder: (ctx, c) {
                final wide = c.maxWidth >= 720;
                final cards = _showcase(context.l10n)
                    .map((s) => _ShowcaseCard(item: s))
                    .toList();
                if (wide) {
                  return Row(
                    children: [
                      for (var i = 0; i < cards.length; i++) ...[
                        if (i > 0) const SizedBox(width: 16),
                        Expanded(child: cards[i]),
                      ],
                    ],
                  );
                }
                return Column(
                  children: [
                    for (var i = 0; i < cards.length; i++) ...[
                      if (i > 0) const SizedBox(height: 16),
                      cards[i],
                    ],
                  ],
                );
              }),
            ],
          ),
        ),
      ),
    );
  }
}

class _ShowcaseCard extends StatelessWidget {
  final _ShowcaseItem item;
  const _ShowcaseCard({required this.item});
  @override
  Widget build(BuildContext context) {
    final canPlay = item.videoUrl != null;
    return AspectRatio(
      aspectRatio: 9 / 16,
      child: ClipRRect(
        borderRadius: BorderRadius.circular(16),
        child: Stack(
          fit: StackFit.expand,
          children: [
            // Background: real thumbnail if available, otherwise gradient
            if (item.thumbnailUrl != null)
              Image.network(item.thumbnailUrl!, fit: BoxFit.cover)
            else
              DecoratedBox(
                decoration: BoxDecoration(
                  gradient: LinearGradient(
                    begin: Alignment.topLeft,
                    end: Alignment.bottomRight,
                    colors: item.gradient,
                  ),
                ),
              ),
            // Vignette so the title is readable on any background
            const DecoratedBox(
              decoration: BoxDecoration(
                gradient: LinearGradient(
                  begin: Alignment.topCenter,
                  end: Alignment.bottomCenter,
                  colors: [Colors.transparent, Color(0xCC000000)],
                  stops: [0.4, 1.0],
                ),
              ),
            ),
            // Play overlay
            if (canPlay)
              const Center(
                child: Icon(Icons.play_circle_outline,
                    color: Colors.white70, size: 56),
              ),
            // Title + tagline
            Positioned(
              left: 14, right: 14, bottom: 14,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.end,
                children: [
                  Text(
                    item.title,
                    textDirection: TextDirection.rtl,
                    style: const TextStyle(
                      color: Colors.white,
                      fontWeight: FontWeight.w800,
                      fontSize: 17,
                      shadows: [Shadow(blurRadius: 6)],
                    ),
                  ),
                  const SizedBox(height: 2),
                  Text(
                    item.tagline,
                    style: TextStyle(
                      color: Colors.white.withValues(alpha: 0.8),
                      fontSize: 11,
                      letterSpacing: 0.3,
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// Pricing — the 3 tiers as marketing chips
// ---------------------------------------------------------------------------

class _Pricing extends StatelessWidget {
  const _Pricing();
  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    return Center(
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 960),
        child: Padding(
          padding: const EdgeInsets.fromLTRB(20, 32, 20, 32),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              _SectionHeading(title: l10n.landingSectionPricing),
              const SizedBox(height: 8),
              Text(
                l10n.landingPricingSubtitle,
                style: TextStyle(
                  color: FacelessTheme.textSecondary.withValues(alpha: 0.85),
                  fontSize: 13,
                ),
              ),
              const SizedBox(height: 20),
              LayoutBuilder(builder: (ctx, c) {
                final wide = c.maxWidth >= 720;
                final cards = [
                  _PriceCard(
                    name: l10n.landingTierStarter,
                    price: r'$9',
                    credits: 12,
                    desc: l10n.landingTierStarterDesc,
                  ),
                  _PriceCard(
                    name: l10n.landingTierCreator,
                    price: r'$29',
                    credits: 60,
                    desc: l10n.landingTierCreatorDesc,
                    recommended: true,
                  ),
                  _PriceCard(
                    name: l10n.landingTierPro,
                    price: r'$79',
                    credits: 200,
                    desc: l10n.landingTierProDesc,
                  ),
                ];
                if (wide) {
                  return Row(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      for (var i = 0; i < cards.length; i++) ...[
                        if (i > 0) const SizedBox(width: 16),
                        Expanded(child: cards[i]),
                      ],
                    ],
                  );
                }
                return Column(
                  children: [
                    for (var i = 0; i < cards.length; i++) ...[
                      if (i > 0) const SizedBox(height: 12),
                      cards[i],
                    ],
                  ],
                );
              }),
              const SizedBox(height: 18),
              Center(
                child: SizedBox(
                  width: 240,
                  height: 48,
                  child: FilledButton(
                    onPressed: () => _goLogin(context, signUp: true),
                    child: Text(l10n.landingStartFree,
                        style: const TextStyle(
                            fontSize: 15, fontWeight: FontWeight.w700)),
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _PriceCard extends StatelessWidget {
  final String name;
  final String price;
  final int credits;
  final String desc;
  final bool recommended;
  const _PriceCard({
    required this.name,
    required this.price,
    required this.credits,
    required this.desc,
    this.recommended = false,
  });
  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.fromLTRB(20, 16, 20, 20),
      decoration: BoxDecoration(
        color: recommended
            ? FacelessTheme.accent.withValues(alpha: 0.10)
            : FacelessTheme.surface,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(
          color: recommended
              ? FacelessTheme.accent.withValues(alpha: 0.5)
              : FacelessTheme.textSecondary.withValues(alpha: 0.15),
          width: recommended ? 1.5 : 1,
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            height: 18,
            child: recommended
                ? Container(
                    padding: const EdgeInsets.symmetric(
                        horizontal: 8, vertical: 2),
                    decoration: BoxDecoration(
                      color: FacelessTheme.accent.withValues(alpha: 0.22),
                      borderRadius: BorderRadius.circular(6),
                    ),
                    child: Text(context.l10n.landingRecommended,
                        style: TextStyle(
                          color: FacelessTheme.accent,
                          fontSize: 9,
                          fontWeight: FontWeight.w700,
                          letterSpacing: 0.4,
                        )),
                  )
                : null,
          ),
          const SizedBox(height: 8),
          Text(name,
              style: const TextStyle(
                color: FacelessTheme.textPrimary,
                fontWeight: FontWeight.w700,
                fontSize: 18,
              )),
          const SizedBox(height: 4),
          Row(
            crossAxisAlignment: CrossAxisAlignment.baseline,
            textBaseline: TextBaseline.alphabetic,
            children: [
              Text(price,
                  style: const TextStyle(
                    color: FacelessTheme.accent,
                    fontWeight: FontWeight.w800,
                    fontSize: 30,
                  )),
              const SizedBox(width: 4),
              Text(context.l10n.landingPerMonth,
                  style: const TextStyle(
                    color: FacelessTheme.textSecondary,
                    fontSize: 13,
                  )),
            ],
          ),
          const SizedBox(height: 8),
          Text(context.l10n.landingCreditsPerMonth(credits),
              style: const TextStyle(
                color: FacelessTheme.textPrimary,
                fontWeight: FontWeight.w600,
                fontSize: 13,
              )),
          const SizedBox(height: 4),
          Text(desc,
              style: const TextStyle(
                color: FacelessTheme.textSecondary,
                fontSize: 12,
              )),
        ],
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// Footer
// ---------------------------------------------------------------------------

class _Footer extends StatelessWidget {
  const _Footer();
  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 32, 20, 24),
      child: Column(
        children: [
          Divider(
            color: FacelessTheme.textSecondary.withValues(alpha: 0.12),
          ),
          const SizedBox(height: 16),
          Row(
            children: [
              const FacelessLogo(size: 24),
              const SizedBox(width: 8),
              Text(
                context.l10n.landingFooterLine,
                style: TextStyle(
                  color: FacelessTheme.textSecondary.withValues(alpha: 0.7),
                  fontSize: 12,
                ),
              ),
              const Spacer(),
              TextButton(
                onPressed: () => _goLogin(context, signUp: false),
                child: Text(context.l10n.commonSignIn),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// Section heading — localized title with a gold rule
// ---------------------------------------------------------------------------

class _SectionHeading extends StatelessWidget {
  final String title;
  const _SectionHeading({required this.title});
  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Container(
          width: 36,
          height: 3,
          decoration: BoxDecoration(
            color: FacelessTheme.accent,
            borderRadius: BorderRadius.circular(2),
          ),
        ),
        const SizedBox(height: 10),
        Text(title,
            style: const TextStyle(
              color: FacelessTheme.textPrimary,
              fontWeight: FontWeight.w800,
              fontSize: 24,
              letterSpacing: 0.3,
            )),
      ],
    );
  }
}

void _goLogin(BuildContext context, {required bool signUp}) {
  Navigator.of(context).push(
    MaterialPageRoute(
      builder: (_) => LoginScreen(startInSignUpMode: signUp),
    ),
  );
}
