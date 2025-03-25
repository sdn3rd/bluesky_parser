#!/usr/bin/env python3
import json
import os
import openai
import argparse
import re
import time
import datetime
import logging
from typing import Dict, List, Any, Optional

# ------------------ Static Config ------------------
# Feature flags - set these to control which features are enabled
ENABLE_TITLE_GENERATION = True  # Set to False to disable title generation
ENABLE_TRANSLATION = True       # Set to False to disable translation
ENABLE_TAGGING = True           # Set to False to disable AI tagging

# Translation language setting
TRANSLATION_LANGUAGE = "Italian"  # Change this to any language you want (e.g., "Spanish", "French", "Japanese", etc.)

# Hardcoded credentials – if non-empty, these override CLI values:
BLUESKY_USERNAME = None
BLUESKY_APP_PASSWORD = None
HARDCODED_API_KEY = None

# Predefined list of tags for AI to select from
TAG_OPTIONS = [
    "vss", "shortform", "micropoem", "monoku", "haiku", "longform",
    "sad", "happy", "whimsical", "fun", "rhyme", "dark",
    "tender", "loving", "longing", "melancholy", "passionate"
]

# Setup logging to a file (not console)
log_dir = os.path.expanduser("~/logs")
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(
    log_dir, f"poetry_processor_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    filename=log_file,
    filemode="w"
)

def parse_arguments():
    parser = argparse.ArgumentParser(description="Process Bluesky posts (poems) and output to a single JSON file")
    parser.add_argument("--input", default="poems.json", help="Input JSON file path (default: poems.json)")
    parser.add_argument("--output", default="processed_poems.json", help="Output JSON file (default: processed_poems.json)")
    parser.add_argument("--raw-output", default="raw_posts.json", help="Raw output JSON file when using --no-openai (default: raw_posts.json)")
    parser.add_argument("--api-key", help="OpenAI API key (optional, overrides hardcoded key)")

    parser.add_argument("--days", type=int, default=1, help="Number of days to process if no start-date/end-date is given (default: 1)")
    parser.add_argument("--all", action="store_true", help="Ignore date filters and process everything")
    parser.add_argument("--no-openai", action="store_true", help="Skip OpenAI processing and just output raw Bluesky posts")

    # Bluesky
    parser.add_argument("--bluesky-user", help="Bluesky username (optional, overrides hardcoded username)")
    parser.add_argument("--bluesky-password", help="Bluesky app password (optional, overrides hardcoded password)")
    parser.add_argument("--no-fetch", dest="fetch", action="store_false", help="Don't fetch posts even if input file is missing")
    parser.set_defaults(fetch=True)  # Set fetch to True by default
    parser.add_argument("--count", type=int, default=None,
                        help="Maximum number of posts to fetch (default: None = all posts from today)")
    parser.add_argument("--limit", type=int, default=100,
                        help="Per-page limit for Bluesky fetch (default=100). We'll keep paginating until count or date limit is reached.")
    
    # Date range
    parser.add_argument("--start-date", help="Only process posts on or after this date (YYYY-MM-DD)")
    parser.add_argument("--end-date", help="Only process posts on or before this date (YYYY-MM-DD)")
    
    # Feature flags via CLI
    parser.add_argument("--disable-title", action="store_true", help="Disable title generation")
    parser.add_argument("--disable-translation", action="store_true", help="Disable translation")
    parser.add_argument("--disable-tagging", action="store_true", help="Disable AI tagging")
    parser.add_argument("--language", default=None, help=f"Translation language (default: {TRANSLATION_LANGUAGE})")

    return parser.parse_args()
    
    # Date range
    parser.add_argument("--start-date", help="Only process posts on or after this date (YYYY-MM-DD)")
    parser.add_argument("--end-date", help="Only process posts on or before this date (YYYY-MM-DD)")

    # Feature flags via CLI
    parser.add_argument("--disable-title", action="store_true", help="Disable title generation")
    parser.add_argument("--disable-translation", action="store_true", help="Disable translation to Italian")
    parser.add_argument("--disable-tagging", action="store_true", help="Disable AI tagging")

    return parser.parse_args()

