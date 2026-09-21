/**
 * Check if the AI Overview section exists.
 * 
 * @returns {boolean}
 * - true: If the AI Overview section exists and does not show unavailable messages.
 * - false: If the AI Overview section does not exist or shows unavailable messages.
 */

export function doesAIOSectionExist_Alt() {
    return document.querySelectorAll('[data-subtree*="mfc"]').length > 0;
}

/**
 * Check if the AI Overview section exists.
 * 
 * @returns {boolean}
 * - true: If the AI Overview section exists and does not show unavailable messages.
 * - false: If the AI Overview section does not exist or shows unavailable messages.
 */

export function doesAIOSectionExist() {
    const all_svg = document.querySelectorAll('svg[height="24"][width="24"]');
    // console.log('DEBUG: Found', all_svg.length, 'SVG elements');
    if (all_svg.length === 0) return false;

    const messagesToFind = [
        "An AI Overview is not available for this search",
        "Can't generate an AI overview right now. Try again later."
    ];

    let AIOverviewExists = false;
    for (let svg of all_svg) {
        const parent_div = svg.closest('div');
        // const iterativeIndex = Array.prototype.indexOf.call(all_svg, svg);
        // console.log('DEBUG: Iteration', iterativeIndex + 1, 'of', all_svg.length, '- checking parent div for SVG element');
        if (parent_div && Array.from(parent_div.children).some(child => child.textContent.trim() === "AI Overview")) {
            // console.log('DEBUG: Found "AI Overview" element in parent div');
            AIOverviewExists = true;
            const allSpans = parent_div.querySelectorAll(':scope > span');
            // console.log('DEBUG: Found', allSpans.length, 'span elements in parent div');
            for (let span of allSpans) {
                const text = span.textContent.trim();
                // console.log('DEBUG: Checking span text:', text);
                if (messagesToFind.includes(text)) {
                    // console.log('DEBUG: Found unavailable message:', text);
                    // console.log('DEBUG: Span display style:', span.style.display);
                    if (span.style.display !== "none") {
                        // console.log('DEBUG: Unavailable message is visible, returning false');
                        return false;
                    } else {
                        // console.log('DEBUG: Unavailable message is hidden (display: none)');
                    }
                }
            }
            // console.log('DEBUG: Found the target AI Overview section, returning', AIOverviewExists);
            return AIOverviewExists;
        }
    }
    // console.log('DEBUG: AIOverviewExists:', AIOverviewExists);
    return AIOverviewExists;
}
