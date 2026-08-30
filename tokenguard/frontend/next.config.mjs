/** @type {import('next').NextConfig} */
const nextConfig = {
  // No output: 'standalone' in dev mode — conflicts with custom server.js
  // API proxy is handled by server.js, not next.config.mjs rewrites
};

export default nextConfig;
