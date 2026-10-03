import requests
from bs4 import BeautifulSoup
import json
import time
import logging
import os
import math 
from typing import List, Dict, Any
from urllib.parse import urlparse, parse_qs, urlunparse, urlencode, urljoin
from requests.exceptions import HTTPError, RequestException 

# --- 1. CONFIGURATION AND SETUP ---

# Paths are relative to the script's directory for reliable operation
CURRENT_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(CURRENT_SCRIPT_DIR, "logs")
OUTPUT_DIR = os.path.join(CURRENT_SCRIPT_DIR, "output")
DISCOURSE_OUTPUT_FILE = os.path.join(OUTPUT_DIR, "discourse_history.jsonl")
DISCOURSE_THREADS_FILE = os.path.join(OUTPUT_DIR, "discourse_threads.json")

# Discourse Configuration 
DISCOURSE_BASE_URL = "https://discourse.imperialconflict.com"
DISCOURSE_CATEGORY_ID = "237"
TOTAL_PAGES = 20 # Set this to a higher number (e.g., 20) for the full run!
POSTS_PER_THREAD_PAGE = 25 
REQUEST_DELAY_SECONDS = 3 
SERVER_ERROR_BACKOFF = 10 

logger = logging.getLogger('DiscourseExtractor') 

# --- 2. UTILITY FUNCTIONS ---

def setup_directories():
    """Creates the necessary log and output directories if they don't exist."""
    os.makedirs(LOG_DIR, exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    logger.info(f"Ensured log directory exists: {LOG_DIR}")
    logger.info(f"Ensured output directory exists: {OUTPUT_DIR}")

def setup_logging():
    """Configures logging: DEBUG to file, INFO+ to console."""
    setup_directories() 
    log_file_path = os.path.join(LOG_DIR, 'discourse_extractor.log')
    logger.setLevel(logging.DEBUG) # Set logger to lowest level for file capture

    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(name)s - %(message)s')
    
    # 1. File Handler (Captures everything: DEBUG and above)
    file_handler = logging.FileHandler(filename=log_file_path, encoding='utf-8')
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.DEBUG)
    
    # 2. Console Handler (Captures INFO and above)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO) 
    
    if not logger.handlers:
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
    return logger

def fetch_json(url: str) -> Dict[str, Any] | None:
    """Fetches and parses JSON from a given URL with error handling and logging."""
    time.sleep(REQUEST_DELAY_SECONDS)
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status() 
        data = response.json()
        logger.debug(f"Successfully fetched JSON from: {url}")
        return data
    except HTTPError as e:
        if e.response.status_code >= 500:
            logger.error(f"Server Overload Detected ({e.response.status_code}) on {url}. Backing off.")
            time.sleep(SERVER_ERROR_BACKOFF) 
        else:
            logger.warning(f"Client Error ({e.response.status_code}) on {url}. Skipping page.")
        return None
    except RequestException as e:
        logger.error(f"Network Failure on {url}: {e}")
        return None
    except json.JSONDecodeError:
        logger.error(f"Failed to decode JSON from {url}")
        return None

def check_link_status(url: str) -> bool:
    """Checks if a given URL returns a non-404 status code (HEAD request)."""
    time.sleep(1) 
    try:
        response = requests.head(url, timeout=5) 
        return response.status_code != 404
    except requests.RequestException:
        return False

# --- 3. STAGE 1: THREAD LIST HARVESTER ---

def fetch_discourse_thread_links() -> List[Dict[str, str]]:
    
    logger.info(f"Generating URLs for {TOTAL_PAGES} pages...")
    category_api_template = f"{DISCOURSE_BASE_URL}/c/general/ic-mafia/{DISCOURSE_CATEGORY_ID}.json?page="
    all_thread_links = {}
    
    for page_num in range(TOTAL_PAGES):
        page_url = category_api_template + str(page_num) 
        logger.info(f"[Page {page_num + 1}/{TOTAL_PAGES}] Fetching Discourse index: {page_url}")
        
        data = fetch_json(page_url)
        if not data or 'topic_list' not in data or 'topics' not in data['topic_list']:
            logger.info(f"End of index pages reached or failed to retrieve data on page {page_num + 1}.")
            break

        topics = data['topic_list']['topics']
        for topic in topics:
            thread_id = str(topic['id'])
            thread_title = topic['title']
            total_posts = topic.get('posts_count', 0)
            
            permalink = f"{DISCOURSE_BASE_URL}/t/{thread_id}"
            
            if 'mafia' in thread_title.lower() or 'game' in thread_title.lower():
                
                if not check_link_status(permalink):
                    logger.warning(f"Thread ID {thread_id} ({thread_title}) is a DEAD LINK (404/Timeout). Skipping.")
                    continue
                
                all_thread_links[thread_id] = {
                    "title": thread_title,
                    "permalink": permalink,
                    "thread_id": thread_id,
                    "total_posts": total_posts 
                }
        
        if len(topics) < 20 and page_num > 0: 
             logger.info(f"Fewer than 20 topics found on page {page_num + 1}. Assuming last page.")
             break

    final_thread_list = list(all_thread_links.values())
    
    with open(DISCOURSE_THREADS_FILE, 'w', encoding='utf-8') as f:
        json.dump(final_thread_list, f, indent=4)

    logger.critical(f"Found {len(final_thread_list)} UNIQUE, LIVE Mafia threads from Discourse.")
    logger.critical(f"Thread links saved to: {DISCOURSE_THREADS_FILE}")
    
    return final_thread_list

