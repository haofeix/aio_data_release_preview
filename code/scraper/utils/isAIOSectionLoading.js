/**
 * Checks if the AI Overview section is in a "Searching" or "Generating" state.
 *
 * @returns {boolean}
 * - true: If "Searching" or "Generating" text is found AND is visible.
 * - false: If "AI Overview" text is found AND is visible.
 * - false: If "Searching" or "Generating" text is found but is hidden (display:none).
 * - false: If no relevant text or SVG anchor is found.
 */
export function isAIOSectionLoading() {
    // 1. Find the SVG anchor element(s)
    const all_svg = document.querySelectorAll('svg[height="24"][width="24"]');
    if (all_svg.length === 0) {
        return false; // No anchor found
    }

    const searchTexts = ["Searching", "Generating"];
    const overviewText = "AI Overview";

    for (let svg of all_svg) {
        // 2. Find the main parent container for this SVG
        const parent_div = svg.closest('div');
        if (!parent_div) continue;

        // 3. Find all potential text elements (span or div) within this container
        const allElements = parent_div.querySelectorAll('span, div');

        let foundVisibleSearching = false;
        let foundHiddenSearching = false;
        let foundVisibleOverview = false;

        for (let el of allElements) {
            // Get text, trim it, and check if it starts with "Searching"
            // (since the div contains a nested SVG)
            const text = el.textContent.trim();
            if (text.length === 0) continue;

            // 4. Check if the element (or its immediate parent) is hidden
            let isVisible = true;
            if (el.style.display === 'none') {
                isVisible = false;
            }

            // Also check parent, as in the "not available" span example
            const parentEl = el.parentElement;
            if (parentEl && parentEl.style.display === 'none' && parentEl !== parent_div) {
                isVisible = false;
            }

            // --- Apply Logic ---

            // Condition 1: Found "Searching" or "Generating"
            if (searchTexts.some(searchText => text.startsWith(searchText))) {
                if (isVisible) {
                    foundVisibleSearching = true;
                } else {
                    foundHiddenSearching = true;
                }
            }

            // Condition 2: Found "AI Overview"
            if (text.includes(overviewText)) {
                if (isVisible) {
                    foundVisibleOverview = true;
                }
            }
        }

        // If visible "Searching" is found, return true immediately.
        if (foundVisibleSearching) {
            return true;
        }

        // If hidden "Searching" is found (and visible wasn't), return false.
        if (foundHiddenSearching) {
            return false;
        }

        // If visible "AI Overview" is found, return false.
        if (foundVisibleOverview) {
            return false;
        }
    }

    // 5. Default case: No matching state was found in any SVG section.
    return false;
}
