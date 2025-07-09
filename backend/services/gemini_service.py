import google.generativeai as genai
import json
import os
import logging
from typing import List, Dict, Optional
import time
from datetime import datetime

logger = logging.getLogger(__name__)

class GeminiService:
    """Service for interacting with Google Gemini AI"""
    
    def __init__(self, model_name='gemini-2.5-pro'):
        self.model_name = model_name
        self.model = self._initialize_model(model_name)
        
    def _initialize_model(self, model_name='gemini-2.5-pro'):
        """Initialize Gemini AI model with API key"""
        # Load API key from config
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        config_path = os.path.join(project_root, 'config', 'gemini_config.json')
        
        if not os.path.exists(config_path):
            raise Exception(f"Gemini config not found. Please create {config_path} with your API key")
        
        with open(config_path, 'r') as f:
            config = json.load(f)
        
        api_key = config.get('api_key')
        if not api_key:
            raise Exception("Gemini API key not found in config")
        
        # Configure Gemini
        genai.configure(api_key=api_key)
        
        # Initialize the specified model
        return genai.GenerativeModel(model_name)
    
    def classify_emails_batch(self, emails: List[Dict]) -> List[Dict]:
        """
        Classify a batch of emails for travel-related content
        
        Args:
            emails: List of email dicts with 'subject' and 'from' fields
            
        Returns:
            List of classification results
        """
        if not emails:
            return []
        
        # Create efficient batch prompt
        prompt = self._create_batch_classification_prompt(emails)
        
        try:
            # Call Gemini API
            response = self.model.generate_content(prompt)
            
            # Parse response
            return self._parse_classification_response(response.text, emails)
            
        except Exception as e:
            print(f"Gemini API error: {e}")
            # Return default classifications on error
            return [self._default_classification(email) for email in emails]
    
    def _create_batch_classification_prompt(self, emails: List[Dict]) -> str:
        """Create optimized prompt for batch email classification"""
        
        # Build email list for prompt (keep it concise to save tokens)
        email_list = []
        for i, email in enumerate(emails):
            subject = email.get('subject', '')
            sender = email.get('from', '')
            # Truncate long subjects to save tokens
            if len(subject) > 100:
                subject = subject[:97] + "..."
            email_list.append(f"{i+1}. From: {sender[:50]} | Subject: {subject}")
        
        emails_text = "\n".join(email_list)
        
        prompt = f"""Classify these {len(emails)} emails as travel-related or not. 

IMPORTANT: Only classify emails that contain ACTUAL ITINERARY INFORMATION (booking confirmations, tickets, reservations with specific dates/times/locations) as travel categories. Marketing emails from travel companies should be classified as 'marketing'.

Categories:
- flight: Flight booking confirmations, boarding passes, e-tickets (with flight numbers/times)
- hotel: Hotel reservation confirmations (with check-in/out dates)
- car_rental: Car rental confirmations (with pickup dates/locations)
- train: Train/rail ticket confirmations
- cruise: Cruise booking confirmations
- tour: Tour/activity booking confirmations (with specific dates)
- travel_insurance: Travel insurance policy confirmations
- flight_change: Flight changes, delays, cancellations (for existing bookings)
- hotel_change: Hotel changes, cancellations (for existing bookings)
- other_travel: Other travel confirmations (visas, parking reservations, etc.)
- marketing: Travel company promotions, newsletters, deals (NO specific booking info)
- not_travel: Not travel-related at all

Return ONLY a JSON array with {len(emails)} objects in this exact format:
[{{"id": 1, "is_travel": true, "category": "flight"}}, {{"id": 2, "is_travel": false, "category": "not_travel"}}, ...]

Note: 'marketing' emails have is_travel=false since they don't contain itinerary information.

Emails to classify:
{emails_text}"""

        return prompt
    
    def _parse_classification_response(self, response_text: str, emails: List[Dict]) -> List[Dict]:
        """Parse Gemini response and create classification results"""
        try:
            # Extract JSON from response
            response_text = response_text.strip()
            # Remove markdown code blocks if present
            if '```json' in response_text:
                start = response_text.find('```json') + 7
                end = response_text.rfind('```')
                if end > start:
                    response_text = response_text[start:end]
            elif '```' in response_text:
                # Handle plain code blocks
                start = response_text.find('```') + 3
                end = response_text.rfind('```')
                if end > start:
                    response_text = response_text[start:end]
            
            classifications = json.loads(response_text.strip())
            
            # Validate and create results
            results = []
            for i, classification in enumerate(classifications):
                if i < len(emails):
                    email = emails[i]
                    is_travel = classification.get('is_travel', False)
                    category = classification.get('category', 'not_travel')
                    
                    results.append({
                        'email_id': email.get('email_id', ''),
                        'subject': email.get('subject', ''),
                        'from': email.get('from', ''),
                        'date': email.get('date', ''),
                        'timestamp': email.get('timestamp', ''),
                        'is_classified': 'true',
                        'classification': category if is_travel else 'not_travel',
                        'is_travel_related': is_travel
                    })
                else:
                    break
            
            # Fill in any missing results with defaults
            while len(results) < len(emails):
                results.append(self._default_classification(emails[len(results)]))
            
            return results
            
        except Exception as e:
            print(f"Error parsing Gemini response: {e}")
            print(f"Response was: {response_text[:200]}...")
            return [self._default_classification(email) for email in emails]
    
    def _default_classification(self, email: Dict) -> Dict:
        """Create default classification for failed cases"""
        return {
            'email_id': email.get('email_id', ''),
            'subject': email.get('subject', ''),
            'from': email.get('from', ''),
            'date': email.get('date', ''),
            'timestamp': email.get('timestamp', ''),
            'is_classified': 'true',
            'classification': 'classification_failed',
            'is_travel_related': False
        }
    
    def estimate_token_cost(self, num_emails: int, task_type: str = 'classification') -> Dict:
        """Estimate token usage and cost for different tasks"""
        
        # Get model-specific pricing
        pricing = self._get_model_pricing()
        
        if task_type == 'classification':
            # Rough estimation: ~50 tokens per email in prompt + response
            estimated_input_tokens = num_emails * 50
            estimated_output_tokens = num_emails * 20
        elif task_type == 'booking_extraction':
            # Booking extraction uses more tokens per email (full content analysis)
            estimated_input_tokens = num_emails * 500  # Larger prompts with full email content
            estimated_output_tokens = num_emails * 100  # More detailed extraction output
        elif task_type == 'trip_detection':
            # Trip detection analyzes batches of extracted data
            batch_size = 50
            num_batches = (num_emails + batch_size - 1) // batch_size
            estimated_input_tokens = num_batches * 2000  # Complex analysis prompts
            estimated_output_tokens = num_batches * 500   # Detailed trip structures
        else:
            # Default estimation
            estimated_input_tokens = num_emails * 100
            estimated_output_tokens = num_emails * 50
        
        input_cost = (estimated_input_tokens * pricing['input_cost_per_1k'] / 1000)
        output_cost = (estimated_output_tokens * pricing['output_cost_per_1k'] / 1000)
        total_cost = input_cost + output_cost
        
        return {
            'model': self.model_name,
            'task_type': task_type,
            'estimated_input_tokens': estimated_input_tokens,
            'estimated_output_tokens': estimated_output_tokens,
            'input_cost_usd': round(input_cost, 6),
            'output_cost_usd': round(output_cost, 6),
            'estimated_cost_usd': round(total_cost, 6)
        }
    
    def _get_model_pricing(self) -> Dict:
        """Get pricing information for the current model from config file"""
        try:
            # Load pricing config
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            pricing_config_path = os.path.join(project_root, 'config', 'gemini_pricing.json')
            
            if not os.path.exists(pricing_config_path):
                # Fallback to default pricing if config not found
                return self._get_fallback_pricing()
            
            with open(pricing_config_path, 'r') as f:
                pricing_config = json.load(f)
            
            pricing_data = pricing_config.get('pricing', {})
            
            # Find matching model pricing
            model_pricing = None
            for model_key, pricing in pricing_data.items():
                if model_key.lower() in self.model_name.lower():
                    model_pricing = pricing
                    break
            
            if not model_pricing:
                # Fallback if model not found in config
                return self._get_fallback_pricing()
            
            # Convert from per 1M tokens to per 1K tokens
            if 'gemini-2.5-pro' in self.model_name.lower():
                # Use small context pricing as default (≤200k tokens)
                input_cost_per_1k = model_pricing.get('input_cost_per_1m_tokens_small', 1.25) / 1000
                output_cost_per_1k = model_pricing.get('output_cost_per_1m_tokens_small', 10.00) / 1000
            else:
                # Flash models and others
                input_cost_per_1k = model_pricing.get('input_cost_per_1m_tokens', 0.30) / 1000
                output_cost_per_1k = model_pricing.get('output_cost_per_1m_tokens', 2.50) / 1000
            
            return {
                'input_cost_per_1k': input_cost_per_1k,
                'output_cost_per_1k': output_cost_per_1k,
                'source': 'config_file',
                'model_info': model_pricing
            }
            
        except Exception as e:
            print(f"Error loading pricing config: {e}")
            return self._get_fallback_pricing()
    
    def _get_fallback_pricing(self) -> Dict:
        """Fallback pricing if config file is not available"""
        if 'flash' in self.model_name.lower():
            # Gemini 2.5-flash fallback pricing
            return {
                'input_cost_per_1k': 0.0003,     # $0.30 per 1M = $0.0003 per 1K
                'output_cost_per_1k': 0.0025,    # $2.50 per 1M = $0.0025 per 1K
                'source': 'fallback'
            }
        else:
            # Gemini 2.5-pro fallback pricing
            return {
                'input_cost_per_1k': 0.00125,    # $1.25 per 1M = $0.00125 per 1K
                'output_cost_per_1k': 0.01,      # $10.00 per 1M = $0.01 per 1K
                'source': 'fallback'
            }