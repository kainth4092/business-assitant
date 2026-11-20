/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  output: process.env.STANDALONE ? 'standalone' : undefined,
};

module.exports = nextConfig;
