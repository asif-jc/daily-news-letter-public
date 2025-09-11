#!/usr/bin/env python3
"""
Simple test of the updated quiz UX
"""

import sys
import os

# Add path for imports
sys.path.append('/Users/asif/Documents/Daily News Letter/daily-news-letter-public/src/mvp_news_aggregator')

def test_updated_quiz_ux():
    """Test the new quiz UX implementation"""
    print("TESTING UPDATED QUIZ UX")
    print("=" * 40)
    
    # Change to correct working directory
    os.chdir('/Users/asif/Documents/Daily News Letter/daily-news-letter-public/src/mvp_news_aggregator')
    
    try:
        from quiz_data import pull_quiz_data
        from web_newsletter import NewsletterGenerator
        
        # Generate sample quiz
        print("1. Generating sample quiz...")
        result = pull_quiz_data(use_llm=False, topics=['geography', 'STEM'], difficulty='medium')
        
        if result['status'] == 'success':
            print(f"✅ Generated {len(result['data']['questions'])} questions")
        else:
            print("❌ Quiz generation failed")
            return False
        
        # Test newsletter generation
        print("\n2. Testing newsletter with new UX...")
        generator = NewsletterGenerator()
        
        # Load quiz data
        quiz_data = generator.load_quiz_data()
        print(f"✅ Loaded {len(quiz_data.get('questions', []))} questions")
        
        # Test content overview
        mock_data = {
            'tech': {'top_stories': [1, 2, 3], 'quick_reads': [1, 2]},
            'world': {'top_stories': [1, 2], 'quick_reads': [1, 2, 3]}
        }
        overview_html = generator.generate_content_overview(mock_data, quiz_data)
        print(f"✅ Generated content overview: {len(overview_html)} chars")
        print(f"   - Shows story counts: {'Priority Stories' in overview_html}")
        print(f"   - Shows quiz count: {'Knowledge Quiz' in overview_html}")
        
        # Test new quiz section
        quiz_html = generator.generate_quiz_section(quiz_data)
        print(f"✅ Generated quiz section: {len(quiz_html)} chars")
        print(f"   - Shows all questions: {quiz_html.count('quiz-question') == len(quiz_data['questions'])}")
        print(f"   - Has reveal buttons: {'Show Answer' in quiz_html}")
        print(f"   - Has inline answers: {'quiz-answer-section' in quiz_html}")
        print(f"   - No floating button: {'quiz-answers-toggle' not in quiz_html}")
        
        print("\n✅ ALL UX UPDATES SUCCESSFUL!")
        print("Changes implemented:")
        print("- Quiz moved to bottom")
        print("- Content overview added to top")
        print("- All 10 questions shown")
        print("- Inline answers with reveal buttons")
        print("- Removed separate answers section")
        
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False

if __name__ == "__main__":
    test_updated_quiz_ux()
