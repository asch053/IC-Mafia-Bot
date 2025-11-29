import requests
from bs4 import BeautifulSoup
import json
import time
import logging
import os
import math 
from typing import List, Dict, Any
# --- CRITICAL FIX: Add urljoin to imports ---
from urllib.parse import urlparse, parse_qs, urlunparse, urlencode, urljoin
from requests.exceptions import HTTPError, RequestException 

# --- 1. CONFIGURATION AND SETUP ---

# --- FIX: Ensure paths are relative to the script's actual directory ---
CURRENT_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(CURRENT_SCRIPT_DIR, "logs")
OUTPUT_DIR = os.path.join(CURRENT_SCRIPT_DIR, "output")
OUTPUT_FILE_NAME = "extracted_history.jsonl"
OUTPUT_FILE_PATH = os.path.join(OUTPUT_DIR, OUTPUT_FILE_NAME)
THREAD_LIST_FILE = os.path.join(OUTPUT_DIR, "mafia_threads.json")

# Forum Configuration 
FORUM_BASE_URL = "https://imperialconflict.com/forum/viewforum.php?id=185" 
THREADS_PER_PAGE = 30 
# NOTE: Set this to 1 for quick testing, 82 for the full run!
TOTAL_PAGES = 82
POSTS_PER_THREAD_PAGE = 25 

HEADERS = {
    'User-Agent': 'MafiaBotHistoryHarvester/1.0 (Contact: your_email@example.com)'
}
REQUEST_DELAY_SECONDS = 3 
SERVER_ERROR_BACKOFF = 10 

logger = logging.getLogger('ForumExtractor') 

# --- 2. UTILITY FUNCTIONS ---

def setup_directories():
    """Creates the necessary log and output directories if they don't exist."""
    os.makedirs(LOG_DIR, exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    logger.info(f"Ensured log directory exists: {LOG_DIR}")
    logger.info(f"Ensured output directory exists: {OUTPUT_DIR}")

def setup_logging():
    """Configures logging to output to a file within the designated log folder."""
    setup_directories() 
    log_file_path = os.path.join(LOG_DIR, 'forum_extractor.log')
    logger.setLevel(logging.INFO)
    file_handler = logging.FileHandler(filename=log_file_path, encoding='utf-8')
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.INFO)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO) 
    if not logger.handlers:
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
    return logger

def generate_pagination_urls(base_url: str, total_pages: int) -> List[str]:
    """Generates a list of all index page URLs using the '&p=' parameter."""
    urls = []
    parsed_url = urlparse(base_url)
    base_query = parse_qs(parsed_url.query)
    
    for page_num in range(1, total_pages + 1):
        new_query = base_query.copy()
        if page_num > 1:
            new_query['p'] = [str(page_num)]
            
        new_url = urlunparse(parsed_url._replace(query=urlencode(new_query, doseq=True)))
        urls.append(new_url)
    return urls

def get_thread_pages(base_thread_url: str, total_posts: int, posts_per_page: int) -> List[str]:
    """Generates all page URLs for a single thread, using '&p=' pagination."""
    if total_posts <= posts_per_page:
        return [base_thread_url]
    
    num_pages = math.ceil(total_posts / posts_per_page)
    urls = []
    parsed_url = urlparse(base_thread_url)
    base_query = parse_qs(parsed_url.query)
    
    for page_num in range(1, num_pages + 1):
        new_query = base_query.copy()
        if page_num > 1:
            new_query['p'] = [str(page_num)] 
            
        new_url = urlunparse(parsed_url._replace(query=urlencode(new_query, doseq=True)))
        urls.append(new_url)
    return urls


# --- 3. STAGE 1: THREAD LIST HARVESTER (URL FIX APPLIED) ---

def fetch_and_parse_thread_links() -> List[Dict[str, str]]:
    
    logger.info(f"Generating URLs for {TOTAL_PAGES} pages...")
    pagination_urls = generate_pagination_urls(FORUM_BASE_URL, TOTAL_PAGES)
    
    all_thread_links = {} 
    
    # Get the base URL part for clean joining (e.g., https://imperialconflict.com/forum/)
    # This ensures we get the base path correctly for relative links.
    base_url_for_join = FORUM_BASE_URL.split('viewforum.php')[0]
    
    for i, page_url in enumerate(pagination_urls):
        page_num = i + 1
        logger.info(f"[{page_num}/{TOTAL_PAGES}] Fetching thread index: {page_url}")
        time.sleep(REQUEST_DELAY_SECONDS) 
        
        try:
            response = requests.get(page_url, headers=HEADERS)
            response.raise_for_status() 
        except RequestException as e:
            logger.error(f"Failed to load page {page_num}: {e}")
            continue

        soup = BeautifulSoup(response.text, 'html.parser')
        
        for thread_item in soup.select('#forum185 div.main-item'):
            
            link_tag = thread_item.select_one('h3.hn a') 
            replies_tag = thread_item.select_one('li.info-replies strong')
            
            if link_tag and replies_tag:
                thread_title = link_tag.get_text(strip=True)
                thread_path = link_tag.get('href')
                
                total_replies_str = replies_tag.get_text(strip=True)
                total_replies = int(total_replies_str) if total_replies_str.isdigit() else 0
                total_posts = total_replies + 1
                
                if thread_path and thread_title and 'mafia' in thread_title.lower():
                    
                    # *** CRITICAL FIX APPLIED: Use urljoin for safe link reconstruction ***
                    # urljoin correctly handles combining base_url_for_join (base domain) 
                    # and thread_path (relative path) without duplication.
                    permalink = urljoin(base_url_for_join, thread_path)
                    
                    query_params = parse_qs(urlparse(thread_path).query)
                    thread_id = query_params.get('id', [''])[0] 
                    
                    if thread_id:
                        all_thread_links[thread_id] = {
                            "title": thread_title,
                            "permalink": permalink,
                            "thread_id": thread_id,
                            "total_posts": total_posts 
                        }

    final_thread_list = list(all_thread_links.values())
    
    with open(THREAD_LIST_FILE, 'w', encoding='utf-8') as f:
        json.dump(final_thread_list, f, indent=4)

    logger.critical(f"Found {len(final_thread_list)} unique Mafia threads across {TOTAL_PAGES} pages.")
    logger.critical(f"Thread links saved to: {THREAD_LIST_FILE}")
    
    return final_thread_list

