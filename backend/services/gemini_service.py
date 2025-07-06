import google.generativeai as genai
import json
import os
from typing import List, Dict, Optional
import time
from datetime import datetime

class GeminiService:
    """Service for interacting with Google Gemini AI"""
    
    def __init__(self):
        self.model = self._initialize_model()
        
    def _initialize_model(self):
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
        
        # Use Gemini 2.5 Pro model for best performance
        return genai.GenerativeModel('gemini-2.5-pro')
    
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
    
    def estimate_token_cost(self, num_emails: int) -> Dict:
        """Estimate token usage and cost for classification"""
        # Rough estimation: ~50 tokens per email in prompt + response
        estimated_tokens = num_emails * 50
        
        # Gemini Pro pricing (approximate)
        input_cost_per_1k = 0.000125  # $0.000125 per 1K input tokens
        output_cost_per_1k = 0.000375  # $0.000375 per 1K output tokens
        
        estimated_cost = (estimated_tokens * input_cost_per_1k / 1000) + \
                        (num_emails * 20 * output_cost_per_1k / 1000)  # ~20 tokens per response
        
        return {
            'estimated_input_tokens': estimated_tokens,
            'estimated_output_tokens': num_emails * 20,
            'estimated_cost_usd': round(estimated_cost, 6)
        }