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
        print(f"Blog ID: {BLOG_ID}")
        
        # Get credentials
        creds = get_blogger_credentials()
        if not creds:
            print("Error: Failed to get credentials")
            return None
            
        print("Building Blogger service...")
        service = build('blogger', 'v3', credentials=creds)
        
        # First verify we can access the blog
        try:
            print("Verifying blog access...")
            blog = service.blogs().get(blogId=BLOG_ID).execute()
            print(f"Successfully accessed blog: {blog.get('name', 'Unknown')}")
        except Exception as e:
            print(f"Error accessing blog: {str(e)}")
            if hasattr(e, 'response'):
                print(f"Response status: {e.response.status_code}")
                print(f"Response content: {e.response.content}")
            return None
        
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
        
        # Clean and validate content
        if not formatted_content or len(formatted_content.strip()) == 0:
            print("Error: Post content is empty")
            return None
            
        if not title or len(title.strip()) == 0:
            print("Error: Post title is empty")
            return None
            
        # Truncate content if it's too long (Blogger has limits)
        if len(formatted_content) > 1000000:  # 1MB limit
            print("Warning: Content is too long, truncating...")
            formatted_content = formatted_content[:1000000]
        
        post = {
            'kind': 'blogger#post',
            'blog': {'id': BLOG_ID},
            'title': title,
            'content': formatted_content
        }
        
        print("Creating post...")
        # Create the post
        posts = service.posts()
        insert = posts.insert(blogId=BLOG_ID, body=post)
        
        print("Executing post creation...")
        post_doc = insert.execute()
        
        print(f"Successfully posted: {title}")
        print(f"Post URL: {post_doc.get('url', 'URL not available')}")
        print(f"Post ID: {post_doc.get('id', 'ID not available')}")
        return post_doc['id']
    except Exception as e:
        print(f"Error posting to Blogger: {str(e)}")
        print(f"Error type: {type(e).__name__}")
        if hasattr(e, 'response'):
            print(f"Response status: {e.response.status_code}")
            print(f"Response content: {e.response.content}")
            try:
                error_content = json.loads(e.response.content)
                if 'error' in error_content:
                    print(f"Error details: {error_content['error']}")
            except:
                pass
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

def update_log(new_posts):
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            logged_data = json.load(f)
    else:
        logged_data = []

    # Add new posts while avoiding duplicates
    for post in new_posts:
        if not any(existing_post['url'] == post['url'] or existing_post['title'] == post['title'] for existing_post in logged_data):
            logged_data.append(post)

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
        markdown_content += f"Published on {news_date}\n\n"
        markdown_content += f"{item['full_content']}"

        if item['image_url']:
            markdown_content += f"\n\n![Image]({item['image_url']})\n\n"

    return markdown_content

def update_news_md(new_news):
    static_content = ""
    dynamic_content = ""

    if os.path.exists(MARKDOWN_FILE):
        with open(MARKDOWN_FILE, "r", encoding="utf-8") as f:
            content = f.read()
            if "<!-- STATIC-START -->" in content and "<!-- STATIC-END -->" in content:
                static_content = content.split("<!-- STATIC-END -->")[0] + "<!-- STATIC-END -->"
                dynamic_content = content.split("<!-- STATIC-END -->")[1].strip()

    new_news_markdown = format_news_to_markdown(new_news)
    updated_content = static_content + "\n" + new_news_markdown + "\n" + dynamic_content

    with open(MARKDOWN_FILE, "w", encoding="utf-8") as f:
        f.write(updated_content)

def retry_failed_posts(failed_posts, max_retries=3):
    print("\n=== Retrying Failed Posts ===")
    successful_retries = 0
    
    for attempt in range(max_retries):
        if not failed_posts:
            break
            
        print(f"\nRetry attempt {attempt + 1} of {max_retries}")
        still_failed = []
        
        for post in failed_posts:
            print(f"\nRetrying post: {post['title']}")
            post_id = post_to_blogger(post['title'], post['content'], post['image_url'])
            if post_id:
                successful_retries += 1
                print(f"Successfully posted on retry: {post['title']}")
            else:
                still_failed.append(post)
                print(f"Still failed on retry: {post['title']}")
        
        failed_posts = still_failed
        if not failed_posts:
            break
            
        # Wait for 30 seconds before next retry
        if attempt < max_retries - 1:
            print("\nWaiting 30 seconds before next retry...")
            time.sleep(30)
    
    return successful_retries, failed_posts

