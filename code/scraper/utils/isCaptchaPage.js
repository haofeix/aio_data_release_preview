/**
 * Utility function to check if the current page is a CAPTCHA page.
 * @returns {boolean} True if it's a CAPTCHA page, false otherwise.
 */
export function isCaptchaPage() {
    const captchaElements = document.querySelectorAll('iframe[title*="reCAPTCHA"], .g-recaptcha');
    return captchaElements.length > 0;
}

// /**
//  * Utility function to check if the current page is a CAPTCHA page.
//  * Polls continuously for 30 seconds to see if an auto-solver resolves it.
//  * @returns {Promise<boolean>} False immediately if solved, True if still present after 30s.
//  */
// export async function isCaptchaPage() {
//     const selectors = 'iframe[title*="reCAPTCHA"], .g-recaptcha, #captcha-form';

//     // Helper to check existence
//     const hasCaptcha = () => document.querySelectorAll(selectors).length > 0;

//     // 1. First Check
//     if (!hasCaptcha()) {
//         return false;
//     }

//     console.log("CAPTCHA detected. Polling for resolution (max 30s)...");

//     const startTime = Date.now();
//     const timeout = 30000; // 30 seconds max wait
//     const checkInterval = 1000; // Check every 1 second

//     // 2. Polling Loop
//     while (Date.now() - startTime < timeout) {
//         // Wait 1 second
//         await new Promise(resolve => setTimeout(resolve, checkInterval));

//         // Re-check: Did the solver remove it?
//         if (!hasCaptcha()) {
//             console.log("CAPTCHA resolved! Returning control.");
//             return false; // Success: Captcha is gone
//         }
//     }

//     console.log("CAPTCHA wait timed out (30s).");
//     return true; // Failure: Captcha still exists
// }