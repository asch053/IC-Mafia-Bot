// Website/js/api.js

/**
 * Universal Data Fetcher (Dual-Mode Data Layer)
 * Detects if it's running inside Google Apps Script (GAS) or standalone statically.
 * Bridges seamlessly with Website/js/MafiaAPICode.js.
 */
(function (global) {
    'use strict';

    if (global.fetchPortalData) {
        // MafiaAPICode.js already loaded and attached
        return;
    }

    async function fetchPortalData(endpoint) {
        console.log(`[api.js] Fetching data for endpoint: ${endpoint}`);

        // 1. Google Apps Script Context (Embedded in Sheets)
        if (typeof google !== 'undefined' && google.script && google.script.run) {
            return new Promise((resolve, reject) => {
                if (endpoint === 'leaderboard' || endpoint === 'records') {
                    google.script.run
                        .withSuccessHandler(resolve)
                        .withFailureHandler(reject)
                        .getLeaderboardData();
                } else {
                    const mode = (endpoint === 'br') ? 'battle_royale' : endpoint;
                    google.script.run
                        .withSuccessHandler(resolve)
                        .withFailureHandler(reject)
                        .getDashboardData(mode); // 'classic' or 'battle_royale'
                }
            });
        }

        // 2. Standalone / Static Web Hosting Context
        try {
            let fileName = endpoint;
            if (endpoint === 'roles') fileName = 'role_definition';
            if (endpoint === 'history') fileName = 'history_archive';
            if (endpoint === 'br') fileName = 'battle_royale';
            if (endpoint === 'records') fileName = 'leaderboard';

            const basePath = (typeof window !== 'undefined' && window.location.pathname.includes('/archive/'))
                ? '../data/'
                : './data/';

            const response = await fetch(`${basePath}${fileName}.json?v=${Date.now()}`, {
                cache: 'no-store',
                headers: {
                    'Cache-Control': 'no-cache',
                    'Pragma': 'no-cache'
                }
            });
            if (!response.ok) throw new Error(`Failed to load ${fileName}.json (Status: ${response.status})`);
            return await response.json();
        } catch (e) {
            console.error("Static data fetch failed:", e);
            throw e;
        }
    }

    global.fetchPortalData = fetchPortalData;

})(typeof window !== 'undefined' ? window : this);