def load_json_file(filepath: str, default_value=None) -> Any:
    if not os.path.exists(filepath):
        msg = f"STEP: [LOAD] File not found: {filepath}"
        print(msg)
        logging.warning(msg)
        return default_value
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        msg = f"STEP: [LOAD] JSON decode error in {filepath}: {e}"
        print(msg)
        logging.error(msg)
        return default_value
    except Exception as e:
        msg = f"STEP: [LOAD] Error loading {filepath}: {e}"
        print(msg)
        logging.error(msg)
        return default_value

def clean_hashtags_from_text(text: str) -> str:
    return re.sub(r'#(\w+)', r'\1', text)

def extract_date_str_as_dt(date_str: str) -> Optional[datetime.datetime]:
    if not date_str:
        return None
    try:
        if date_str.endswith('Z'):
            date_str = date_str[:-1] + '+00:00'
        dt = datetime.datetime.fromisoformat(date_str)
        return dt.replace(tzinfo=None)
    except Exception:
        return None

def get_openai_client_version() -> int:
    try:
        if hasattr(openai, 'ChatCompletion'):
            return 0
        elif hasattr(openai, 'OpenAI'):
            return 1
        else:
            return -1
    except Exception:
        return -1

def log_and_call_openai(api_key: str, model: str, system_prompt: str, user_prompt: str,
                        context: str, retry_count: int = 0) -> Optional[str]:
    """Common helper that logs what we're calling the AI for, then calls it."""
    msg = f"STEP: [OpenAI] {context} => calling model={model}"
    print(msg)
    logging.info(msg)

    openai.api_key = api_key
    try:
        openai_version = get_openai_client_version()
        if openai_version == 1:
            client = openai.OpenAI(api_key=api_key)
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ]
            )
            result = response.choices[0].message.content
        else:
            response = openai.ChatCompletion.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ]
            )
            result = response['choices'][0]['message']['content']

        if "i'm sorry" in result.lower() and retry_count < 3:
            msg2 = f"STEP: [OpenAI] 'I'm sorry' => retry attempt={retry_count + 1}"
            print(msg2)
            logging.warning(msg2)
            time.sleep(2)
            return log_and_call_openai(api_key, model, system_prompt, user_prompt, context, retry_count + 1)
        return result.strip()
    except Exception as e:
        msg3 = f"STEP: [OpenAI] Error during {context}: {e}"
        print(msg3)
        logging.error(msg3)
        if retry_count < 3:
            msg4 = f"STEP: [OpenAI] Retrying {context}, attempt={retry_count + 1}"
            print(msg4)
            logging.warning(msg4)
            time.sleep(2 * (retry_count + 1))
            return log_and_call_openai(api_key, model, system_prompt, user_prompt, context, retry_count + 1)
        return None

def call_openai_fix_grammar(text: str, api_key: str) -> str:
    """Grammar fix for ANY text, by AI."""
    system_prompt = (
        "You are a helpful assistant that corrects capitalization and punctuation in English text. "
        "Do not change the words, only fix the grammar."
    )
    result = log_and_call_openai(api_key, "gpt-3.5-turbo", system_prompt, text, context="Grammar Fix")
    return result if result else text

def call_openai_generate_title(poem_text: str, api_key: str) -> str:
    system_prompt = "You are a creative poetry title generator. Create simple, clever, and memorable titles for poems."
    user_prompt = (
        "Create a short, engaging title for this poem. The title should:\n"
        "1. Be concise (1-5 words)\n"
        "2. Use alliteration if possible\n"
        "3. Capture the essence or main emotion\n"
        "4. Not use hashtags or special characters\n\n"
        f"Poem:\n{poem_text}\n\n"
        "Return ONLY the title, nothing else."
    )
    result = log_and_call_openai(api_key, "gpt-3.5-turbo", system_prompt, user_prompt, context="Title Generation")
    if result:
        cleaned_title = re.sub(r'[^\w\s]', '', result).strip()
        return cleaned_title
    return "Untitled Poem"

def call_openai_translation(text: str, target_language: str, api_key: str, is_title: bool = False) -> str:
    """Translate text to target_language. If is_title=True, we do a direct short translation prompt."""
    if is_title:
        system_prompt = f"You are a highly skilled translator of English text to {target_language}."
        user_prompt = (
            f"Directly translate this English poetry title to {target_language} and return ONLY the translation, "
            f"nothing else. No quotes, explanations, or arrows. Title: '{text}'"
        )
        context = f"Title Translation => {target_language}"
    else:
        system_prompt = f"You are a highly skilled translator of English poetry to {target_language}."
        user_prompt = (
            f"Translate thoughtfully, considering the poem's context, style, and intention. "
            f"Capture the essence and feeling of the poem. Source:\n{text}"
        )
        context = f"Poem Translation => {target_language}"

    result = log_and_call_openai(api_key, "gpt-3.5-turbo", system_prompt, user_prompt, context=context)
    if result:
        return result.strip('"').strip("'")
    return "tbd"

