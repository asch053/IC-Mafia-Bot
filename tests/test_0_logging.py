import logging
import os
from datetime import datetime

# --- CRITICAL FIX: GLOBAL MOCK ENVIRONMENT VARIABLES ---
# By placing this at the top of the logging setup, it runs instantly 
# when ANY test file imports `setup_test_logging`, ensuring the environment 
# is mocked before `config.py` is ever evaluated.
env_mocks = {
    "BOT_TOKEN": "test_token", "SERVER_ID": "1", "TALKY_TALKY_CHANNEL_ID": "1",
    "STORIES_CHANNEL_ID": "1", "VOTING_CHANNEL_ID": "1", "RULES_AND_ROLES_CHANNEL_ID": "1",
    "DEADZOR_CHANNEL_ID": "1", "SIGN_UP_HERE_CHANNEL_ID": "1", "MOD_CHANNEL_ID": "1",
    "ANNOUNCEMENT_CHANNEL_ID": "1", "LIVING_ROLE_ID": "1", "DEAD_ROLE_ID": "1",
    "MOD_ROLE_ID": "1", "SPECTATOR_ROLE_ID": "1", "CLASSIC_TOP_SKILL_ROLE_ID": "1",
    "CLASSIC_TOP_SURVIVOR_ROLE_ID": "1", "CLASSIC_RED_SHIRT_ROLE_ID": "1",
    "BR_TOP_WINS_ROLE_ID": "1", "BR_TOP_SURVIVOR_ROLE_ID": "1", "BR_RED_SHIRT_ROLE_ID": "1",
    "GOOGLE_SHEET_ID": "mock", "GOOGLE_CREDENTIALS_FILE": "mock.json", 
    "GOOGLE_SIMULATION_SHEET_ID": "mock", "GOOGLE_AI_API_KEY": "mock", 
    "OWNER_ID": "1", "GAME_TYPE": "Testing", "BOT_PREFIX": "/"
}
for key, value in env_mocks.items():
    os.environ.setdefault(key, value)

# Global flag to ensure the session start message is only logged once per test run
_session_initialized = False

def setup_test_logging():
    """
    Configures a dedicated logger for unit tests.
    Outputs to ./tests/logs/[datestamp]_testoutput_error.log
    """
    global _session_initialized
    
    # 1. Define paths
    log_dir = os.path.join("tests", "logs")
    datestamp = datetime.now().strftime("%Y-%m-%d")
    log_filename = f"{datestamp}_testoutput_error.log"
    log_path = os.path.join(log_dir, log_filename)

    # 2. Ensure the directory exists
    os.makedirs(log_dir, exist_ok=True)

    # 3. Get the 'discord' logger (which your bot components use)
    logger = logging.getLogger('discord')
    logger.setLevel(logging.DEBUG) # Catch everything during tests!

    # 4. Create a file handler for errors and debug info
    file_handler = logging.FileHandler(log_path, encoding='utf-8')
    formatter = logging.Formatter('[%(asctime)s] [%(levelname)-8s] %(name)s - %(funcName)s:%(lineno)d: %(message)s')
    file_handler.setFormatter(formatter)
    
    # 5. Clear existing handlers to avoid duplicate log lines
    # This prevents the issue where each test file adds an additional handler to the same logger
    if logger.hasHandlers():
        logger.handlers.clear()

    logger.addHandler(file_handler)

    # Also add a stream handler so you still see output in the VS Code terminal
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Only log the session start message the first time this is called in a process
    if not _session_initialized:
        logger.info("\n\n----------------------------------------------------------------------------------------\n\n--- UNIT TEST SESSION STARTED ---")
        _session_initialized = True

    return logger