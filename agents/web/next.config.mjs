const isDev = process.env.NODE_ENV === 'development';

/** @type {import('next').NextConfig} */
const nextConfig = {
  output: isDev ? undefined : 'export',
  trailingSlash: true,
  images: { unoptimized: true },
  ...(isDev && {
    async rewrites() {
      return [
        { source: '/api/:path*', destination: 'http://127.0.0.1:8081/api/:path*' },
        { source: '/media/:path*', destination: 'http://127.0.0.1:8081/media/:path*' },
      ];
    },
  }),
};
export default nextConfig;
