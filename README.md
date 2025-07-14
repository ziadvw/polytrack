# Polymarket Markets Scraper

A Python utility to fetch all markets from the Polymarket API with pagination and save them to timestamped JSON files.

## Features

- Fetches all markets from Polymarket API with automatic pagination
- Saves data to timestamped JSON files
- Progress tracking during fetching
- Command-line interface with options
- Error handling for API requests

## Installation

1. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

### Basic Usage
```bash
python main/utils.py
```

This will fetch all markets and save them to a file named `markets_scrape_last_updated_YYYY-MM-DD_HH-MM-SS_EDT.json` in the current directory.

### Advanced Usage

```bash
# Save to a specific directory
python main/utils.py --output-dir ./data

# Use a different API base URL
python main/utils.py --base-url https://custom-api.polymarket.com

# Combine options
python main/utils.py -o ./data --base-url https://gamma-api.polymarket.com
```

### Command Line Options

- `--output-dir`, `-o`: Directory to save the output file (default: current directory)
- `--base-url`: Base URL for Polymarket API (default: https://gamma-api.polymarket.com)

## Output

The script will:
1. Fetch markets in batches of 100
2. Show progress during fetching
3. Save all markets to a timestamped JSON file
4. Print the total number of markets saved and the file path

## Example Output

```
Fetching markets from Polymarket API...
Fetched 100 markets (total: 100)
Fetched 100 markets (total: 200)
Fetched 50 markets (total: 250)
Finished fetching markets. Total fetched: 250

✅ Successfully saved 250 markets to: ./markets_scrape_last_updated_2024-01-15_14-30-45_EDT.json
``` 