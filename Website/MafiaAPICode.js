/* * 🐍 Lydia's Mafia Analytics Engine v11 (Unified)
 * - Single Entry Point: 'Index.html'
 * - Handles both Classic and Battle Royale data requests.
 */

function doGet(e) {
  // Simple and safe: Always load Index.
  return HtmlService.createTemplateFromFile('Index')
    .evaluate()
    .setTitle('🕵️‍♂️ Mafia Analytics')
    .addMetaTag('viewport', 'width=device-width, initial-scale=1')
    .setXFrameOptionsMode(HtmlService.XFrameOptionsMode.ALLOWALL);
}

function getDashboardData(mode) {
  // Default to classic if undefined
  mode = mode || 'classic';
  
  if (mode === 'battle_royale') {
    return calculateBattleRoyaleStats_();
  } else {
    return calculateClassicStats_();
  }
}

// --- 🏎️ CLASSIC CALCULATOR ---
function calculateClassicStats_() {
  let games = getSheetData_('Games');
  games = games.filter(g => g.game_type && g.game_type.toLowerCase().trim() === 'classic');
  games.sort((a, b) => new Date(a.start_time_utc) - new Date(b.start_time_utc));

  let factionStats = { Town: 0, Mafia: 0, Neutral: 0, Draw: 0, Total: 0 };
  let trendData = [];
  
  games.forEach(g => {
    factionStats.Total++;
    let winner = g.winning_faction || 'Draw';
    if (winner === 'Town') factionStats.Town++;
    else if (winner === 'Mafia') factionStats.Mafia++;
    else if (winner === 'Draw') factionStats.Draw++;
    else { factionStats.Neutral++; winner = 'Neutral'; }

    trendData.push({
      date: new Date(g.start_time_utc).toLocaleDateString(),
      townPct: ((factionStats.Town / factionStats.Total) * 100).toFixed(1),
      mafiaPct: ((factionStats.Mafia / factionStats.Total) * 100).toFixed(1),
      neutralPct: ((factionStats.Neutral / factionStats.Total) * 100).toFixed(1),
      drawPct: ((factionStats.Draw / factionStats.Total) * 100).toFixed(1)
    });
  });

  const analyticsData = getSheetData_('Analytics');
  const leaderboard = analyticsData.map(row => {
    if (!row['player_name']) return null;
    return {
      name: row['player_name'],
      skillScore: row['skill_score'],
      p_score: row['persuasion_(p)'],
      e_score: row['elusiveness_(e)'],
      u_score: row['understanding_(u)'],
      games: row['games_played'],
      winRate: row['win_rate_%'],
      n1Deaths: row['n1_deaths'],
      d1Lynches: row['d1_lynches']
    };
  }).filter(item => item !== null);

  return { mode: 'classic', gameStats: factionStats, trend: trendData, leaderboard: leaderboard };
}

// --- ⚔️ BATTLE ROYALE CALCULATOR ---
function calculateBattleRoyaleStats_() {
  let games = getSheetData_('Games');
  let players = getSheetData_('Players');

  games = games.filter(g => g.game_type && g.game_type.toLowerCase().includes('battle'));
  const gameIds = new Set(games.map(g => g.game_id));
  let gamePhaseMap = {};
  games.forEach(g => { gamePhaseMap[g.game_id] = parseInt(g.total_phases) || 1; });

  let pStats = {};
  let winCounts = { 'Draw': 0 };
  games.forEach(g => { if (g.winning_faction === 'Draw') winCounts['Draw']++; });

  players.forEach(p => {
    if (!gameIds.has(p.game_id)) return;
    const name = p.player_name;
    if (!pStats[name]) pStats[name] = { name: name, games: 0, wins: 0, phasesPlayed: 0, phasesPossible: 0, n1Deaths: 0 };
    const s = pStats[name];
    s.games++;
    const isWinner = String(p.is_winner).toUpperCase() === 'TRUE';
    if (isWinner) {
      s.wins++;
      if (!winCounts[name]) winCounts[name] = 0;
      winCounts[name]++;
    }
    
    // Survival Logic
    const totalPhases = gamePhaseMap[p.game_id] || 1;
    let phasesSurvived = totalPhases;
    if (p.status !== "Alive" && !isWinner && p.death_phase) {
       const match = p.death_phase.match(/(\d+)/);
       if (match) {
         let rawSurvived = parseInt(match[0]) - 1; 
         phasesSurvived = Math.max(0, Math.min(rawSurvived, totalPhases - 1));
       }
    }
    s.phasesPlayed += phasesSurvived;
    s.phasesPossible += totalPhases;
    if ((p.death_phase || "").includes("Night 1")) s.n1Deaths++;
  });

  const leaderboard = Object.values(pStats).map(p => ({
    name: p.name, games: p.games, wins: p.wins,
    winRate: ((p.wins / p.games) * 100).toFixed(0),
    survRate: p.phasesPossible > 0 ? ((p.phasesPlayed / p.phasesPossible) * 100).toFixed(0) : "0",
    n1Deaths: p.n1Deaths
  })).sort((a, b) => b.wins - a.wins || b.games - a.games);

  let chartLabels = [], chartValues = [];
  const sortedWinners = Object.keys(winCounts).map(k => ({ name: k, count: winCounts[k] })).sort((a, b) => b.count - a.count);
  sortedWinners.forEach(item => { if (item.count > 0) { chartLabels.push(item.name); chartValues.push(item.count); } });

  return { mode: 'battle_royale', leaderboard: leaderboard, chart: { labels: chartLabels, values: chartValues }, totalGames: games.length };
}

function getSheetData_(sheetName) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sheet = ss.getSheetByName(sheetName);
  if (!sheet) return [];
  const data = sheet.getDataRange().getValues();
  if (data.length < 2) return [];
  const headers = data[0];
  const rows = data.slice(1);
  return rows.map(row => {
    let obj = {};
    headers.forEach((header, index) => {
      const cleanHeader = header.toString().toLowerCase().replace(/\s+/g, '_');
      obj[cleanHeader] = row[index];
    });
    return obj;
  });
}