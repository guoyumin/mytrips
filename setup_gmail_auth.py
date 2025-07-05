#!/usr/bin/env python3
"""
Setup Gmail OAuth authentication independently
Run this script first to authenticate and save credentials
"""

import os
import json
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

def authenticate_gmail():
    """Authenticate and save Gmail credentials"""
    creds = None
    
    # Token file stores the user's access and refresh tokens
    if os.path.exists('token.json'):
        print("Found existing token.json file")
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
    
    # If there are no (valid) credentials available, let the user log in
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("Token expired, refreshing...")
            creds.refresh(Request())
        else:
            print("No valid credentials found, starting OAuth flow...")
            
            if not os.path.exists('credentials.json'):
                print("\n❌ ERROR: credentials.json file not found!")
                print("\nPlease follow these steps:")
                print("1. Go to https://console.cloud.google.com/")
                print("2. Create a new project or select existing one")
                print("3. Enable Gmail API")
                print("4. Create OAuth 2.0 credentials (Desktop application)")
                print("5. Download the credentials")
                print("6. Save as 'credentials.json' in this directory")
                return None
            
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            
            # This will open browser for authentication
            creds = flow.run_local_server(port=0)
            print("✓ Authentication successful!")
        
        # Save the credentials for the next run
        token_data = {
            'token': creds.token,
            'refresh_token': creds.refresh_token,
            'token_uri': creds.token_uri,
            'client_id': creds.client_id,
            'client_secret': creds.client_secret,
            'scopes': creds.scopes
        }
        
        with open('token.json', 'w') as token:
            json.dump(token_data, token)
        print("✓ Credentials saved to token.json")
    
    # Test the connection
    try:
        service = build('gmail', 'v1', credentials=creds)
        results = service.users().labels().list(userId='me').execute()
        labels = results.get('labels', [])
        
        print(f"\n✓ Successfully connected to Gmail!")
        print(f"Found {len(labels)} labels in your account")
        
        # Get user's email address
        profile = service.users().getProfile(userId='me').execute()
        email = profile.get('emailAddress')
        print(f"Authenticated as: {email}")
        
        return True
        
    except Exception as error:
        print(f'❌ An error occurred: {error}')
        return False

if __name__ == '__main__':
    print("Gmail OAuth Setup")
    print("=" * 50)
    
    success = authenticate_gmail()
    
    if success:
        print("\n✅ Setup complete! You can now run:")
        print("   python test_gmail_connection.py")
    else:
        print("\n❌ Setup failed. Please check the error messages above.")