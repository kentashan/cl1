import { bundle } from "@remotion/bundler";
import { renderMedia, selectComposition } from "@remotion/renderer";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const CHROME_PATH = "/root/.cache/ms-playwright/chromium_headless_shell-1194/chrome-linux/headless_shell";

const bundleLocation = await bundle({
  entryPoint: path.join(__dirname, "src/index.jsx"),
  webpackOverride: (config) => config,
  publicDir: path.join(__dirname, "public"),
});

const composition = await selectComposition({
  serveUrl: bundleLocation,
  id: "CaptionVideo",
  inputProps: {},
  browserExecutable: CHROME_PATH,
  chromiumOptions: { args: ["--no-sandbox"] },
});

await renderMedia({
  composition,
  serveUrl: bundleLocation,
  codec: "h264",
  outputLocation: path.join(__dirname, "output_captions.mp4"),
  inputProps: {},
  timeoutInMilliseconds: 300000,
  browserExecutable: CHROME_PATH,
  chromiumOptions: { args: ["--no-sandbox"] },
  onProgress: ({ progress }) => {
    process.stdout.write(`\rRendering: ${Math.round(progress * 100)}%`);
  },
});

console.log("\nDone!");
