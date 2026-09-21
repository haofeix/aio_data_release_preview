/**
 * Utility that get all links from the search result page.
 */

import { getAIODiv } from "./getAIO.js";

function cleanLinks(links) {
    const seen = new Set();
    const cleaned = [];
    for (const url of links) {
        const parsed = new URL(url);
        if (parsed.hostname.includes("youtube.com") || parsed.hostname.includes("youtu.be")) {
            parsed.searchParams.delete("t");
        }
        const base = parsed.toString();
        if (!seen.has(base)) {
            seen.add(base);
            cleaned.push(base);
        }
    }
    return cleaned;
}

// function getSearchResults() {
//     const AIODiv = getAIODiv();
//     // const resultContainer = document.querySelector("div#search");
//     // remove AIO from search results
//     if (AIODiv) {
//         // if (resultContainer.contains(AIODiv)) {
//         //     let node = AIODiv;

//         //     // climb up until direct child of resultContainer
//         //     while (node.parentElement && node.parentElement !== resultContainer) {
//         //         node = node.parentElement;
//         //     }

//         //     if (node.parentElement === resultContainer) {
//         //         node.remove();
//         //     }
//         // }
//         AIODiv.remove();
//     }
//     const resultContainer = document.querySelector("div#search");

//     const rawLinks = [...resultContainer.querySelectorAll("a[href]")].map(a => a.href);
//     return cleanLinks(rawLinks);
// }

/**
 * Update on 2026-03-30: After collecting links from SERP we put back the AIO card.
 * 
 */
function getSearchResults() {
    const resultContainer = document.querySelector("div#search");
    if (!resultContainer) {
        return [];
    }

    const AIODiv = getAIODiv();
    let aioParent = null;
    let aioNextSibling = null;

    if (AIODiv) {
        // Remember where it was
        aioParent = AIODiv.parentElement;
        aioNextSibling = AIODiv.nextSibling;
        AIODiv.remove();
    }

    const rawLinks = [...resultContainer.querySelectorAll("a[href]")]
        .map(a => a.href);

    // Put AIO back where it was
    if (AIODiv && aioParent) {
        if (aioNextSibling) {
            aioParent.insertBefore(AIODiv, aioNextSibling);
        } else {
            aioParent.appendChild(AIODiv);
        }
    }

    return cleanLinks(rawLinks);
}

export { getSearchResults };