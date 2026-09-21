/**
 * Utility function to check if the current page is a Google search result page.
 * @returns {boolean} True if it's a Google search result page, false otherwise.
 */
export function isSearchResultPage() {
    const searchResultPageElement = document.querySelector('html[itemtype="http://schema.org/SearchResultsPage"]');
    return searchResultPageElement !== null;
}