def call_openai_tagging(text: str, api_key: str, tag_options: List[str]) -> List[str]:
    """Call AI to pick up to 5 relevant tags from tag_options for the text."""
    system_prompt = (
        "You are an expert in poetry analysis. Analyze the following poem and select up to 5 tags "
        f"that best describe it from this list: {', '.join(tag_options)}. "
        "Provide only the tags as a comma-separated list, in lowercase."
    )
    result = log_and_call_openai(api_key, "gpt-3.5-turbo", system_prompt, text, context="Tagging")
    if result:
        raw_tags = [tag.strip().lower() for tag in result.split(',')][:5]
        validated = [t for t in raw_tags if t in tag_options]
        return validated
    return []

def apply_title_case(title: str) -> str:
    """Simple Title Casing."""
    return ' '.join(word.capitalize() for word in title.split())

def process_post_through_ai(post_data: Dict, api_key: str, enable_title: bool, 
                           enable_translation: bool, enable_tagging: bool, translation_language: str = TRANSLATION_LANGUAGE) -> Optional[Dict]:
    """
    Process a post with AI features based on enabled flags.
    """
    logging.info("STEP: [Process] Starting AI processing of one post...")

    # 1. Gather content
    if 'content' not in post_data or not post_data['content'].strip():
        print("STEP: [Process] Post has no content => skipping.")
        return None

    # Grammar fix for content
    content_clean = clean_hashtags_from_text(post_data['content'])
    content_fixed = call_openai_fix_grammar(content_clean, api_key)
    post_data['poem_en'] = content_fixed  # store under 'poem_en' for consistency

    # 2. Title (if enabled)
    if enable_title:
        existing_title = post_data.get('title_en') or post_data.get('title')
        if existing_title:
            # fix grammar of existing
            tfix = call_openai_fix_grammar(clean_hashtags_from_text(existing_title), api_key)
            post_data['title_en'] = apply_title_case(tfix)
        else:
            # generate from content
            new_title = call_openai_generate_title(content_fixed, api_key)
            post_data['title_en'] = apply_title_case(new_title)
    else:
        # Just clean any existing title or use a placeholder
        existing_title = post_data.get('title_en') or post_data.get('title')
        if existing_title:
            post_data['title_en'] = apply_title_case(clean_hashtags_from_text(existing_title))
        else:
            post_data['title_en'] = "Untitled Poem"

    # 3. Translation (if enabled)
    if enable_translation:
        lang_key = translation_language.lower()
        
        # Translate title
        title_translated = call_openai_translation(post_data['title_en'], translation_language, api_key, is_title=True)
        post_data[f'title_{lang_key}'] = apply_title_case(title_translated) if title_translated else "tbd"

        # Translate poem
        poem_translated = call_openai_translation(post_data['poem_en'], translation_language, api_key)
        post_data[f'poem_{lang_key}'] = poem_translated if poem_translated else "tbd"

    # 4. Tag with AI (if enabled)
    if enable_tagging:
        post_data['tags'] = call_openai_tagging(post_data['poem_en'], api_key, TAG_OPTIONS)
    else:
        post_data['tags'] = []

    # 5. Category (just set to 'Uncategorized')
    if 'category' not in post_data:
        post_data['category'] = "Uncategorized"

    return post_data

