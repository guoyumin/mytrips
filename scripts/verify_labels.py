from backend.lib.email_classifier import EmailClassifier
from backend.lib.ai.ai_provider_interface import AIProviderInterface

class MockAIProvider(AIProviderInterface):
    def get_model_info(self):
        return {'model_name': 'mock-model', 'provider': 'mock'}
    def generate_content(self, prompt):
        return {'content': '[]'}
    def estimate_cost(self, input_tokens, output_tokens):
        return {'estimated_cost_usd': 0.0}

def verify_labels_in_prompt():
    classifier = EmailClassifier(MockAIProvider())
    
    test_emails = [
        {
            'email_id': '123',
            'subject': 'Flight Confirmation',
            'from': 'airline@test.com',
            'labels': '["Trips", "Travel"]'
        }
    ]
    
    prompt = classifier._create_classification_prompt(test_emails)
    
    print("Generated Prompt:")
    print("-" * 20)
    print(prompt)
    print("-" * 20)
    
    if 'Labels: ["Trips", "Travel"]' in prompt:
        print("\nSUCCESS: Labels are included in the prompt.")
    else:
        print("\nFAILURE: Labels are MISSING from the prompt.")

if __name__ == "__main__":
    verify_labels_in_prompt()
