import sys
import os
import asyncio
import logging
import random
import datetime
from unittest.mock import MagicMock, AsyncMock
import simulate_config as config
import simulate_Rolegeneration as setup_generator
from simulate_roles import get_role_instance


# --- 🔧 PATH FIXER ---
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)
# ---------------------

from game.engine import Game
from game.player import Player
from collections import defaultdict
import game.actions as actions


# FORCE OVERWRITE: Apply simulation settings to the running game config
import simulate_config as sim_config
import config as root_config

# --- 🔄 SYNC TUNING PARAMS TO PRODUCTION CONFIG ---
root_config.MAX_MISSED_VOTES = sim_config.MAX_MISSED_VOTES
root_config.PROBABILITY_TOWN_SMART = sim_config.PROBABILITY_TOWN_SMART
root_config.BASE_INTUITION = sim_config.BASE_INTUITION
root_config.PROBABILITY_MAFIA_SMART = sim_config.PROBABILITY_MAFIA_SMART
root_config.PROBABILITY_HARD_BANDWAGON = sim_config.PROBABILITY_HARD_BANDWAGON
root_config.PROBABILITY_SOFT_BANDWAGON = sim_config.PROBABILITY_SOFT_BANDWAGON
root_config.PROBABILITY_CURIOUS_BANDWAGON = sim_config.PROBABILITY_CURIOUS_BANDWAGON



# --- 📝 LOGGING SETUP ---
# 1. Strip leading slashes to ensure it stays relative to the current directory
relative_save_path = config.data_save_path.strip("/").strip("\\")

# 2. Build the full directory path
LOG_FILE_PATH = os.path.join(current_dir, relative_save_path)

# 3. Create the directory if it doesn't exist
if not os.path.exists(LOG_FILE_PATH):
    try:
        os.makedirs(LOG_FILE_PATH)
    except OSError as e:
        print(f"❌ Error creating directory {LOG_FILE_PATH}: {e}")

# 4. Define the Log File Name inside that directory
DATETIME = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
LOG_FILE = os.path.join(LOG_FILE_PATH, f"{DATETIME}_sim_debug.log")

print("----- Simulation Logging Setup -----")
print(f"📂 Base Directory: {current_dir}")
print(f"📂 Log Folder:    {LOG_FILE_PATH}")
print(f"📝 Log File:      {LOG_FILE}")

logger = logging.getLogger('discord')
logger.setLevel(logging.INFO)

# Clear old handlers to prevent duplicate logs
if logger.hasHandlers():
    logger.handlers.clear()

try:
    file_handler = logging.FileHandler(LOG_FILE, mode='w', encoding='utf-8')
    file_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s', datefmt='%H:%M:%S'))
    logger.addHandler(file_handler)
    logger.propagate = False
    print("✅ Logger initialized successfully.")
except Exception as e:
    print(f"❌ CRITICAL ERROR: Could not create log file: {e}")
# ------------------------

