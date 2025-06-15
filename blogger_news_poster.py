import os
import json
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from datetime import datetime
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import pickle
import time

# Load environment variables
load_dotenv()

# Your news URL to scrape
NEWS_URL = "https://www.ada.lk/latest-news/11"

# File to store previously fetched news links
LOG_FILE = "news_log.json"
MARKDOWN_FILE = "README.md"

# Blogger API configuration
SCOPES = ['https://www.googleapis.com/auth/blogger']
BLOG_ID = os.getenv('BLOG_ID')  # Your Blogger blog ID
CREDENTIALS_FILE = 'credentials.json'
TOKEN_FILE = 'token.pickle'

def get_blogger_credentials():
    creds = None
    if os.path.exists(TOKEN_FILE):
        try:
            with open(TOKEN_FILE, 'rb') as token:
                creds = pickle.load(token)
        except Exception as e:
            print(f"Error loading token file: {str(e)}")
            print("Will create new credentials.")
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as e:
                print(f"Error refreshing token: {str(e)}")
                print("Will create new credentials.")
                creds = None
        
        if not creds:
            try:
                print("Starting OAuth flow...")
                flow = InstalledAppFlow.from_client_secrets_file(
                    CREDENTIALS_FILE, 
                    SCOPES,
                    redirect_uri='http://localhost:8080/'
                )
                creds = flow.run_local_server(
                    port=8080,
                    prompt='consent',
                    authorization_prompt_message='Please authorize the application in your browser.'
                )
                
                # Save the credentials for the next run
                with open(TOKEN_FILE, 'wb') as token:
                    pickle.dump(creds, token)
                print("Successfully saved credentials.")
            except Exception as e:
                print(f"Error during OAuth flow: {str(e)}")
                return None
    
    return creds

def post_to_blogger(title, content, image_url=None):
    try:
        print(f"\n=== Attempting to post to Blogger ===")
        print(f"Title: {title}")
        
        # Get credentials
        creds = get_blogger_credentials()
        if not creds:
            print("Error: Failed to get credentials")
            return None
            
        service = build('blogger', 'v3', credentials=creds)
        
        # Format content with proper HTML
        formatted_content = f'<div style="font-family: Arial, sans-serif; line-height: 1.6;">'
        
        # Add image if available
        if image_url:
            formatted_content += f'<img src="{image_url}" alt="{title}" style="max-width: 100%; height: auto; margin-bottom: 20px;"><br>'
        
        # Split content into paragraphs and format each
        paragraphs = content.split('\n\n')
        for para in paragraphs:
            if para.strip():  # Only add non-empty paragraphs
                formatted_content += f'<p style="margin-bottom: 15px;">{para.strip()}</p>'
        
        formatted_content += '</div>'
        
        post = {
            'kind': 'blogger#post',
            'blog': {'id': BLOG_ID},
            'title': title,
            'content': formatted_content
        }
        
        # Create the post
        posts = service.posts()
        insert = posts.insert(blogId=BLOG_ID, body=post)
        post_doc = insert.execute()
        
        print(f"Successfully posted: {title}")
        print(f"Post URL: {post_doc.get('url', 'URL not available')}")
        return post_doc['id']
    except Exception as e:
        print(f"Error posting to Blogger: {str(e)}")
        return None

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
    # Check if credentials file exists
    if not os.path.exists(CREDENTIALS_FILE):
        print("Error: credentials.json file not found. Please set up your Blogger API credentials.")
        return

    # Check if BLOG_ID is set
    if not BLOG_ID:
        print("Error: BLOG_ID not set in .env file")
        return

    # Fetch news and check for duplicates
    news_items = fetch_news()
    logged_urls = read_log()
    new_news = [news for news in news_items if news['link'] not in logged_urls]

    if new_news:
        # Track successfully posted articles
        successfully_posted_news = []
        
        # Post to Blogger with 10-second delay between posts
        for i, news in enumerate(new_news):
            if i > 0:  # Add delay after first post
                print("\nWaiting 10 seconds before posting next article...")
                time.sleep(10)
            
            try:
                news_date = datetime.strptime(news['date'], "%d %m %Y %H:%M:%S").strftime("%B %d, %Y, %I:%M %p")
            except ValueError:
                news_date = news['date']
            
            content = f"Published on {news_date}\n\n{news['full_content']}"
            try:
                post_id = post_to_blogger(news['title'], content, news['image_url'])
                if post_id:
                    print(f"Successfully posted to Blogger: {news['title']}")
                    successfully_posted_news.append(news)
                else:
                    print(f"Failed to post to Blogger: {news['title']}")
            except Exception as e:
                print(f"Error posting to Blogger: {str(e)}")
                print(f"Skipping README update for this article...")

        # Only update log and README for successfully posted articles
        if successfully_posted_news:
            new_urls = [news['link'] for news in successfully_posted_news]
            update_log(new_urls)
            update_news_md(successfully_posted_news)
            print(f"Added {len(successfully_posted_news)} new news articles to README.md.")
        else:
            print("No articles were successfully posted to Blogger. README.md and log were not updated.")
    else:
        print("No new news to add.")

if __name__ == "__main__":
    main() 