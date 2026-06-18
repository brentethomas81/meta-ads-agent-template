/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  // Dashboard pulls live data; never cache the page at build time.
  experimental: {},
  // Belt-and-suspenders against stale views: tell browsers/proxies never to
  // cache the dashboard HTML. (Next's immutable /_next/static assets still cache.)
  async headers() {
    return [
      {
        source: "/",
        headers: [
          { key: "Cache-Control", value: "no-store, no-cache, must-revalidate, max-age=0" },
        ],
      },
    ];
  },
};
export default nextConfig;