def fetch_bluesky_posts(username: str,
                        app_password: str,
                        per_page_limit: int = 100,
                        max_count: Optional[int] = None,
                        start_date_str: Optional[str] = None) -> List[Dict]:
    """
    Fetch posts from Bluesky with smart pagination:
    - If max_count is specified, fetch only that many posts (newest first)
    - If start_date is specified, fetch posts from that date onwards
    - By default, fetch today's posts only
    """
    import requests

    # Set default start_date to today if not specified
    if not start_date_str:
        start_date_str = datetime.datetime.now().strftime("%Y-%m-%d")
        print(f"STEP: [Fetch] No start date specified, defaulting to today: {start_date_str}")

    # Parse the start date and set to midnight (00:00:00)
    try:
        start_dt = datetime.datetime.strptime(start_date_str, "%Y-%m-%d")
        start_dt = start_dt.replace(hour=0, minute=0, second=0, microsecond=0)
        print(f"STEP: [Fetch] Using start date: {start_dt}")
    except ValueError:
        print(f"STEP: [Fetch] Invalid start date format: {start_date_str}, using today")
        start_dt = datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    msg = f"STEP: [Fetch] Pagination with limit={per_page_limit}, max_count={max_count if max_count else 'unlimited'}, since={start_dt.strftime('%Y-%m-%d')}"
    print(msg)
    logging.info(msg)

    # 1) authenticate
    auth_url = "https://bsky.social/xrpc/com.atproto.server.createSession"
    auth_data = {"identifier": username, "password": app_password}
    try:
        auth_response = requests.post(auth_url, json=auth_data)
        auth_response.raise_for_status()
        auth_json = auth_response.json()
        access_token = auth_json.get("accessJwt")
        did = auth_json.get("did")
        if not access_token or not did:
            print("STEP: [Fetch] Failed to authenticate with Bluesky. Invalid response.")
            return []
    except Exception as e:
        print(f"STEP: [Fetch] Error authenticating: {e}")
        return []

    headers = {"Authorization": f"Bearer {access_token}"}
    base_url = "https://bsky.social/xrpc/app.bsky.feed.getAuthorFeed"

    all_posts: List[Dict] = []
    next_cursor: Optional[str] = None

    while True:
        limit = min(per_page_limit, 100)
        params = {"actor": did, "limit": limit}
        if next_cursor:
            params["cursor"] = next_cursor

        try:
            r = requests.get(base_url, headers=headers, params=params)
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            print(f"STEP: [Fetch] Page fetch error: {e}")
            break

        feed_items = data.get("feed", [])
        if not feed_items:
            print("STEP: [Fetch] No feed items => done.")
            break

        # Process this page's posts
        oldest_dt_in_page = None
        page_posts: List[Dict] = []
        for item in feed_items:
            post = item.get("post", {})
            record = post.get("record", {})
            dt_str = record.get("createdAt", "")
            dt_obj = extract_date_str_as_dt(dt_str)
            
            # Track the oldest date in this page
            if dt_obj and (not oldest_dt_in_page or dt_obj < oldest_dt_in_page):
                oldest_dt_in_page = dt_obj
                
            # Check if post is from start_dt or later
            if dt_obj and dt_obj.date() >= start_dt.date():
                page_posts.append({
                    "content": record.get("text", ""),
                    "published_at": dt_str,
                    "tags": " ".join(record.get("tags", [])),
                    "uri": post.get("uri", ""),
                    "cid": post.get("cid", "")
                })

        # Add posts from this page
        all_posts.extend(page_posts)
        print(f"STEP: [Fetch] Kept {len(page_posts)} posts from this page. Total so far={len(all_posts)}.")
        
        # Check if we should stop pagination
        if max_count and len(all_posts) >= max_count:
            print(f"STEP: [Fetch] Reached max count ({max_count}) => stopping pagination")
            all_posts = all_posts[:max_count]  # Trim to exact count
            break
            
        # Stop if oldest post on this page is before our start date
        if oldest_dt_in_page and oldest_dt_in_page.date() < start_dt.date():
            print(f"STEP: [Fetch] Reached posts older than start date ({start_dt.date()}) => stopping pagination")
            break
            
        # Stop if no next cursor
        next_cursor = data.get("cursor")
        if not next_cursor:
            print("STEP: [Fetch] No next cursor => done.")
            break

    print(f"STEP: [Fetch] Pagination done. We collected {len(all_posts)} total posts.")
    return all_posts

