/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Standalone output bundles the minimal Node server + only the deps
  // actually used at runtime, so the Docker image stays small (~150 MB
  // instead of 600 MB if we shipped all of node_modules).
  output: "standalone",
  images: {
    // Unsplash is the only remote image source we use — CC0 cinematic
    // photography for the marketing showcase. images.unsplash.com is
    // their CDN; auto-format conversion happens server-side via the
    // ?auto=format query param.
    remotePatterns: [
      { protocol: "https", hostname: "images.unsplash.com" },
    ],
  },
};

module.exports = nextConfig;
