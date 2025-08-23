# import os
# import sendgrid
# from sendgrid.helpers.mail import Mail, To, Content
# from typing import List, Dict
# from datetime import datetime
# from database import NewsletterDB
# import logging

# logger = logging.getLogger(__name__)

# class NewsletterEmailSender:
#     def __init__(self, db_path: str = "data/newsletter.db"):
#         self.db = NewsletterDB(db_path)
#         self.sendgrid_api_key = os.getenv('SENDGRID_API_KEY')
#         self.sg = sendgrid.SendGridAPIClient(api_key=self.sendgrid_api_key)
        
#         # Email configuration
#         self.from_email = "news@ajcanalytics.com"  # You'll need a domain
#         self.from_name = "AJC Analytics Daily News"
        
#     def get_active_subscribers(self) -> List[Dict]:
#         """Get all active subscribers from database"""
#         return self.db.get_active_subscribers()
    
#     def generate_simple_email_html(self, newsletter_date: str = None) -> str:
#         """Generate simplified HTML for email (not the full web version)"""
#         if not newsletter_date:
#             newsletter_date = datetime.now().strftime('%Y-%m-%d')
        
#         # Load curated data
#         with self.db.get_connection() as conn:
#             cursor = conn.execute("""
#                 SELECT * FROM newsletter_curated 
#                 WHERE newsletter_date = ?
#                 ORDER BY tier, importance_score DESC
#             """, (newsletter_date,))
#             articles = [dict(row) for row in cursor.fetchall()]
        
#         if not articles:
#             return None
        
#         # Separate by tier
#         top_stories = [a for a in articles if a['tier'] == 'top_story'][:5]
#         quick_reads = [a for a in articles if a['tier'] == 'quick_read'][:8]
        
#         formatted_date = datetime.strptime(newsletter_date, '%Y-%m-%d').strftime('%B %d, %Y')
        
#         # Simple email template
#         html = f"""
#         <html>
#         <head>
#             <meta charset="UTF-8">
#             <meta name="viewport" content="width=device-width, initial-scale=1.0">
#             <style>
#                 body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; }}
#                 .header {{ background: #2c3e50; color: white; padding: 20px; text-align: center; }}
#                 .content {{ padding: 20px; }}
#                 .article {{ margin-bottom: 20px; padding-bottom: 15px; border-bottom: 1px solid #eee; }}
#                 .article-title {{ font-weight: bold; margin-bottom: 5px; }}
#                 .article-title a {{ color: #2c3e50; text-decoration: none; }}
#                 .article-meta {{ font-size: 12px; color: #666; margin-bottom: 8px; }}
#                 .article-summary {{ color: #555; }}
#                 .view-online {{ background: #f8f9fa; padding: 15px; text-align: center; margin: 20px 0; }}
#                 .footer {{ background: #f8f9fa; padding: 20px; text-align: center; font-size: 12px; color: #666; }}
#             </style>
#         </head>
#         <body>
#             <div class="header">
#                 <h1>Daily News Feed</h1>
#                 <p>{formatted_date}</p>
#             </div>
            
#             <div class="view-online">
#                 <a href="https://your-domain.com/newsletter/{newsletter_date}" style="color: #667eea; text-decoration: none; font-weight: bold;">
#                     📖 View Full Newsletter Online
#                 </a>
#             </div>
            
#             <div class="content">
#                 <h2 style="color: #2c3e50;">Today's Top Stories</h2>
#         """
        
#         # Add top stories
#         for story in top_stories:
#             html += f"""
#                 <div class="article">
#                     <div class="article-title">
#                         <a href="{story['url']}">{story['title']}</a>
#                     </div>
#                     <div class="article-meta">{story['source']} • {story['category'].title()}</div>
#                     <div class="article-summary">{story.get('llm_summary', '')[:200]}...</div>
#                 </div>
#             """
        
#         # Add quick reads section
#         if quick_reads:
#             html += "<h2 style='color: #2c3e50;'>Worth Monitoring</h2>"
#             for read in quick_reads:
#                 html += f"""
#                     <div class="article">
#                         <div class="article-title">
#                             <a href="{read['url']}">{read['title']}</a>
#                         </div>
#                         <div class="article-meta">{read['source']} • {read['category'].title()}</div>
#                     </div>
#                 """
        
#         html += """
#             </div>
            
#             <div class="footer">
#                 <p>Daily News Feed by AJC Analytics</p>
#                 <p><a href="{{unsubscribe}}">Unsubscribe</a> | <a href="mailto:asif.ajcanalytics@gmail.com">Feedback</a></p>
#             </div>
#         </body>
#         </html>
#         """
        
#         return html
    
