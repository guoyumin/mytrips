from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import json
import os
from typing import List, Dict, Optional

class GmailService:
    def __init__(self):
        self.service = self._build_service()
    
    def _build_service(self):
        creds = None
        if os.path.exists('token.json'):
            with open('token.json', 'r') as token:
                token_data = json.load(token)
                creds = Credentials(
                    token=token_data['token'],
                    refresh_token=token_data['refresh_token'],
                    token_uri=token_data['token_uri'],
                    client_id=token_data['client_id'],
                    client_secret=token_data['client_secret'],
                    scopes=token_data['scopes']
                )
        
        if not creds:
            raise Exception("No valid credentials found. Please authenticate first.")
        
        return build('gmail', 'v1', credentials=creds)
    
    def search_emails(self, query: str, max_results: int = 100) -> List[Dict]:
        try:
            results = self.service.users().messages().list(
                userId='me',
                q=query,
                maxResults=max_results
            ).execute()
            
            messages = results.get('messages', [])
            return messages
            
        except HttpError as error:
            print(f'An error occurred: {error}')
            return []
    
    def get_email(self, email_id: str) -> Dict:
        try:
            message = self.service.users().messages().get(
                userId='me',
                id=email_id,
                format='full'
            ).execute()
            
            return self._parse_email(message)
            
        except HttpError as error:
            print(f'An error occurred: {error}')
            return {}
    
    def _parse_email(self, message: Dict) -> Dict:
        headers = message['payload'].get('headers', [])
        
        email_data = {
            'id': message['id'],
            'thread_id': message['threadId'],
            'subject': next((h['value'] for h in headers if h['name'] == 'Subject'), ''),
            'from': next((h['value'] for h in headers if h['name'] == 'From'), ''),
            'to': next((h['value'] for h in headers if h['name'] == 'To'), ''),
            'date': next((h['value'] for h in headers if h['name'] == 'Date'), ''),
            'body': self._get_email_body(message['payload']),
            'attachments': self._get_attachments(message['payload'])
        }
        
        return email_data
    
    def _get_email_body(self, payload: Dict) -> str:
        body = ''
        
        if 'parts' in payload:
            for part in payload['parts']:
                if part['mimeType'] == 'text/plain':
                    data = part['body']['data']
                    body += self._decode_base64(data)
                elif part['mimeType'] == 'text/html':
                    data = part['body']['data']
                    body += self._decode_base64(data)
        elif payload['body'].get('data'):
            body = self._decode_base64(payload['body']['data'])
            
        return body
    
    def _get_attachments(self, payload: Dict) -> List[Dict]:
        attachments = []
        
        if 'parts' in payload:
            for part in payload['parts']:
                if part.get('filename'):
                    attachments.append({
                        'filename': part['filename'],
                        'mime_type': part['mimeType'],
                        'size': part['body'].get('size', 0)
                    })
                    
        return attachments
    
    def _decode_base64(self, data: str) -> str:
        import base64
        return base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')