# --- 4. STAGE 2: POST SCRAPER (JSON API - FINAL FIX) ---

def scrape_discourse_posts(thread_list: List[Dict[str, str]]) -> int:
    """Scrapes ALL posts for each thread using the dedicated /posts.json endpoint."""
    total_posts_extracted = 0
    
    logger.critical(f"Starting post extraction for {len(thread_list)} Discourse threads...")
    
    with open(DISCOURSE_OUTPUT_FILE, 'w', encoding='utf-8') as f_out: 
        logger.info(f"Cleared existing data in {DISCOURSE_OUTPUT_FILE} for fresh post run.")
        
        for i, thread in enumerate(thread_list):
            thread_id = thread["thread_id"]
            thread_title = thread["title"]
            
            thread_api_url = f"{DISCOURSE_BASE_URL}/posts.json?topic_id={thread_id}"
            
            logger.info(f"[{i+1}/{len(thread_list)}] Fetching ALL POSTS for: {thread_title}...")

            thread_data = fetch_json(thread_api_url)

            # *** CRITICAL FIX APPLIED HERE ***
            # The API returns posts under the key 'latest_posts'
            posts_to_process = thread_data.get('latest_posts', []) if thread_data else []
            
            if not posts_to_process:
                logger.warning(f"Failed to retrieve post data for thread ID {thread_id} or data is empty. Skipping.")
                continue

            # This total posts check is now much more reliable since we retrieve content.
            expected_count = thread.get('total_posts', len(posts_to_process))
            if len(posts_to_process) != expected_count:
                logger.warning(f"    Fetched {len(posts_to_process)} posts, but expected {expected_count}. Data may be incomplete.")


            for post_num, post in enumerate(posts_to_process):
                
                # --- Logging Post Progress (INFO to console) ---
                logger.info(f"    Processing post {post_num + 1}/{len(posts_to_process)}...")
                
                # --- Content Extraction and Cleaning ---
                # 'cooked' contains the HTML content (confirmed by user JSON)
                content_html = post.get('cooked', '')
                soup = BeautifulSoup(content_html, 'html.parser')
                content = soup.get_text(strip=True)
                
                # --- Metadata Extraction ---
                timestamp_raw = post.get('created_at', 'N/A')
                username = post.get('username', 'Unknown User')
                post_number = post.get('post_number')
                
                specific_post_url = f"{thread['permalink']}/{post_number}"

                record = {
                    "timestamp": timestamp_raw,
                    "source_type": "Discourse-Post",
                    "source_id": specific_post_url,
                    "username": username,
                    "user_id": "N/A", 
                    "content": content
                }
                logger.info(f"Extracted post by {username} at {timestamp_raw} => {specific_post_url}")
                logger.debug(f" Record generated: {json.dumps(record, indent=None)}")

                f_out.write(json.dumps(record, ensure_ascii=False) + '\n')
                total_posts_extracted += 1
                        
    logger.critical(f"----- DISCOURSE POST EXTRACTION COMPLETE -----")
    logger.critical(f"TOTAL DISCOURSE POSTS WRITTEN: {total_posts_extracted}")
    return total_posts_extracted

# --- 5. MAIN EXECUTION ---
if __name__ == "__main__":
    logger = setup_logging()
    
    try:
        logger.info(f"Starting Discourse History Extractor pipeline...")
        
        threads_to_scrape = fetch_discourse_thread_links() 
        
        if threads_to_scrape:
            scrape_discourse_posts(threads_to_scrape)
        else:
            logger.warning("No Discourse Mafia threads found. Skipping post scraping.")
        
    except KeyboardInterrupt:
        logger.critical("Extraction manually stopped.")
    except Exception as e:
        logger.critical(f"Main execution failed: {e}", exc_info=True)