from backend.lib.email_classifier import EmailClassifier
from backend.lib.ai.ai_provider_interface import AIProviderInterface

class MockAIProvider(AIProviderInterface):
    def get_model_info(self):
        return {'model_name': 'mock-model', 'provider': 'mock'}
    def generate_content(self, prompt):
        return {'content': '[]'}
    def estimate_cost(self, input_tokens, output_tokens):
        return {'estimated_cost_usd': 0.0}

def verify_prompt_update():
    classifier = EmailClassifier(MockAIProvider())
    
    test_emails = [
        {
            'email_id': '123',
            'subject': 'Flight to Tokyo',
            'from': 'airline@test.com',
            'labels': '["Trip/Japan"]'
        }
    ]
    
    prompt = classifier._create_classification_prompt(test_emails)
    
    print("Generated Prompt Snippet:")
    print("-" * 40)
    # Print the relevant section
    start_idx = prompt.find("IMPORTANT:")
    end_idx = prompt.find("Categories:")
    print(prompt[start_idx:end_idx])
    print("-" * 40)
    
    if "STRONG SIGNAL" in prompt and '"Trip/"' in prompt:
        print("\nSUCCESS: Prompt contains the new label instructions.")
    else:
        print("\nFAILURE: Prompt is missing the new instructions.")

if __name__ == "__main__":
    verify_prompt_update()
