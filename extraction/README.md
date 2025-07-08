# Confluence Data Extraction

This module contains tools for extracting data from Confluence using the REST API.

## Files

- `confluence_data_extractor.py` - Main script for extracting Confluence data
- `confluence_data_extractor.ipynb` - Jupyter notebook version (legacy)
- `clean_confluence_data.py` - Data cleaning utilities
- `exports/` - Directory containing exported data

## Setup

1. Make sure you have the virtual environment activated:
   ```bash
   source venv/bin/activate
   ```

2. Set up your Confluence credentials in a `.env` file in the project root:
   ```env
   CONFLUENCE_URL=https://your-domain.atlassian.net
   CONFLUENCE_USERNAME=your-email@example.com
   CONFLUENCE_API_TOKEN=your-api-token
   ```

   **Note**: To get an API token, go to your Atlassian account settings → Security → API tokens → Create API token.

## Usage

### List Available Spaces

```bash
python extraction/confluence_data_extractor.py --list-spaces
```

### Extract Data from a Space

#### Basic extraction (metadata only):
```bash
python extraction/confluence_data_extractor.py --space SPACE_KEY
```

#### Extract with content:
```bash
python extraction/confluence_data_extractor.py --space SPACE_KEY --include-content
```

#### Limit number of pages:
```bash
python extraction/confluence_data_extractor.py --space SPACE_KEY --max-pages 10
```

#### Custom output directory:
```bash
python extraction/confluence_data_extractor.py --space SPACE_KEY --output-dir ./my_exports
```

### Command Line Options

- `--space`, `-s`: Confluence space key to extract data from
- `--list-spaces`, `-l`: List all available spaces and exit
- `--include-content`, `-c`: Include page content in extraction (increases processing time and file size)
- `--max-pages`, `-m`: Maximum number of pages to extract
- `--output-dir`, `-o`: Output directory for exported files (default: exports)
- `--config`: Path to .env file (default: .env in current directory)

## Output Formats

The script exports data in multiple formats:

1. **CSV** - Page metadata only (excludes HTML content for compatibility)
2. **JSON** - Complete data including HTML content and plain text
3. **Excel** - Metadata in one sheet, content in another (requires openpyxl)

## Example Workflow

```bash
# 1. List available spaces
python extraction/confluence_data_extractor.py --list-spaces

# 2. Extract data from a specific space
python extraction/confluence_data_extractor.py --space Founders --include-content

# 3. Check the exports directory for generated files
ls extraction/exports/
```

## Data Structure

The extracted data includes:

- `id` - Page ID
- `title` - Page title
- `type` - Content type (usually 'page')
- `status` - Page status
- `created` - Creation date
- `updated` - Last update date
- `version` - Page version number
- `url` - Direct URL to the page
- `html_content` - Raw HTML content (if --include-content)
- `plain_text` - Plain text content (if --include-content)
- `ancestors` - Parent page hierarchy (if --include-content)
- `labels` - Page labels/tags (if available and --include-content)

## Error Handling

The script includes robust error handling for:
- Authentication failures
- Network issues
- Invalid space keys
- Missing pages
- Rate limiting (automatic delays)

## Tips

1. **Start small**: Use `--max-pages 5` to test before extracting large spaces
2. **Use metadata only**: Skip `--include-content` for faster extraction if you only need page information
3. **Check permissions**: Ensure your API token has access to the spaces you want to extract
4. **Monitor rate limits**: The script includes automatic delays, but very large extractions may take time

## Troubleshooting

**"Confluence credentials not properly configured"**
- Check your `.env` file is in the project root
- Verify your API token is correct
- Ensure your Confluence URL is complete (e.g., `https://domain.atlassian.net`)

**"No pages found in space"**
- Verify the space key is correct (case-sensitive)
- Check that your account has access to the space
- Try listing spaces first to see available options

**"Connection test failed"**
- Check your internet connection
- Verify your Confluence URL
- Ensure your API token hasn't expired 