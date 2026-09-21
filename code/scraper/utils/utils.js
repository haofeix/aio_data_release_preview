/** Utility functions for various tasks */

/**
 * Delays execution for a specified number of milliseconds, adding a random extra delay.
 * @param {number} ms The base number of milliseconds to delay.
 * @returns {Promise} A promise that resolves after the delay.
 */
function delay(ms) {
    const extra = Math.floor(Math.random() * ms);
    return new Promise((resolve) => setTimeout(resolve, ms + extra));
}

export { delay };