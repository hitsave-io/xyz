/** @type {import('@remix-run/dev').AppConfig} */
module.exports = {
  appDirectory: "./src",
  ignoredRouteFiles: ["**/.*"],
  serverDependenciesToBundle: [
    "hast-to-hyperscript",
    "property-information",
    "space-separated-tokens",
    "comma-separated-tokens",
    "web-namespaces",
    "unist-util-is",
  ],
  // appDirectory: "app",
  // assetsBuildDirectory: "public/build",
  // serverBuildPath: ".netlify/functions-internal/server.js",
  // publicPath: "/build/",
};
