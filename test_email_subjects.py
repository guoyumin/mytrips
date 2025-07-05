#!/usr/bin/env python3
"""
Simple test to list only email subjects
"""

import os
import json
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

def list_email_subjects():
    if not os.path.exists('token.json'):
        print("❌ No token.json found! Run setup_gmail_auth.py first")
        return
    
    try:
        # Load credentials
        with open('token.json', 'r') as token:
            token_data = json.load(token)
            creds = Credentials(
                token=token_data.get('token'),
                refresh_token=token_data.get('refresh_token'),
                token_uri=token_data.get('token_uri'),
                client_id=token_data.get('client_id'),
                client_secret=token_data.get('client_secret'),
                scopes=token_data.get('scopes')
            )
        
        # Build Gmail service
        service = build('gmail', 'v1', credentials=creds)
        
        # Search for recent emails
        results = service.users().messages().list(
            userId='me',
            q='newer_than:10d',
            maxResults=20
        ).execute()
        
        messages = results.get('messages', [])
        
        print(f"\n📧 Found {len(messages)} emails in the last 10 days:\n")
        print("=" * 60)
        
        for i, msg in enumerate(messages, 1):
            message = service.users().messages().get(
                userId='me',
                id=msg['id']
            ).execute()
            
            headers = message['payload'].get('headers', [])
            subject = next((h['value'] for h in headers if h['name'] == 'Subject'), 'No Subject')
            
            print(f"{i:2d}. {subject}")
        
        print("=" * 60)
                
    except Exception as e:
        print(f"❌ Error: {str(e)}")

if __name__ == "__main__":
    list_email_subjects()