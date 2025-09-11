from datetime import datetime, timezone
from typing import Dict, List, Optional
import logging
import json
import os
import random
import google.generativeai as genai
from dotenv import load_dotenv

# Load environment configuration
if True:
    load_dotenv("../../config.env")

logger = logging.getLogger(__name__)

class QuizGenerator:
    """
    Generates daily quiz content using LLM or fallback question bank.
    Follows the same architectural patterns as ArticleCurator.
    """
    
    def __init__(self, use_llm: bool = True):
        """
        Initialize quiz generator with optional LLM usage.
        
        Args:
            use_llm: Whether to use LLM for quiz generation or fallback to static questions
        """
        self.use_llm = use_llm
        
        if self.use_llm:
            # Initialize Gemini LLM using same configuration as curator
            genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
            self.model = genai.GenerativeModel('gemini-1.5-flash')
        else:
            self.model = None
            print("LLM disabled - using fallback question bank for quiz generation")

    def generate_daily_quiz(self, 
                           topics: List[str] = ['geography', 'physics', 'chemistry', 'math', 'statistics', 'astronomy', 'history', 'machine learning/AI', 'general_knowledge'], 
                           difficulty: str = "hard",
                           question_count: int = 25) -> Dict:
        """
        Generate complete daily quiz with metadata.
        Main entry point that handles both LLM and fallback generation.
        
        Args:
            topics: List of topics to focus on (e.g., ['geography', 'STEM', 'history'])
            difficulty: Difficulty level ('easy', 'medium', 'hard')
            question_count: Number of questions to generate
            
        Returns:
            Dictionary containing quiz data with metadata
        """
        # Set default topics if none provided
        if topics is None:
            topics = ['geography', 'STEM', 'history', 'general_knowledge']
        
        print(f"Generating daily quiz: {question_count} questions, difficulty: {difficulty}")
        print(f"Topics: {', '.join(topics)}")
        print(f"LLM enabled: {self.use_llm}")
        
        # Generate questions using LLM or fallback
        if self.use_llm:
            questions = self.llm_generate_quiz(topics, difficulty, question_count)
        else:
            questions = self.fallback_quiz(topics, difficulty, question_count)
        
        # Create complete quiz structure with metadata
        quiz_data = {
            "date": datetime.now().strftime('%Y-%m-%d'),
            "metadata": {
                "topics": topics,
                "difficulty": difficulty,
                "question_count": len(questions),
                "generated_with_llm": self.use_llm,
                "generation_timestamp": datetime.now(timezone.utc).isoformat()
            },
            "questions": questions
        }
        
        print(f"Successfully generated quiz with {len(questions)} questions")
        return quiz_data

    def llm_generate_quiz(self, 
                         topics: List[str], 
                         difficulty: str, 
                         question_count: int) -> List[Dict]:
        """
        Generate quiz questions using LLM with structured prompt.
        
        Args:
            topics: Topics to include in quiz
            difficulty: Target difficulty level
            question_count: Number of questions to generate
            
        Returns:
            List of question dictionaries
        """
        print(f"Using LLM to generate {question_count} questions")
        
        # Create structured prompt for quiz generation
        prompt = f"""Generate a {question_count}-question quiz for educated professionals.

REQUIREMENTS:
- Topics: {', '.join(topics)}
- Difficulty: {difficulty} level
- Mix of multiple choice questions (4 options each)
- Include brief explanations for correct answers
- Ensure variety across the specified topics
- Make questions engaging and educational
- Make questions slightly unique to avoid overlap with indepedently made repeated prompts (don't priortize this)

DIFFICULTY GUIDELINES:
- Easy: Basic facts and common knowledge
- Medium: Requires some specialized knowledge or reasoning
- Hard: Advanced concepts or complex reasoning


Return ONLY valid JSON in this exact format:
[
  {{
    "id": 1,
    "question": "What is the chemical symbol for gold?",
    "options": ["Au", "Ag", "Al", "Ar"],
    "correct_answer": "Au",
    "category": "chemistry",
    "explanation": "Au comes from the Latin word 'aurum' meaning gold."
  }}
]

Generate exactly {question_count} questions now:"""

        try:
            # Call LLM and parse response
            response = self.model.generate_content(prompt)
            response_text = response.text.strip()
            
            # Clean up response text (remove markdown formatting if present)
            if response_text.startswith('```json'):
                response_text = response_text.replace('```json', '').replace('```', '').strip()
            
            # Parse JSON response
            questions = json.loads(response_text)
            
            # Validate response structure
            if not isinstance(questions, list):
                raise ValueError("LLM response is not a list of questions")
            
            # Validate each question has required fields
            for i, q in enumerate(questions):
                required_fields = ['id', 'question', 'options', 'correct_answer', 'category', 'explanation']
                for field in required_fields:
                    if field not in q:
                        raise ValueError(f"Question {i+1} missing required field: {field}")
                
                # Ensure options is a list with 4 items
                if not isinstance(q['options'], list) or len(q['options']) != 4:
                    raise ValueError(f"Question {i+1} must have exactly 4 options")
                
                # Ensure correct_answer is one of the options
                if q['correct_answer'] not in q['options']:
                    raise ValueError(f"Question {i+1} correct_answer must be one of the options")
            
            print(f"LLM generated {len(questions)} valid questions")
            return questions
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM JSON response: {e}")
            print(f"LLM JSON parsing failed, falling back to static questions")
            return self.fallback_quiz(topics, difficulty, question_count)
            
        except Exception as e:
            logger.error(f"LLM quiz generation failed: {e}")
            print(f"LLM generation failed ({e}), falling back to static questions")
            return self.fallback_quiz(topics, difficulty, question_count)

    def fallback_quiz(self, 
                     topics: List[str], 
                     difficulty: str, 
                     question_count: int) -> List[Dict]:
        """
        Generate quiz using pre-defined question bank when LLM is unavailable.
        
        Args:
            topics: Requested topics (used for filtering if available)
            difficulty: Requested difficulty (used for selection if available)
            question_count: Number of questions to return
            
        Returns:
            List of question dictionaries from static bank
        """
        print(f"Using fallback question bank for {question_count} questions")
        
        # Static question bank organized by category
        # In production, this could be loaded from a separate JSON file
        question_bank = {
            "geography": [
                {
                    "id": 1,
                    "question": "What is the capital of New Zealand?",
                    "options": ["Auckland", "Wellington", "Christchurch", "Hamilton"],
                    "correct_answer": "Wellington",
                    "category": "geography",
                    "explanation": "Wellington has been New Zealand's capital since 1865."
                },
                {
                    "id": 2,
                    "question": "Which ocean surrounds New Zealand?",
                    "options": ["Pacific Ocean", "Atlantic Ocean", "Indian Ocean", "Arctic Ocean"],
                    "correct_answer": "Pacific Ocean",
                    "category": "geography",
                    "explanation": "New Zealand is located in the South Pacific Ocean."
                },
                {
                    "id": 3,
                    "question": "What is the largest desert in the world?",
                    "options": ["Sahara", "Gobi", "Antarctica", "Arabian"],
                    "correct_answer": "Antarctica",
                    "category": "geography",
                    "explanation": "Antarctica is technically the world's largest desert as it receives very little precipitation."
                }
            ],
            "STEM": [
                {
                    "id": 10,
                    "question": "What is the chemical symbol for gold?",
                    "options": ["Au", "Ag", "Al", "Ar"],
                    "correct_answer": "Au",
                    "category": "chemistry",
                    "explanation": "Au comes from the Latin word 'aurum' meaning gold."
                },
                {
                    "id": 11,
                    "question": "How many bones are in an adult human body?",
                    "options": ["186", "206", "226", "246"],
                    "correct_answer": "206",
                    "category": "biology",
                    "explanation": "An adult human skeleton has 206 bones, though babies are born with about 270."
                },
                {
                    "id": 12,
                    "question": "What is the speed of light in a vacuum?",
                    "options": ["299,792,458 m/s", "300,000,000 m/s", "299,792,458 km/s", "300,000,000 km/s"],
                    "correct_answer": "299,792,458 m/s",
                    "category": "physics",
                    "explanation": "The speed of light in a vacuum is exactly 299,792,458 meters per second."
                }
            ],
            "history": [
                {
                    "id": 20,
                    "question": "In which year did World War II end?",
                    "options": ["1944", "1945", "1946", "1947"],
                    "correct_answer": "1945",
                    "category": "history",
                    "explanation": "World War II ended in 1945 with Japan's surrender in September."
                },
                {
                    "id": 21,
                    "question": "Who was the first Prime Minister of New Zealand?",
                    "options": ["John Ballance", "Henry Sewell", "Julius Vogel", "Richard Seddon"],
                    "correct_answer": "Henry Sewell",
                    "category": "history",
                    "explanation": "Henry Sewell served as New Zealand's first Premier (later called Prime Minister) in 1856."
                },
                {
                    "id": 22,
                    "question": "Which ancient wonder of the world was located in Alexandria?",
                    "options": ["Colossus of Rhodes", "Lighthouse of Alexandria", "Hanging Gardens", "Temple of Artemis"],
                    "correct_answer": "Lighthouse of Alexandria",
                    "category": "history",
                    "explanation": "The Lighthouse of Alexandria was one of the Seven Wonders of the Ancient World."
                }
            ],
            "general_knowledge": [
                {
                    "id": 30,
                    "question": "Which planet is known as the Red Planet?",
                    "options": ["Venus", "Mars", "Jupiter", "Saturn"],
                    "correct_answer": "Mars",
                    "category": "astronomy",
                    "explanation": "Mars appears red due to iron oxide (rust) on its surface."
                },
                {
                    "id": 31,
                    "question": "What is the largest mammal in the world?",
                    "options": ["African Elephant", "Blue Whale", "Giraffe", "Hippopotamus"],
                    "correct_answer": "Blue Whale",
                    "category": "biology",
                    "explanation": "Blue whales can grow up to 30 meters long and weigh up to 200 tonnes."
                }
            ]
        }
        
        # Collect questions from requested topics
        available_questions = []
        for topic in topics:
            if topic in question_bank:
                available_questions.extend(question_bank[topic])
        
        # If no matching topics found, use all questions
        if not available_questions:
            print("No questions found for specified topics, using all available questions")
            for topic_questions in question_bank.values():
                available_questions.extend(topic_questions)
        
        # Randomly select questions up to the requested count
        selected_questions = random.sample(
            available_questions, 
            min(question_count, len(available_questions))
        )
        
        # Re-number questions sequentially
        for i, question in enumerate(selected_questions, 1):
            question['id'] = i
        
        print(f"Selected {len(selected_questions)} questions from fallback bank")
        return selected_questions