#     def generate_text_version(self, newsletter_date: str = None) -> str:
#         """Generate plain text version for email clients that don't support HTML"""
#         if not newsletter_date:
#             newsletter_date = datetime.now().strftime('%Y-%m-%d')
        
#         # Load curated data
#         with self.db.get_connection() as conn:
#             cursor = conn.execute("""
#                 SELECT * FROM newsletter_curated 
#                 WHERE newsletter_date = ?
#                 ORDER BY tier, importance_score DESC
#             """, (newsletter_date,))
#             articles = [dict(row) for row in cursor.fetchall()]
        
#         formatted_date = datetime.strptime(newsletter_date, '%Y-%m-%d').strftime('%B %d, %Y')
        
#         text = f"""
# DAILY NEWS FEED - {formatted_date}
# =====================================

# View full newsletter online: https://your-domain.com/newsletter/{newsletter_date}

# TOP STORIES
# -----------
# """
        
#         top_stories = [a for a in articles if a['tier'] == 'top_story'][:5]
#         for i, story in enumerate(top_stories, 1):
#             text += f"""
# {i}. {story['title']}
#    {story['source']} | {story['url']}
#    {story.get('llm_summary', '')[:150]}...

# """
        
#         quick_reads = [a for a in articles if a['tier'] == 'quick_read'][:8]
#         if quick_reads:
#             text += "\nWORTH MONITORING\n----------------\n"
#             for read in quick_reads:
#                 text += f"• {read['title']} ({read['source']})\n  {read['url']}\n\n"
        
#         text += """
# ---
# Daily News Feed by AJC Analytics
# Feedback: asif.ajcanalytics@gmail.com
# Unsubscribe: {unsubscribe}
# """
        
#         return text
    
#     def send_newsletter(self, newsletter_date: str = None, test_email: str = None) -> bool:
#         """Send newsletter to all subscribers or test email"""
#         try:
#             html_content = self.generate_simple_email_html(newsletter_date)
#             text_content = self.generate_text_version(newsletter_date)
            
#             if not html_content:
#                 logger.error("No newsletter content found for date")
#                 return False
            
#             # Get recipients
#             if test_email:
#                 recipients = [{"email": test_email, "name": "Test User"}]
#                 logger.info(f"Sending test email to {test_email}")
#             else:
#                 subscribers = self.get_active_subscribers()
#                 recipients = [{"email": sub['email'], "name": sub.get('name', '')} for sub in subscribers]
#                 logger.info(f"Sending newsletter to {len(recipients)} subscribers")
            
#             if not recipients:
#                 logger.warning("No recipients found")
#                 return False
            
#             # Prepare email
#             formatted_date = datetime.strptime(newsletter_date or datetime.now().strftime('%Y-%m-%d'), '%Y-%m-%d').strftime('%B %d, %Y')
#             subject = f"Daily News Feed - {formatted_date}"
            
#             # Send to each recipient
#             success_count = 0
#             for recipient in recipients:
#                 try:
#                     message = Mail(
#                         from_email=(self.from_email, self.from_name),
#                         to_emails=recipient['email'],
#                         subject=subject,
#                         html_content=html_content,
#                         plain_text_content=text_content
#                     )
                    
#                     response = self.sg.send(message)
                    
#                     if response.status_code in [200, 201, 202]:
#                         success_count += 1
#                         logger.info(f"Email sent to {recipient['email']}")
#                     else:
#                         logger.error(f"Failed to send to {recipient['email']}: {response.status_code}")
                        
#                 except Exception as e:
#                     logger.error(f"Error sending to {recipient['email']}: {e}")
            
#             logger.info(f"Newsletter sending complete: {success_count}/{len(recipients)} sent successfully")
#             return success_count > 0
            
#         except Exception as e:
#             logger.error(f"Error sending newsletter: {e}")
#             return False
    
#     def send_test_email(self, test_email: str, newsletter_date: str = None) -> bool:
#         """Send a test email to verify everything works"""
#         return self.send_newsletter(newsletter_date, test_email)

# # Usage functions
# def send_daily_newsletter(date: str = None):
#     """Send newsletter to all subscribers"""
#     sender = NewsletterEmailSender()
#     return sender.send_newsletter(date)

# def send_test_newsletter(email: str, date: str = None):
#     """Send test newsletter to single email"""
#     sender = NewsletterEmailSender()
#     return sender.send_test_email(email, date)

# if __name__ == "__main__":
#     # Test sending
#     test_email = "asif.ajcanalytics@gmail.com"
#     print(f"Sending test newsletter to {test_email}...")
#     success = send_test_newsletter(test_email)
#     print(f"Test email sent: {success}")