"""
Main entry point for the agentic newsletter pipeline
"""


# src/version_agentic/main.py

"""
Agentic Newsletter Pipeline - Entry Point

Exact replica of MVP functionality with improved architecture
"""

import sys
import os
from pathlib import Path

# Add parent directory to path for MVP imports
current_dir = Path(__file__).parent
parent_dir = current_dir.parent
sys.path.insert(0, str(parent_dir))

from coordinator.pipeline_coordinator import run_agentic_pipeline


def main():
    """Main execution - matches MVP main.py behavior exactly"""
    
    # Configuration
    RUN_ETL = True
    USE_LLM = False
    
    if RUN_ETL:
        newsletter_data = run_agentic_pipeline(use_llm=USE_LLM)
        return newsletter_data
    else:
        # Fallback to HTML regeneration only - same as MVP  
        from mvp_news_aggregator.web_newsletter import regenerate_newsletter_with_nzt
        regenerate_newsletter_with_nzt()


if __name__ == "__main__":
    main()
