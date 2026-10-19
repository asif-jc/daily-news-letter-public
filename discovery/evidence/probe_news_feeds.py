"""Probe configured feeds; keep retrieved article content in ignored local storage."""
import concurrent.futures
import json
from pathlib import Path
import sys
from datetime import datetime, timezone, timedelta
import time
import requests
import feedparser
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'src/mvp_news_aggregator'))
from sources import RSS_FEEDS

def probe(item):
    category,source=item
    started=time.monotonic()
    row={'category':category,'source':source['name'],'url':source['url']}
    articles=[]
    try:
        response=requests.get(source['url'],timeout=(5,15),headers={'User-Agent':'NewsletterDiscovery/1.0'})
        row.update(status=response.status_code,final_url=response.url,content_type=response.headers.get('content-type'))
        if response.ok:
            feed=feedparser.parse(response.content)
            entries=feed.entries[:50]
            recent=unknown=basic=0
            for entry in entries:
                parsed=entry.get('published_parsed') or entry.get('updated_parsed')
                published=datetime(*parsed[:6],tzinfo=timezone.utc) if parsed else None
                desc=entry.get('summary') or entry.get('description') or ''
                from bs4 import BeautifulSoup
                desc=BeautifulSoup(desc,'html.parser').get_text(' ',strip=True)[:500]
                title=entry.get('title','')
                # Match the production rule that treats undated entries as fresh.
                in_window=published is None or published >= datetime.now(timezone.utc)-timedelta(hours=24)
                recent+=int(in_window)
                unknown+=int(published is None)
                eligible=in_window and len(desc.strip())>30 and 'sponsored' not in title.lower()
                basic+=int(eligible)
                if eligible:
                    articles.append({'title':title,'url':entry.get('link',''),'description':desc,'category':category,'source':source['name'],'published':published.isoformat() if published else None})
            row.update(entries=len(feed.entries),considered=len(entries),recent_24h=recent,unknown_dates=unknown,basic_eligible=basic,parse_warning=bool(feed.bozo))
    except requests.RequestException as e:
        row['error_type']=type(e).__name__
    row['seconds']=round(time.monotonic()-started,2)
    return row,articles

items=[(category,source) for category,sources in RSS_FEEDS.items() for source in sources]
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
    results=list(pool.map(probe,items))
summary={'checked_at':datetime.now(timezone.utc).isoformat(),'feeds':[r for r,a in results],'configured_empty_categories':[c for c,s in RSS_FEEDS.items() if not s]}
articles=[a for row,entries in results for a in entries]
Path('.local/news-candidates.json').write_text(json.dumps(articles,indent=2))
Path('discovery/evidence/news-feed-health.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary,indent=2))
