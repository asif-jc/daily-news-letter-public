import os
import sendgrid
from sendgrid.helpers.mail import Mail
from datetime import datetime
import pytz
import json
from typing import Dict, List, Optional
from dotenv import load_dotenv

# Load environment variables - try multiple paths
load_dotenv("../../config.env")
load_dotenv("../config.env")
load_dotenv("config.env")

# Debug: Check if API key is loaded
api_key = os.getenv('SENDGRID_API_KEY')
print(f"DEBUG: SENDGRID_API_KEY loaded: {'Yes' if api_key else 'No'}")
if api_key:
    print(f"DEBUG: API key starts with: {api_key[:10]}...")

class EmailNewsletterSender:
    def __init__(self):
        self.sendgrid_api_key = os.getenv('SENDGRID_API_KEY')
        if not self.sendgrid_api_key:
            raise ValueError("SENDGRID_API_KEY environment variable not set")
        
        self.sg = sendgrid.SendGridAPIClient(api_key=self.sendgrid_api_key)
        self.from_email = "asif.cheena20102001@gmail.com"
        self.from_name = "Daily News Feed"
        self.newsletter_url = "https://asif-jc.github.io/daily-news-letter-public/"
    
    def get_nz_date(self) -> str:
        """Get current date in New Zealand timezone"""
        nz_tz = pytz.timezone('Pacific/Auckland')
        nz_time = datetime.now(nz_tz)
        return nz_time.strftime('%Y-%m-%d')
    
    def load_subscribers(self, path: str = 'sub_information.json') -> Dict:
        """Load subscriber data from JSON file"""
        try:
            if not os.path.exists(path):
                print(f"Subscriber data not found at {path}")
                return {}
            
            with open(path, 'r', encoding='utf-8') as f:
                subscriber_data = json.load(f)
            
            subscribers = subscriber_data.get('email_subscriptions', {})
            print(f"Loaded {len(subscribers)} subscribers")
            return subscribers
        except Exception as e:
            print(f"Error loading subscriber data: {e}")
            return {}
    
    def load_newsletter_data(self, path: str = 'data/loading/newsletter_curated.json') -> Dict:
        """Load curated newsletter data from JSON file"""
        try:
            with open(path, 'r', encoding='utf-8') as f:
                newsletter_data = json.load(f)
            
            category_names = {
                'world': 'Global News',
                'tech': 'Technology',
                'finance': 'Markets & Finance', 
                'nz': 'New Zealand'
            }
            
            for category, data in newsletter_data.items():
                for story in data.get('top_stories', []):
                    story['category_label'] = category
                    story['category_display'] = category_names.get(category, category.title())
                for read in data.get('quick_reads', []):
                    read['category_label'] = category
                    read['category_display'] = category_names.get(category, category.title())
            
            return newsletter_data
        except Exception as e:
            print(f"Error loading newsletter data: {e}")
            return {}
    
    def get_all_stories_for_email(self, data: Dict) -> List[Dict]:
        """Get all stories from newsletter data sorted by importance"""
        all_stories = []
        
        for category, articles in data.items():
            for story in articles.get('top_stories', []):
                story['story_type'] = 'top_story'
                all_stories.append(story)
            for read in articles.get('quick_reads', []):
                read['story_type'] = 'quick_read'
                all_stories.append(read)
        
        all_stories.sort(key=lambda x: x.get('importance_score', 0), reverse=True)
        return all_stories
    
    def format_published_date(self, published_str: str) -> str:
        """Format published date for email display"""
        if not published_str:
            return "Recent"
        
        try:
            pub_date = datetime.fromisoformat(published_str.replace('Z', '+00:00'))
            nz_tz = pytz.timezone('Pacific/Auckland')
            nz_date = pub_date.astimezone(nz_tz)
            return nz_date.strftime('%d %b %Y, %-I:%M %p %Z')
        except Exception:
            return "Recent"
    
    def generate_email_html(self, data: Dict) -> str:
        """Generate HTML email content"""
        date = self.get_nz_date()
        formatted_date = datetime.strptime(date, '%Y-%m-%d').strftime('%B %d, %Y')
        
        all_stories = self.get_all_stories_for_email(data)
        
        html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Daily News Feed - {formatted_date}</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif; line-height: 1.6; color: #333; margin: 0; padding: 0; background-color: #f8f9fa; }}
        .container {{ max-width: 600px; margin: 0 auto; background: white; }}
        .header {{ background: #2c3e50; color: white; padding: 2rem; text-align: center; }}
        .header h1 {{ font-size: 2rem; font-weight: 300; margin: 0 0 0.5rem 0; }}
        .header .date {{ font-size: 1rem; opacity: 0.9; }}
        .view-online {{ background: #667eea; padding: 1rem; text-align: center; }}
        .view-online a {{ color: white; text-decoration: none; font-weight: 600; font-size: 1.1rem; }}
        .content {{ padding: 1.5rem; }}
        .story {{ margin-bottom: 1.5rem; padding: 1rem; border-radius: 6px; background: #f8f9fa; border-left: 4px solid #667eea; }}
        .story.top_story {{ border-left-color: #dc3545; background: #fff5f5; }}
        .story.quick_read {{ border-left-color: #28a745; background: #f8fff9; padding: 0.75rem; }}
        .category-badge {{ display: inline-block; padding: 0.25rem 0.75rem; border-radius: 12px; font-size: 0.75rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 0.5rem; }}
        .category-badge.tech {{ background: #e3f2fd; color: #1976d2; }}
        .category-badge.world {{ background: #fff3e0; color: #f57c00; }}
        .category-badge.finance {{ background: #e8f5e8; color: #388e3c; }}
        .category-badge.nz {{ background: #f3e5f5; color: #7b1fa2; }}
        .story-title {{ font-size: 1.1rem; font-weight: 600; margin-bottom: 0.5rem; }}
        .story-title a {{ color: #2c3e50; text-decoration: none; }}
        .story-meta {{ font-size: 0.9rem; color: #6c757d; margin-bottom: 0.75rem; }}
        .story-summary {{ color: #495057; }}
        .footer {{ background: #2c3e50; color: white; padding: 1.5rem; text-align: center; font-size: 0.9rem; }}
        .footer a {{ color: #667eea; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Daily News Feed</h1>
            <div class="date">{formatted_date}</div>
        </div>
        
        <div class="view-online">
            <a href="{self.newsletter_url}">📖 View Full Newsletter Online</a>
        </div>
        
        <div class="content">'''
        
        for story in all_stories:
            story_type = story.get('story_type', 'story')
            category_label = story.get('category_label', '')
            category_display = story.get('category_display', '')
            
            html += f'''
            <div class="story {story_type}">
                <span class="category-badge {category_label}">{category_display}</span>
                <div class="story-title">
                    <a href="{story.get('url', '#')}">{story.get('title', 'No Title')}</a>
                </div>
                <div class="story-meta">{story.get('source', 'Unknown')} • {self.format_published_date(story.get('published'))}</div>'''
            
            if story.get('enhanced_summary'):
                html += f'<div class="story-summary">{story["enhanced_summary"]}</div>'
            elif story.get('llm_summary'):
                html += f'<div class="story-summary">{story["llm_summary"]}</div>'
            
            html += '</div>'
        
        html += f'''
        </div>
        
        <div class="footer">
            <p>Daily News Feed by AJC Analytics</p>
            <p><a href="{self.newsletter_url}">View Online</a> | <a href="mailto:asif.ajcanalytics@gmail.com">Feedback</a></p>
        </div>
    </div>
</body>
</html>'''
        
        return html
    
    def send_newsletter_email(self, test_email: Optional[str] = None) -> bool:
        """Send newsletter email to subscribers or test email"""
        try:
            newsletter_data = self.load_newsletter_data()
            if not newsletter_data:
                print("No newsletter data available")
                return False
            
            html_content = self.generate_email_html(newsletter_data)
            
            if test_email:
                recipients = [test_email]
                print(f"Sending test email to {test_email}")
            else:
                subscribers = self.load_subscribers()
                recipients = list(subscribers.keys())
                print(f"Sending newsletter to {len(recipients)} subscribers")
            
            if not recipients:
                print("No recipients found")
                return False
            
            date = self.get_nz_date()
            formatted_date = datetime.strptime(date, '%Y-%m-%d').strftime('%B %d, %Y')
            subject = f"Daily News Feed - {formatted_date}"
            
            success_count = 0
            for recipient in recipients:
                try:
                    message = Mail(
                        from_email=(self.from_email, self.from_name),
                        to_emails=recipient,
                        subject=subject,
                        html_content=html_content
                    )
                    
                    response = self.sg.send(message)
                    
                    if response.status_code in [200, 201, 202]:
                        success_count += 1
                        print(f"Email sent to {recipient}")
                    else:
                        print(f"Failed to send to {recipient}: {response.status_code}")
                        
                except Exception as e:
                    print(f"Error sending to {recipient}: {e}")
            
            print(f"Email sending complete: {success_count}/{len(recipients)} sent successfully")
            return success_count > 0
            
        except Exception as e:
            print(f"Error sending newsletter: {e}")
            return False

def send_test_email(email: str):
    """Send test newsletter to single email"""
    sender = EmailNewsletterSender()
    return sender.send_newsletter_email(test_email=email)

def send_newsletter():
    """Send newsletter to all subscribers"""
    sender = EmailNewsletterSender()
    return sender.send_newsletter_email()

if __name__ == "__main__":
    test_email = "asif.ajcanalytics@gmail.com"
    print(f"Sending test newsletter to {test_email}...")
    success = send_test_email(test_email)
    print(f"Test email sent: {success}")
