// Website/js/api.js

/**
 * Universal Data Fetcher (Dual-Mode Data Layer)
 * Detects if it's running inside Google Apps Script (GAS) or standalone statically.
 */
async function fetchPortalData(endpoint) {
    console.log(`Fetching data for endpoint: ${endpoint}`);
    
    // 1. Google Apps Script Context (Embedded in Sheets)
    if (typeof google !== 'undefined' && google.script && google.script.run) {
        return new Promise((resolve, reject) => {
            if (endpoint === 'leaderboard') {
                google.script.run
                    .withSuccessHandler(resolve)
                    .withFailureHandler(reject)
                    .getLeaderboardData();
            } else {
                google.script.run
                    .withSuccessHandler(resolve)
                    .withFailureHandler(reject)
                    .getDashboardData(endpoint); // 'classic' or 'battle_royale'
            }
        });
    }
    
    // 2. Standalone / Static Web Hosting Context
    try {
        let fileName = endpoint;
        if (endpoint === 'roles') fileName = 'role_definition';
        if (endpoint === 'history') fileName = 'history_archive';
        
        const response = await fetch(`./data/${fileName}.json`);
        if (!response.ok) throw new Error(`Failed to load ${fileName}.json (Status: ${response.status})`);
        return await response.json();
    } catch (e) {
        console.error("Static data fetch failed:", e);
        throw e;
    }
}
