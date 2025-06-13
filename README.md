# Ada LK News Blogger Automation

This script automatically scrapes news from Ada LK and posts them to both a GitHub README.md file and a Blogger blog.

## Setup Instructions

1. Install the required dependencies:
```bash
pip install -r requirements.txt
```

2. Set up Google Blogger API:
   - Go to the [Google Cloud Console](https://console.cloud.google.com/)
   - Create a new project
   - Enable the Blogger API v3
   - Create OAuth 2.0 credentials
   - Download the credentials and save them as `credentials.json` in the project directory

3. Create a `.env` file with your Blogger blog ID:
```
BLOG_ID=your_blog_id_here
```

4. First run authentication:
   - Run the script for the first time
   - A browser window will open asking you to authorize the application
   - Grant the necessary permissions
   - The token will be saved for future use

## Usage

Simply run the script:
```bash
python blogger_news_poster.py
```

The script will:
1. Scrape new articles from Ada LK
2. Update the README.md file with the new articles
3. Post the new articles to your Blogger blog
4. Keep track of posted articles to avoid duplicates

## Features

- Automatic news scraping from Ada LK
- Posts to both GitHub README and Blogger
- Handles images and formatting
- Maintains a log of posted articles
- Preserves static content in README.md

## Notes

- The script uses the `<!-- STATIC-START -->` and `<!-- STATIC-END -->` markers to preserve static content in the README.md file
- Make sure to keep your credentials secure and never commit them to version control
- The script will automatically handle duplicate posts and maintain a log of posted articles

## Code

Here's the main script for scraping and posting news:

```python
import os
import json
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from datetime import datetime

# Load environment variables
load_dotenv()

# Your news URL to scrape
NEWS_URL = "https://www.ada.lk/latest-news/11"

# File to store previously fetched news links
LOG_FILE = "news_log.json"
MARKDOWN_FILE = "README.md"

def fetch_full_content(news_url):
    response = requests.get(news_url)
    if response.status_code != 200:
        print(f"Failed to fetch content from {news_url}.")
        return ""

    soup = BeautifulSoup(response.text, "html.parser")
    content = soup.find("div", class_="single-body-wrap")

    if content:
        paragraphs = content.find_all("p")
        full_content = "\n\n".join([para.get_text(strip=True) for para in paragraphs])
        return full_content
    else:
        return "Full content not found."

def fetch_news():
    response = requests.get(NEWS_URL)
    if response.status_code != 200:
        print("Failed to fetch news.")
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    news_items = []

    for news_div in soup.find_all("div", class_="row bg-white cat-b-row mt-3"):
        link = news_div.find("a", href=True)["href"]
        title = news_div.find("h5").get_text(strip=True)
        date = news_div.find("h6").get_text(strip=True).replace("•", "").strip()
        short_desc = news_div.find("p", class_="cat-b-text").get_text(strip=True)
        
        # Handle missing images safely
        image_tag = news_div.find("img")
        image_url = image_tag["src"] if image_tag and "src" in image_tag.attrs else None

        # Fetch the full content for the news
        full_content = fetch_full_content(link)

        news_items.append({
            "link": link,
            "title": title,
            "date": date,
            "short_desc": short_desc,
            "image_url": image_url,
            "full_content": full_content
        })

    return news_items

def read_log():
    if not os.path.exists(LOG_FILE):
        return []
    with open(LOG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def update_log(new_urls):
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            logged_data = json.load(f)
    else:
        logged_data = []

    logged_data.extend(new_urls)

    with open(LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(logged_data, f, indent=4)

def format_news_to_markdown(news_items):
    markdown_content = ""
    for item in news_items:
        try:
            news_date = datetime.strptime(item['date'], "%d %m %Y %H:%M:%S").strftime("%B %d, %Y, %I:%M %p")
        except ValueError:
            news_date = item['date']  # Use raw date if parsing fails

        markdown_content += f"\n\n---\n\n"
        markdown_content += f"## {item['title']}\n\n"
        markdown_content += f"\n*Published on: {news_date}*\n\n"
        # markdown_content += f"_{item['short_desc']}_\n\n"
        markdown_content += f"{item['full_content']}"

        # Only add the image if it exists
        if item['image_url']:
            markdown_content += f"\n\n![Image]({item['image_url']})\n\n"

    return markdown_content

def update_news_md(new_news):
    static_content = ""
    dynamic_content = ""

    # Read the existing README and separate static content
    if os.path.exists(MARKDOWN_FILE):
        with open(MARKDOWN_FILE, "r", encoding="utf-8") as f:
            content = f.read()
            if "<!-- STATIC-START -->" in content and "<!-- STATIC-END -->" in content:
                static_content = content.split("<!-- STATIC-END -->")[0] + "<!-- STATIC-END -->"
                dynamic_content = content.split("<!-- STATIC-END -->")[1].strip()

    # Generate markdown for new news
    new_news_markdown = format_news_to_markdown(new_news)

    # Combine static content, new news, and existing dynamic content
    updated_content = static_content + "\n\n" + new_news_markdown + "\n\n" + dynamic_content

    # Write back to README
    with open(MARKDOWN_FILE, "w", encoding="utf-8") as f:
        f.write(updated_content)

def main():
    news_items = fetch_news()
    logged_urls = read_log()
    new_news = [news for news in news_items if news['link'] not in logged_urls]

    if new_news:
        new_urls = [news['link'] for news in new_news]
        update_log(new_urls)
        update_news_md(new_news)
        print(f"Added {len(new_news)} new news articles to README.md.")
    else:
        print("No new news to add.")

if __name__ == "__main__":
    main()
```

<!-- STATIC-START -->
// ... existing code ...
<!-- STATIC-END --> 