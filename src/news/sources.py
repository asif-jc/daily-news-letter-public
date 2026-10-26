"""Approved public source feeds and publisher hosts."""

RSS_FEEDS = {
    "world": [
        {"name": "BBC World News", "url": "https://feeds.bbci.co.uk/news/world/rss.xml"}
    ],
    "tech": [
        {"name": "TechCrunch", "url": "https://techcrunch.com/feed/"},
        {
            "name": "Ars Technica",
            "url": "https://feeds.arstechnica.com/arstechnica/index",
        },
    ],
    "finance": [
        {
            "name": "CNBC Finance",
            "url": "https://www.cnbc.com/id/10001147/device/rss/rss.html",
        }
    ],
    "nz": [
        {"name": "RNZ Politics", "url": "https://www.rnz.co.nz/rss/political.xml"},
        {"name": "RNZ Business", "url": "https://www.rnz.co.nz/rss/business.xml"},
    ],
}

PUBLISHER_HOSTS = (
    "bbc.co.uk",
    "bbc.com",
    "techcrunch.com",
    "arstechnica.com",
    "cnbc.com",
    "rnz.co.nz",
)
FEED_HOSTS = PUBLISHER_HOSTS + ("bbci.co.uk",)
