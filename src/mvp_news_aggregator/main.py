import json

from collector import ArticleCollector
from sources import RSS_FEEDS
# from database import NewsletterDB
# from subscribers import add_subscribers
from curator import ArticleCurator
from db_utils import *
from scrapper import *
from web_newsletter import NewsletterGenerator, generate_newsletter, regenerate_newsletter_with_nzt

def run_daily_pipeline(use_llm: bool = True): 
    # 1. Collect articles
    collector = ArticleCollector(RSS_FEEDS)
    results = collector.collect_all()
    
    # 2. Curate with optional LLM
    curator = ArticleCurator(use_llm=use_llm)
    newsletter_data = curator.curate_newsletter(results, hours=24)
    with open('data/loading/newsletter_curated.json', 'w') as f:
        json.dump(newsletter_data, f, indent=2)

    # 3. Generate HTML
    html = generate_newsletter()
    
    return newsletter_data


if __name__ == "__main__":
    
    RUN_ETL = True
    USE_LLM = False  # Toggle this to enable/disable LLM processing

    if RUN_ETL:
        run_daily_pipeline(use_llm=USE_LLM)
    else:
        regenerate_newsletter_with_nzt()


