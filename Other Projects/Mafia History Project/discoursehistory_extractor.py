import requests
from bs4 import BeautifulSoup
import json
import re
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
REQUEST_DELAY_SECONDS = 0.5 
SERVER_ERROR_BACKOFF = 5 

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
    time.sleep(0.5) 
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

# --- 4. STAGE 2: POST SCRAPER (JSON API - TOPIC STREAM) ---

def html_to_clean_markdown(html_content: str) -> str:
    """Converts Discourse cooked HTML to clean Markdown with preserved paragraphs and lists."""
    if not html_content:
        return ""
    soup = BeautifulSoup(html_content, 'html.parser')
    for br in soup.find_all('br'):
        br.replace_with('\n')
    for li in soup.find_all('li'):
        li.insert_before('\n- ')
    for p in soup.find_all('p'):
        p.insert_before('\n\n')
    for bq in soup.find_all('blockquote'):
        bq.insert_before('\n\n> ')
    for h in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
        for tag in soup.find_all(h):
            tag.insert_before('\n\n### ')
    text = soup.get_text()
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()

def scrape_discourse_posts(thread_list: List[Dict[str, str]]) -> int:
    """Scrapes ALL true posts for each thread using the /t/{topic_id}.json endpoint."""
    total_posts_extracted = 0
    
    logger.critical(f"Starting post extraction for {len(thread_list)} Discourse threads...")
    
    with open(DISCOURSE_OUTPUT_FILE, 'w', encoding='utf-8') as f_out: 
        logger.info(f"Cleared existing data in {DISCOURSE_OUTPUT_FILE} for fresh post run.")
        
        for i, thread in enumerate(thread_list):
            thread_id = thread["thread_id"]
            thread_title = thread["title"]
            
            thread_api_url = f"{DISCOURSE_BASE_URL}/t/{thread_id}.json"
            logger.info(f"[{i+1}/{len(thread_list)}] Fetching ALL POSTS for: {thread_title} (ID: {thread_id})...")

            thread_data = fetch_json(thread_api_url)
            if not thread_data:
                logger.warning(f"Failed to retrieve topic data for thread ID {thread_id}. Skipping.")
                continue

            post_stream = thread_data.get('post_stream', {})
            posts_to_process = list(post_stream.get('posts', []))
            stream_ids = post_stream.get('stream', [])

            # Handle pagination if topic has more posts than initial page (usually > 20)
            if len(stream_ids) > len(posts_to_process):
                already_fetched_ids = {p.get('id') for p in posts_to_process}
                remaining_ids = [pid for pid in stream_ids if pid not in already_fetched_ids]
                
                chunk_size = 50
                for c_idx in range(0, len(remaining_ids), chunk_size):
                    chunk = remaining_ids[c_idx:c_idx + chunk_size]
                    more_url = f"{DISCOURSE_BASE_URL}/t/{thread_id}/posts.json"
                    params = [('post_ids[]', pid) for pid in chunk]
                    time.sleep(REQUEST_DELAY_SECONDS)
                    try:
                        resp = requests.get(more_url, params=params, timeout=30)
                        if resp.status_code == 200:
                            more_posts = resp.json().get('post_stream', {}).get('posts', [])
                            posts_to_process.extend(more_posts)
                    except Exception as err:
                        logger.warning(f"Error fetching remaining posts for thread {thread_id}: {err}")

            if not posts_to_process:
                logger.warning(f"No posts found for thread ID {thread_id}. Skipping.")
                continue

            logger.info(f"  -> Extracted {len(posts_to_process)} true posts for '{thread_title}'")

            for post_num, post in enumerate(posts_to_process):
                content_html = post.get('cooked', '')
                content = html_to_clean_markdown(content_html)
                
                timestamp_raw = post.get('created_at', 'N/A')
                username = post.get('username', 'Unknown User')
                post_number = post.get('post_number', post_num + 1)
                
                specific_post_url = f"{thread['permalink']}/{post_number}"

                record = {
                    "timestamp": timestamp_raw,
                    "source_type": "Discourse-Post",
                    "source_id": specific_post_url,
                    "username": username,
                    "user_id": str(post.get('user_id', 'N/A')), 
                    "content": content
                }

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
        
        if os.path.exists(DISCOURSE_THREADS_FILE):
            logger.info(f"Loading existing thread list from {DISCOURSE_THREADS_FILE}")
            with open(DISCOURSE_THREADS_FILE, 'r', encoding='utf-8') as f:
                threads_to_scrape = json.load(f)
        else:
            threads_to_scrape = fetch_discourse_thread_links() 
        
        if threads_to_scrape:
            scrape_discourse_posts(threads_to_scrape)
        else:
            logger.warning("No Discourse Mafia threads found. Skipping post scraping.")
        
    except KeyboardInterrupt:
        logger.critical("Extraction manually stopped.")
    except Exception as e:
        logger.critical(f"Main execution failed: {e}", exc_info=True)