def final_date_filter(posts: List[Dict],
                      days: int,
                      start_date_str: Optional[str] = None,
                      end_date_str: Optional[str] = None) -> List[Dict]:
    """
    Final filter for any leftover or for end-date. Also handles --days if user didn't set start_date.
    If user has --all, we'll skip calling this.
    """
    start_dt = None
    end_dt = None

    if start_date_str:
        try:
            start_dt = datetime.datetime.strptime(start_date_str, "%Y-%m-%d")
        except ValueError:
            pass
    if end_date_str:
        try:
            end_dt = datetime.datetime.strptime(end_date_str, "%Y-%m-%d")
        except ValueError:
            pass

    kept = []

    if start_dt or end_dt:
        print(f"STEP: [Filter] Doing final range filter. start={start_dt}, end={end_dt}")
        for p in posts:
            dt = extract_date_str_as_dt(p.get('published_at',''))
            if not dt:
                continue  # skip no date
            if start_dt and dt < start_dt:
                continue
            if end_dt and dt > end_dt:
                continue
            kept.append(p)
        print(f"STEP: [Filter] Final range => kept={len(kept)} / {len(posts)}.")
        return kept
    else:
        # fallback to days
        if days < 1 or days > 9999:
            return posts
        cutoff = datetime.datetime.now() - datetime.timedelta(days=days)
        for p in posts:
            dt = extract_date_str_as_dt(p.get('published_at',''))
            if dt and dt >= cutoff:
                kept.append(p)
            elif not dt:
                # keep if no date?
                kept.append(p)
        print(f"STEP: [Filter] Days={days} => kept={len(kept)} / {len(posts)}.")
        return kept