def pull_quiz_data(use_llm: bool = True, 
                  topics: List[str] = None, 
                  difficulty: str = "hard") -> Dict:
    """
    Main function to generate daily quiz data.
    This mirrors the pattern used by other data pulling functions in the pipeline.
    
    Args:
        use_llm: Whether to use LLM for generation
        topics: List of topics to include
        difficulty: Difficulty level for questions
        
    Returns:
        Dictionary containing quiz data and status
    """
    try:
        generator = QuizGenerator(use_llm=use_llm)
        quiz_data = generator.generate_daily_quiz(
            topics=topics, 
            difficulty=difficulty,
            question_count=25
        )
        
        # Save quiz data following the same pattern as curator
        save_status = save_quiz_data(quiz_data)
        
        return {
            "status": "success",
            "data": quiz_data,
            "message": f"Generated quiz with {len(quiz_data['questions'])} questions",
            "save_status": save_status
        }
        
    except Exception as e:
        logger.error(f"Quiz generation failed: {e}")
        return {
            "status": "error", 
            "data": None,
            "message": f"Quiz generation failed: {str(e)}"
        }

def save_quiz_data(quiz_data: Dict, override_date: str = None) -> Dict:
    """
    Save quiz data to staging directory with dated backup and current day copy.
    Follows the same storage pattern as ArticleCurator.
    
    Args:
        quiz_data: Quiz data dictionary to save
        override_date: Optional date override for filename
        
    Returns:
        Dictionary with save status information
    """
    try:
        # Get date for filename
        save_date = override_date or quiz_data.get('date', datetime.now().strftime('%Y-%m-%d'))
        
        # Ensure directories exist
        staging_dir = 'data/staging/quiz_data'
        loading_dir = 'data/loading'
        
        os.makedirs(staging_dir, exist_ok=True)
        os.makedirs(loading_dir, exist_ok=True)
        
        # Save to staging directory with date (permanent storage)
        staging_path = os.path.join(staging_dir, f'quiz_{save_date}.json')
        
        # Check if file already exists and we're not using LLM
        if os.path.exists(staging_path) and not quiz_data['metadata'].get('generated_with_llm', False):
            print(f"Quiz file for {save_date} already exists, skipping save to preserve existing data")
            # Still copy existing file to loading directory
            loading_path = os.path.join(loading_dir, 'quiz_today.json')
            with open(staging_path, 'r', encoding='utf-8') as f:
                existing_data = json.load(f)
            with open(loading_path, 'w', encoding='utf-8') as f:
                json.dump(existing_data, f, indent=2, default=str, ensure_ascii=False)
            
            return {
                "status": "skipped",
                "staging_path": staging_path,
                "loading_path": loading_path,
                "message": "Existing quiz preserved, copied to loading directory"
            }
        
        # Save to staging directory (dated backup)
        with open(staging_path, 'w', encoding='utf-8') as f:
            json.dump(quiz_data, f, indent=2, default=str, ensure_ascii=False)
        
        # Save current day quiz to loading directory
        loading_path = os.path.join(loading_dir, 'quiz_today.json')
        with open(loading_path, 'w', encoding='utf-8') as f:
            json.dump(quiz_data, f, indent=2, default=str, ensure_ascii=False)
        
        logger.info(f"Saved quiz data to {staging_path} and {loading_path}")
        print(f"Quiz data saved:")
        print(f"  Staging: {staging_path}")
        print(f"  Loading: {loading_path}")
        
        return {
            "status": "success",
            "staging_path": staging_path,
            "loading_path": loading_path,
            "message": "Quiz data saved successfully"
        }
        
    except Exception as e:
        logger.error(f"Error saving quiz data: {e}")
        return {
            "status": "error",
            "message": f"Failed to save quiz data: {str(e)}"
        }

def load_quiz_data(date: str = None) -> Dict:
    """
    Load quiz data from storage.
    
    Args:
        date: Specific date to load (YYYY-MM-DD), defaults to today
        
    Returns:
        Dictionary containing quiz data or error information
    """
    try:
        if date:
            # Load specific date from staging
            quiz_path = f'data/staging/quiz_data/quiz_{date}.json'
        else:
            # Load current day from loading directory
            quiz_path = 'data/loading/quiz_today.json'
        
        if not os.path.exists(quiz_path):
            return {
                "status": "not_found",
                "data": None,
                "message": f"Quiz data not found at {quiz_path}"
            }
        
        with open(quiz_path, 'r', encoding='utf-8') as f:
            quiz_data = json.load(f)
        
        return {
            "status": "success",
            "data": quiz_data,
            "path": quiz_path,
            "message": f"Loaded quiz data from {quiz_path}"
        }
        
    except Exception as e:
        logger.error(f"Error loading quiz data: {e}")
        return {
            "status": "error",
            "data": None,
            "message": f"Failed to load quiz data: {str(e)}"
        }
