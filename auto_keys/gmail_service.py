import os.path
import base64
import re
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

class GmailService:
    """Handles Gmail API authentication and email searching."""

    def __init__(self):
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.creds_path = os.path.join(self.base_dir, 'credentials.json')
        self.token_path = os.path.join(self.base_dir, 'token.json')
        self.creds = None

    def authenticate(self):
        """Authenticates the user and returns the service."""
        if os.path.exists(self.token_path):
            self.creds = Credentials.from_authorized_user_file(self.token_path, SCOPES)
        
        # If there are no (valid) credentials available, let the user log in.
        if not self.creds or not self.creds.valid:
            if self.creds and self.creds.expired and self.creds.refresh_token:
                self.creds.refresh(Request())
            else:
                if not os.path.exists(self.creds_path):
                    raise FileNotFoundError(
                        f"Missing {self.creds_path}. Please download it from Google Cloud Console."
                    )
                flow = InstalledAppFlow.from_client_secrets_file(self.creds_path, SCOPES)
                # access_type='offline' is critical to get a refresh_token
                # prompt='consent' forces Google to show the consent screen and issue a refresh_token
                self.creds = flow.run_local_server(port=0, access_type='offline', prompt='consent')
            
            # Save the credentials for the next run
            with open(self.token_path, 'w') as token:
                token.write(self.creds.to_json())

        return build('gmail', 'v1', credentials=self.creds)

    def get_stream_link(self):
        """Searches for the 'todays private stream' email and extracts the link."""
        service = self.authenticate()
        
        # Search for messages with the subject
        query = 'subject:"todays private stream"'
        results = service.users().messages().list(userId='me', q=query).execute()
        messages = results.get('messages', [])

        if not messages:
            print("❌ No 'todays private stream' emails found.")
            return None

        # Get the latest message
        msg_id = messages[0]['id']
        message = service.users().messages().get(userId='me', id=msg_id).execute()
        
        # Extract body from payload
        payload = message.get('payload', {})
        body = ""

        if 'parts' in payload:
            for part in payload['parts']:
                if part['mimeType'] == 'text/html':
                    data = part['body'].get('data')
                    if data:
                        body = base64.urlsafe_b64decode(data).decode()
                        break
        else:
            data = payload.get('body', {}).get('data')
            if data:
                body = base64.urlsafe_b64decode(data).decode()

        if not body:
            print("❌ Could not read email body.")
            return None

        # Extract the link to join
        # Pattern: href="https://clicks.aweber.com/y/ct/?..." 
        # Search for the link that contains "the link to join" or just the aweber link
        links = re.findall(r'href="(https://clicks\.aweber\.com/[^"]+)"', body)
        
        if links:
            # Usually the first one is the stream link
            print(f"🎯 Found stream link via API: {links[0]}")
            return links[0]
        
        print("❌ Could not find the join link in the email body.")
        return None

