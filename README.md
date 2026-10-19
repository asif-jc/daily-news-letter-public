# 📰 Daily Newsletter Generator

**Webletter URL** - https://asif-jc.github.io/daily-news-letter-public/

**Version 1.5** - Automated AI-curated newsletter system with GitHub Pages deployment

---

The news-only replacement is being developed as a local review workflow. See [its setup, stage artifacts, and limits](src/news/README.md). It does not publish or send email; the existing deployment path remains in place until review.

## 🚀 Version 2 Roadmap

**Upcoming Features:**
- **Hourly Critical Coverage** - New priority section for breaking news
- **Agentic Workflow** - Migration to LangChain or Google AI SDK for improved automation
- **Email Subscription** - Email out daily and critical articles to a subset of users
- **User Defines Preference** - User can define preference and refresh pipeline on this information (incurs uncertain LLM usage has cost complexity)
- **Market and Index Data** - Commodity index prices
- **Foreign Exchange (FX) Data** - NZD/USD, NZD/AUD, NZD/INR
---

## 📋 Overview

An intelligent newsletter system that automatically collects, curates, and publishes daily news from multiple RSS sources. Uses Google's Gemini AI to select and summarize the most important stories across Technology, Finance, World News, and New Zealand categories.

**🌐 Live Newsletter:** [View Latest Edition](https://asif-jc.github.io/daily-news-letter-public/)

## ✨ Features

### 🔄 **Automated Pipeline**
- Daily execution via GitHub Actions (8 PM UTC)
- RSS feed aggregation from trusted news sources
- AI-powered content curation and summarization
- Automatic deployment to GitHub Pages

### 🤖 **AI Content Curation**
- **Google Gemini Integration** for intelligent article selection
- **Top Stories** - 3 major developments with detailed summaries
- **Quick Reads** - 5 secondary stories with brief explanations  
- **Content Enhancement** - Web scraping for deeper article analysis

### 📊 **Multi-Category Coverage**
- **World News** - BBC World, CNN International
- **Technology** - TechCrunch, Ars Technica  
- **Finance** - Yahoo Finance, CNBC, Investing.com
- **New Zealand** - Local news sources (configurable)

### 🗂️ **Data Management**
- JSON-based storage system (GitHub Actions compatible)
- Automatic deduplication using content hashing
- Timestamped backups and article archiving

---

## 🏗️ Architecture

```
┌─────────────────┐    ┌──────────────┐    ┌─────────────────┐
│   RSS Sources   │───▶│  Collector   │───▶│    Curator      │
│                 │    │              │    │   (Gemini AI)   │
└─────────────────┘    └──────────────┘    └─────────────────┘
                                                    │
┌─────────────────┐    ┌──────────────┐    ┌─────────────────┐
│  GitHub Pages   │◀───│   Generator  │◀───│  JSON Storage   │
│   (Website)     │    │    (HTML)    │    │                 │
└─────────────────┘    └──────────────┘    └─────────────────┘
```

### Core Components

**📥 Article Collector** (`collector.py`)
- Fetches RSS feeds from configured sources
- Generates unique content hashes for deduplication  
- Handles multiple date formats and content cleaning

**🎯 Content Curator** (`curator.py`)
- Filters recent articles (configurable time window)
- Uses Gemini AI to select most important stories
- Scrapes full article content for top stories
- Generates enhanced summaries and explanations

**📰 Newsletter Generator** (`web_newsletter.py`)
- Creates responsive HTML newsletter layout
- Organizes content by category and importance
- Includes publication metadata and styling

**⚙️ Pipeline Orchestrator** (`main.py`)
- Coordinates the entire workflow
- Manages data flow between components
- Handles both fresh generation and cached modes

---

## 🛠️ Technical Setup

### Prerequisites
- Python 3.11+
- Google Gemini API key
- GitHub repository with Pages enabled

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/your-username/daily-news-letter-public.git
   cd daily-news-letter-public
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment**
   ```bash
   cp config.env.example config.env
   # Add your GEMINI_API_KEY
   ```

4. **Set up GitHub Secrets**
   - Add `GEMINI_API_KEY` to repository secrets
   - Enable GitHub Pages in repository settings

### Local Development

**Generate newsletter locally:**
```bash
python src/mvp_news_aggregator/main.py
```

**View generated content:**
- Newsletter: `newsletter.html`
- Raw data: `data/loading/newsletter_curated.json`

---

## 📁 Project Structure

```
├── src/mvp_news_aggregator/    # Core application code
│   ├── collector.py            # RSS feed collection
│   ├── curator.py              # AI content curation  
│   ├── web_newsletter.py       # HTML generation
│   ├── sources.py              # RSS feed configuration
│   └── main.py                 # Pipeline orchestration
├── .github/workflows/          # GitHub Actions automation
├── data/loading/               # JSON data storage
├── assets/                     # Stylesheet and images
├── docs/                       # Generated site files
└── requirements.txt            # Python dependencies
```

---

## ⚙️ Configuration

### RSS Sources (`sources.py`)
```python
RSS_FEEDS = {
    "tech": [
        {"name": "TechCrunch", "url": "https://techcrunch.com/feed/"},
        {"name": "Ars Technica", "url": "http://feeds.arstechnica.com/arstechnica/index"}
    ],
    # Add more categories and sources
}
```

### Content Curation Settings
- **Article Age Filter**: 24 hours (configurable)
- **Top Stories**: 3 per category
- **Quick Reads**: 5 per category
- **Content Enhancement**: Full text scraping for top stories

### Deployment Schedule
- **Automated**: Daily at 8 PM UTC
- **Manual**: Trigger via GitHub Actions interface

---

## 🔍 Data Flow

1. **Collection Phase**
   - Fetch RSS feeds from all configured sources
   - Parse and normalize article metadata
   - Generate unique IDs for deduplication
   - Save raw articles with timestamps

2. **Curation Phase**  
   - Filter articles by recency and quality
   - Group articles by news category
   - Use Gemini AI to select most important stories
   - Scrape full content for detailed summaries

3. **Generation Phase**
   - Create responsive HTML newsletter
   - Organize content by importance level
   - Apply consistent styling and branding
   - Generate both current and dated versions

4. **Deployment Phase**
   - Copy assets and HTML to docs/ directory
   - Deploy via GitHub Actions to Pages
   - Archive previous versions for history

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)  
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Development Guidelines
- Follow existing code structure and naming conventions
- Test changes with local newsletter generation
- Update documentation for new features
- Ensure GitHub Actions compatibility

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- **Google Gemini AI** for intelligent content curation
- **RSS Sources** for providing structured news feeds  
- **GitHub Pages** for free hosting and deployment
- **BeautifulSoup & Feedparser** for robust content parsing

---

*Built with ❤️ for staying informed in our fast-moving world*
