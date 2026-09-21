/**
 * Utility functions to extract the AI Overview section from a webpage.
 * TODOs:
 * - Preserve the Markdown formatting when extracting content.
 * - Inclusion/Exclusion such as videos, images, tables, etc.
 */

/**
 * Helper functions: Credit to Chrome Extension "Hide or Collapse Google AI Overviews"
 * https://chromewebstore.google.com/detail/hide-or-collapse-google-a/hheehjpllbfdcgnmnohhpenhfjdbldca
 */
function filterNested(list) {
    const arr = list.filter(Boolean);
    return arr.filter((el) => !arr.some((other) => other !== el && other.contains(el)));
}

function findAIOModules() {
    const modules = new Set();

    // Strategy 1: Direct ID lookup (most stable)
    const top = document.querySelector("#Odp5De");
    if (top) {
        modules.add(top);
        return filterNested(Array.from(modules));
    }

    // Strategy 2: Find via #m-x-content and walk up to module boundary
    document.querySelectorAll("#m-x-content").forEach((inner) => {
        const mfc = inner.closest('div[data-subtree="mfc"]');
        const root = (mfc && (mfc.closest("div.yf") || mfc))
            || inner.closest("div.yf")
            || null;
        if (root) modules.add(root);
    });

    // Strategy 3: Find via data-subtree="aimc" and walk up
    document.querySelectorAll('[data-subtree="aimc"]').forEach((aimc) => {
        const mfc = aimc.closest('div[data-subtree="mfc"]');
        const root = (mfc && (mfc.closest("div.yf") || mfc))
            || aimc.closest("div.yf")
            || null;
        if (root) modules.add(root);
    });

    if (modules.size > 0) {
        return filterNested(Array.from(modules));
    }

    return [];
}

/**
 * Finds the AI Overview wrapper div by locating the H1
 * with the exact text "AI Overview" and selecting its
 * immediate next sibling, if it is a DIV.
 *
 * @returns {HTMLElement | null} The DIV element immediately following the H1, or null.
 */
function getAIODiv() {
    // Primary: Use structural module detection
    const aioModules = findAIOModules();
    if (aioModules.length > 0) {
        // Return the first module found.
        // Prefer the inner content container if available.
        const mod = aioModules[0];
        const innerContent = mod.querySelector('[jsname="HKDuG"]')
            || mod.querySelector('[data-subtree="aimc"]')
            || mod.querySelector('#m-x-content');
        console.log("primary")
        return innerContent || mod;
    }

    // Fallback 1: New heading structure (div[role="heading"])
    const headings = document.querySelectorAll('div[role="heading"]');
    for (let h of headings) {
        if (h.textContent.trim() === 'AI Overview') {
            let ancestor = h.parentElement;
            while (ancestor) {
                const next = ancestor.nextElementSibling;
                if (next && next.tagName === 'DIV') {
                    const contentBlock = next.querySelector('[jsname="HKDuG"]');
                    console.log("fallback 1")
                    if (contentBlock) return contentBlock;
                    if (next.hasAttribute('data-ve-view')) return next;
                }
                ancestor = ancestor.parentElement;
            }
            break;
        }
    }

    // Fallback 2: Legacy heading structure (h1/h2)
    const all_h1s = document.querySelectorAll('h1,h2');
    for (let h1 of all_h1s) {
        if (h1.textContent.trim() === 'AI Overview') {
            const nextElement = h1.nextElementSibling;
            if (nextElement && nextElement.tagName === 'DIV') {
                console.log("fallback 2")
                return nextElement;
            }
            break;
        }
    }

    return null;
}

/**
 * Extracts the AI Overview content from the provided DIV element.
 *
 * @param {HTMLElement} AIODiv The DIV element containing the AI Overview section.
 * @returns {string} The concatenated text content of all relevant paragraphs within the AI Overview section.
 */
