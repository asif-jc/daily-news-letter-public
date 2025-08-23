# import sqlite3
# import hashlib
# import json
# from datetime import datetime, timezone
# from pathlib import Path
# from typing import Dict, List, Optional, Any
# import logging

# logger = logging.getLogger(__name__)

# class NewsletterDB:
#     def __init__(self, db_path: str = "data/newsletter.db"):
#         self.db_path = Path(db_path)
#         self.init_database()
    
#     def get_connection(self):
#         """Get a database connection"""
#         conn = sqlite3.connect(self.db_path)
#         conn.row_factory = sqlite3.Row  # Enable dict-like access
#         return conn
    
#     def init_database(self):
#         """Initialize database with tables and indexes"""
#         with self.get_connection() as conn:
#             # Articles table
#             conn.execute("""
#                 CREATE TABLE IF NOT EXISTS articles (
#                     id INTEGER PRIMARY KEY AUTOINCREMENT,
#                     title TEXT NOT NULL,
#                     url TEXT NOT NULL,
#                     description TEXT,
#                     source TEXT NOT NULL,
#                     category TEXT NOT NULL,
#                     published DATETIME NOT NULL,
#                     fetched_at DATETIME NOT NULL,
#                     content_hash TEXT UNIQUE,
#                     word_count INTEGER DEFAULT NULL,
#                     selected_for_newsletter BOOLEAN DEFAULT NULL,
#                     newsletter_date DATE DEFAULT NULL,
#                     priority_score REAL DEFAULT NULL,
#                     click_count INTEGER DEFAULT 0
#                 )
#             """)
            
#             # Subscribers table
#             conn.execute("""
#                 CREATE TABLE IF NOT EXISTS subscribers (
#                     id INTEGER PRIMARY KEY AUTOINCREMENT,
#                     email TEXT UNIQUE NOT NULL,
#                     name TEXT DEFAULT NULL,
#                     active BOOLEAN DEFAULT TRUE,
#                     preferences TEXT DEFAULT NULL,
#                     frequency TEXT DEFAULT 'daily',
#                     timezone TEXT DEFAULT 'Pacific/Auckland',
#                     created_at DATETIME NOT NULL,
#                     updated_at DATETIME NOT NULL,
#                     last_sent DATETIME DEFAULT NULL,
#                     open_count INTEGER DEFAULT 0,
#                     click_count INTEGER DEFAULT 0
#                 )
#             """)
            
#             # Create indexes for performance
#             conn.execute("CREATE INDEX IF NOT EXISTS idx_articles_category ON articles(category)")
#             conn.execute("CREATE INDEX IF NOT EXISTS idx_articles_published ON articles(published)")
#             conn.execute("CREATE INDEX IF NOT EXISTS idx_articles_newsletter_date ON articles(newsletter_date)")
#             conn.execute("CREATE INDEX IF NOT EXISTS idx_articles_selected ON articles(selected_for_newsletter)")
#             conn.execute("CREATE INDEX IF NOT EXISTS idx_subscribers_active ON subscribers(active)")
#             conn.execute("CREATE INDEX IF NOT EXISTS idx_subscribers_frequency ON subscribers(frequency)")
            
#             conn.commit()
#             logger.info("Database initialized successfully")
    
    
#     def normalize_url(self, url: str) -> str:
#         """Remove common tracking parameters from URLs"""
#         import urllib.parse as urlparse
        
#         parsed = urlparse.urlparse(url)
        
#         # Remove common tracking parameters
#         query_params = urlparse.parse_qs(parsed.query)
#         tracking_params = ['utm_source', 'utm_medium', 'utm_campaign', 'utm_content', 
#                         'utm_term', 'ref', 'source', 'fbclid', 'gclid']
        
#         for param in tracking_params:
#             query_params.pop(param, None)
        
#         # Rebuild URL without tracking params
#         clean_query = urlparse.urlencode(query_params, doseq=True)
#         clean_url = urlparse.urlunparse((
#             parsed.scheme, parsed.netloc, parsed.path,
#             parsed.params, clean_query, ''  # Remove fragment too
#         ))
        
#         return clean_url.rstrip('/')


#     def generate_content_hash(self, title: str, url: str) -> str:
#         """Generate a hash for duplicate detection"""
#         normalized_url = self.normalize_url(url)
#         content = f"{title.strip().lower()}|{normalized_url}"
#         return hashlib.md5(content.encode()).hexdigest()
    
