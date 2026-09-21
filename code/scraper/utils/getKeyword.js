/**
 * Utility functions to extract search keywords from a Google search results page.
 */

/**
 * Retrieves the original search keyword from the search input field.
 * @returns {string|null} The original search keyword or null if not found.
 */

function getSearchKeyword() {
    const searchInput = document.querySelector('textarea[name="q"]');
    return searchInput ? searchInput.value : null;
}

/**
 * Retrieves the corrected search keyword if a spelling correction is suggested.
 * @returns {string|null} - The corrected search keyword or null if not found.
 */
function getCorrectedKeyword() {
    const headings = document.querySelectorAll('div[role="heading"]');
    for (const heading of headings) {
        if (heading.textContent.includes('These are results for')) {
            const link = heading.querySelector('a');
            if (link) {
                const correctedText = link.textContent.trim();
                return correctedText;
            }
        }
    }
    return null;
}

export { getSearchKeyword, getCorrectedKeyword };