import puppeteer from "puppeteer";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const delay = (ms) => new Promise(resolve => setTimeout(resolve, ms));

async function getBrowser() {
    const stealthArgs = [
        '--no-sandbox',
        '--disable-setuid-sandbox',
        '--disable-dev-shm-usage',
        '--disable-accelerated-2d-canvas',
        '--no-first-run',
        '--no-zygote',
        '--disable-gpu',
        '--disable-web-security',
        '--disable-features=VizDisplayCompositor',
        '--disable-background-networking',
        '--disable-background-timer-throttling',
        '--disable-backgrounding-occluded-windows',
        '--disable-breakpad',
        '--disable-component-extensions-with-background-pages',
        // '--disable-extensions',
        '--disable-features=TranslateUI',
        '--disable-ipc-flooding-protection',
        '--disable-renderer-backgrounding',
        '--enable-features=NetworkService,NetworkServiceInProcess',
        '--force-color-profile=srgb',
        '--hide-scrollbars',
        '--metrics-recording-only',
        '--mute-audio',
        '--lang=en-US',
        '--accept-lang=en-US,en',
        '--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    ];

    return puppeteer.launch({
        headless: false,
        defaultViewport: { width: 1366, height: 768 },
        args: stealthArgs,
    });
}

async function executeScrapingLogic(page) {
    try {
        // Read and inject all utility functions
        const utilityFiles = [
            './utils/utils.js',
            './utils/isCaptchaPage.js',
            './utils/isSearchResultPage.js',
            './utils/getKeyword.js',
            './utils/isAIOSectionLoading.js',
            './utils/doesAIOSectionExist.js',
            './utils/showMoreButton.js',
            './utils/getAIO.js',
            './utils/getSearchResult.js'
        ];

        // Inject utility functions into the page
        for (const filePath of utilityFiles) {
            try {
                const fileContent = fs.readFileSync(new URL(filePath, import.meta.url), 'utf8');
                // Remove import/export statements and inject the functions
                const cleanedContent = fileContent
                    .replace(/import\s+.*?from\s+['"].*?['"];?\s*/g, '')
                    .replace(/export\s+\{[^}]*\};?\s*/g, '')
                    // FIX: Handle "export async function" AND "export function"
                    .replace(/export\s+(async\s+)?function/g, '$1function')
                    .replace(/export\s+\{/g, '// export {')
                    .replace(/export\s+const/g, 'const');

                await page.evaluate(cleanedContent);
            } catch (error) {
                throw new Error(`Failed to load utility file ${filePath}: ${error.message}`);
            }
        }

        // Execute the main scraping logic
        const results = await page.evaluate(async () => {
            // Helper delay function for the page context
            const delay = (ms) => new Promise(resolve => setTimeout(resolve, ms));

            try {
                // Step 1: Check if it's "I am not a robot" page
                console.log("Test CAPTCHA page...")
                // ADD 'await' HERE vvv
                const captchaCheck = typeof isCaptchaPage === 'function' ? await isCaptchaPage() : false;

                console.log("Final CAPTCHA status:", captchaCheck);

                if (captchaCheck) {
                    return {
                        isCaptchaPage: true,
                        timestamp: new Date().toISOString(),
                        message: "CAPTCHA detected"
                    };
                }

                // Step 2: Check if it's a search result page
                const searchResultCheck = typeof isSearchResultPage === 'function' ? isSearchResultPage() : false;
                console.log("Search result page?", searchResultCheck);

                // Step 3: Get search keyword and corrected keyword
                const searchKeyword = typeof getSearchKeyword === 'function' ? getSearchKeyword() : null;
                console.log("Search keyword:", searchKeyword);
                const correctedKeyword = typeof getCorrectedKeyword === 'function' ? getCorrectedKeyword() : null;
                console.log("Corrected keyword:", correctedKeyword);

                // Step 4: Validate "AI Overview" section
                let maxTimeout = 1000; // Original 1-second loading wait
                while (maxTimeout > 0) {
                    const loading = typeof isAIOSectionLoading === 'function' ? isAIOSectionLoading() : false;
                    console.log("Is AI Overview loading...", loading);
                    if (!loading) {
                        break;
                    }
                    await delay(500);
                    maxTimeout -= 500;
                }

                // Test if the "AI Overview" section exists
                const doesExist = typeof doesAIOSectionExist === 'function' ? doesAIOSectionExist() : false;
                const doesExistAlt = typeof doesAIOSectionExist_Alt === 'function' ? doesAIOSectionExist_Alt() : false;
                console.log("Does AI Overview exist (method 1):", doesExist);
                console.log("Does AI Overview exist (method 2):", doesExistAlt);

                // Step 4.5: Click "Show more" button if it exists
                let showMoreClicked = false;
                try {
                    if (typeof doesShowMoreButtonExist === 'function' && typeof clickShowMoreButton === 'function') {
                        const showMoreExists = doesShowMoreButtonExist();
                        console.log("'Show more' button exist?", showMoreExists);
                        if (showMoreExists) {
                            await clickShowMoreButton();
                            console.log("'Show more' button clicked successfully.");
                            showMoreClicked = true;
                        }
                    }
                } catch (error) {
                    console.error("Error while handling 'Show more' button:", error);
                }

                // Step 5: Get AI Overview
                const aioJSON = typeof getAIO_JSON === 'function' ? getAIO_JSON() : {};
                console.log("AI Overview JSON:", aioJSON);

                // Step 6: Get AI Overview Div for search results
                const aioDiv = typeof getAIODiv === 'function' ? getAIODiv() : null;

                // Step 7: Get all links in search result page
                const searchResults = typeof getSearchResults === 'function' ? getSearchResults(aioDiv) : [];
                console.log("Search Results:", searchResults);

                return {
                    isCaptchaPage: captchaCheck,
                    isSearchResultPage: searchResultCheck,
                    searchKeyword: searchKeyword,
                    correctedKeyword: correctedKeyword,
                    aioExists: doesExist,
                    aioExistsAlt: doesExistAlt,
                    showMoreClicked: showMoreClicked,
                    aiOverview: aioJSON,
                    searchResults: searchResults,
                    timestamp: new Date().toISOString()
                };
            } catch (error) {
                console.error("Error in scraping logic:", error);
                return {
                    error: error.message,
                    timestamp: new Date().toISOString()
                };
            }
        });

        return results;
    } catch (error) {
        console.error("Error executing scraping logic:", error);
        return {
            error: error.message,
            timestamp: new Date().toISOString()
        };
    }
}

/** Scrape one Google query and save result.json plus SERP snapshots locally. */
export async function scrape(keyword, outputDir = "output") {
    if (typeof keyword !== "string" || !keyword.trim()) {
        throw new Error("A non-empty search keyword is required.");
    }
    outputDir = path.resolve(outputDir);
    const browser = await getBrowser();
    try {
        const pages = await browser.pages();
        const page = pages[0] || await browser.newPage();
        await page.setViewport({ width: 1366, height: 768 });

        // Manual stealth techniques - Override webdriver property and other automation indicators
        await page.evaluateOnNewDocument(() => {
            // Remove webdriver property
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined,
            });

            // Remove automation indicators
            delete navigator.__proto__.webdriver;

            // Override chrome object
            window.navigator.chrome = {
                runtime: {},
                app: {
                    isInstalled: false,
                },
                webstore: {
                    onInstallStageChanged: {},
                    onDownloadProgress: {},
                }
            };

            // Override plugins to appear more realistic
            Object.defineProperty(navigator, 'plugins', {
                get: () => [
                    {
                        0: { type: "application/x-google-chrome-pdf", suffixes: "pdf", description: "Portable Document Format", __proto__: Plugin.prototype },
                        description: "Portable Document Format",
                        filename: "internal-pdf-viewer",
                        length: 1,
                        name: "Chrome PDF Plugin"
                    }
                ],
            });

            // Override languages
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en'],
            });

            // Override platform
            Object.defineProperty(navigator, 'platform', {
                get: () => 'MacIntel',
            });

            // Override hardwareConcurrency
            Object.defineProperty(navigator, 'hardwareConcurrency', {
                get: () => 4,
            });

            // Override deviceMemory if it exists
            if ('deviceMemory' in navigator) {
                Object.defineProperty(navigator, 'deviceMemory', {
                    get: () => 8,
                });
            }

            // Override permissions
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery.call(window.navigator.permissions, parameters)
            );

            // Hide automation properties
            const getParameter = WebGLRenderingContext.prototype.getParameter;
            WebGLRenderingContext.prototype.getParameter = function (parameter) {
                if (parameter === 37445) {
                    return 'Intel Inc.';
                }
                if (parameter === 37446) {
                    return 'Intel Iris OpenGL Engine';
                }
                return getParameter.call(this, parameter);
            };
        });

        console.log("Navigating to Google...");
        await page.goto("https://google.com/", { waitUntil: "networkidle0", timeout: 5000 });

        // await delay(1000 + Math.random() * 2000);

        // Check if reCAPTCHA is present
        const isRecaptcha = await page.$('iframe[title*="reCAPTCHA"]') || await page.$('.g-recaptcha');
        if (isRecaptcha) {
            console.log("reCAPTCHA detected, trying alternative approach...");
            // Try using search URL directly instead of typing
            const searchUrl = `https://www.google.com/search?q=${encodeURIComponent(keyword)}`;
            await page.goto(searchUrl, { waitUntil: "networkidle0", timeout: 30000 });
        } else {
            // Find search input with multiple selectors
            const searchSelector = await page.waitForSelector('textarea[aria-label*="Search"], input[name="q"], textarea[name="q"]', { timeout: 10000 });

            if (searchSelector) {
                // Simulate human behavior - move mouse to search box first
                const searchBox = await page.$('textarea[aria-label*="Search"], input[name="q"], textarea[name="q"]');
                const box = await searchBox.boundingBox();
                await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
                await delay(100 + Math.random() * 200);

                // Click the search box
                await page.click('textarea[aria-label*="Search"], input[name="q"], textarea[name="q"]');
                await delay(500 + Math.random() * 1000);

                // Type with human-like delays
                for (const char of keyword) {
                    await page.type('textarea[aria-label*="Search"], input[name="q"], textarea[name="q"]', char, { delay: 50 + Math.random() * 150 });
                }

                await delay(500 + Math.random() * 1000);
                await Promise.all([
                    page.waitForNavigation({ waitUntil: "networkidle0", timeout: 30000 }),
                    page.keyboard.press("Enter"),
                ]);
            }
        }

        const pageTitle = await page.title();
        console.log("Page title:", pageTitle);

        // Execute the scraping logic
        console.log("Executing scraping logic...");
        const scrapingResults = await executeScrapingLogic(page);
        if (scrapingResults.error) {
            throw new Error(scrapingResults.error);
        }
        if (scrapingResults.isCaptchaPage) {
            throw new Error("Google returned a CAPTCHA; no successful result was saved.");
        }
        if (!scrapingResults.isSearchResultPage) {
            throw new Error("Google did not return a search results page.");
        }

        fs.mkdirSync(outputDir, { recursive: true });
        const snapshots = { screenshot: null, htmlSnapshot: null };
        try {
            await page.evaluate(() => { document.body.style.zoom = '50%'; });
            const screenshotPath = path.join(outputDir, "screenshot.png");
            await page.screenshot({ path: screenshotPath });
            snapshots.screenshot = screenshotPath;
        } catch (error) {
            console.warn("Could not save screenshot:", error.message);
        }
        const htmlPath = path.join(outputDir, "snapshot.html");
        fs.writeFileSync(htmlPath, await page.content(), "utf8");
        snapshots.htmlSnapshot = htmlPath;

        const result = { keyword, pageTitle, snapshots, ...scrapingResults };
        const resultPath = path.join(outputDir, "result.json");
        fs.writeFileSync(resultPath, JSON.stringify(result, null, 2) + "\n", "utf8");
        console.log(`Saved ${resultPath}`);
        return result;
    } finally {
        await browser.close();
    }
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
    const [keyword, outputDir] = process.argv.slice(2);
    if (!keyword || process.argv.length > 4) {
        console.error('Usage: node browser.js "search query" [output-directory]');
        process.exitCode = 1;
    } else {
        scrape(keyword, outputDir).catch(error => {
            console.error(error.message);
            process.exitCode = 1;
        });
    }
}
