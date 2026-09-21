# Google AI Overview scraper

This is the core browser scraper used to collect Google AI Overview (AIO) text, cited sources, and search-result links. It runs one query in a local Chrome browser and saves the result and search-page snapshots.

## Files

| File | Purpose |
|---|---|
| `browser.js` | Opens Google, submits a query, injects the DOM helpers, extracts results, and writes local files. Exports `scrape(keyword, outputDir)` and also works as a command-line script. |
| `utils/getAIO.js` | Locates the AIO, extracts its text, cited URLs and text snippets, and disclaimer. |
| `utils/getSearchResult.js` | Collects and deduplicates links from the search-results container, temporarily excluding the AIO content. These are container links, not a separately classified list of organic results. |
| `utils/doesAIOSectionExist.js` | Checks whether an AIO is present. |
| `utils/isAIOSectionLoading.js` | Checks the AIO loading state. |
| `utils/showMoreButton.js` | Expands the AIO's “Show more” section. |
| `utils/getKeyword.js` | Reads the query and Google's corrected query. |
| `utils/isCaptchaPage.js`, `utils/isSearchResultPage.js` | Recognize CAPTCHA and search-result pages. |
| `utils/utils.js` | Shared delay helper used in the browser context. |
| `package.json` | Node.js dependency and command-line entry point. |

## Install and run

Requires Node.js 18+ and a graphical desktop session. Puppeteer is pinned to `22.15.0`, the version installed in the original project environment. `npm install` installs Puppeteer and its matching browser.

From this directory:

```sh
npm install
npm start -- "what is photosynthesis" ./output/photosynthesis
```

The output directory is optional and defaults to `./output`. Use a separate directory for each query; running again in the same directory overwrites its output files.

The module can also be called from another ES module:

```js
import { scrape } from "./browser.js";

const result = await scrape("what is photosynthesis", "./output/photosynthesis");
console.log(result.aiOverview);
```

Helper paths are resolved relative to `browser.js`, so the module can be called from a different working directory.

## Output

| File | Contents |
|---|---|
| `result.json` | `keyword`, page title, detected/corrected query, AIO-presence flags, `aiOverview` with text and references, search-result links, timestamp, and snapshot paths. |
| `snapshot.html` | Captured Google search-results HTML. |
| `screenshot.png` | Search-page screenshot at 50% zoom, when screenshot capture succeeds. |

An ordinary results page without an AIO is still saved. A CAPTCHA, a non-results page, or an extraction failure raises an error and makes the CLI exit unsuccessfully. Screenshot failure is logged and represented by a null screenshot path.

## Scope and provenance

This folder contains the AIO/SERP extraction core. It does not include Google Trends collection, SQS dispatch, AWS Lambda/S3 deployment, cited-page crawling, or CAPTCHA-solving extensions. The verifier uses the cited-page content already supplied under `raw/aio_results/**/page_analysis/`; new collections need that content separately before verification.

The DOM helper files are unchanged copies of `temp_download/pipeline/ai-overview-scraper/utils/` from the research project. `browser.js` retains the original extraction flow and browser setup, with a local CLI in place of the cloud handlers. Local startup, helper-file resolution, native browser-method binding, navigation waiting, and failure propagation were adjusted for this standalone entry point.

The selectors and extraction rules reflect the study implementation. Google changes its page structure, so a fresh crawl may require selector updates and cannot reproduce the historical observations exactly.
