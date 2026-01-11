import sys
import os
import asyncio
import json
import argparse
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from collections import Counter
import datetime
import simulate_config as config
from headless_game import HeadlessGame
import gc

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)
os.chdir(parent_dir)

# 📝 CONFIG
SIM_SHEET_ID = config.SIMUALTION_GOOGLE_SHEET_ID
TUNE_SHEET_ID = config.TUNING_GOOGLE_SHEET_ID
SIMULATION_COUNT = 1000  # Number of games to simulate per player count
LOG_FILE_PATH = os.path.join(current_dir, f"{config.data_save_path}")
PLAYER_COUNTS = config.PLAYER_COUNTS_TO_SIMULATE



async def run_suite(game_type, SIMULATION_COUNT, balance_version, gf_investigate, doc_player_count, cop_player_count, trb_player_count, 
                    sk_player_count, mrb_player_count, mob_ratio, tuning, tune_town_smart, tune_intuition_base, tune_mafia_smart, 
                    tune_hard_bandwagon, tune_soft_bandwagon, tune_curious_bandwagon, SIM_SHEET_ID=SIM_SHEET_ID):
    # if tuning then load DOE parameters from Json file
    if tuning:
        SIM_SHEET_ID = config.TUNING_GOOGLE_SHEET_ID
        doe_file = os.path.join(current_dir, "DOE Generation", "mafia_doe_scenarios.json")
        with open(doe_file, "r") as f:
            doe_scenarios = json.load(f)
        print(f"🎯 Running Tuning Suite with {len(doe_scenarios)} scenarios from {doe_file}")
        for scenario in doe_scenarios:
            params = scenario["Parameters"]
            print(f"\n🔧 Tuning Scenario {scenario['Scenario_ID']}: "
                  f"Town Smart={params['PROBABILITY_TOWN_SMART']}, "
                  f"Base Intuition={params['BASE_INTUITION']}, "
                  f"Mafia Smart={params['PROBABILITY_MAFIA_SMART']}, "
                  f"Hard Bandwagon={params['PROBABILITY_HARD_BANDWAGON']}, "
                  f"Soft Bandwagon={params['PROBABILITY_SOFT_BANDWAGON']}, "
                  f"Curious Bandwagon={params['PROBABILITY_CURIOUS_BANDWAGON']}")
            await run_suite(game_type, SIMULATION_COUNT, f"{balance_version}_{scenario['Scenario_ID']}", gf_investigate, 
                            doc_player_count, cop_player_count, trb_player_count, sk_player_count, mrb_player_count, 
                            mob_ratio, False, 
                            params['PROBABILITY_TOWN_SMART'], params['BASE_INTUITION'], params['PROBABILITY_MAFIA_SMART'], 
                            params['PROBABILITY_HARD_BANDWAGON'], params['PROBABILITY_SOFT_BANDWAGON'], params['PROBABILITY_CURIOUS_BANDWAGON'],
                            SIM_SHEET_ID)
        return
    else:
        print(f"🏎️  Starting Suite: {len(PLAYER_COUNTS)} batches x {SIMULATION_COUNT} games.") 
        for count in PLAYER_COUNTS:
            print(f"🔄  Running {count} Players...")
            batch_history = await run_batch(game_type, SIMULATION_COUNT, count, balance_version, gf_investigate, doc_player_count, cop_player_count, trb_player_count, 
                            sk_player_count, mrb_player_count, mob_ratio, tuning, tune_town_smart, tune_intuition_base, tune_mafia_smart, 
                            tune_hard_bandwagon, tune_soft_bandwagon, tune_curious_bandwagon, SIM_SHEET_ID)
            
            os.makedirs(LOG_FILE_PATH, exist_ok=True)
            history_file = os.path.join(LOG_FILE_PATH, f"sim_history_p{count}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
            with open(history_file, "w") as f:
                json.dump(batch_history, f, indent=2)
            print(f"📜 Batch simulation history for {count} players saved to {history_file}")
            del batch_history
    print(f"\n✅ SUITE COMPLETE!")

async def run_batch(game_type, SIMULATION_COUNT, player_count, balance_version, gf_investigate, doc_player_count, cop_player_count, trb_player_count, 
                    sk_player_count, mrb_player_count, mob_ratio, tuning, tune_town_smart, tune_intuition_base, tune_mafia_smart, 
                    tune_hard_bandwagon, tune_soft_bandwagon, tune_curious_bandwagon, SIM_SHEET_ID):
    game_results = [] 
    winners = []      
    batch_role_counts = None 
    batch_history = {}
    run_timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # --- SIMULATIONS LOOP ---
    for i in range(SIMULATION_COUNT):
        game = HeadlessGame(game_type=game_type, simnum = i+1, balance_version=balance_version, gf_investigate=gf_investigate, doc_player_count=doc_player_count, 
                            cop_player_count=cop_player_count, trb_player_count=trb_player_count, sk_player_count=sk_player_count, mrb_player_count=mrb_player_count,
                            mob_ratio=mob_ratio, tune_town_smart=tune_town_smart, tune_intuition_base=tune_intuition_base, tune_mafia_smart=tune_mafia_smart,
                            tune_hard_bandwagon=tune_hard_bandwagon, tune_soft_bandwagon=tune_soft_bandwagon, tune_curious_bandwagon=tune_curious_bandwagon)
        for j in range(player_count): 
            await game.add_simulated_player(f"Bot_{j}")
        # Run Simulation 
        winner = await game.run_simulation()
        # Capture Winner
        winners.append(winner)
        # Capture History
        batch_history[i+1] = game.simulation_history
        
        # Capture Setup (First Run)
        if i == 0 and hasattr(game, 'roles') and game.roles:
            role_names = [r.name for r in game.roles]
            batch_role_counts = Counter(role_names)
        
        # --- 1. CAPTURE LISTS ---
        def get_role_list(pid_set):
            roles = []
            for pid in pid_set:
                p = game.players.get(pid)
                if p and p.role: roles.append(p.role.name)
            return ", ".join(sorted(roles))
        if not tuning: 
            net_str = get_role_list(game.knowledge.get('town_network', []))
            mafia_str = get_role_list(game.knowledge.get('known_mafia', []))
            plain_str = get_role_list(game.knowledge.get('known_plain_town', []))

        # --- 2. CAPTURE DEATH PHASES ---
        # Helper to safely get death phase or empty string if alive/not in game
        def get_death(role_name):
            return game.vip_death_phases.get(role_name, "")
        if not tuning:
            cop_death = get_death("Town Cop")
            doc_death = get_death("Town Doctor")
            trb_death = get_death("Town Role Blocker")
            gf_death  = get_death("Godfather")
            mrb_death = get_death("Mob Role Blocker")
            sk_death  = get_death("Serial Killer")

        # --- 3. BUILD ROW ---
        game_id = f"{balance_version}_{player_count}p_{i+1}"
        last_phase = game.game_settings['current_phase']
        phases = game.game_settings['phase_number']
        num_players = len(game.players)
        scenario_type = "Small" if num_players < 13 else "Medium" if num_players < 18 else "Large"
        # if tuning, capture minimal data
        tuning = True
        if tuning == True:
            game_results.append([
                game_id,            
                game_type,
                last_phase,          
                phases,
                num_players, 
                scenario_type,            
                winner,             
                balance_version
            ])
        else:
            game_results.append([
                game_id,            
                game_type,
                last_phase,          
                phases,
                num_players, 
                scenario_type,            
                winner,             
                balance_version,
                net_str,    # Town Network
                mafia_str,  # Known Mafia
                plain_str,  # Known Plain Town
                cop_death,  # Phase Town Cop Death
                doc_death,  # Phase Town Doc Death
                trb_death,  # Phase Town RB Death
                gf_death,   # Phase Mob GF Death
                mrb_death,  # Phase Mob RB Death
                sk_death    # Phase SK Death
            ])
            
        if (i+1) % 250 == 0:
            print(f"   ... {i+1}/{SIMULATION_COUNT}")
        
        # Clean up memory
        await game.reset()
        del game

    # Clean up
    gc.collect()

    # Stats & Upload
    counts = Counter(winners)
    total = len(winners)
    print(f"🏆 P{player_count} Results: Last Phase: {last_phase} [{phases}] | Town: {counts['Town']} | Mafia: {counts['Mafia']} | SK: {counts['Serial Killer']} | Draws: {counts['Draw']}")

    save_local_log(counts, total, game_type, player_count, balance_version)
    await upload_batch_data(tuning, game_results, counts, batch_role_counts, game_type, player_count, balance_version, run_timestamp,
                            tune_town_smart, tune_intuition_base, tune_mafia_smart, tune_hard_bandwagon, tune_soft_bandwagon, tune_curious_bandwagon, SIM_SHEET_ID)
    
    return batch_history


def save_local_log(counts, total, game_type, player_count, version):
    os.makedirs(LOG_FILE_PATH, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S").replace(":", "-").replace(" ", "_")
    town_pct = (counts['Town'] / total) * 100
    mafia_pct = (counts['Mafia'] / total) * 100
    sk_pct = (counts['Serial Killer'] / total) * 100
    
    log_entry = (
        f"[{timestamp}] Ver: {version} | P: {player_count} | "
        f"Type: {game_type} | Total Games: {total} | "
        f"Town: {counts['Town']} ({town_pct:.1f}%) | "
        f"Mafia: {counts['Mafia']} ({mafia_pct:.1f}%) | "
        f"SK: {counts['Serial Killer']} ({sk_pct:.1f}%) | "
        f"Draws: {counts['Draw']}\n"
        f"Version: {version}\n"
    )
    LOG_FILE_NAME = os.path.join(LOG_FILE_PATH, f"{timestamp}-simulation_history.log").replace(" ", "_")
    print(f"📝 Saving local log to {LOG_FILE_NAME}")
    try:
        with open(LOG_FILE_NAME, "a", encoding="utf-8") as f:
            f.write(log_entry)
    except: pass

async def upload_batch_data(tuning, game_rows, counts, role_counts, game_type, player_count, balance_version, timestamp, 
                            tune_town_smart, tune_intuition_base, tune_mafia_smart, tune_hard_bandwagon, tune_soft_bandwagon, tune_curious_bandwagon, SIM_SHEET_ID):
    try:
        scope = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
        creds = ServiceAccountCredentials.from_json_keyfile_name(config.GOOGLE_CREDENTIALS_FILE, scope)
        client = gspread.authorize(creds)
        
        if tuning:
            sheet = client.open_by_key(TUNE_SHEET_ID)
        else:
            sheet = client.open_by_key(SIM_SHEET_ID)
        print (f"🌐 Uploading batch data to Google Sheets...{sheet}")
        # 1. GAMES TAB
        try:
            ws = sheet.worksheet("Games")
        except:
            ws = sheet.add_worksheet(title="Games", rows=5000, cols=20)
            ws.append_row([
                "Game ID", "Game Type", "Last Phase",  "Total Phases", "Winning Faction", "Balance Version", 
                "Final Town Network", "Final Known Mafia", "Final Known Plain Town",
                "Phase Town Cop Death", "Phase Town Doc Death", "Phase Town RB Death",
                "Phase Mob GF Death", "Phase Mob RB Death", "Phase SK Death"
            ])
        ws.append_rows(game_rows)

        # 2. VERSIONS TAB
        try:
            ws_ver = sheet.worksheet("Balance Versions")
        except:
            ws_ver = sheet.add_worksheet(title="Balance Versions", rows=1000, cols=10)
            ws_ver.append_row(["Balance Version", "Run Datetime", "Game Type", "Players", "Total Runs", "Town Win %", "Mafia Win %", "SK Win %", "Draw %",
                               "Probability Town Smart", "Base Intuition", "Probability Mafia Smart", "Probability Hard Bandwagon", "Probability Soft Bandwagon", "Probability Curious Bandwagon"])
        
        total = sum(counts.values())
        ws_ver.append_row([
            balance_version, timestamp, game_type, player_count, total,
            counts['Town']/total, counts['Mafia']/total, counts['Serial Killer']/total, counts['Draw']/total, 
            tune_town_smart, tune_intuition_base, tune_mafia_smart, tune_hard_bandwagon, tune_soft_bandwagon, tune_curious_bandwagon
        ])

        # 3. SETUPS TAB
        try:
            ws_setups = sheet.worksheet("Setups")
        except:
            ws_setups = sheet.add_worksheet(title="Setups", rows=1000, cols=15)
            ws_setups.append_row([
                "Balance Version", "Player Count", "Godfather", "Mob Goon", "Mob Role Blocker", 
                "Town Doctor", "Town Cop", "Town Role Blocker", "Plain Townie", 
                "Serial Killer", "Jester", "Vigilante"
            ])
            
        if role_counts:
            ws_setups.append_row([
                balance_version, player_count,
                role_counts.get("Godfather", 0), role_counts.get("Mob Goon", 0), role_counts.get("Mob Role Blocker", 0),
                role_counts.get("Town Doctor", 0), role_counts.get("Town Cop", 0), role_counts.get("Town Role Blocker", 0),
                role_counts.get("Plain Townie", 0), role_counts.get("Serial Killer", 0),
                role_counts.get("Jester", 0), role_counts.get("Vigilante", 0)
            ])

        print("   ✅ Upload Complete.")
    except Exception as e:
        print(f"❌ Upload Failed: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--type', type=str, default='classic')
    parser.add_argument('--num_sims', type=int, default=SIMULATION_COUNT)
    parser.add_argument('--version', type=str, default=None)
    parser.add_argument('--gf-investigate', action='store_true')
    parser.add_argument('--doc-player-count', type=int, default=config.min_doctor_players)
    parser.add_argument('--cop-player-count', type=int, default=config.min_cop_players)
    parser.add_argument('--trb-player-count', type=int, default=config.min_town_rb_players)
    parser.add_argument('--sk-player-count', type=int, default=config.min_sk_players)
    parser.add_argument('--mrb-player-count', type=int, default=config.min_mob_rb_mafia_count)
    parser.add_argument('--mob-ratio', type=int, default=3)
    parser.add_argument('--tuning', action='store_true') # Parameter to detemrine if running sims for parameter tuning or balancing
    parser.add_argument('--tune_town_smart', type=float, default=config.PROBABILITY_TOWN_SMART)
    parser.add_argument('--tune_intuition_base', type=float, default=config.BASE_INTUITION)
    parser.add_argument('--tune_mafia_smart', type=float, default=config.PROBABILITY_MAFIA_SMART)
    parser.add_argument('--tune_hard_bandwagon', type=float, default=config.PROBABILITY_HARD_BANDWAGON)
    parser.add_argument('--tune_soft_bandwagon', type=float, default=config.PROBABILITY_SOFT_BANDWAGON)
    parser.add_argument('--tune_curious_bandwagon', type=float, default=config.PROBABILITY_CURIOUS_BANDWAGON)
    parser.add_argument('--logging', action='store_true', help='Enable verbose game logging (Slows down simulation)')

    args = parser.parse_args()

    # 🔄 UPDATE CONFIG BASED ON ARGUMENT
    config.LOGGING_ENABLED = args.logging
    print(f"📝 Verbose Logging: {'ENABLED (Slow)' if config.LOGGING_ENABLED else 'DISABLED (Fast)'}")

    if not args.version:
        args.version = f"Suite_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}"

    try:
        asyncio.run(run_suite(args.type,args.num_sims ,args.version, args.gf_investigate, args.doc_player_count, args.cop_player_count, 
                              args.trb_player_count, args.sk_player_count, args.mrb_player_count, args.mob_ratio, 
                              args.tuning, args.tune_town_smart, args.tune_intuition_base, args.tune_mafia_smart, 
                              args.tune_hard_bandwagon, args.tune_soft_bandwagon, args.tune_curious_bandwagon))
    except KeyboardInterrupt:
        print("\n🛑 Stopped.")