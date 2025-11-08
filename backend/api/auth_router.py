from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse
from google.auth.transport import requests
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
import os
import json
from backend.lib.gmail_client import GmailClient
from backend.lib.config_manager import config_manager

router = APIRouter()

SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']
REDIRECT_URI = "http://localhost:8000/api/auth/callback"

@router.get("/login")
async def login():
    credentials_path = config_manager.get_gmail_credentials_path()

    flow = Flow.from_client_secrets_file(
        credentials_path,
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI
    )

    authorization_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true'
    )

    return {"auth_url": authorization_url, "state": state}

@router.get("/callback")
async def callback(request: Request):
    code = request.query_params.get("code")
    if not code:
        raise HTTPException(status_code=400, detail="No authorization code provided")

    try:
        # Get correct paths from config manager
        credentials_path = config_manager.get_gmail_credentials_path()
        token_path = config_manager.get_gmail_token_path()

        flow = Flow.from_client_secrets_file(
            credentials_path,
            scopes=SCOPES,
            redirect_uri=REDIRECT_URI
        )

        flow.fetch_token(code=code)
        credentials = flow.credentials

        # Save credentials using the proper format
        with open(token_path, 'w') as token_file:
            token_file.write(credentials.to_json())

        # Redirect to success page
        return RedirectResponse(url="/?auth=success")

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Authentication failed: {str(e)}")

@router.get("/status")
async def auth_status():
    """
    Check Gmail authentication status

    Returns:
        {
            "authenticated": bool,
            "error": str or None
        }
    """
    try:
        credentials_path = config_manager.get_gmail_credentials_path()
        token_path = config_manager.get_gmail_token_path()

        # Create a temporary GmailClient to check auth status
        gmail_client = GmailClient(credentials_path, token_path)
        return gmail_client.get_auth_status()
    except Exception as e:
        return {
            "authenticated": False,
            "error": str(e)
        }