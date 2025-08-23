# from typing import List, Dict, Optional

# from database import NewsletterDB


# def add_subscribers(subscribers_data: List[Dict], db_path: str = "data/newsletter.db"):
#     """
#     Simple function to add multiple subscribers
    
#     subscribers_data format:
#     [
#         {"email": "john@example.com", "name": "John Smith"},
#         {"email": "jane@example.com", "name": "Jane Doe", "preferences": {"categories": ["tech", "finance"]}},
#         {"email": "bob@example.com"}  # name and preferences optional
#     ]
#     """
#     db = NewsletterDB(db_path)
    
#     for subscriber in subscribers_data:
#         email = subscriber.get('email')
#         name = subscriber.get('name')
#         preferences = subscriber.get('preferences')
        
#         if email:
#             subscriber_id = db.add_subscriber(email, name, preferences)
#             if subscriber_id:
#                 print(f"Added: {email} (ID: {subscriber_id})")
#             else:
#                 print(f"Skipped: {email} (already exists or error)")
#         else:
#             print(f"Skipped invalid subscriber: {subscriber}")