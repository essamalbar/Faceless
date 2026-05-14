/**
 * SparkleLogo — SVG mirror of lib/widgets/faceless_logo.dart.
 *
 * Constellation layout: one hero sparkle slightly off-center, two
 * satellites at the corners, all on a gold gradient disc. Coordinates
 * are proportional to the radius so the mark stays crisp at any size.
 *
 * Keep the layout pinned to the Flutter widget — if you change one,
 * change both, or the brand will read differently between app and web.
 */
type Props = {
  size?: number;
  withBackground?: boolean;
  markColor?: string;
  className?: string;
};

function sparklePath(cx: number, cy: number, r: number) {
  const pinch = 0.18;
  const w = r * pinch;
  // Two crossed pinched diamonds — vertical + horizontal. Returns a
  // single SVG path string with two sub-paths so we can fill once.
  return (
    `M ${cx} ${cy - r} L ${cx + w} ${cy} L ${cx} ${cy + r} L ${cx - w} ${cy} Z ` +
    `M ${cx - r} ${cy} L ${cx} ${cy + w} L ${cx + r} ${cy} L ${cx} ${cy - w} Z`
  );
}

export function SparkleLogo({
  size = 32,
  withBackground = true,
  markColor = "#0A0E1A",
  className = "",
}: Props) {
  const cx = 50;
  const cy = 50;
  const r = 50;

  const heroX = cx - r * 0.06;
  const heroY = cy + r * 0.02;
  const sat1X = cx + r * 0.42;
  const sat1Y = cy - r * 0.42;
  const sat2X = cx + r * 0.45;
  const sat2Y = cy + r * 0.4;

  const heroR = r * 0.5;
  const sat1R = r * 0.2;
  const sat2R = r * 0.15;

  const gradId = `sparkle-grad-${size}`;

  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 100 100"
      className={className}
      aria-hidden="true"
    >
      {withBackground && (
        <>
          <defs>
            <linearGradient id={gradId} x1="0" y1="0" x2="1" y2="1">
              <stop offset="0%" stopColor="#E7B53C" />
              <stop offset="100%" stopColor="#B07F1F" />
            </linearGradient>
          </defs>
          <circle cx={cx} cy={cy} r={r} fill={`url(#${gradId})`} />
        </>
      )}
      <path
        d={
          sparklePath(heroX, heroY, heroR) +
          " " +
          sparklePath(sat1X, sat1Y, sat1R) +
          " " +
          sparklePath(sat2X, sat2Y, sat2R)
        }
        fill={markColor}
        fillRule="evenodd"
      />
    </svg>
  );
}
