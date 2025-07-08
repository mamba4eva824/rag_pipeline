#!/usr/bin/env python3
"""
Confluence Data Extractor

This script provides a structured approach to extract data from Confluence using the REST API.
It can extract page metadata, content, and export data to various formats.

Usage:
    python confluence_data_extractor.py --space SPACE_KEY [options]

Example:
    python confluence_data_extractor.py --space Founders --include-content --max-pages 10
"""

import requests
import pandas as pd
import json
import os
import argparse
import sys
from dotenv import load_dotenv
import base64
from requests.auth import HTTPBasicAuth
import time
from datetime import datetime
import html2text
import re
from typing import List, Dict, Any, Optional


class ConfluenceExtractor:
    """Main class for Confluence data extraction"""
    
    def __init__(self, confluence_url: str, username: str, api_token: str):
        """Initialize the Confluence extractor with credentials"""
        # Ensure URL has proper protocol
        if not confluence_url.startswith(('http://', 'https://')):
            confluence_url = 'https://' + confluence_url
        
        self.confluence_url = confluence_url.rstrip('/')
        self.username = username
        self.api_token = api_token
        self.session = None
        
    def create_session(self) -> requests.Session:
        """Create and return a session object for Confluence API calls with proper authentication"""
        session = requests.Session()
        session.auth = HTTPBasicAuth(self.username, self.api_token)
        session.headers.update({
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        })
        self.session = session
        return session
    
    def test_connection(self) -> bool:
        """Test the connection to Confluence API"""
        try:
            if not self.session:
                self.create_session()
            url = f"{self.confluence_url}/wiki/rest/api/space"
            response = self.session.get(url)
            return response.status_code == 200
        except Exception as e:
            print(f"Connection test failed: {e}")
            return False
    
    def get_space_info(self, space_key: str) -> Optional[Dict[str, Any]]:
        """Get information about a specific space"""
        if not self.session:
            self.create_session()
            
        url = f"{self.confluence_url}/wiki/rest/api/space/{space_key}"
        response = self.session.get(url)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Error fetching space info: {response.status_code}")
            print(response.text)
            return None
    
    def get_all_spaces(self) -> List[Dict[str, Any]]:
        """Get information about all spaces the user has access to"""
        if not self.session:
            self.create_session()
            
        spaces = []
        start = 0
        limit = 100
        
        while True:
            url = f"{self.confluence_url}/wiki/rest/api/space?start={start}&limit={limit}"
            response = self.session.get(url)
            if response.status_code != 200:
                print(f"Error fetching spaces: {response.status_code}")
                print(response.text)
                break
                
            data = response.json()
            results = data.get('results', [])
            if not results:
                break
                
            spaces.extend(results)
            if len(results) < limit:
                break
                
            start += limit
            time.sleep(0.5)  # Be nice to the API
        
        return spaces
    
    def get_pages_in_space(self, space_key: str, expand: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all pages in a specific space"""
        if not self.session:
            self.create_session()
            
        pages = []
        start = 0
        limit = 25
        
        # Default expansion includes basic history for author info
        if not expand:
            expand = "history.createdBy,history.lastUpdated,version"
        
        while True:
            url = f"{self.confluence_url}/wiki/rest/api/content"
            params = {
                'spaceKey': space_key,
                'start': start,
                'limit': limit,
                'expand': expand
            }
            
            response = self.session.get(url, params=params)
            if response.status_code != 200:
                print(f"Error fetching pages: {response.status_code}")
                print(response.text)
                break
                
            data = response.json()
            batch_pages = data.get('results', [])
            pages.extend(batch_pages)
                
            # Check if there are more pages
            if len(batch_pages) < limit:
                break
                
            start += limit
            time.sleep(0.5)  # Be nice to the API
        
        return pages
    
    def get_page_content(self, page_id: str, expand: str = 'body.storage') -> Optional[Dict[str, Any]]:
        """Get detailed content for a specific page"""
        if not self.session:
            self.create_session()
            
        url = f"{self.confluence_url}/wiki/rest/api/content/{page_id}?expand={expand}"
        response = self.session.get(url)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Error fetching page content: {response.status_code}")
            print(response.text)
            return None
    
    @staticmethod
    def extract_text_from_html(html_content: str) -> str:
        """Convert HTML content to plain text"""
        h = html2text.HTML2Text()
        h.ignore_links = False
        h.ignore_images = False
        h.ignore_tables = False
        return h.handle(html_content)
    
    def extract_confluence_data_to_dataset(self, space_key: str, include_content: bool = False, 
                                         max_pages: Optional[int] = None) -> pd.DataFrame:
        """Extract data from Confluence directly to a pandas DataFrame
        
        Parameters:
        -----------
        space_key : str
            The Confluence space key to extract data from
        include_content : bool, default=False
            Whether to include page content in the dataset (significantly increases size)
        max_pages : int, optional
            Maximum number of pages to extract (None for all pages)
        
        Returns:
        --------
        pd.DataFrame
            DataFrame containing the extracted Confluence data
        """
        print(f"Extracting data from Confluence space: {space_key}")
        
        # Test connection
        if not self.test_connection():
            print("Failed to connect to Confluence API")
            return pd.DataFrame()
        
        print("✓ Connection established")
        
        # Get pages
        print("Retrieving pages...")
        pages = self.get_pages_in_space(space_key)
        if not pages:
            print(f"No pages found in space '{space_key}'")
            return pd.DataFrame()
            
        total_pages = len(pages)
        print(f"Found {total_pages} pages in space '{space_key}'")
        
        # Filter out Systems Team Meeting Minutes (experimental filtering)
        excluded_titles = ["Systems Team - Meeting Minutes"]
        original_count = len(pages)
        pages = [page for page in pages if page.get('title', '') not in excluded_titles]
        filtered_count = len(pages)
        
        if original_count != filtered_count:
            print(f"🔬 EXPERIMENT: Filtered out {original_count - filtered_count} pages matching: {excluded_titles}")
            print(f"   Remaining pages: {filtered_count}/{original_count}")
        
        # Limit pages if specified
        if max_pages and max_pages < filtered_count:
            pages = pages[:max_pages]
            print(f"Limiting to {max_pages} pages")
        
        # Prepare data collection
        all_data = []
        
        # Extract page data
        for i, page in enumerate(pages, 1):
            page_id = page['id']
            title = page['title']
            print(f"Processing page {i}/{len(pages)}: {title}")
            
            page_data = {
                'id': page_id,
                'title': title,
                'type': page.get('type', 'unknown'),
                'status': page.get('status', 'unknown'),
                'created': page.get('history', {}).get('createdDate', 'unknown'),
                'updated': page.get('history', {}).get('lastUpdated', {}).get('when', 'unknown'),
                'version': page.get('version', {}).get('number', 0),
                'url': f"{self.confluence_url}/wiki/spaces/{space_key}/pages/{page_id}"
            }
            
            # Get content if requested
            if include_content:
                page_detail = self.get_page_content(page_id, expand='body.storage,version,ancestors,metadata,history.createdBy,history.lastUpdated')
                
                if page_detail and 'body' in page_detail and 'storage' in page_detail['body']:
                    html_content = page_detail['body']['storage']['value']
                    page_data['html_content'] = html_content
                    page_data['plain_text'] = self.extract_text_from_html(html_content)
                    
                    # Get parent page hierarchy
                    ancestors = [a.get('title', 'Unknown') for a in page_detail.get('ancestors', [])]
                    page_data['ancestors'] = ' > '.join(ancestors) if ancestors else 'Root'
                    
                    # Get labels/tags if available
                    if 'metadata' in page_detail and 'labels' in page_detail['metadata']:
                        labels = [label.get('name', '') for label in page_detail['metadata']['labels'].get('results', [])]
                        page_data['labels'] = ', '.join(labels) if labels else ''
                    
                    # Extract author information from history
                    history = page_detail.get('history', {})
                    
                    # Created by information
                    created_by = history.get('createdBy', {})
                    page_data['created_by'] = created_by.get('displayName', 'Unknown')
                    page_data['created_by_email'] = created_by.get('email', '')
                    page_data['created_by_username'] = created_by.get('username', '')
                    
                    # Last updated by information
                    last_updated = history.get('lastUpdated', {})
                    updated_by = last_updated.get('by', {})
                    page_data['updated_by'] = updated_by.get('displayName', 'Unknown')
                    page_data['updated_by_email'] = updated_by.get('email', '')
                    
                    # Version information (can also contain author data)
                    version = page_detail.get('version', {})
                    version_by = version.get('by', {})
                    page_data['version_by'] = version_by.get('displayName', 'Unknown')
                    page_data['version_by_email'] = version_by.get('email', '')
                else:
                    print(f"  ⚠️ Could not retrieve content for {title}")
            else:
                # Even without content, try to get basic author info from the page list
                history = page.get('history', {})
                created_by = history.get('createdBy', {})
                page_data['created_by'] = created_by.get('displayName', 'Unknown')
                page_data['created_by_email'] = created_by.get('email', '')
                
                last_updated = history.get('lastUpdated', {})
                updated_by = last_updated.get('by', {})
                page_data['updated_by'] = updated_by.get('displayName', 'Unknown')
                page_data['updated_by_email'] = updated_by.get('email', '')
            
            all_data.append(page_data)
            time.sleep(0.5)  # Be nice to the API
        
        # Convert to DataFrame
        df = pd.DataFrame(all_data)
        
        # Convert date columns to datetime
        for col in ['created', 'updated']:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors='coerce')
        
        print(f"✓ Successfully extracted data for {len(df)} pages")
        return df


def export_data(df: pd.DataFrame, space_key: str, output_dir: str = 'exports') -> None:
    """Export the extracted data to different formats"""
    if df.empty:
        print("No data to export")
        return
    
    # Create exports directory
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # Define export paths
    csv_path = os.path.join(output_dir, f"confluence_data_{space_key}_{timestamp}.csv")
    json_path = os.path.join(output_dir, f"confluence_data_{space_key}_{timestamp}.json")
    
    # Export to CSV (exclude HTML content for CSV to avoid issues)
    try:
        export_cols = [col for col in df.columns if col != 'html_content']
        df[export_cols].to_csv(csv_path, index=False, encoding='utf-8')
        print(f"✓ Data exported to CSV: {csv_path}")
    except Exception as e:
        print(f"Error exporting to CSV: {e}")
    
    # Export to JSON (include all content)
    try:
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(df.to_dict(orient='records'), f, ensure_ascii=False, indent=2, default=str)
        print(f"✓ Data exported to JSON: {json_path}")
    except Exception as e:
        print(f"Error exporting to JSON: {e}")
    
    # Try to export to Excel if openpyxl is available
    try:
        excel_path = os.path.join(output_dir, f"confluence_data_{space_key}_{timestamp}.xlsx")
        with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
            # Export metadata to one sheet
            metadata_cols = [col for col in df.columns if col not in ['html_content', 'plain_text']]
            df[metadata_cols].to_excel(writer, index=False, sheet_name='Metadata')
            
            # If plain_text exists, export it to another sheet
            if 'plain_text' in df.columns:
                df[['id', 'title', 'plain_text']].to_excel(writer, index=False, sheet_name='Content')
        
        print(f"✓ Data exported to Excel: {excel_path}")
    except ImportError:
        print("⚠️ openpyxl not installed. Skipping Excel export. Install with: pip install openpyxl")
    except Exception as e:
        print(f"Error exporting to Excel: {e}")


def list_spaces(extractor: ConfluenceExtractor) -> None:
    """List all available spaces"""
    print("Retrieving available spaces...")
    spaces = extractor.get_all_spaces()
    
    if spaces:
        spaces_df = pd.DataFrame([{
            'key': space['key'],
            'name': space['name'],
            'type': space['type'],
            'description': space.get('description', {}).get('plain', {}).get('value', 'No description')
        } for space in spaces])
        
        print(f"\nFound {len(spaces)} spaces:")
        print(spaces_df.to_string(index=False))
    else:
        print("No spaces found or error occurred.")


def main():
    """Main function to handle command line arguments and execute extraction"""
    parser = argparse.ArgumentParser(
        description='Extract data from Confluence using REST API',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --list-spaces
  %(prog)s --space Founders
  %(prog)s --space Founders --include-content --max-pages 10
  %(prog)s --space KB --output-dir ./my_exports
        """
    )
    
    parser.add_argument('--space', '-s', type=str, help='Confluence space key to extract data from')
    parser.add_argument('--list-spaces', '-l', action='store_true', help='List all available spaces and exit')
    parser.add_argument('--include-content', '-c', action='store_true', 
                       help='Include page content in extraction (increases processing time and file size)')
    parser.add_argument('--max-pages', '-m', type=int, help='Maximum number of pages to extract')
    parser.add_argument('--output-dir', '-o', type=str, default='exports', 
                       help='Output directory for exported files (default: exports)')
    parser.add_argument('--config', type=str, help='Path to .env file (default: .env in current directory)')
    
    args = parser.parse_args()
    
    # Load environment variables
    if args.config:
        load_dotenv(args.config)
    else:
        load_dotenv()
    
    # Get credentials from environment
    confluence_url = os.getenv('CONFLUENCE_URL')
    confluence_username = os.getenv('CONFLUENCE_USERNAME')
    confluence_api_token = os.getenv('CONFLUENCE_API_TOKEN')
    
    # Validate credentials
    if not all([confluence_url, confluence_username, confluence_api_token]):
        print("❌ Error: Confluence credentials not properly configured.")
        print("Please set the following environment variables:")
        print("  - CONFLUENCE_URL")
        print("  - CONFLUENCE_USERNAME")
        print("  - CONFLUENCE_API_TOKEN")
        print("\nYou can create a .env file with these variables or set them in your environment.")
        sys.exit(1)
    
    # Create extractor instance
    extractor = ConfluenceExtractor(confluence_url, confluence_username, confluence_api_token)
    
    # Handle list spaces command
    if args.list_spaces:
        list_spaces(extractor)
        return
    
    # Validate space argument
    if not args.space:
        print("❌ Error: Space key is required. Use --space SPACE_KEY or --list-spaces to see available spaces.")
        sys.exit(1)
    
    # Extract data
    try:
        df = extractor.extract_confluence_data_to_dataset(
            space_key=args.space,
            include_content=args.include_content,
            max_pages=args.max_pages
        )
        
        if not df.empty:
            # Display basic info about the dataset
            print(f"\n📊 Dataset Summary:")
            print(f"   Rows: {len(df)}")
            print(f"   Columns: {len(df.columns)}")
            print(f"   Columns: {', '.join(df.columns)}")
            
            # Export data
            export_data(df, args.space, args.output_dir)
            
            print(f"\n✅ Data extraction completed successfully!")
        else:
            print("❌ No data was extracted. Please check your space key and permissions.")
            
    except KeyboardInterrupt:
        print("\n⚠️ Extraction interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error during extraction: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main() 