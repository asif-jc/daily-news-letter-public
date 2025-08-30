# Version Agentic - Newsletter Pipeline v2.0

**Services + Agents Architecture**

## Overview

This is the redesigned newsletter pipeline that separates concerns between:
- **Services**: Deterministic utilities (RSS collection, HTML generation, deployment)
- **Agents**: LLM-powered decision makers (article curation, content enhancement)
- **Coordinator**: Orchestrates the entire pipeline with robust error handling

## Architecture

```
src/version_agentic/
├── main.py                     # Entry point
├── coordinator/                # Pipeline orchestration
│   ├── pipeline_coordinator.py # Main coordinator
│   ├── state_manager.py        # Pipeline state tracking
│   └── config_loader.py        # Configuration management
├── services/                   # Deterministic utilities
│   ├── collector_service.py    # RSS fetching
│   ├── scraping_service.py     # Web content extraction
│   ├── generator_service.py    # HTML generation
│   └── deployment_service.py   # File operations
├── agents/                     # LLM-powered decision makers
│   ├── base_agent.py          # Agent interface
│   ├── curation_agent.py      # Article selection
│   └── enhancement_agent.py   # Content summarization
├── config/                     # YAML configurations
│   ├── pipeline.yaml          # Pipeline stages & behavior
│   ├── agents.yaml            # Agent configurations
│   └── sources.yaml           # RSS sources
└── utils/                      # Helper utilities
    ├── logging.py
    ├── retry.py
    └── validators.py
```

## Implementation Status

🔄 **In Development**: All files created but implementation pending

**Implementation Plan:**
1. **Phase 1**: Coordinator foundation + CollectorService
2. **Phase 2**: Migrate existing functionality to services
3. **Phase 3**: Create LangChain-based agents
4. **Phase 4**: Add advanced features (monitoring, personalization)

## Key Features

- **YAML-driven Configuration**: Pipeline behavior, agent settings, sources
- **Robust Error Handling**: Retries, timeouts, fallback strategies  
- **State Management**: Tracks intermediate results, timings, errors
- **Observability**: Comprehensive logging, debug state saving
- **Extensible**: Easy to add new services/agents

## Migration from MVP

The existing `mvp_news_aggregator` will be gradually migrated:
- `collector.py` → `services/collector_service.py`
- `curator.py` → `agents/curation_agent.py` + `agents/enhancement_agent.py`
- `web_newsletter.py` → `services/generator_service.py`
- New: `coordinator/pipeline_coordinator.py` for orchestration

## Future Enhancements

- **Dynamic Source Discovery**: Agents that find new RSS sources
- **Personalization Agents**: User preference learning
- **Quality Monitoring**: Content quality scoring
- **Email Integration**: Subscriber management and delivery