def main():
    # Check if credentials file exists
    if not os.path.exists(CREDENTIALS_FILE):
        print("Error: credentials.json file not found. Please set up your Blogger API credentials.")
        return

    # Check if BLOG_ID is set
    if not BLOG_ID:
        print("Error: BLOG_ID not set in .env file")
        return

    print("\nStarting news scraping and posting process...")
    
    # First verify credentials
    print("Verifying Blogger credentials...")
    creds = get_blogger_credentials()
    if not creds:
        print("Failed to get valid credentials. Please check your OAuth configuration.")
        return
        
    print("Credentials verified successfully.")
    
    # Verify we can access the blog
    try:
        service = build('blogger', 'v3', credentials=creds)
        blog = service.blogs().get(blogId=BLOG_ID).execute()
        print(f"Successfully connected to blog: {blog.get('name', 'Unknown')}")
    except Exception as e:
        print(f"Error accessing blog: {str(e)}")
        if hasattr(e, 'response'):
            print(f"Response status: {e.response.status_code}")
            print(f"Response content: {e.response.content}")
        return

    # Fetch news and check for duplicates
    news_items = fetch_news()
    logged_posts = read_log()
    
    # Filter out already posted news
    new_news = []
    for news in news_items:
        if not any(post['url'] == news['link'] or post['title'] == news['title'] for post in logged_posts):
            new_news.append(news)
        else:
            print(f"Skipping already posted article: {news['title']}")
    
    print(f"New articles to post: {len(new_news)}")

    if new_news:
        # Post each new article to Blogger
        successful_posts = 0
        failed_posts = []
        new_posted_articles = []
        
        for i, news in enumerate(new_news):
            # Add 10-second delay between posts, except for the first post
            if i > 0:
                print("\nWaiting 10 seconds before posting next article...")
                time.sleep(10)
                
            try:
                news_date = datetime.strptime(news['date'], "%d %m %Y %H:%M:%S").strftime("%B %d, %Y, %I:%M %p")
            except ValueError:
                news_date = news['date']
            
            # Format the content with proper spacing
            content = f"Published on {news_date}\n\n{news['full_content']}"
            # Ensure proper paragraph breaks
            content = content.replace('\n', '\n\n')
            post_id = post_to_blogger(news['title'], content, news['image_url'])
            if post_id:
                successful_posts += 1
                print(f"Successfully posted to Blogger with ID: {post_id}")
                # Add to new posted articles list
                new_posted_articles.append({
                    'url': news['link'],
                    'title': news['title'],
                    'post_id': post_id,
                    'date_posted': datetime.now().isoformat()
                })
            else:
                failed_posts.append({
                    'title': news['title'],
                    'content': content,
                    'image_url': news['image_url']
                })
                print(f"Failed to post to Blogger: {news['title']}")
        
        # Update log with successfully posted articles
        if new_posted_articles:
            update_log(new_posted_articles)
            # Update README.md with new articles
            update_news_md(new_news)
            print(f"Updated README.md with {len(new_news)} new articles")
        
        # Retry failed posts
        if failed_posts:
            print("\n=== Initial Posting Summary ===")
            print(f"Total new articles: {len(new_news)}")
            print(f"Successfully posted: {successful_posts}")
            print(f"Failed to post: {len(failed_posts)}")
            
            print("\nRetrying failed posts...")
            successful_retries, still_failed = retry_failed_posts(failed_posts)
            
            # Update final statistics
            successful_posts += successful_retries
            
            print("\n=== Final Posting Summary ===")
            print(f"Total new articles: {len(new_news)}")
            print(f"Successfully posted: {successful_posts}")
            print(f"Failed to post: {len(still_failed)}")
            
            if still_failed:
                print("\nStill failed posts:")
                for post in still_failed:
                    print(f"- {post['title']}")
                
                # Save failed posts to a file for manual review
                failed_posts_file = "failed_posts.json"
                with open(failed_posts_file, "w", encoding="utf-8") as f:
                    json.dump(still_failed, f, indent=4, ensure_ascii=False)
                print(f"\nFailed posts have been saved to {failed_posts_file} for manual review")
        else:
            print("\nPosting Summary:")
            print(f"Total new articles: {len(new_news)}")
            print(f"Successfully posted: {successful_posts}")
            print(f"Failed to post: 0")
    else:
        print("No new news to add.")

if __name__ == "__main__":
    main() 