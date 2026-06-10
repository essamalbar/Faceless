import 'package:flutter/material.dart';

import '../theme.dart';
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
      backgroundColor: FacelessTheme.bg,
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
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 16, 20, 0),
      child: Row(
        children: [
          const FacelessLogo(size: 28),
          const SizedBox(width: 10),
          const Text('Faceless Lab',
              style: TextStyle(
                color: FacelessTheme.textPrimary,
                fontWeight: FontWeight.w700,
                fontSize: 16,
              )),
          const Spacer(),
          TextButton(
            onPressed: () => _goLogin(context, signUp: false),
            child: const Text('Sign in'),
          ),
        ],
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
    return Stack(
      children: [
        Positioned.fill(
          child: IgnorePointer(
            child: DecoratedBox(
              decoration: const BoxDecoration(
                gradient: RadialGradient(
                  center: Alignment(0.0, -0.4),
                  radius: 1.0,
                  colors: [Color(0x44E7B53C), Color(0x000A0E1A)],
                ),
              ),
            ),
          ),
        ),
        Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 720),
            child: Padding(
              padding: const EdgeInsets.fromLTRB(20, 60, 20, 60),
              child: Column(
                children: [
                  Container(
                    width: 96,
                    height: 96,
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      boxShadow: [
                        BoxShadow(
                          color:
                              FacelessTheme.accent.withValues(alpha: 0.4),
                          blurRadius: 32,
                          offset: const Offset(0, 8),
                        ),
                      ],
                    ),
                    child: const FacelessLogo(size: 96),
                  ),
                  const SizedBox(height: 28),
                  Text(
                    'Faceless Lab',
                    textAlign: TextAlign.center,
                    style: Theme.of(context)
                        .textTheme
                        .displaySmall!
                        .copyWith(
                          fontWeight: FontWeight.w800,
                          letterSpacing: 0.5,
                          color: FacelessTheme.textPrimary,
                        ),
                  ),
                  const SizedBox(height: 10),
                  Text(
                    'AI-generated horror shorts and Arabic songs.',
                    textAlign: TextAlign.center,
                    style: TextStyle(
                      color: FacelessTheme.textSecondary.withValues(alpha: 0.9),
                      fontSize: 16,
                      letterSpacing: 0.3,
                    ),
                  ),
                  const SizedBox(height: 4),
                  const Text(
                    'قصص قصيرة وأغانٍ بالذكاء الاصطناعي',
                    textAlign: TextAlign.center,
                    style: TextStyle(
                      color: FacelessTheme.textSecondary,
                      fontSize: 14,
                      height: 1.5,
                    ),
                  ),
                  const SizedBox(height: 28),
                  // Dual-CTA: two large feature chips so visitors
                  // immediately see both modes exist. Both route to
                  // signup; the home screen's segmented selector
                  // chooses Horror vs Song after auth.
                  Row(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      _ModeChip(
                        icon: Icons.movie_filter_outlined,
                        title: 'Horror shorts',
                        ar: 'قصص رعب',
                        onTap: () => _goLogin(context, signUp: true),
                      ),
                      const SizedBox(width: 12),
                      _ModeChip(
                        icon: Icons.music_note_outlined,
                        title: 'AI songs',
                        ar: 'أغاني',
                        onTap: () => _goLogin(context, signUp: true),
                      ),
                    ],
                  ),
                  const SizedBox(height: 24),
                  SizedBox(
                    width: 280,
                    height: 52,
                    child: FilledButton.icon(
                      onPressed: () => _goLogin(context, signUp: true),
                      icon: const Icon(Icons.auto_awesome, size: 20),
                      label: const Text(
                        'Start free',
                        style: TextStyle(
                            fontSize: 16, fontWeight: FontWeight.w700),
                      ),
                    ),
                  ),
                  const SizedBox(height: 10),
                  Text(
                    'Free to draft · pay only when you generate',
                    style: TextStyle(
                      color:
                          FacelessTheme.textSecondary.withValues(alpha: 0.7),
                      fontSize: 12,
                      letterSpacing: 0.3,
                    ),
                    textAlign: TextAlign.center,
                  ),
                ],
              ),
            ),
          ),
        ),
      ],
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


/// Dual-CTA mode chip used in the hero. Two of these sit side-by-side
/// so visitors see immediately that the product does both Horror and
/// Songs without scrolling. Both tap-targets go to signup.
class _ModeChip extends StatelessWidget {
  final IconData icon;
  final String title;
  final String ar;
  final VoidCallback onTap;
  const _ModeChip({
    required this.icon,
    required this.title,
    required this.ar,
    required this.onTap,
  });
  @override
  Widget build(BuildContext context) {
    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(14),
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 14),
          decoration: BoxDecoration(
            color: FacelessTheme.surface,
            borderRadius: BorderRadius.circular(14),
            border: Border.all(
              color: FacelessTheme.accent.withValues(alpha: 0.30),
            ),
          ),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(icon, color: FacelessTheme.accent, size: 28),
              const SizedBox(height: 6),
              Text(
                title,
                style: const TextStyle(
                  color: FacelessTheme.textPrimary,
                  fontWeight: FontWeight.w700,
                  fontSize: 13,
                ),
              ),
              const SizedBox(height: 2),
              Text(
                ar,
                style: TextStyle(
                  color: FacelessTheme.textSecondary.withValues(alpha: 0.75),
                  fontSize: 11,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