# --- 4. STAGE 2: POST SCRAPER ---

def scrape_thread_posts(thread_list: List[Dict[str, str]]) -> int:
    
    total_posts_extracted = 0
    
    logger.critical(f"Starting post extraction for {len(thread_list)} threads...")
    
    with open(OUTPUT_FILE_PATH, 'w', encoding='utf-8') as f_out: 
        logger.info(f"Cleared existing data in {OUTPUT_FILE_PATH} for fresh post run.")
        
        for i, thread in enumerate(thread_list):
            thread_url = thread["permalink"]
            thread_title = thread["title"]
            total_posts = thread["total_posts"]

            page_urls = get_thread_pages(thread_url, total_posts, POSTS_PER_THREAD_PAGE)
            
            logger.info(f"[{i+1}/{len(thread_list)}] Scraping: {thread_title} ({total_posts} posts across {len(page_urls)} pages)")
            
            for page_url in page_urls:
                time.sleep(REQUEST_DELAY_SECONDS) 
                
                try:
                    response = requests.get(page_url, headers=HEADERS)
                    response.raise_for_status() 
                    thread_soup = BeautifulSoup(response.text, 'html.parser')
                    
                    # CONFIRMED SELECTOR: Post Container
                    posts = thread_soup.select('div.main-content.main-topic div.post') 
                    
                    if not posts:
                        logger.warning(f"No posts found in {page_url}. Skipping page.")
                        continue
                    
                    for post in posts:
                        # CONFIRMED SELECTOR: Timestamp
                        timestamp_tag = post.select_one('h3.post-ident a.permalink')
                        timestamp_raw = timestamp_tag.get_text(strip=True) if timestamp_tag else "N/A"
                        
                        # CONFIRMED SELECTOR: Username
                        username_tag = post.select_one('.post-author .username a')
                        username = username_tag.get_text(strip=True) if username_tag else "Unknown User"

                        # CONFIRMED SELECTOR: Content
                        content_tag = post.select_one('.post-entry .entry-content')
                        content = " ".join(content_tag.get_text(strip=True).split()) if content_tag else "No Content"

                        record = {
                            "timestamp": timestamp_raw,
                            "source_type": "Forum-Post",
                            "source_id": page_url, 
                            "username": username,
                            "user_id": "N/A", 
                            "content": content
                        }
                        
                        f_out.write(json.dumps(record, ensure_ascii=False) + '\n')
                        total_posts_extracted += 1
                        
                except HTTPError as e:
                    if e.response.status_code >= 500:
                        logger.error(f"Server Overload Detected ({e.response.status_code}) on {page_url}. Backing off.")
                        time.sleep(SERVER_ERROR_BACKOFF) 
                    else:
                        logger.warning(f"Client Error ({e.response.status_code}) on {page_url}. Skipping page.")
                        
                except RequestException as e:
                    logger.critical(f"Network Failure on {page_url}: {e}. Skipping page.")

                except Exception as e:
                    logger.critical(f"An unexpected error occurred during processing: {e}", exc_info=True)

    logger.critical(f"----- POST EXTRACTION COMPLETE -----")
    logger.critical(f"TOTAL POSTS WRITTEN: {total_posts_extracted}")
    return total_posts_extracted


# --- 5. MAIN EXECUTION ---
if __name__ == "__main__":
    logger = setup_logging()
    
    try:
        logger.info(f"Starting Mafia History Extractor pipeline...")
        
        # NOTE: Set TOTAL_PAGES = 1 in the configuration block above for a quick test!
        threads_to_scrape = fetch_and_parse_thread_links() 
        
        if threads_to_scrape:
            scrape_thread_posts(threads_to_scrape)
        else:
            logger.warning("No Mafia threads found. Skipping post scraping.")
        
    except KeyboardInterrupt:
        logger.critical("Extraction manually stopped.")
    except Exception as e:
        logger.critical(f"Main execution failed: {e}", exc_info=True)