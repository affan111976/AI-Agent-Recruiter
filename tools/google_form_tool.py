from langchain_core.tools import tool
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import os
import pickle
from typing import List, Dict
from datetime import datetime

SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets.readonly',
]

def get_sheets_service():
    """Authenticate and return Google Sheets service."""
    creds = None
    
    # Check for existing token
    if os.path.exists('sheets_token.pickle'):
        with open('sheets_token.pickle', 'rb') as token:
            creds = pickle.load(token)
    
    # If no valid credentials, authenticate
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials2.json', SCOPES)
            creds = flow.run_local_server(port=0)
        
        # Save credentials
        with open('sheets_token.pickle', 'wb') as token:
            pickle.dump(creds, token)
    
    # Use gspread for easier interface
    client = gspread.authorize(creds)
    return client

@tool
def fetch_google_form_responses(sheet_id: str) -> List[Dict]:
    """
    Fetches all responses from a Google Form's linked spreadsheet.
    
    Args:
        sheet_id: The Google Sheets ID from the form responses
        
    Returns:
        List of candidate dictionaries with their application data
    """
    print(f"--- FETCHING APPLICATIONS FROM GOOGLE FORM ---")
    print(f"Sheet ID: {sheet_id}")
    
    try:
        # Authenticate and open spreadsheet
        client = get_sheets_service()
        sheet = client.open_by_key(sheet_id)
        worksheet = sheet.get_worksheet(0)  # First sheet
        
        # Get all records as list of dictionaries
        all_records = worksheet.get_all_records()
        
        print(f"✅ Found {len(all_records)} form submissions")
        
        # Transform Google Form data to our candidate format
        candidates = []
        for record in all_records:
            # Map Google Form columns to our format
            # Adjust these field names to match YOUR form's column headers
            candidate = {
                "name": record.get("Name") or record.get("Name"),
                "email": record.get("email id") or record.get("Email"),
                "phone": record.get("phone Number") or record.get("Phone"),
                "resume": record.get("Resume/Experience") or record.get("Resume"),
                "applied_at": record.get("Timestamp", datetime.now().isoformat())
            }
            
            # Only add if we have minimum required fields
            if candidate["name"] and candidate["email"] and candidate["resume"]:
                candidates.append(candidate)
                print(f"  ✓ {candidate['name']} ({candidate['email']})")
            else:
                print(f"  ⚠️  Skipping incomplete submission")
        
        print(f"✅ Successfully processed {len(candidates)} valid applications\n")
        return candidates
        
    except Exception as e:
        print(f"❌ Error fetching form responses: {e}")
        import traceback
        traceback.print_exc()
        return []

def get_form_column_mapping(sheet_id: str) -> Dict[str, str]:
    """
    Helper function to see what columns exist in your form.
    Run this once to map your form fields correctly.
    """
    try:
        client = get_sheets_service()
        sheet = client.open_by_key(sheet_id)
        worksheet = sheet.get_worksheet(0)
        
        # Get first row (headers)
        headers = worksheet.row_values(1)
        
        print("\n📋 Your Google Form Columns:")
        print("="*50)
        for i, header in enumerate(headers, 1):
            print(f"{i}. {header}")
        print("="*50)
        print("\n💡 Update the field mapping in fetch_google_form_responses()")
        print("   to match these column names.\n")
        
        return {h: h for h in headers}
        
    except Exception as e:
        print(f"Error: {e}")
        return {}

# Standalone function for manual testing
if __name__ == "__main__":
    # Test fetching
    sheet_id = os.getenv("GOOGLE_FORM_SHEET_ID")
    if sheet_id:
        print("Testing Google Form integration...\n")
        get_form_column_mapping(sheet_id)
        candidates = fetch_google_form_responses(sheet_id)
        print(f"\nFetched {len(candidates)} candidates")
    else:
        print("Set GOOGLE_FORM_SHEET_ID in .env file")