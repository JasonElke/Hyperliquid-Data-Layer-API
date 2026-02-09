import os
import sys

# Add the project root to sys.path to allow imports from auto_keys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from auto_keys.gmail_service import GmailService

def test():
    print("🧪 Testing Gmail API...")
    try:
        gmail_svc = GmailService()
        link = gmail_svc.get_stream_link()
        if link:
            print(f"✅ Success! Found stream link: {link}")
        else:
            print("❌ Could not find the 'todays private stream' email.")
    except Exception as e:
        print(f"❌ Error during Gmail test: {str(e)}")

if __name__ == "__main__":
    test()

