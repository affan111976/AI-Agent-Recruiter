from dotenv import load_dotenv
load_dotenv()
from langchain_core.tools import tool
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from email.mime.text import MIMEText
import base64
import os
import pickle

SCOPES = ['https://www.googleapis.com/auth/gmail.send']

def get_gmail_service():
    """Authenticate and return Gmail API service."""
    creds = None
    
    # Token file stores the user's access and refresh tokens
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    
    # If no valid credentials, let user log in
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        
        # Save credentials for next run
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)
    
    return build('gmail', 'v1', credentials=creds)

@tool
def send_email_tool(recipient_email: str, subject: str, body: str) -> str:
    """Sends an email using Gmail API."""
    try:
        service = get_gmail_service()
        
        # Create message
        message = MIMEText(body)
        message['to'] = recipient_email
        message['subject'] = subject
        
        # Encode message
        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
        
        # Send message
        send_message = service.users().messages().send(
            userId="me",
            body={'raw': raw_message}
        ).execute()
        
        return f"Email sent successfully to {recipient_email} (Message ID: {send_message['id']})"
    
    except Exception as e:
        return f"Failed to send email: {str(e)}"

"""
```

**This will work immediately!** Your emails will come from:
```
From: Affan Ahmad - HR Department <onboarding@resend.dev>
"""
#14RQTJQLQD48N7XL21JT627M
#617242943447-5uoai7kah6q4kmkso2u2t2n4pje0gvse.apps.googleusercontent.com - Client id

if __name__ == "__main__":
    print("--- GMAIL AUTHENTICATION ---")
    print("Requesting access to Gmail...")
    
    # This triggers the browser login
    service = get_gmail_service()
    
    print("✅ Success! Authentication complete.")
    print("🔑 'token.pickle' has been created in your project folder.")