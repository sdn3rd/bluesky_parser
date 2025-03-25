# Bluesky Poetry Processor

A Python script for fetching poems from Bluesky, processing them with OpenAI, and outputting them to JSON.

## Features

- Fetch posts from a Bluesky account (newest first)
- Process poems with OpenAI for:
  - Grammar correction
  - Title generation
  - Translation to another language
  - Automatic tagging
- Output to a single JSON file
- Configurable via command-line arguments and top-level settings

## Installation

### Requirements

- Python 3.6+
- OpenAI API key (for AI processing)
- Bluesky account with app password

### Dependencies

```bash
pip install openai requests
```

### Setup

1. Clone this repository:
   ```bash
   git clone https://github.com/yourusername/bluesky-poetry-processor.git
   cd bluesky-poetry-processor
   ```

2. Configure your credentials at the top of the script or via command-line arguments.

## Configuration

Edit the top of the script to configure default behavior:

```python
# Feature flags - set these to control which features are enabled
ENABLE_TITLE_GENERATION = True  # Set to False to disable title generation
ENABLE_TRANSLATION = True       # Set to False to disable translation
ENABLE_TAGGING = True           # Set to False to disable AI tagging

# Translation language setting
TRANSLATION_LANGUAGE = "Italian"  # Change this to any language you want

# Hardcoded credentials – if non-empty, these override CLI values:
BLUESKY_USERNAME = None
BLUESKY_APP_PASSWORD = None
HARDCODED_API_KEY = None  # OpenAI API key

# Predefined list of tags for AI to select from
TAG_OPTIONS = [
    "vss", "shortform", "micropoem", "monoku", "haiku", "longform",
    "sad", "happy", "whimsical", "fun", "rhyme", "dark",
    "tender", "loving", "longing", "melancholy", "passionate"
]
```

## Usage

### Basic Usage

```bash
# Fetch today's posts from Bluesky and process with OpenAI
python bluesky_poem_parser.py --bluesky-user your_username --bluesky-password your_app_password --api-key your_openai_key
```

### Command Line Arguments

| Argument | Description |
|----------|-------------|
| `--input FILE` | Input JSON file path (default: poems.json) |
| `--output FILE` | Output processed JSON file (default: processed_poems.json) |
| `--raw-output FILE` | Raw output JSON file when using --no-openai (default: raw_posts.json) |
| `--api-key KEY` | OpenAI API key (overrides hardcoded key) |
| `--days N` | Number of days to process (default: 1) |
| `--all` | Ignore date filters and process everything |
| `--no-openai` | Skip OpenAI processing and just output raw Bluesky posts |
| `--bluesky-user USER` | Bluesky username |
| `--bluesky-password PASS` | Bluesky app password |
| `--no-fetch` | Don't fetch posts even if input file is missing |
| `--count N` | Maximum number of posts to fetch (default: all posts from today) |
| `--limit N` | Per-page limit for Bluesky fetch (default: 100) |
| `--start-date DATE` | Only process posts on or after this date (YYYY-MM-DD) |
| `--end-date DATE` | Only process posts on or before this date (YYYY-MM-DD) |
| `--disable-title` | Disable title generation |
| `--disable-translation` | Disable translation |
| `--disable-tagging` | Disable AI tagging |
| `--language LANG` | Translation language (default: Italian) |

### Example Usages

#### Fetch Today's Posts Only

```bash
python bluesky_poem_parser.py
```

#### Fetch Last 7 Days of Posts 

```bash
python bluesky_poem_parser.py --days 7
```

#### Fetch Posts Within a Date Range

```bash
python bluesky_poem_parser.py --start-date 2024-03-01 --end-date 2024-03-31
```

#### Fetch Posts Without OpenAI Processing

```bash
python bluesky_poem_parser.py --no-openai
```

#### Fetch Posts and Translate to Spanish

```bash
python bluesky_poem_parser.py --language Spanish
```

#### Only Generate Titles, No Translation or Tagging

```bash
python bluesky_poem_parser.py --disable-translation --disable-tagging
```

#### Fetch a Specific Number of Posts (Newest First)

```bash
python bluesky_poem_parser.py --count 10
```

#### Process Already Fetched Posts from Input File

```bash
python bluesky_poem_parser.py --no-fetch --input my_posts.json --output processed.json
```

## Output Format

The script produces a JSON file with this structure:

```json
[
  {
    "content": "Original Bluesky post content",
    "published_at": "2024-03-25T12:34:56Z",
    "tags": "original post tags",
    "uri": "at://...",
    "cid": "...",
    "poem_en": "Grammar-corrected poem text",
    "title_en": "Generated or Corrected Title",
    "title_italian": "Translated Title",
    "poem_italian": "Translated Poem",
    "tags": ["sad", "melancholy", "longing"],
    "category": "Uncategorized"
  },
  // Additional processed poems...
]
```

Note: If you change the translation language using `--language` or `TRANSLATION_LANGUAGE`, 
the JSON will have fields like `title_spanish` and `poem_spanish` instead.

## Customizing Tag Options

To customize the available tags for AI tagging, edit the `TAG_OPTIONS` list at the top of the script.

## Logging

The script generates detailed logs in the `~/logs` directory. The log file path is shown at the end of each run.

## License

[BSD 3-Clause License](LICENSE)