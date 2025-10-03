import json
import argparse

from collector import ArticleCollector
from sources import RSS_FEEDS
# from database import NewsletterDB
# from subscribers import add_subscribers
from curator import ArticleCurator
from db_utils import *
from scrapper import *
from web_newsletter import NewsletterGenerator, generate_newsletter, regenerate_newsletter_with_nzt
from quiz_data import pull_quiz_data
from foreign_exchange_data import pull_fx_data
from market_data import pull_market_data
from email_newsletter_sender import send_newsletter, send_test_email

def run_daily_pipeline(use_llm: bool = True, send_email: bool = False, test_email: str = None): 
    # 1. Collect articles
    collector = ArticleCollector(RSS_FEEDS)
    results = collector.collect_all()
    
    # 2. Curate with LLM
    curator = ArticleCurator(use_llm=use_llm)
    newsletter_data = curator.curate_newsletter(results, hours=24)
    with open('data/loading/newsletter_curated.json', 'w') as f:
        json.dump(newsletter_data, f, indent=2)

    # 3. Pull quiz data
    quiz_data = pull_quiz_data(use_llm=use_llm)
    print(f"Quiz data status: {quiz_data.get('status')}")
    
    # 3.5. Pull foreign exchange data
    fx_data = pull_fx_data()
    print(f"FX data status: {fx_data.get('status')}")
    
    # 3.6. Pull market data (ETF prices)
    market_data = pull_market_data()
    print(f"Market data status: {market_data.get('status')}")

    # 4. Generate HTML
    html = generate_newsletter()
    
    # 5. Send email if requested
    if send_email:
        if test_email:
            email_success = send_test_email(test_email)
            print(f"Test email sent: {email_success}")
        else:
            email_success = send_newsletter()
            print(f"Newsletter email sent: {email_success}")
    
    return newsletter_data


if __name__ == "__main__":
    
    RUN_ETL = True
    USE_LLM = False

    if RUN_ETL:
        run_daily_pipeline(use_llm=USE_LLM, send_email=True, test_email="asif.cheena20102001@gmail.com")
    else:
        regenerate_newsletter_with_nzt()


