import sys
from pathlib import Path
import json

# Add project root to path
project_root = Path(__file__).parent
sys.path.append(str(project_root))

from backend.lib.gmail_client import GmailClient
from backend.lib.config_manager import config_manager

def debug_email_labels(email_id):
    print(f"Debugging labels for email: {email_id}")
    
    try:
        credentials_path = config_manager.get_gmail_credentials_path()
        token_path = config_manager.get_gmail_token_path()
        client = GmailClient(credentials_path, token_path)
        
        # 1. Check Label Cache
        print("\n1. Label Cache (First 10):")
        for i, (lid, name) in enumerate(client.label_cache.items()):
            if i >= 10: break
            print(f"  {lid}: {name}")
            
        # 2. Fetch Raw Message
        print("\n2. Fetching Raw Message...")
        message = client.get_message(email_id, format='metadata')
        raw_labels = message.get('labelIds', [])
        print(f"  Raw labelIds: {raw_labels}")
        
        # 3. Process Labels (Simulate logic)
        print("\n3. Processing Labels...")
        label_names = []
        for label_id in raw_labels:
            if label_id in ['INBOX', 'SENT', 'UNREAD', 'IMPORTANT']:
                print(f"  Skipping system label: {label_id}")
                continue
            
            label_name = client.label_cache.get(label_id, label_id)
            print(f"  Mapped {label_id} -> {label_name}")
            label_names.append(label_name)
            
        print(f"\nFinal Label Names (Simulated): {label_names}")

        # 4. Actual Method Call
        print("\n4. Calling get_message_headers()...")
        headers = client.get_message_headers(email_id)
        print(f"  Result headers keys: {headers.keys()}")
        print(f"  Result label_names: {headers.get('label_names')}")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    # Use the email ID found in the previous step
    debug_email_labels("19a64d02db69e527")
