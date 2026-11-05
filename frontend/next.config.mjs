/** @type {import('next').NextConfig} */
const pages = process.env.AGENTSHIELD_PAGES_BUILD === '1';
const nextConfig = {
  reactStrictMode: true,
  ...(pages ? {
    output: 'export',
    basePath: '/agentshield',
    trailingSlash: true,
    images: { unoptimized: true },
  } : {}),
};
export default nextConfig;
