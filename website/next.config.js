/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Standalone output bundles the minimal Node server + only the deps
  // actually used at runtime, so the Docker image stays small (~150 MB
  // instead of 600 MB if we shipped all of node_modules).
  output: "standalone",
  // Old shared song links were minted with the apex domain
  // (https://faceless-lab.com/p/<token>) before the apex was reassigned
  // from the API service to this marketing site. Forward /p/* to the
  // app subdomain so already-distributed share links keep working.
  async redirects() {
    return [
      {
        source: "/p/:token",
        destination: "https://app.faceless-lab.com/p/:token",
        permanent: false,
      },
      {
        source: "/p/:token/:rest*",
        destination: "https://app.faceless-lab.com/p/:token/:rest*",
        permanent: false,
      },
    ];
  },
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