function getAIOContent(AIODiv) {
    // TODO: Preserve the Markdown formatting when extracting content.
    if (!AIODiv) {
        return "";
    }
    const all_paragraphs = AIODiv.querySelectorAll('span[data-huuid]');
    if (all_paragraphs.length === 0) {
        const altContent = getAIOContent_Alt(AIODiv);
        if (altContent) return altContent;
        return "";
    }
    return Array.from(all_paragraphs).map(p => p.textContent.trim()).join(" ");
}

/**
 * Alternative function to extract AI Overview content from the provided DIV element.
 * 
 * @param {HTMLElement} AIODiv The DIV element containing the AI Overview section.
 * @returns {string} The concatenated text content of all relevant paragraphs within the AI Overview section.
 */
function getAIOContent_Alt(AIODiv) {
    if (!AIODiv) {
        return "";
    }
    const aioClone = AIODiv.cloneNode(true);
    // Remove citation elements to avoid mixing cited text with main content
    const notranslateElements = aioClone.querySelectorAll('.notranslate');
    notranslateElements.forEach(el => el.remove());
    const allCitationElements = aioClone.querySelectorAll('div[data-sfc-cp], span[data-sfc-cp]');
    const filteredCitationElements = Array.from(allCitationElements).filter(el => {
        const hasText = el.textContent.trim().length > 0;
        return hasText;
    });
    const allText = filteredCitationElements.map(el => el.textContent.trim());
    return allText.join(" ");
}

function getAIOReferences(AIODiv) {
    if (!AIODiv) {
        return [];
    }
    const citationDialog = AIODiv.querySelectorAll('div.notranslate[data-type="hovc"]');
    if (citationDialog.length === 0) {
        return [];
    }
    for (let dialog of citationDialog) {
        const linkElements = dialog.querySelectorAll("a");
        if (linkElements.length === 0) {
            continue;
        }
        const references = [];
        linkElements.forEach(linkElement => {
            let ariaLabel = linkElement.getAttribute("aria-label") || "";
            // Remove trailing ". Opens in new tab." suffix (case-insensitive)
            ariaLabel = ariaLabel.replace(/\.\s*Opens in new tab\.?\s*$/i, "").trim();
            const href = linkElement.getAttribute("href") || "";
            const [urlPart, citedTextPart] = href.split("#:~:text=");
            const url = urlPart || "";
            const citedText = citedTextPart ? decodeURIComponent(citedTextPart) : "";
            references.push({
                title: ariaLabel,
                url: url,
                cited_text: citedText
            });
        });
        return references;
    }
    return [];
}

function getAIODisclaimer(AIODiv) {
    if (!AIODiv) {
        return "";
    }

    // Find the "Dive deeper in AI Mode" element by its text content
    let diveDeeper = null;
    const candidates = AIODiv.querySelectorAll('div, span');
    for (let el of candidates) {
        if (el.textContent.trim() === 'Dive deeper in AI Mode') {
            diveDeeper = el;
            break;
        }
    }

    // Walk up from "Dive deeper" and scan siblings for the disclaimer
    if (diveDeeper) {
        let container = diveDeeper.closest('div');
        while (container && container !== AIODiv) {
            let sibling = container.nextElementSibling;
            while (sibling) {
                const text = sibling.textContent.trim();
                if (text && text.length > 10 && text.length < 200
                    && !sibling.querySelector('button, [role="button"]')
                    && !sibling.querySelector('[aria-label="Share"]')) {
                    return text;
                }
                sibling = sibling.nextElementSibling;
            }
            container = container.parentElement;
        }
    }
}

function getAIO_JSON() {
    const AIODiv = getAIODiv();
    if (!AIODiv) {
        return {};
    }
    return {
        content: getAIOContent(AIODiv),
        references: getAIOReferences(AIODiv),
        disclaimer: getAIODisclaimer(AIODiv)
    };
}



export { getAIODiv, getAIOContent, getAIOReferences, getAIODisclaimer, getAIO_JSON };