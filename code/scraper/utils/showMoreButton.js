/**
 * Utility function to check if the "Show more" button exists and click it.
 */

import { delay } from "./utils.js";

/**
 * Utility function to check if the "Show more" button exists and is visible.
 * @returns {boolean} True if the "Show more" button exists and is visible, false otherwise.
 */
function doesShowMoreButtonExist() {
    const showMoreButton = document.querySelector('div[aria-label="Show more AI Overview"]');
    if (!showMoreButton || showMoreButton.style.display === 'none' || showMoreButton.getAttribute('aria-expanded') === 'true') {
        return false;
    }
    return true;
}

/**
 * Utility function to click the "Show more" button if it exists and is visible.
 * @param {number} maxTimeout Maximum time to wait for the section to expand (in milliseconds).
 * @return {Promise<void>}
 * @throws {Error} If the section does not expand within the timeout period.
 */
async function clickShowMoreButton(maxTimeout = 3000) {
    const showMoreButton = document.querySelector('div[aria-label="Show more AI Overview"]');
    if (showMoreButton && showMoreButton.style.display !== 'none') {
        showMoreButton.click();
    }
    const pollInterval = 100;
    let elapsedTime = 0;

    while (elapsedTime < maxTimeout) {
        await delay(pollInterval);
        elapsedTime += pollInterval;
        if (!doesShowMoreButtonExist()) {
            return; // Success
        }
    }
    throw new Error('Timeout: AI Overview content did not expand.');
}

export { doesShowMoreButtonExist, clickShowMoreButton };