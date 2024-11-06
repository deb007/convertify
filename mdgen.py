import re
import os
from urllib.parse import urlparse
from datetime import datetime
from pathlib import Path
import requests
from bs4 import BeautifulSoup
import html2text
import time

def sanitize_filename(title):
    """Convert a string into a safe filename."""
    # Remove or replace invalid filename characters
    sanitized = re.sub(r'[<>:"/\\|?*]', '', title)
    # Replace spaces with dashes
    sanitized = sanitized.replace(' ', '-')
    # Remove any multiple dashes
    sanitized = re.sub(r'-+', '-', sanitized)
    return sanitized.strip('-')

def extract_article_content(url):
    """Extract and convert article content to markdown."""
    try:
        # Add headers to mimic a browser request
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        # Fetch the webpage
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        # Parse the HTML
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Remove unwanted elements
        for element in soup.find_all(['script', 'style', 'nav', 'footer', 'iframe']):
            element.decompose()
            
        # Try to find the main article content
        article_content = None
        
        # Common article containers
        possible_article_elements = [
            soup.find('article'),
            soup.find(class_=re.compile(r'article|post|entry|content')),
            soup.find(id=re.compile(r'article|post|entry|content')),
            soup.find('main'),
        ]
        
        for element in possible_article_elements:
            if element:
                article_content = element
                break
                
        if not article_content:
            # Fallback to body if no article container found
            article_content = soup.find('body')
        
        # Convert to markdown
        h = html2text.HTML2Text()
        h.ignore_links = False
        h.ignore_images = False
        h.ignore_tables = False
        h.body_width = 0  # Don't wrap text
        
        markdown_content = h.handle(str(article_content))
        
        # Clean up the markdown
        # Remove excessive newlines
        markdown_content = re.sub(r'\n\s*\n', '\n\n', markdown_content)
        # Remove any remaining HTML comments
        markdown_content = re.sub(r'<!--.*?-->', '', markdown_content, flags=re.DOTALL)
        
        return markdown_content.strip()
        
    except requests.exceptions.RequestException as e:
        return f"Error fetching content: {str(e)}"
    except Exception as e:
        return f"Error processing content: {str(e)}"

def process_links(input_file, output_dir):
    """Process each link from the input file and create individual markdown notes."""
    # Create output directory if it doesn't exist
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    with open(input_file, 'r') as f:
        # Read all lines and filter out empty ones
        links = [line.strip() for line in f.readlines() if line.strip()]
    
    for link in links:
        try:
            # Parse the URL to get the domain and path
            parsed_url = urlparse(link)
            # Create a basic filename from the domain and last path segment
            base_name = parsed_url.netloc.replace('www.', '')
            path_segment = parsed_url.path.split('/')[-1] if parsed_url.path else ''
            
            # Generate filename
            timestamp = datetime.now().strftime('%Y%m%d')
            filename = sanitize_filename(f"{timestamp}-{base_name}-{path_segment}")
            if not filename.endswith('.md'):
                filename += '.md'
            
            print(f"Processing: {link}")
            # Extract article content
            article_content = extract_article_content(link)
            
            # Create markdown content
            content = f"""---
url: {link}
date_added: {datetime.now().strftime('%Y-%m-%d')}
source: {parsed_url.netloc}
---

# {base_name}

[Original Link]({link})

## Article

{article_content}
"""
            
            # Write to file
            output_path = os.path.join(output_dir, filename)
            with open(output_path, 'w', encoding='utf-8') as note_file:
                note_file.write(content)
            
            print(f"Created note: {filename}")
            
            # Add a small delay between requests to be polite to servers
            time.sleep(2)
            
        except Exception as e:
            print(f"Error processing link: {link}")
            print(f"Error details: {str(e)}")

if __name__ == "__main__":
    # Example usage
    input_file = "links.txt"  # Your text file containing links
    output_dir = "notes"      # Directory where markdown files will be created
    process_links(input_file, output_dir)
