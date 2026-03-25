import type { NextConfig } from "next";
import { dirname } from "node:path";
import { fileURLToPath } from "node:url";

const projectRoot = dirname(fileURLToPath(import.meta.url));
const isDesktopBuild = process.env.SLIDEDROP_DESKTOP_BUILD === "1";

const nextConfig: NextConfig = {
  output: "export",
  assetPrefix: isDesktopBuild ? "./" : undefined,
  images: {
    unoptimized: true,
  },
  trailingSlash: true,
  turbopack: {
    root: projectRoot,
  },
};

export default nextConfig;
