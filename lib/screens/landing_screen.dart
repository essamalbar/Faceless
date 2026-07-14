import 'package:flutter/material.dart';

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
              TextButton(
                onPressed: () => _goLogin(context, signUp: false),
                child: const Text('Sign in'),
              ),
              const SizedBox(width: 10),
              GradientButton(
                label: 'Get started',
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
    final copy = Column(
      crossAxisAlignment:
          wide ? CrossAxisAlignment.start : CrossAxisAlignment.center,
      children: [
        const BrandPill('AI Music Studio · Arabic & beyond', dot: true),
        const SizedBox(height: 22),
        DefaultTextStyle(
          style: FacelessTheme.display(size: wide ? 56 : 40, height: 1.04),
          textAlign: wide ? TextAlign.start : TextAlign.center,
          child: Wrap(
            alignment: wide ? WrapAlignment.start : WrapAlignment.center,
            children: [
              Text('Turn any idea into a ',
                  textAlign: wide ? TextAlign.start : TextAlign.center,
                  style: FacelessTheme.display(size: wide ? 56 : 40, height: 1.04)),
              GradientText('finished song.',
                  style: FacelessTheme.display(size: wide ? 56 : 40, height: 1.04)),
            ],
          ),
        ),
        const SizedBox(height: 20),
        ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 520),
          child: Text(
            'Write a theme, or upload a track for a faithful cover. Faceless '
            'composes the lyrics, voices it, designs the cover, and cuts a '
            'cinematic video — you approve before a single credit is spent.',
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
              label: 'Start creating',
              icon: Icons.auto_awesome,
              onPressed: () => _goLogin(context, signUp: true),
            ),
            OutlinedButton.icon(
              onPressed: () => _goLogin(context, signUp: false),
              icon: const Icon(Icons.play_arrow_rounded),
              label: const Text('Sign in'),
            ),
          ],
        ),
        const SizedBox(height: 22),
        Text('★★★★★   Loved by creators · 60 free credits to start',
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
            child: const Stack(
              children: [
                Positioned(top: 12, left: 12, child: BrandPill('Now generating', dot: true)),
                Center(child: Text('🌙', style: TextStyle(fontSize: 64))),
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
                    Text('Cinematic · 92 BPM · Arabic pop',
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
    return Center(
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 960),
        child: Padding(
          padding: const EdgeInsets.fromLTRB(20, 32, 20, 32),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              _SectionHeading(en: 'How it works', ar: 'كيف تعمل'),
              const SizedBox(height: 24),
              LayoutBuilder(
                builder: (ctx, c) {
                  // Two-column on wide screens, stacked on narrow.
                  final wide = c.maxWidth >= 720;
                  final cards = [
                    _StepCard(
                      number: '1',
                      title: 'Pick a mode',
                      body: 'Horror shorts: one-sentence premise becomes a '
                          'cinematic Arabic story with characters and shots. '
                          'Songs: a theme + style becomes a full Arabic '
                          'ballad with cover art.',
                    ),
                    _StepCard(
                      number: '2',
                      title: 'Review before you spend',
                      body: 'AI drafts the script or lyrics + cover prompt '
                          'for free. You see exactly what gets generated. '
                          'Approve only when it feels right.',
                    ),
                    _StepCard(
                      number: '3',
                      title: 'Download or share',
                      body: 'Square MP4 with music + visuals, ready for '
                          'WhatsApp and Instagram. Save the lyrics or '
                          'script as a PDF. Share a public link with '
                          'OG preview baked in.',
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
const _showcase = <_ShowcaseItem>[
  _ShowcaseItem(
    title: 'البئر المهجور',
    tagline: 'Horror · Folkloric · 2 min',
    gradient: [Color(0xFFB07F1F), Color(0xFFE7B53C)],
  ),
  _ShowcaseItem(
    title: 'صوت من الجدار',
    tagline: 'Horror · Urban · 90 sec',
    gradient: [Color(0xFF8B5CF6), Color(0xFF5B21B6)],
  ),
  _ShowcaseItem(
    title: 'تحت حراسة القمر',
    tagline: 'Song · Romantic ballad · 3 min',
    gradient: [Color(0xFF1E3A8A), Color(0xFF312E81)],
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
              _SectionHeading(en: 'What it makes', ar: 'ماذا تصنع'),
              const SizedBox(height: 24),
              LayoutBuilder(builder: (ctx, c) {
                final wide = c.maxWidth >= 720;
                final cards = _showcase
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
    return Center(
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 960),
        child: Padding(
          padding: const EdgeInsets.fromLTRB(20, 32, 20, 32),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              _SectionHeading(en: 'Pricing', ar: 'الأسعار'),
              const SizedBox(height: 8),
              Text(
                'Credits power both modes. 1 song ≈ 1 credit. '
                '1 horror clip = 1 credit (avg short = 8–12).',
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
                    name: 'Starter',
                    price: r'$9',
                    credits: 12,
                    desc: 'For trying ideas',
                  ),
                  _PriceCard(
                    name: 'Creator',
                    price: r'$29',
                    credits: 60,
                    desc: 'For weekly drops',
                    recommended: true,
                  ),
                  _PriceCard(
                    name: 'Pro',
                    price: r'$79',
                    credits: 200,
                    desc: 'For daily output',
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
                    child: const Text('Start free',
                        style: TextStyle(
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
                    child: const Text('Recommended',
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
              const Text('/ month',
                  style: TextStyle(
                    color: FacelessTheme.textSecondary,
                    fontSize: 13,
                  )),
            ],
          ),
          const SizedBox(height: 8),
          Text('$credits credits / month',
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
                'Faceless Lab · faceless-lab.com',
                style: TextStyle(
                  color: FacelessTheme.textSecondary.withValues(alpha: 0.7),
                  fontSize: 12,
                ),
              ),
              const Spacer(),
              TextButton(
                onPressed: () => _goLogin(context, signUp: false),
                child: const Text('Sign in'),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// Section heading — bilingual title with a gold rule
// ---------------------------------------------------------------------------

class _SectionHeading extends StatelessWidget {
  final String en;
  final String ar;
  const _SectionHeading({required this.en, required this.ar});
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
        Row(
          children: [
            Text(en,
                style: const TextStyle(
                  color: FacelessTheme.textPrimary,
                  fontWeight: FontWeight.w800,
                  fontSize: 24,
                  letterSpacing: 0.3,
                )),
            const SizedBox(width: 10),
            Text(ar,
                style: TextStyle(
                  color: FacelessTheme.textSecondary.withValues(alpha: 0.7),
                  fontSize: 16,
                )),
          ],
        ),
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