#     def count_words(self, text: str) -> int:
#         """Simple word count for description"""
#         if not text:
#             return 0
#         return len(text.split())
    
#     # ARTICLES CRUD OPERATIONS
    
#     def insert_article(self, article: Dict) -> Optional[int]:
#         """Insert a single article, return ID if successful"""
#         try:
#             # Generate content hash and word count
#             content_hash = self.generate_content_hash(article['title'], article['url'])
#             word_count = self.count_words(article.get('description', ''))
            
#             with self.get_connection() as conn:
#                 cursor = conn.execute("""
#                     INSERT INTO articles (
#                         title, url, description, source, category, 
#                         published, fetched_at, content_hash, word_count
#                     ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
#                 """, (
#                     article['title'],
#                     article['url'],
#                     article.get('description'),
#                     article['source'],
#                     article['category'],
#                     article['published'],
#                     article['fetched_at'],
#                     content_hash,
#                     word_count
#                 ))
                
#                 article_id = cursor.lastrowid
#                 logger.info(f"Inserted article: {article['title'][:50]}... (ID: {article_id})")
#                 return article_id
                
#         except sqlite3.IntegrityError:
#             logger.warning(f"Duplicate article skipped: {article['title'][:50]}...")
#             return None
#         except Exception as e:
#             logger.error(f"Error inserting article: {e}")
#             return None
    
#     def insert_articles_batch(self, articles: List[Dict]) -> int:
#         """Insert multiple articles, return count of successful inserts"""
#         inserted_count = 0
#         for article in articles:
#             if self.insert_article(article):
#                 inserted_count += 1
        
#         logger.info(f"Batch insert complete: {inserted_count}/{len(articles)} articles inserted")
#         return inserted_count
    
#     def get_articles_by_category(self, category: str, limit: int = 50) -> List[Dict]:
#         """Get recent articles by category"""
#         with self.get_connection() as conn:
#             cursor = conn.execute("""
#                 SELECT * FROM articles 
#                 WHERE category = ? 
#                 ORDER BY published DESC 
#                 LIMIT ?
#             """, (category, limit))
            
#             return [dict(row) for row in cursor.fetchall()]
    
#     def get_articles_for_newsletter(self, newsletter_date: str = None) -> Dict[str, List[Dict]]:
#         """Get articles selected for newsletter, grouped by category"""
#         query = """
#             SELECT * FROM articles 
#             WHERE selected_for_newsletter = 1
#         """
#         params = []
        
#         if newsletter_date:
#             query += " AND newsletter_date = ?"
#             params.append(newsletter_date)
        
#         query += " ORDER BY category, priority_score DESC, published DESC"
        
#         with self.get_connection() as conn:
#             cursor = conn.execute(query, params)
#             articles = [dict(row) for row in cursor.fetchall()]
        
#         # Group by category
#         grouped = {}
#         for article in articles:
#             category = article['category']
#             if category not in grouped:
#                 grouped[category] = []
#             grouped[category].append(article)
        
#         return grouped
    
#     def mark_articles_for_newsletter(self, article_ids: List[int], newsletter_date: str):
#         """Mark specific articles for inclusion in newsletter"""
#         with self.get_connection() as conn:
#             placeholders = ','.join(['?'] * len(article_ids))
#             conn.execute(f"""
#                 UPDATE articles 
#                 SET selected_for_newsletter = 1, newsletter_date = ?
#                 WHERE id IN ({placeholders})
#             """, [newsletter_date] + article_ids)
            
#             conn.commit()
#             logger.info(f"Marked {len(article_ids)} articles for newsletter {newsletter_date}")
    
#     # SUBSCRIBERS CRUD OPERATIONS
    
#     def add_subscriber(self, email: str, name: str = None, preferences: Dict = None) -> Optional[int]:
#         """Add a new subscriber"""
#         try:
#             now = datetime.now(timezone.utc)
#             preferences_json = json.dumps(preferences) if preferences else None
            
#             with self.get_connection() as conn:
#                 cursor = conn.execute("""
#                     INSERT INTO subscribers (
#                         email, name, preferences, created_at, updated_at
#                     ) VALUES (?, ?, ?, ?, ?)
#                 """, (email, name, preferences_json, now, now))
                
#                 subscriber_id = cursor.lastrowid
#                 logger.info(f"Added subscriber: {email} (ID: {subscriber_id})")
#                 return subscriber_id
                
