/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
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
