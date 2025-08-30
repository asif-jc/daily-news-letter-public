"""
Main pipeline coordinator - orchestrates services and agents
"""

# src/version_agentic/coordinator/pipeline_coordinator.py

import os
import sys
import json
import logging
import asyncio
from datetime import datetime
from typing import Dict, Any, Optional
from pathlib import Path

sys.path.append(os.getcwd())

class PipelineState:
    """Pipeline state management with minimal logging"""
    def __init__(self):
        self.data = {}
        self.start_time = datetime.now()
        self.stage_results = {}
    
    def set_stage_result(self, stage_name: str, result: Any):
        """Store result from a pipeline stage"""
        self.stage_results[stage_name] = result
    
    def get_stage_result(self, stage_name: str) -> Any:
        """Get result from previous stage"""
        return self.stage_results.get(stage_name)
    
    def save_json_output(self, newsletter_data: Dict, file_path: str = 'data/loading/newsletter_curated.json'):
        """Save newsletter data to JSON - exactly like MVP"""
        with open(file_path, 'w') as f:
            json.dump(newsletter_data, f, indent=2)

class PipelineCoordinator:
    """
    Pipeline orchestrator that replicates MVP functionality exactly
    
    Calls the same MVP classes (ArticleCollector, ArticleCurator, generate_newsletter)
    with improved structure and proper logging
    """
    
    def __init__(self, use_llm: bool = True):
        self.use_llm = use_llm
        self.state = PipelineState()
        self.logger = self._setup_logging()
        
        self.logger.info(f"Pipeline coordinator initialized (LLM enabled: {use_llm})")
    
    def _setup_logging(self):
        """Configure structured logging"""
        logger = logging.getLogger('NewsletterPipeline')
        
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                datefmt='%H:%M:%S'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
        
        return logger
    
    async def run_pipeline(self) -> Dict[str, Any]:
        """
        Execute complete pipeline - exact replica of run_daily_pipeline()
        
        Returns: newsletter_data dict (same as MVP)
        """
        pipeline_start = datetime.now()
        self.logger.info("Pipeline execution started")
        
        try:
            # Stage 1: Collection
            results = await self._run_collection_stage()
            self.state.set_stage_result('collection', results)
            
            # Stage 2: Curation  
            newsletter_data = await self._run_curation_stage(results)
            self.state.set_stage_result('curation', newsletter_data)
            
            # Stage 3: JSON persistence
            self.state.save_json_output(newsletter_data)
            self.state.set_stage_result('json_save', True)
            
            # Stage 4: HTML generation
            html_result = await self._run_generation_stage()
            self.state.set_stage_result('generation', html_result)
            
            duration = (datetime.now() - pipeline_start).total_seconds()
            self.logger.info(f"Pipeline completed successfully in {duration:.1f}s")
            
            return newsletter_data
            
        except Exception as e:
            duration = (datetime.now() - pipeline_start).total_seconds()
            self.logger.error(f"Pipeline failed after {duration:.1f}s: {str(e)}")
            raise
    
    async def _run_collection_stage(self) -> Dict:
        """
        Article collection - exact replica of MVP collection logic
        """
        self.logger.debug("Starting article collection")
        
        # Import exactly as MVP does
        from src.mvp_news_aggregator.collector import ArticleCollector
        from src.mvp_news_aggregator.sources import RSS_FEEDS
        
        # Execute exactly as MVP does
        collector = ArticleCollector(RSS_FEEDS)
        results = collector.collect_all()
        
        # Log meaningful summary
        total_articles = sum(len(articles) for articles in results.values())
        categories = list(results.keys())
        self.logger.info(f"Collected {total_articles} articles across {len(categories)} categories: {', '.join(categories)}")
        
        return results
    
    async def _run_curation_stage(self, results: Dict) -> Dict:
        """
        Article curation - exact replica of MVP curation logic
        """
        self.logger.debug("Starting article curation")
        
        # Import exactly as MVP does
        from src.mvp_news_aggregator.curator import ArticleCurator
        
        # Execute exactly as MVP does
        curator = ArticleCurator(use_llm=self.use_llm)
        newsletter_data = curator.curate_newsletter(results, hours=24)
        
        # Log meaningful summary
        curated_stats = {}
        total_top = total_quick = 0
        for category, data in newsletter_data.items():
            top_count = len(data.get('top_stories', []))
            quick_count = len(data.get('quick_reads', []))
            curated_stats[category] = {'top': top_count, 'quick': quick_count}
            total_top += top_count
            total_quick += quick_count
        
        method = "LLM curation" if self.use_llm else "simple selection"
        self.logger.info(f"Curation complete via {method}: {total_top} top stories, {total_quick} quick reads")
        
        return newsletter_data
    
    async def _run_generation_stage(self) -> str:
        """
        HTML generation - exact replica of MVP generation logic  
        """
        self.logger.debug("Starting HTML generation")
        
        # Import exactly as MVP does
        from src.mvp_news_aggregator.web_newsletter import generate_newsletter
        
        # Execute exactly as MVP does
        html = generate_newsletter()
        
        self.logger.info("HTML newsletter generated successfully")
        return html


def run_agentic_pipeline(use_llm: bool = True) -> Dict[str, Any]:
    """
    Main pipeline entry point - exact replica of run_daily_pipeline()
    
    Args:
        use_llm: Enable/disable LLM processing (same as MVP)
    
    Returns:
        newsletter_data: Same format as MVP output
    """
    coordinator = PipelineCoordinator(use_llm=use_llm)
    return asyncio.run(coordinator.run_pipeline())