#         except sqlite3.IntegrityError:
#             logger.warning(f"Subscriber already exists: {email}")
#             return None
#         except Exception as e:
#             logger.error(f"Error adding subscriber: {e}")
#             return None
    
#     def get_active_subscribers(self, frequency: str = None) -> List[Dict]:
#         """Get active subscribers, optionally filtered by frequency"""
#         query = "SELECT * FROM subscribers WHERE active = 1"
#         params = []
        
#         if frequency:
#             query += " AND frequency = ?"
#             params.append(frequency)
        
#         with self.get_connection() as conn:
#             cursor = conn.execute(query, params)
#             return [dict(row) for row in cursor.fetchall()]
    
#     def update_subscriber_last_sent(self, subscriber_id: int):
#         """Update the last_sent timestamp for a subscriber"""
#         now = datetime.now(timezone.utc)
#         with self.get_connection() as conn:
#             conn.execute("""
#                 UPDATE subscribers 
#                 SET last_sent = ?, updated_at = ?
#                 WHERE id = ?
#             """, (now, now, subscriber_id))
#             conn.commit()
    
#     def deactivate_subscriber(self, email: str):
#         """Deactivate a subscriber (unsubscribe)"""
#         now = datetime.now(timezone.utc)
#         with self.get_connection() as conn:
#             cursor = conn.execute("""
#                 UPDATE subscribers 
#                 SET active = 0, updated_at = ?
#                 WHERE email = ?
#             """, (now, email))
            
#             if cursor.rowcount > 0:
#                 logger.info(f"Deactivated subscriber: {email}")
#                 return True
#             else:
#                 logger.warning(f"Subscriber not found: {email}")
#                 return False
    
#     # UTILITY METHODS
    
#     def get_stats(self) -> Dict[str, Any]:
#         """Get database statistics"""
#         with self.get_connection() as conn:
#             # Article stats
#             article_cursor = conn.execute("""
#                 SELECT 
#                     COUNT(*) as total_articles,
#                     COUNT(CASE WHEN selected_for_newsletter = 1 THEN 1 END) as selected_articles,
#                     COUNT(DISTINCT category) as categories,
#                     COUNT(DISTINCT source) as sources
#                 FROM articles
#             """)
#             article_stats = dict(article_cursor.fetchone())
            
#             # Subscriber stats
#             subscriber_cursor = conn.execute("""
#                 SELECT 
#                     COUNT(*) as total_subscribers,
#                     COUNT(CASE WHEN active = 1 THEN 1 END) as active_subscribers
#                 FROM subscribers
#             """)
#             subscriber_stats = dict(subscriber_cursor.fetchone())
            
#             return {**article_stats, **subscriber_stats}
    
#     def cleanup_old_articles(self, days_old: int = 30):
#         """Remove articles older than specified days"""
#         cutoff_date = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
#         cutoff_date = cutoff_date.replace(day=cutoff_date.day - days_old)
        
#         with self.get_connection() as conn:
#             cursor = conn.execute("""
#                 DELETE FROM articles 
#                 WHERE published < ? AND selected_for_newsletter IS NULL
#             """, (cutoff_date,))
            
#             deleted_count = cursor.rowcount
#             conn.commit()
#             logger.info(f"Cleaned up {deleted_count} old articles")
#             return deleted_count

# # # Test function
# # def test_database():
# #     """Test database operations"""
# #     db = NewsletterDB("test_newsletter.db")
    
# #     # Test article insertion
# #     test_article = {
# #         'title': 'Test Article',
# #         'url': 'https://example.com/test',
# #         'description': 'This is a test article with some content.',
# #         'source': 'Test Source',
# #         'category': 'tech',
# #         'published': datetime.now(timezone.utc),
# #         'fetched_at': datetime.now(timezone.utc)
# #     }
    
# #     article_id = db.insert_article(test_article)
# #     print(f"Inserted article with ID: {article_id}")
    
# #     # Test subscriber insertion
# #     subscriber_id = db.add_subscriber("test@example.com", "Test User", {"categories": ["tech", "finance"]})
# #     print(f"Inserted subscriber with ID: {subscriber_id}")
    
# #     # Test stats
# #     stats = db.get_stats()
# #     print(f"Database stats: {stats}")

# # if __name__ == "__main__":
# #     test_database()