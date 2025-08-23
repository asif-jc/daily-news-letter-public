import json

from collector import ArticleCollector
from sources import RSS_FEEDS
# from database import NewsletterDB
# from subscribers import add_subscribers
from curator import ArticleCurator
from db_utils import *
from scrapper import *
from web_newsletter import NewsletterGenerator
from web_newsletter import generate_newsletter

def run_daily_pipeline(): 
    # 1. Collect articles
    collector = ArticleCollector(RSS_FEEDS)
    results = collector.collect_all()
    
    # 2. Curate with LLM
    curator = ArticleCurator()
    newsletter_data = curator.curate_newsletter(results, hours=24)
    with open('data/loading/newsletter_curated.json', 'w') as f:
        json.dump(newsletter_data, f, indent=2)

    # 3. Generate HTML
    html = generate_newsletter()
    
    return newsletter_data


if __name__ == "__main__":
    run_daily_pipeline()


