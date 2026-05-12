#!/usr/bin/env node

import { createServer } from "node:http";
import { readFileSync, writeFileSync } from "node:fs";
import { basename, resolve } from "node:path";
import { chromium } from "playwright";

const DEFAULT_INPUT = "docs/assets/oci-ai-document-review-architecture.excalidraw";
const DEFAULT_OUTPUT = "docs/assets/oci-ai-document-review-architecture.png";
const DEFAULT_SCALE = 3;
const EXCALIDRAW_VERSION = "0.18.0";
const EXCALIFONT_URL =
  "https://fonts.gstatic.com/s/playpensans/v22/dg4i_pj1p6gXP0gzAZgm4c89TCIjqS-xRg.woff2";

function parseArgs(argv) {
  const options = {
    input: DEFAULT_INPUT,
    output: DEFAULT_OUTPUT,
    scale: DEFAULT_SCALE,
  };

  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    if (arg === "--input") {
      options.input = argv[++i];
    } else if (arg === "--output") {
      options.output = argv[++i];
    } else if (arg === "--scale") {
      options.scale = Number(argv[++i]);
    } else if (arg === "--help" || arg === "-h") {
      printUsage();
      process.exit(0);
    } else {
      throw new Error(`Unknown option: ${arg}`);
    }
  }

  if (!Number.isFinite(options.scale) || options.scale <= 0) {
    throw new Error("--scale must be a positive number");
  }

  return options;
}

function printUsage() {
  console.log(`Render the architecture Excalidraw source to PNG.

Usage:
  npm run docs:render-architecture
  node scripts/render_architecture.mjs [--input file.excalidraw] [--output file.png] [--scale 3]`);
}

function loadExcalidraw(path) {
  const data = JSON.parse(readFileSync(path, "utf8"));
  data.elements = (data.elements || []).filter((element) => !element.isDeleted);
  return data;
}

function createExporterPage() {
  return `<!doctype html>
<html>
  <head>
    <meta charset="utf-8" />
    <script type="module">
      import { exportToBlob } from "https://esm.sh/@excalidraw/excalidraw@${EXCALIDRAW_VERSION}?bundle-deps";
      window.__exportToBlob = exportToBlob;
      window.__READY__ = true;
    </script>
  </head>
  <body></body>
</html>`;
}

async function main() {
  const options = parseArgs(process.argv.slice(2));
  const inputPath = resolve(options.input);
  const outputPath = resolve(options.output);
  const excalidrawData = loadExcalidraw(inputPath);

  const server = createServer((_, res) => {
    res.writeHead(200, { "content-type": "text/html; charset=utf-8" });
    res.end(createExporterPage());
  });
  await new Promise((resolveListen) => server.listen(0, resolveListen));
  const { port } = server.address();

  const browser = await chromium.launch();
  const page = await browser.newPage();

  page.on("console", (message) => {
    if (message.type() === "error") {
      console.error(`browser error: ${message.text()}`);
    }
  });
  page.on("pageerror", (error) => {
    console.error(`browser page error: ${error.message}`);
  });

  await page.route("**/*Excalifont*", async (route) => {
    const response = await fetch(EXCALIFONT_URL);
    const body = Buffer.from(await response.arrayBuffer());
    await route.fulfill({ body, contentType: "font/woff2" });
  });

  try {
    await page.goto(`http://127.0.0.1:${port}`, {
      waitUntil: "networkidle",
      timeout: 60_000,
    });
    await page.waitForFunction(
      () => window.__READY__ === true,
      undefined,
      { timeout: 60_000 },
    );

    const pngBase64 = await page.evaluate(
      async ({ data, scale }) => {
        const blob = await window.__exportToBlob({
          elements: data.elements,
          appState: {
            exportBackground: true,
            exportWithDarkMode: false,
            viewBackgroundColor:
              data.appState?.viewBackgroundColor || "#ffffff",
          },
          files: data.files || null,
          exportPadding: 40,
          getDimensions: (width, height) => ({
            width: width * scale,
            height: height * scale,
            scale,
          }),
        });

        const reader = new FileReader();
        return await new Promise((resolveRead) => {
          reader.onload = () => resolveRead(reader.result.split(",")[1]);
          reader.readAsDataURL(blob);
        });
      },
      { data: excalidrawData, scale: options.scale },
    );

    writeFileSync(outputPath, Buffer.from(pngBase64, "base64"));
    console.log(
      `Rendered ${basename(inputPath)} -> ${outputPath} at ${options.scale}x`,
    );
  } finally {
    await browser.close();
    server.close();
  }
}

main().catch((error) => {
  console.error(error.message);
  process.exit(1);
});