def main():
    args = parse_arguments()

    print(f"\n{'='*50}")
    print(f"POETRY PROCESSING STARTED - {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*50}")
    logging.info("STEP: [Main] Starting Poetry Processing.")

    # 1) Credentials
    api_key = HARDCODED_API_KEY.strip() if HARDCODED_API_KEY and HARDCODED_API_KEY.strip() else None
    if args.api_key:
        api_key = args.api_key
    if not api_key and not args.no_openai:
        env_key = os.environ.get("OPENAI_API_KEY", "").strip()
        if env_key:
            api_key = env_key
        else:
            print("WARNING: No OpenAI API key provided. If you want to process with OpenAI, provide an API key.")
            print("Using --no-openai mode automatically.")
            args.no_openai = True

    bs_user = BLUESKY_USERNAME.strip() if BLUESKY_USERNAME and BLUESKY_USERNAME.strip() else ""
    bs_pass = BLUESKY_APP_PASSWORD.strip() if BLUESKY_APP_PASSWORD and BLUESKY_APP_PASSWORD.strip() else ""
    if args.bluesky_user:
        bs_user = args.bluesky_user
    if args.bluesky_password:
        bs_pass = args.bluesky_password

    # Check for feature flag overrides from command line
    enable_title = ENABLE_TITLE_GENERATION and not args.disable_title
    enable_translation = ENABLE_TRANSLATION and not args.disable_translation
    enable_tagging = ENABLE_TAGGING and not args.disable_tagging
    
    # Get translation language - CLI overrides the variable at the top of the script
    translation_language = args.language if args.language else TRANSLATION_LANGUAGE

    # 2) Log config
    print(f"STEP: [Main] Input: {args.input}")
    print(f"STEP: [Main] Output: {args.output if not args.no_openai else args.raw_output}")
    print(f"STEP: [Main] Days filter: {args.days} (ignored if start/end date is given)")
    print(f"STEP: [Main] Start date: {args.start_date}, End date: {args.end_date}")
    print(f"STEP: [Main] Max posts: {args.count if args.count else 'No limit'}")
    print(f"STEP: [Main] All posts: {args.all}")
    print(f"STEP: [Main] OpenAI processing: {not args.no_openai}")
    if not args.no_openai:
        print(f"STEP: [Main] Features: Title={enable_title}, Translation={enable_translation}, Tagging={enable_tagging}")
        if enable_translation:
            print(f"STEP: [Main] Translation language: {translation_language}")

    # 3) Fetch or load - always try to fetch if input file doesn't exist
    should_fetch = args.fetch or not os.path.exists(args.input)
    
    if should_fetch:
        # Check if we have Bluesky credentials before trying to fetch
        if not bs_user or not bs_pass:
            print("ERROR: No Bluesky credentials provided for fetching. Set via BLUESKY_USERNAME and BLUESKY_APP_PASSWORD at the top of the script, or use --bluesky-user and --bluesky-password arguments.")
            return
            
        print(f"STEP: [Main] Fetching posts from Bluesky (limit={args.limit})...")
        posts = fetch_bluesky_posts(
            bs_user, 
            bs_pass, 
            per_page_limit=args.limit,
            max_count=args.count,
            start_date_str=args.start_date
        )
        if not posts:
            print("STEP: [Main] No posts fetched, exiting.")
            return
        
        # Save raw posts to input file
        try:
            with open(args.input, 'w', encoding='utf-8') as f:
                json.dump(posts, f, indent=4, ensure_ascii=False)
            print(f"STEP: [Fetch] Wrote raw posts to {args.input}")
        except Exception as e:
            print(f"STEP: [Fetch] Error writing to {args.input}: {e}")
    else:
        # Load from local file
        posts = load_json_file(args.input, [])
        if not posts:
            print("STEP: [Main] No data in input file => exit.")
            return

    if isinstance(posts, dict):
        posts = [posts]

    # 4) Skip OpenAI processing if requested
    if args.no_openai:
        output_file = args.raw_output
        print(f"STEP: [Main] Skipping OpenAI processing as requested, writing raw posts to {output_file}")
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(posts, f, indent=4, ensure_ascii=False)
            print(f"STEP: [Main] Successfully wrote raw posts to {output_file}")
        except Exception as e:
            print(f"STEP: [Main] Error writing to output file {output_file}: {e}")
            logging.error(f"Error writing to output file {output_file}: {e}")
        print(f"\n{'='*50}")
        print(f"POETRY PROCESSING COMPLETED - {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Log file: {log_file}")
        print(f"{'='*50}")
        return

    # 5) final date filter, unless --all
    if not args.all:
        posts = final_date_filter(posts, args.days, args.start_date, args.end_date)
        print(f"STEP: [Main] after final date filter => {len(posts)} post(s).")
    else:
        print("STEP: [Main] --all => skipping final date filter.")

    if not posts:
        print("STEP: [Main] 0 posts remain => no AI needed => exit.")
        return

    # 6) AI processing for grammar fix, translations, etc. for each post
    processed_posts = []
    processed_count = 0
    for post in posts:
        processed = process_post_through_ai(
            post, api_key, 
            enable_title=enable_title, 
            enable_translation=enable_translation, 
            enable_tagging=enable_tagging,
            translation_language=translation_language
        )
        if processed:
            processed_posts.append(processed)
            processed_count += 1

    print(f"STEP: [Main] Processed {processed_count}/{len(posts)} posts with AI steps.")

    # 7) Write all processed posts to a single JSON file
    try:
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(processed_posts, f, indent=4, ensure_ascii=False)
        print(f"STEP: [Main] Successfully wrote all processed poems to {args.output}")
    except Exception as e:
        print(f"STEP: [Main] Error writing to output file {args.output}: {e}")
        logging.error(f"Error writing to output file {args.output}: {e}")

    print(f"\n{'='*50}")
    print(f"POETRY PROCESSING COMPLETED - {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Log file: {log_file}")
    print(f"{'='*50}")

    if isinstance(posts, dict):
        posts = [posts]

    # 4) final date filter, unless --all
    if not args.all:
        posts = final_date_filter(posts, args.days, args.start_date, args.end_date)
        print(f"STEP: [Main] after final date filter => {len(posts)} post(s).")
    else:
        print("STEP: [Main] --all => skipping final date filter.")

    if not posts:
        print("STEP: [Main] 0 posts remain => no AI needed => exit.")
        return

    # 5) AI processing for grammar fix, translations, etc. for each post
    processed_posts = []
    processed_count = 0
    for post in posts:
        processed = process_post_through_ai(
            post, api_key, 
            enable_title=enable_title, 
            enable_translation=enable_translation, 
            enable_tagging=enable_tagging
        )
        if processed:
            processed_posts.append(processed)
            processed_count += 1

    print(f"STEP: [Main] Processed {processed_count}/{len(posts)} posts with AI steps.")

    # 6) Write all processed posts to a single JSON file
    try:
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(processed_posts, f, indent=4, ensure_ascii=False)
        print(f"STEP: [Main] Successfully wrote all processed poems to {args.output}")
    except Exception as e:
        print(f"STEP: [Main] Error writing to output file {args.output}: {e}")
        logging.error(f"Error writing to output file {args.output}: {e}")

    print(f"\n{'='*50}")
    print(f"POETRY PROCESSING COMPLETED - {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Log file: {log_file}")
    print(f"{'='*50}")

if __name__ == "__main__":
    main()