class SimulatedPlayer(Player):
    """A Bot Player that makes decisions based on shared knowledge."""
    def __init__(self, user_id, name, game_ref):
        super().__init__(user_id, name, name)
        self.game = game_ref
        self.last_target = None

    def decide_vote(self):
        """Decides who to vote for based on role and knowledge."""
        if not self.is_alive: return None
        logger.debug(f"[SIM] {self.display_name} [{self.role.name} - {self.role.alignment}]: Deciding vote...")
        # --- HELPER: Get all living players (excluding self) ---
        living_others = [p for p in self.game.players.values() if p.is_alive and p.id != self.id]
        if not living_others: 
            # Should trigger end game usually
            logger.debug(f"[SIM] {self.display_name}: No living others to vote for.")
            return None 
        # ==========================================================
        # 1. SCUM LOGIC (Overrides everything else)
        # ==========================================================
        if self.role.alignment in ["Mafia"]:
            logger.debug(f"[SIM] {self.display_name} (Scum): Executing Scum voting logic...")
            # Check current votes on teammates
            lynch_votes = getattr(self.game, 'lynch_votes', {})
            teammates_in_trouble = []
            total_living = len([p for p in self.game.players.values() if p.is_alive])
            logger.debug(f"[SIM] {self.display_name} (Scum): Checking for teammates in trouble...")
            # Identify teammates and their vote counts
            for pid, voters in lynch_votes.items():
                p = self.game.players.get(pid)
                if p and p.is_alive and p.role.alignment == self.role.alignment:
                    # Only add teammates who have at least 3 votes and more than 15% of the votes
                    if len(voters) >= 3 and len(voters) > (total_living * 0.15):
                        teammates_in_trouble.append((p, len(voters)))
            # Sort by most votes
            teammates_in_trouble.sort(key=lambda x: x[1], reverse=True)
            if teammates_in_trouble:
                target, votes = teammates_in_trouble[0]
                total_living = len([p for p in self.game.players.values() if p.is_alive])
                logger.debug(f"[SIM] {self.display_name} (Scum): Teammate {target.display_name} has {votes} votes out of {total_living} living.")
                # BUSSING: If teammate is doomed (has > 1/3 of living votes), vote for them to blend in
                if votes >= (total_living / 3) and target.id is not self.id:
                    logger.info(f"[SIM] {self.display_name} (Scum) BUSSING teammate {target.display_name}")
                    return target.display_name
            # COUNTER-WAGONING LOGIC
                # DEFENDING: Vote for the leading NON-MAFIA wagon to save teammate
                candidates_with_votes = []
                for tid, voters in lynch_votes.items():
                    t = self.game.players.get(tid)
                    if t and t.is_alive and t.role.alignment != self.role.alignment:
                        candidates_with_votes.append((t, len(voters)))
                candidates_with_votes.sort(key=lambda x: x[1], reverse=True)
                if candidates_with_votes and random.random() < self.game.simulation_parameters['tune_mafia_smart']: # 50% chance to counter-wagon
                    logger.info(f"[SIM] {self.display_name} (Scum) COUNTER-WAGON on {candidates_with_votes[0][0].display_name}")
                    return candidates_with_votes[0][0].display_name
            # Fallback: Join biggest town wagon or vote random non-scum
            possible_targets = [p for p in self.game.players.values() 
                                if p.is_alive and p.role.alignment != self.role.alignment]
            if possible_targets:
                # find largest wagon
                current_votes = getattr(self.game, 'lynch_votes', {})
                candidates_with_votes = []
                for tid, voters in current_votes.items():
                    t = self.game.players.get(tid)
                    if t and t.is_alive and t.role.alignment != self.role.alignment and len(voters) > 0:
                        candidates_with_votes.append((t, len(voters)))
                candidates_with_votes.sort(key=lambda x: x[1], reverse=True)
                if candidates_with_votes and random.random() < self.game.simulation_parameters['tune_mafia_smart']: # 50% chance to bandwagon
                    logger.info(f"[SIM] {self.display_name} (Scum) BANDWAGON on {candidates_with_votes[0][0].display_name}")
                    return candidates_with_votes[0][0].display_name
                # Else choose a random non-scum target
                target = random.choice(possible_targets)
                logger.info(f"[SIM] {self.display_name} (Scum) voting random non-scum {target.display_name}")
                return target.display_name
            return None
        # ==========================================================
        # 2. TOWN NETWORK LOGIC (Cop + Verified PRs)
        # ==========================================================
        cop_id = self.game.knowledge['cop_id']
        is_in_network = self.id in self.game.knowledge['town_network']
        is_town = self.role.alignment == "Town"
        town_safe = is_town and is_in_network
        logger.debug(f"[SIM] {self.display_name} (Verified Town): Executing Town voting logic...")
        # A. FOLLOW THE LEADER (Non-Cop Network Members)
        if town_safe and self.id != cop_id:
            cop_target_id = None
            lynch_votes = getattr(self.game, 'lynch_votes', {})
            for target_id, voters in lynch_votes.items():
                if cop_id in voters:
                    cop_target_id = target_id
                    break 
            if cop_target_id:
                target = self.game.players.get(cop_target_id)
                if target and target.is_alive:
                    logger.info(f"[SIM] {self.display_name} [{self.role.name}] (Network) following Cop's lead on {target.display_name} [{target.role.name}]")
                    return target.display_name
        # B. LEADER LOGIC (Cop or Network Member acting alone)
        if town_safe:
            logger.debug(f"[SIM] {self.display_name} [{self.role.name} - {self.role.alignment}] (Network): Deciding vote as Cop/Network member...")
            living_players = [p for p in self.game.players.values() if p.is_alive and p.id != self.id]
            # Priority 1: SCUM (Alive)
            # FIX: Check ALL known mafia, pick the first ALIVE one
            known_scum_ids = self.game.knowledge['known_mafia']
            alive_scum = [p for p in living_players if p.id in known_scum_ids]
            if alive_scum:
                logger.info(f"[SIM] {self.display_name} [{self.role.name}] (Network) voting known scum {alive_scum[0].display_name} [{alive_scum[0].role.name}]")
                return alive_scum[0].display_name
            # Priority 2: UNKNOWNS
            all_known = (self.game.knowledge['town_network'] | 
                         self.game.knowledge['known_mafia'] | 
                         self.game.knowledge['known_plain_town'])
            unlisted = [p for p in living_players if p.id not in all_known]
            if unlisted:
                target = random.choice(unlisted)
                logger.info(f"[SIM] {self.display_name} [{self.role.name}] (Network) voting unknown {target.display_name} [{target.role.name}]")
                return target.display_name
            # Priority 3: PLAIN TOWNIES
            known_plain = [p for p in living_players if p.id in self.game.knowledge['known_plain_town']]
            if known_plain:
                target = random.choice(known_plain)
                logger.info(f"[SIM] {self.display_name} [{self.role.name}]  (Network) voting known plain townie {target.display_name}")
                return target.display_name

            # Priority 4: PARANOIA
            if living_players:
                target = random.choice(living_players)
                logger.info(f"[SIM] {self.display_name} [{self.role.name}] (Network) voting random player out of paranoia {target.display_name} [{target.role.name}]")
                return target.display_name
            
        # ==========================================================
        # 3. STANDARD / PLAIN TOWNIE / SK LOGIC
        # ==========================================================
        logger.debug(f"[SIM] {self.display_name} [{self.role.name} - {self.role.alignment}]: Executing Standard voting logic...")
        
        
        # A. PUBLIC CLAIM: Follow the Cop if they found scum
        if self.game.knowledge.get('public_cop_claim'):
            # FIX: Look for ANY living known mafia
            known_scum_ids = self.game.knowledge['known_mafia']
            # We filter self.game.players to find living targets in that set
            alive_targets = [p for p in self.game.players.values() 
                             if p.is_alive and p.id in known_scum_ids and p.id is not self.id]
            if alive_targets:
                target = alive_targets[0]
                logger.info(f"[SIM] {self.display_name} [{self.role.name}] (Standard) following Public Cop Claim on {target.display_name} [{target.role.name}]")
                return target.display_name
        # B. Stepped BANDWAGON (Smart Herd Mentality)
        # If no info, join the biggest wagon to prevent draws/inactivity
        current_votes = getattr(self.game, 'lynch_votes', {})
        candidates_with_votes = []
        total_living = len([p for p in self.game.players.values() if p.is_alive])
        # Build list of Bandwagon targets with votes
        for tid, voters in current_votes.items():
            t = self.game.players.get(tid)
            if t and t.is_alive and len(voters) >= 2 and t is not self.id:  # only consider targets with 2+ votes as bandwagons and not yourself
                candidates_with_votes.append((t, len(voters)))
        # Sort by size (biggest wagons first)
        candidates_with_votes.sort(key=lambda x: x[1], reverse=True)
        if candidates_with_votes and random.random() < self.game.simulation_parameters['tune_town_smart'] : # chance to bandwagon
            top_target, top_votes = candidates_with_votes[0] # Get biggest wagon
            #1. Hard Bandwagon (Consensus): >33% of living players
            if top_votes > (total_living / 3) and random.random() < self.game.simulation_parameters['tune_hard_bandwagon']: # chance to hard bandwagon
                logger.info(f"[SIM] {self.display_name} [{self.role.name}] (Standard) HARD BANDWAGON on {top_target.display_name} [{top_target.role.name}] with {top_votes} votes")
                return top_target.display_name
            #2. Soft Bandwagon (Building Momentum): > 15% of living players
            elif top_votes > (total_living * 0.15) and random.random() < self.game.simulation_parameters['tune_soft_bandwagon']: # chance to soft bandwagon
                logger.info(f"[SIM] {self.display_name} [{self.role.name}] (Standard) SOFT BANDWAGON on {top_target.display_name} [{top_target.role.name}] with {top_votes} votes")
                return top_target.display_name
            # 3. Curiosity Bandwagon (Minority): > 2 votes
            elif top_votes >= 2 and random.random() < self.game.simulation_parameters['tune_curious_bandwagon']: # chance to curiosity bandwagon
                logger.info(f"[SIM] {self.display_name} [{self.role.name}] (Standard) CURIOUS BANDWAGON on {top_target.display_name} [{top_target.role.name}] with {top_votes} votes")
                return top_target.display_name
        # ==========================================================
        # C. Smart Random Vote (increased chance to hit scum as game gets later)
        game_completeness = self.game.game_settings['phase_number'] / len(self.game.players)
        if random.random() < self.game.simulation_parameters['tune_town_smart'] * (self.game.simulation_parameters['tune_intuition_base'] + game_completeness):
            scum_candidates = [p for p in living_others if p.role.alignment != "Town" and p.id is not self.id]
            # add mafia to visible scum & 25% chance that SK gets added
            visible_scum = []
            for s in scum_candidates:
                if s.role.alignment == "Serial Killer":
                    if random.random() > 0.15: # 15% chance to be seen
                        visible_scum.append(s)
                else:
                    visible_scum.append(s) # Mafia are always visible to intuition
            if visible_scum:
                target = random.choice(visible_scum)
                logger.info(f"[SIM] {self.display_name} [{self.role.name}] (Standard) voting smart random scum candidate {target.display_name} [{target.role.name}]")
                return target.display_name
        # ==========================================================
        
        # D. RANDOM (Last Resort)
        # list all living players
        living_others = [p for p in self.game.players.values() 
                                if p.is_alive and p.id is not self.id]
        if living_others:
            target = random.choice(living_others)
            logger.info(f"[SIM] {self.display_name} [{self.role.name}] (Standard) voting random player {target.display_name} [{target.role.name}]")
            return target.display_name
        return None

    def decide_night_action(self):
        if not self.is_alive or not self.role: return None
        abilities = self.role.abilities
        logger.info(f"[SIM] {self.display_name} [{self.role.name} - {self.role.alignment}]: Deciding night action... Abilities: {abilities}")
        # Mafia
        if self.role.alignment == "Mafia":
            # Mafia Kill Process
            if 'kill' in abilities:
                # if mafia then avoid targeting mafia if possible
                targets = [p for p in self.game.players.values() if p.is_alive and p.role.alignment != "Mafia"]
                if targets: 
                    target = random.choice(targets)
                    logger.info(f"[SIM] {self.display_name} - {self.role.name} {self.role.alignment} - targets random town member {target.display_name}")
                    return "kill", target.display_name
            # Mafia RB Block Process
            if self.role.alignment == "Mafia" and 'block' in abilities:
                # Mafia RB: block random non-mafia member
                targets = [p for p in self.game.players.values() if p.is_alive and p.role.alignment != "Mafia" and p != self]
                if targets:
                    target = random.choice(targets)
                    logger.info(f"[SIM] {self.display_name} - {self.role.name} (Mafia RB) - blocks random town member {target.display_name}")
                    return "block", target.display_name
            else:
                return None
        # Town Roles
        if self.role.alignment == "Town":
            # Town Doctor Heal Process
            if 'heal' in abilities:
                if self.id not in self.game.knowledge['town_network']: 
                    # Not in network, heal self if didn't heal self yesterday, else random heal
                    if self.last_target != self.display_name:
                        logger.info(f"[SIM] {self.display_name} - {self.role.name} (Doctor) - heals self")
                        self.last_target = self.display_name
                        return "heal", self.display_name
                    possible = [p for p in self.game.players.values() if p.is_alive]
                    if possible:
                        target = random.choice(possible)
                        logger.info(f"[SIM] {self.display_name} - {self.role.name} (Doctor) - heals random member {target.display_name}")
                        self.last_target = target.display_name
                        return "heal", target.display_name
                    logger.info(f"[SIM] {self.display_name} - {self.role.name} (Doctor) - heals self (only option)")
                    self.last_target = self.display_name
                    return "heal", self.display_name
                network = [p for p in self.game.players.values() if p.is_alive and p.id in self.game.knowledge['town_network']]
                if network: 
                    target = random.choice(network)
                    logger.info(f"[SIM] {self.display_name} - {self.role.name} (Doctor) - heals network member {target.display_name}")
                    self.last_target = target.display_name
                    return "heal", target.display_name
                # If no network members alive, heal self if didn't heal yesterday, otherwise random heal
                if self.last_target != self.display_name:
                    logger.info(f"[SIM] {self.display_name} - {self.role.name} (Doctor) - heals self")
                    self.last_target = self.display_name
                    return "heal", self.display_name
                possible = [p for p in self.game.players.values() if p.is_alive]
                if possible:
                    target = random.choice(possible)
                    logger.info(f"[SIM] {self.display_name} - {self.role.name} (Doctor) - heals random member {target.display_name}")
                    self.last_target = target.display_name
                    return "heal", target.display_name
                logger.info(f"[SIM] {self.display_name} - {self.role.name} (Doctor) - heals self (only option)")
                self.last_target = self.display_name
                return "heal", self.display_name
            # Town RB
            if 'block' in abilities:
                # Set list of possible block targets to everyone except self
                possible = [p for p in self.game.players.values() if p.is_alive and p != self]
                all_targets = possible[:] # Keep a copy of all valid targets
                # If town blocker is part of town network, follow priortiies
                if self.id in self.game.knowledge['town_network']:
                    # list of all alive people in known mob list
                    possible = [p for p in all_targets if p.id in self.game.knowledge['known_mafia']]             
                    if not possible:
                        # List all alive known plain town
                        possible = [p for p in all_targets if p.id in self.game.knowledge['known_plain_town']]
                        if not possible:
                            # Target any random alive player not in known town network
                            possible = [p for p in all_targets if p.id not in self.game.knowledge['town_network']]
                # Block random member
                if possible: 
                    target = random.choice(possible)
                    logger.info(f"[SIM] {self.display_name} - {self.role.name} (Town RB) - blocks {target.display_name}")
                    return "block", target.display_name
            # Cop
            if 'investigate' in abilities:
                # Set list of possible investigation targets to everyone except self
                possible = [p for p in self.game.players.values() if p.is_alive and p != self]
                # Avoid investigating known players
                all_known = (self.game.knowledge['town_network'] | 
                            self.game.knowledge['known_mafia'] | 
                            self.game.knowledge['known_plain_town'])
                # Narrow to uninvestigated players
                possible = [p for p in possible if p.id not in all_known]
                if possible: 
                    target = random.choice(possible)
                    logger.info(f"[SIM] {self.display_name} - {self.role.name} (Cop) - investigates {target.display_name}")
                    return "investigate", target.display_name
        # SK Kill
        if self.role.name == "Serial Killer":
            if 'kill' in abilities:
                targets = [p for p in self.game.players.values() if p.is_alive and p != self]
                if targets: 
                    target = random.choice(targets)
                    logger.info(f"[SIM] {self.display_name} - {self.role.name} (SK) - targets random member {target.display_name}")
                    return "kill", target.display_name
        
        return None 
        

