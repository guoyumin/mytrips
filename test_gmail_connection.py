#!/usr/bin/env python3
"""
Test Gmail connection by listing email subjects from the last 10 days
"""

import os
import json
from datetime import datetime
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

def test_gmail_connection():
    print("Testing Gmail connection...")
    print("-" * 50)
    
    # Check if token exists
    if not os.path.exists('token.json'):
        print("❌ No token.json found!")
        print("Please run 'python setup_gmail_auth.py' first to authenticate")
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
        print("✓ Gmail service initialized successfully")
        
        # Search for emails from last 10 days
        query = "newer_than:10d"
        print(f"\nSearching for emails with query: {query}")
        
        results = service.users().messages().list(
            userId='me',
            q=query,
            maxResults=10
        ).execute()
        
        messages = results.get('messages', [])
        
        if not messages:
            print("\nNo emails found in the last 10 days")
            return
        
        print(f"\nFound {len(messages)} emails. Fetching details...\n")
        
        # Get details for each email
        for i, msg in enumerate(messages, 1):
            try:
                # Get the full message
                message = service.users().messages().get(
                    userId='me',
                    id=msg['id']
                ).execute()
                
                # Extract headers
                headers = message['payload'].get('headers', [])
                subject = next((h['value'] for h in headers if h['name'] == 'Subject'), 'No Subject')
                from_addr = next((h['value'] for h in headers if h['name'] == 'From'), 'Unknown')
                date = next((h['value'] for h in headers if h['name'] == 'Date'), 'Unknown Date')
                
                print(f"{i}. Subject: {subject}")
                print(f"   From: {from_addr}")
                print(f"   Date: {date}")
                print("-" * 50)
                
            except Exception as e:
                print(f"Error fetching email {i}: {str(e)}")
                
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")

if __name__ == "__main__":
    test_gmail_connection()