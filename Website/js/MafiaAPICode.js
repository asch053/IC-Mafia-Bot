/**
 * Mafia Analytics Data Layer (Website/js/MafiaAPICode.js)
 * Unified data fetcher supporting both static hosting (standard fetch)
 * and Google Apps Script (google.script.run) environments.
 */

(function (global) {
    'use strict';

    /**
     * Map friendly endpoint aliases to actual JSON file names in data/
     */
    const ENDPOINT_MAP = {
        'roles': 'role_definition',
        'role_definition': 'role_definition',
        'history': 'history_archive',
        'history_archive': 'history_archive',
        'leaderboard': 'leaderboard',
        'records': 'leaderboard',
        'classic': 'classic',
        'battle_royale': 'battle_royale',
        'br': 'battle_royale',
        'users': 'master_user_map',
        'master_user_map': 'master_user_map',
        'phase_all': 'phase_by_phase_all',
        'phase_by_phase_all': 'phase_by_phase_all'
    };

    /**
     * Determine the base URL for the data directory dynamically.
     * Works seamlessly whether hosted at root, in /archive/, or via file:///
     */
    function resolveDataBaseUrl() {
        // 1. Resolve relative to MafiaAPICode.js or api.js script location
        if (typeof document !== 'undefined') {
            const scripts = document.getElementsByTagName('script');
            for (let i = 0; i < scripts.length; i++) {
                const src = scripts[i].src || '';
                if (src.includes('MafiaAPICode.js') || src.includes('api.js')) {
                    try {
                        const scriptUrl = new URL(src, window.location.href);
                        return new URL('../data/', scriptUrl).href;
                    } catch (e) {
                        // ignore and fall back
                    }
                }
            }

            // 2. Pathname heuristic fallback for archive subfolders
            const pathname = window.location.pathname || '';
            if (pathname.includes('/archive/') || pathname.includes('\\archive\\')) {
                return '../data/';
            }
        }
        return './data/';
    }

    /**
     * Render a clean, non-crashing fallback UI when data loading fails.
     */
    function renderFallbackUI(errorMessage, endpoint, fileName) {
        console.error(`[MafiaAPICode] Error loading endpoint "${endpoint}" (${fileName}.json):`, errorMessage);

        if (typeof document === 'undefined') return;

        // 1. Update #loader container if present on the page
        const loader = document.getElementById('loader');
        if (loader) {
            loader.classList.remove('hidden');
            loader.style.display = 'block';
            loader.innerHTML = `
                <div class="portal-error-card" style="background: rgba(207, 56, 56, 0.15); border: 1px solid #cf3838; border-radius: 8px; padding: 24px; max-width: 650px; margin: 30px auto; text-align: center; color: #e0e0e0; box-shadow: 0 4px 12px rgba(0,0,0,0.5);">
                    <div style="font-size: 2.2rem; margin-bottom: 8px;">⚠️</div>
                    <h3 style="color: #cf3838; margin: 0 0 10px 0; font-size: 1.3rem;">Data Loading Failed</h3>
                    <p style="margin: 8px 0; color: #ddd;">
                        Unable to load data for <strong>${endpoint}</strong> (<code>${fileName}.json</code>).
                    </p>
                    <p style="font-size: 0.85rem; color: #aaa; background: rgba(0,0,0,0.3); padding: 8px 12px; border-radius: 4px; word-break: break-all; margin: 12px 0;">
                        ${errorMessage}
                    </p>
                    <div style="margin-top: 16px; display: flex; gap: 10px; justify-content: center;">
                        <button onclick="location.reload()" style="background: #cf3838; color: white; border: none; padding: 8px 18px; border-radius: 4px; cursor: pointer; font-weight: bold; font-size: 0.9rem; transition: 0.2s;">
                            🔄 Retry
                        </button>
                    </div>
                </div>
            `;
        }

        // 2. Update #leaderboardBody if present (e.g. LeaderBoard.html)
        const lbBody = document.getElementById('leaderboardBody');
        if (lbBody) {
            lbBody.innerHTML = `
                <tr>
                    <td colspan="3" style="text-align: center; color: #cf3838; padding: 25px;">
                        ⚠️ <strong>Failed to load leaderboard data</strong>: ${errorMessage}
                        <br><br>
                        <button onclick="location.reload()" style="background: #cf3838; color: white; border: none; padding: 6px 14px; border-radius: 4px; cursor: pointer;">🔄 Retry</button>
                    </td>
                </tr>
            `;
        }
    }

    /**
     * Primary Portal Data Fetcher
     * @param {string} endpoint - The requested endpoint name (e.g. 'leaderboard', 'classic', 'battle_royale', 'roles', 'history')
     * @returns {Promise<any>}
     */
    async function fetchPortalData(endpoint) {
        if (!endpoint || typeof endpoint !== 'string') {
            throw new Error(`Invalid endpoint provided: ${endpoint}`);
        }

        const cleanKey = endpoint.toLowerCase().trim();
        const fileName = ENDPOINT_MAP[cleanKey] || cleanKey;

        // 1. Google Apps Script Context (when embedded in Google Sheets / Apps Script)
        if (typeof google !== 'undefined' && google.script && google.script.run) {
            return new Promise((resolve, reject) => {
                if (cleanKey === 'leaderboard' || cleanKey === 'records') {
                    google.script.run
                        .withSuccessHandler(resolve)
                        .withFailureHandler((err) => {
                            const msg = err && err.message ? err.message : String(err);
                            renderFallbackUI(msg, endpoint, fileName);
                            reject(new Error(msg));
                        })
                        .getLeaderboardData();
                } else if (cleanKey === 'classic' || cleanKey === 'battle_royale' || cleanKey === 'br') {
                    const mode = cleanKey === 'classic' ? 'classic' : 'battle_royale';
                    google.script.run
                        .withSuccessHandler(resolve)
                        .withFailureHandler((err) => {
                            const msg = err && err.message ? err.message : String(err);
                            renderFallbackUI(msg, endpoint, fileName);
                            reject(new Error(msg));
                        })
                        .getDashboardData(mode);
                } else {
                    // Fall back to static fetch for endpoints not natively handled in Code.gs
                    fetchStaticData(fileName, endpoint).then(resolve).catch(reject);
                }
            });
        }

        // 2. Standalone / Static Web Hosting Context
        return await fetchStaticData(fileName, endpoint);
    }

    /**
     * Fetch static JSON dataset with fallback paths & proper error handling.
     */
    async function fetchStaticData(fileName, originalEndpoint) {
        const baseUrl = resolveDataBaseUrl();
        const primaryUrl = `${baseUrl}${fileName}.json?v=${Date.now()}`;
        const candidateUrls = [
            primaryUrl,
            `./data/${fileName}.json?v=${Date.now()}`,
            `../data/${fileName}.json?v=${Date.now()}`,
            `data/${fileName}.json?v=${Date.now()}`
        ];

        let lastError = null;

        for (const url of candidateUrls) {
            try {
                const response = await fetch(url, {
                    cache: 'no-store',
                    headers: {
                        'Cache-Control': 'no-cache',
                        'Pragma': 'no-cache'
                    }
                });

                if (response.ok) {
                    const data = await response.json();
                    return data;
                } else {
                    lastError = new Error(`HTTP ${response.status} (${response.statusText || 'Not Found'})`);
                }
            } catch (err) {
                lastError = err;
            }
        }

        const errorMsg = lastError ? (lastError.message || String(lastError)) : 'Network error or file not found';
        renderFallbackUI(errorMsg, originalEndpoint, fileName);
        throw new Error(`Failed to load ${fileName}.json: ${errorMsg}`);
    }

    // Attach to global window object and export
    global.fetchPortalData = fetchPortalData;

})(typeof window !== 'undefined' ? window : this);