class HeadlessGame(Game):
    def __init__(self, game_type="classic", simnum=None, balance_version="default", gf_investigate=False, doc_player_count=config.min_doctor_players, 
                            cop_player_count=config.min_cop_players, trb_player_count=config.min_town_rb_players, sk_player_count=config.min_sk_players, 
                            mrb_player_count=config.min_mob_rb_mafia_count, mob_ratio=4,
                            tune_town_smart=config.PROBABILITY_TOWN_SMART, tune_intuition_base=config.BASE_INTUTION, tune_mafia_smart=config.PROBABILITY_MAFIA_SMART,
                            tune_hard_bandwagon=config.PROBABILITY_HARD_BANDWAGON,tune_soft_bandwagon=config.PROBABILITY_SOFT_BANDWAGON,tune_curious_bandwagon=config.PROBABILITY_CURIOUS_BANDWAGON):
        mock_bot = MagicMock()
        mock_bot.get_channel.return_value = AsyncMock()
        mock_user = MagicMock()
        mock_user.send = AsyncMock()
        mock_bot.get_user.return_value = mock_user
        mock_bot.fetch_user = AsyncMock(return_value=mock_user)
        
        mock_guild = MagicMock()
        mock_guild.get_role.return_value = MagicMock()
        mock_guild.get_member.return_value = mock_user
        
        super().__init__(mock_bot, mock_guild, game_type=game_type)
        self.is_simulation = True
        self.sim_num = simnum
        self.balance_version = balance_version
        self.roles = []

        # Create dictonary of game setup parameters
        self.game_parameters = {
            'gf_investigate': gf_investigate,
            'doc_player_count': doc_player_count,
            'cop_player_count': cop_player_count,
            'trb_player_count': trb_player_count,
            'sk_player_count': sk_player_count,
            'mrb_player_count': mrb_player_count,
            'mob_ratio': mob_ratio
        }
        self.simulation_parameters = { 
            'tune_town_smart': tune_town_smart,
            'tune_intuition_base': tune_intuition_base,
            'tune_mafia_smart': tune_mafia_smart,
            'tune_hard_bandwagon': tune_hard_bandwagon,
            'tune_soft_bandwagon': tune_soft_bandwagon, 
            'tune_curious_bandwagon': tune_curious_bandwagon
        }

        # Stats & Knowledge
        self.knowledge = {
            'cop_id': None,
            'town_network': set(),
            'known_plain_town': set(),
            'known_mafia': set()
        }
        self.lynch_votes = {}
        self.night_actions = {}
        # Store game history for analysis. Store for each simulation the night actions & outcomes, lynch votes and outcomes
        self.game_history = {
            'night_actions': [],
            'night_outcomes': [],
            'lynch_votes': [],
            'lynch_outcomes': []
        }
        # Overall simulation history across multiple games       
        self.simulation_history = []
        # NEW: Track when specific roles die { "Town Cop": 3, "Godfather": 5 }
        self.vip_death_phases = {}

        # --- Simulation-specific history tracking ---
        self.night_outcomes = {}
        self.successful_saves = {}
        self.captured_investigation_results = {}

    # --- SILENCERS ---
    async def send_role_dm(self, *args): pass
    async def announce(self, *args): pass
    async def update_player_discord_roles(self, *args): pass
    
    async def add_simulated_player(self, name):
        pid = len(self.players) + 1
        player = SimulatedPlayer(pid, name, self)
        self.players[pid] = player
        return player

    async def process_night_actions(self):
        """Processes all recorded night actions in the correct priority order."""
        # If no actions were taken, add a 'no_actions' event and return
        if not self.night_actions:
            self.narration_manager.add_event('no_actions')
            return
        # Prepare a structure to hold the outcomes of actions for narration
        night_outcomes = {
            player_id: {'action': data['type'], 'target': data['target_id'], 'status': None}
            for player_id, data in self.night_actions.items()
        }
        self.heals_on_players.clear() # Reset heals and kills tracking
        logger.info("Processing night actions...")
        logger.info(f"Initial night actions: {self.night_actions}")
        logger.info(f"Initial night outcomes before processing: {night_outcomes}")

        # Group actions by their primary priority
        action_priority = {"block": 1, "heal": 2, "kill": 3, "investigate": 4}

        # Create a mapping of priority to list of player IDs
        actions_by_priority = defaultdict(list)
        for player_id, data in self.night_actions.items():
            priority = action_priority.get(data['type'], 99) # Default to 99 if action type is unknown
            actions_by_priority[priority].append(player_id) # Group player IDs by action priority
            logger.debug(f"Action '{data['type']}' from player {player_id} assigned to priority {priority}.")
        # Sort and flatten actions into a final processing order
        final_processing_order = []
        # Itterate over priority groups in ascending order
        for priority in sorted(actions_by_priority.keys()):
            priority_group = actions_by_priority[priority]
            logger.info(f"Processing priority group {priority} with players: {priority_group}")
        # Step 1: Shuffle the group to ensure fairness among roles with the same sub-priority.
            random.shuffle(priority_group)
        # Step 2: Sort the now-shuffled group by the role's specific night_priority using Python's built-in sort.
            # This is stable, maintaining the shuffled order for ties.
            sorted_group = sorted(priority_group, key=lambda pid: self.night_actions[pid].get('night_priority', 99))
        # Step 3: Append the sorted group to the final processing order.           
            final_processing_order.extend(sorted_group)

        logger.info(f"Final action processing order: {final_processing_order}")

        # Process each action in the final determined order
        for player_id in final_processing_order:
            action_data = self.night_actions.get(player_id) # Get the action data for this player
            if not action_data: continue
            logger.info(f"Processing action for player {player_id}: {action_data}")
            handler = actions.ACTION_HANDLERS.get(action_data['type']) # Get the handler function for this action type
            logger.info(f"Found handler for action '{action_data['type']}': {handler}")
            if handler:
                try:
                    handler(self, player_id, action_data['target_id'], night_outcomes) # Call the handler function
                except Exception as e:
                    logger.error(f"Error processing action for player {player_id}: {e}", exc_info=True)
        logger.info(f"Final night outcomes after handlers: {night_outcomes}")
        self.night_outcomes = night_outcomes

    async def _resolve_night_deaths(self):
        """
        Final step of the night. Compares kill attempts against heals to determine
        who dies, and generates the definitive kill/save narration events.
        Checks if the killer is still alive before processing the kill.
        """
        logger.info("Resolving final night deaths...")
        phase_str = f"Night {self.game_settings['phase_number']}"
        self.successful_saves.clear()

        # Iterate through a copy of the items because we might modify player state within the loop
        for victim_id, killer_ids in list(self.kill_attempts_on.items()):
            victim_obj = self.players.get(victim_id)
            if not victim_obj or not victim_obj.is_alive: # Skip if victim already died this phase
                logger.warning(f"Victim {victim_id} is already dead or does not exist, skipping.")
                continue

            # Get the primary killer (first one in the list for attribution)
            killer_id = killer_ids[0]
            killer_obj = self.players.get(killer_id)
            if not killer_obj: # Safety check if killer object doesn't exist
                logger.warning(f"Could not find killer object for ID {killer_id} targeting {victim_id}")
                continue

            # --- Check for Saves ---
            if victim_id in self.heals_on_players:
                healer_id = self.heals_on_players[victim_id][0]
                healer_obj = self.players.get(healer_id)
                if healer_obj: # Ensure healer exists
                    self.successful_saves[victim_id] = healer_obj.display_name
                    event_type = 'save_battle_royale' if self.game_settings.get('game_type') == "battle_royale" else 'save'
                    # Pass killer_obj for the narration event
                    self.narration_manager.add_event(event_type, healer=healer_obj, victim=victim_obj, killer=killer_obj)
                    logger.info(f"{victim_obj.display_name} was saved by {healer_obj.display_name}.")
                else:
                    logger.warning(f"Could not find healer object for ID {healer_id} who saved {victim_id}")
                # Even if healer object not found, the save prevents the kill. Continue to next victim.
                continue

            # --- Process Kill (Only if Not Saved) ---
            
            if killer_obj.is_alive:
                # Killer is alive, process the kill
                victim_obj.kill(phase_str, f"Killed by {killer_obj.role.name if killer_obj.role else 'Unknown'}")
                logger.info(f"{victim_obj.display_name} has been killed by {killer_obj.display_name}.")
                self._handle_promotions(victim_obj)
                event_type = 'kill_battle_royale' if self.game_settings.get('game_type') == "battle_royale" else 'kill'
                self.narration_manager.add_event(event_type, killer=killer_obj, victim=victim_obj)
                logger.info(f"{victim_obj.display_name} was killed by {killer_obj.display_name}.")
            else:
                # Killer died earlier in this same resolution phase. Their kill fails.
                event_type = 'kill_missed_battle_royale' if self.game_settings.get('game_type') == "battle_royale" else 'failed_kill_killer_dead'
                self.narration_manager.add_event(event_type, killer=killer_obj, victim=victim_obj)
                logger.info(f"Kill attempt by {killer_obj.display_name} (now dead) on {victim_obj.display_name} failed.")

        # Clear attempts AFTER the loop is finished
        self.kill_attempts_on.clear()
        logger.info("Night deaths resolved.")

    # --- SIMULATION LOOP ---
    async def run_simulation(self):
        logger.info(f"--- STARTING SIMULATION {self.sim_num} ---")
        success = await self.prepare_game_simulation()
        if not success: 
            logger.error("Failed to prepare game simulation due to role generation error.")
            return "Error"
        winner = None
        days_passed = 0
        player_count = len(self.players)
        
        while not winner and days_passed < player_count + 5:
            days_passed += 1
            # NIGHT
            self.game_settings["current_phase"] = "night"
            self.game_settings["phase_number"] += 1
            logger.info(f"--- SIMULATION {self.sim_num}: {self.game_settings['current_phase']} {days_passed} | Total Phases = {self.game_settings['phase_number']} ---")
            await self.simulate_night_phase()
            self._check_vip_deaths() # Check deaths after night kills
            self._update_cop_information()
            self.game_settings["current_phase"] = "pre-day"
            winner = self.check_win_conditions()
            if winner: break

            # DAY
            self.game_settings["current_phase"] = "day"
            self.game_settings["phase_number"] += 1
            logger.info(f"--- SIMULATION {self.sim_num}: {self.game_settings['current_phase']} {days_passed} | Total Phases = {self.game_settings['phase_number']} ---")
            await self.simulate_day_phase()
            self._check_vip_deaths() # Check deaths after lynch
            self.game_settings["current_phase"] = "pre-night"
            winner = self.check_win_conditions()
            if winner: break
            
        logger.info(f"--- {self.sim_num} GAME ENDED: {winner} ---")
        return winner or "Draw"

    def _check_vip_deaths(self):
        """Records the phase number when key roles die."""
        current_phase = self.game_settings["phase_number"]
        
        # Roles we care about
        watch_list = [
            "Town Cop", "Town Doctor", "Town Role Blocker",
            "Godfather", "Mob Role Blocker", "Serial Killer"
        ]
        
        for player in self.players.values():
            if not player.is_alive and player.role:
                r_name = player.role.name
                if r_name in watch_list:
                    # Only record the first time a role type dies
                    if r_name not in self.vip_death_phases:
                        self.vip_death_phases[r_name] = current_phase

    async def prepare_game_simulation(self):
        """Sets up the game for simulation, including role assignment."""
        logger.info(f"[SIM] Preparing {self.game_settings['game_type']} game simulation for {len(self.players)} players......")
        player_count = len(self.players)
        game_type = self.game_settings['game_type']
        game_parameters = self.game_parameters
        logger.info(f"[SIM] Generating roles for {player_count} players in a {game_type} game using {game_parameters} parameters.")
        role_names = setup_generator.generate_roles(player_count, game_type, game_parameters)
        if not role_names: 
            logger.error(f"[SIM] Role generation failed for {player_count} players in a {game_type} game.")
            return False
        logger.info(f"[SIM] Generated {len(role_names)} for {player_count} players. Roles: {role_names}")
        self.roles = [get_role_instance(name) for name in role_names if get_role_instance(name)]
        roles_copy = self.roles[:]
        # Shuffle roles before assignment
        random.shuffle(roles_copy) 
        # Assign roles to players
        for player in self.players.values():
            if roles_copy:
                player.role = roles_copy.pop()
            else:
                player.role = get_role_instance("Plain Townie")
            logger.info(f"[SIM] Assigned Role: {player.display_name} -> {player.role.name}")
            # If Cop, store their ID for knowledge tracking
            if player.role.name == "Town Cop":
                self.knowledge['cop_id'] = player.id
                self.knowledge['town_network'].add(player.id)
        return True

    def _update_cop_information(self):
        """Updates the shared knowledge based on the Cop's investigation."""
        #------------------------------------------#
        # UPDATE KNOWLEDGE FROM COP INVESTIGATION  #
        #------------------------------------------#
        cop_id = self.knowledge['cop_id']
        cop_blocked = False
        if not cop_id: 
            logger.info("[SIM] No Cop in game; skipping Cop information update.")
            return
        cop = self.players.get(cop_id)
        if not cop or not cop.is_alive: 
            logger.info("[SIM] Cop is dead; skipping Cop information update.")
            return
        # Find town and mob RB to see if cop was blocked
        for player in self.players.values():
            if player.is_alive and (player.role.name == "Town Role Blocker" or player.role.name == "Mob Role Blocker"):
                player_action = self.night_actions.get(player.id)
                if player_action and player_action['type'] == 'block':
                    target_id = player_action['target_id']
                    if target_id == cop_id:
                        cop_blocked = True
                        break
        if cop_blocked:
            logger.info("[SIM] Cop was blocked; skipping Cop information update.")
            return
        logger.info(f"[SIM] Updating Cop information for {cop.display_name}")
        cop_action = self.night_actions.get(cop_id)
        if cop_action and cop_action['type'] == 'investigate':
            target_id = cop_action['target_id']
            target = self.players.get(target_id)
            gf_investigate = self.game_parameters['gf_investigate']
            logger.info(f"[SIM] GF has investigate status of {gf_investigate} | {self.game_parameters['gf_investigate']}")
            # Update knowledge based on investigation result
            if target:
                result_str = "Unknown"
                # If target returns Mafia and
                if target.role.alignment == "Mafia" and target.role.name != "Godfather":
                    self.knowledge['known_mafia'].add(target_id)
                    self.knowledge['public_cop_claim'] = True
                    logger.info(f"[SIM] Cop found Mafia: {target.display_name}")
                    result_str = "Mafia"
                elif target.role.alignment == "Mafia" and target.role.name == "Godfather":
                    if gf_investigate:
                        self.knowledge['known_mafia'].add(target_id)
                        logger.info(f"[SIM] Cop found Godfather: {target.display_name}")
                        result_str = "Mafia"
                    else:
                        self.knowledge['known_plain_town'].add(target_id)
                        logger.info(f"[SIM] Cop found Godfather but returned plain townie: {target.display_name}")
                        result_str = "Town"
                elif target.role.alignment == "Town":
                    # Add town doctor or town role block to trusted town circle
                    if target.role.name == "Town Doctor" or target.role.name == "Town Role Blocker":
                        self.knowledge['town_network'].add(target_id)
                        logger.info(f"[SIM] Cop added trusted town to network: {target.display_name}")
                    # Else add to known town list
                    else:
                        self.knowledge['known_plain_town'].add(target_id)
                        logger.info(f"[SIM] Cop found Plain Townie: {target.display_name}")
                    result_str = "Town"
                
                self.captured_investigation_results[target_id] = result_str
                        
        #------------------------------------------  #
        # Update Blocker Information (if applicable) #
        # ------------------------------------------ #
        # Find RB player
        for player in self.players.values():
            if player.is_alive and player.role.name in ["Town Role Blocker"]:
                # Check if RB is in the town network
                if player.id not in self.knowledge['town_network']:
                    continue
                # Get RB's night action
                rb_action = self.night_actions.get(player.id)
                # If RB blocked someone, and that someone is on possible town list, and kill still happened, add to network
                if rb_action and rb_action['type'] == 'block':
                    target_id = rb_action['target_id']
                    # check is target is in possible town list
                    if target_id not in self.knowledge['town_network']: continue
                    target = self.players.get(target_id)
                    # find action outcome for target if any
                    action_data = self.night_actions.get(target_id)
                    if action_data and action_data['type'] == 'kill' and action_data['status'] == 'blocked':
                        # Add player to known mob
                        self.knowledge['known_mafia'].add(target_id)
                        logger.info(f"[SIM] Role Blocker identified Mafia: {target.display_name}")
                    else:
                        self.knowledge['town_network'].add(target_id)
                        logger.info(f"[SIM] Role Blocker added trusted town to network: {target.display_name}")

    async def simulate_day_phase(self):
        """Simulates the day phase with voting."""
        logger.info(f"[SIM] Starting day phase simulation...")
        
        phase_data = {
            "phase": "day",
            "phase_number": self.game_settings["phase_number"],
            "votes": {},
            "outcome": None
        }

        # CLEAR PREVIOUS VOTES
        self.lynch_votes.clear()
        # VOTING
        cop_id = self.knowledge['cop_id']
        # COP VOTES IF ALIVE
        if cop_id:
            cop = self.players.get(cop_id)
            if cop and cop.is_alive:
                t = cop.decide_vote()
                if t: await self._cast_vote(cop, t)
        # Godfather votes next if alive
        for player in self.players.values():
            if player.is_alive and player.role.name == "Godfather":
                t = player.decide_vote()
                if t: await self._cast_vote(player, t)
        # OTHER PLAYERS VOTE
        for player in self.players.values():
            if player.is_alive and player.id != cop_id:
                t = player.decide_vote()
                if t: await self._cast_vote(player, t)
        
        # Capture votes
        for target_id, voters in self.lynch_votes.items():
            if voters:
                target_name = self.players[target_id].display_name
                voter_names = [self.players[v].display_name for v in voters]
                phase_data["votes"][target_name] = voter_names

        logger.info(f"[SIM] Tallying votes for day phase...")     
        alive_before = [p.display_name for p in self.players.values() if p.is_alive]
        await self.tally_votes()
        alive_after = [p.display_name for p in self.players.values() if p.is_alive]
        lynched = [p for p in alive_before if p not in alive_after]
        phase_data["outcome"] = f"Lynched: {lynched[0]}" if lynched else "No Lynch"
        self.simulation_history.append(phase_data)
        logger.info(f"[SIM] Day phase simulation complete.")
        

    async def _cast_vote(self, player, target_name):
        m = AsyncMock()
        m.user.id = player.id
        m.user.name = player.display_name
        logger.info(f"[SIM] {player.display_name} casts vote for {target_name}")
        await self.process_lynch_vote(m, m.user, target_name)

    async def simulate_night_phase(self):
        """Simulates the night phase with night actions."""
        # Clear previous night actions
        self.night_actions.clear()
        self.captured_investigation_results.clear()
        
        phase_data = {
            "phase": "night",
            "phase_number": self.game_settings["phase_number"],
            "actions": [],
            "outcome": []
        }

        logger.info(f"[SIM] Starting night phase simulation...")
        # NIGHT ACTIONS
        for player in self.players.values(): 
            if player.is_alive: # Only alive players act
                d = player.decide_night_action() # (ability, target_name)
                if d:
                    phase_data["actions"].append({
                        "player": player.display_name,
                        "action": d[0],
                        "target": d[1],
                        "outcome": "" # Placeholder for outcome
                    })
                    logger.info(f"[SIM] {player.display_name} decides to {d[0]} {d[1]}")
                    a, t = d
                    m = AsyncMock()
                    m.user.id = player.id
                    await self.record_night_action(m, a, t)
        # TALLY NIGHT ACTIONS
        logger.info(f"[SIM] Processing night actions...")
        alive_before = [p.display_name for p in self.players.values() if p.is_alive]
        await self.process_night_actions()
        await self._resolve_night_deaths()
        alive_after = [p.display_name for p in self.players.values() if p.is_alive]
        deaths = [p for p in alive_before if p not in alive_after]
        phase_data["outcome"] = f"Deaths: {', '.join(deaths)}" if deaths else "No Deaths"

        # CAPTURE DETAILED OUTCOMES
        for action_log in phase_data["actions"]:
            player_obj = self.get_player_by_name(action_log["player"])
            if not player_obj: continue
            target_obj = self.get_player_by_name(action_log["target"])
            if not target_obj: continue

            outcome_description = "Action successful." # Default
            action_outcome = self.night_outcomes.get(player_obj.id)

            if action_outcome and action_outcome.get('status') == 'blocked':
                blocker_id = self.blocked_players_this_night.get(player_obj.id)
                blocker_name = self.players.get(blocker_id).display_name if blocker_id else "Unknown"
                outcome_description = f"Blocked by {blocker_name}."
            else:
                action_type = action_log["action"]
                if action_type == 'kill':
                    if target_obj.id in self.successful_saves:
                        healer_name = self.successful_saves[target_obj.id]
                        outcome_description = f"Target was saved by {healer_name}."
                    elif target_obj.role and target_obj.role.is_night_immune:
                        outcome_description = "Target was immune."
                    elif not target_obj.is_alive:
                        outcome_description = "Kill successful."
                    else: # Target is still alive, kill must have failed
                         outcome_description = "Kill failed (e.g., killer died before kill resolved)."

                elif action_type == 'heal':
                    if target_obj.id in self.successful_saves:
                        outcome_description = "Saved target from an attack."
                    else:
                        outcome_description = "Healed target, but they were not attacked."
                
                elif action_type == 'block':
                    target_action_outcome = self.night_outcomes.get(target_obj.id)
                    if target_action_outcome and target_action_outcome.get('status') == 'blocked':
                         blocked_action_type = target_action_outcome.get('action', 'an')
                         if blocked_action_type == 'kill':
                             outcome_description = "Successfully blocked a kill."
                         else:
                             outcome_description = f"Successfully blocked the target's {blocked_action_type} action."
                    else:
                        outcome_description = "Blocked target, but they had no action."

                elif action_type == 'investigate':
                    result = self.captured_investigation_results.get(target_obj.id)
                    if result:
                        outcome_description = f"Investigation result: {result}"
                    else:
                        outcome_description = "Investigation yielded no result."

            action_log["outcome"] = outcome_description

        self.simulation_history.append(phase_data)
        logger.info(f"[SIM] Night phase simulation complete.")