import time
from datetime import datetime, timedelta
from auto_keys.extract_key import KeyExtractor

def wait_until_6pm():
    """Wait until 18:05 (6:05 PM) to run the script."""
    now = datetime.now()
    # Target time today: 18:05:00
    target = now.replace(hour=18, minute=5, second=0, microsecond=0)
    
    # If it's already past 18:05 today, target 18:05 tomorrow
    if now > target:
        target += timedelta(days=1)
    
    wait_seconds = (target - now).total_seconds()
    
    hours = int(wait_seconds // 3600)
    minutes = int((wait_seconds % 3600) // 60)
    
    print(f"⏳ Waiting {hours}h {minutes}m until the next run at {target.strftime('%H:%M:%S')}...")
    time.sleep(wait_seconds)

def wait_until_1am():
    """Wait until 01:00 AM of the next day."""
    now = datetime.now()
    # Target is tomorrow at 1 AM
    target = (now + timedelta(days=1)).replace(hour=1, minute=0, second=0, microsecond=0)
    
    wait_seconds = (target - now).total_seconds()
    hours = int(wait_seconds // 3600)
    minutes = int((wait_seconds % 3600) // 60)
    print(f"📺 Keeping Chrome open for viewing. Waiting {hours}h {minutes}m until 01:00 AM...")
    time.sleep(wait_seconds)
    print("🌙 It's 01:00 AM. Closing Chrome now.")

if __name__ == "__main__":
    extractor = KeyExtractor()
    
    print("🤖 Hyperliquid Key Extractor - AUTO SCHEDULER MODE")
    print("💡 The script will run immediately once, then trigger at 18:05 (6:05 PM) every day.")
    
    first_run = True
    while True:
        try:
            # 1. Wait for the next 6:05 PM window (except for the very first run)
            if not first_run:
                wait_until_6pm()
            
            # 2. Start run with retries until 11 PM
            success = False
            print(f"\n🚀 [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Starting Extraction Flow...")
            
            while datetime.now().hour < 23: # Loop until 11:00 PM
                # Close old driver if still open for some reason
                if extractor.driver:
                    try:
                        extractor.driver.quit()
                    except:
                        pass
                    extractor.driver = None

                print(f"🔄 [{datetime.now().strftime('%H:%M:%S')}] Starting a 15-minute session...")
                success = extractor.run_flow(wait_timeout_mins=15)
                
                if success:
                    print(f"✅ [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Flow completed successfully.")
                    break
                else:
                    now_hour = datetime.now().hour
                    if now_hour < 23:
                        print(f"❌ Session failed/timed out. Retrying in 30 seconds... (Current time: {datetime.now().strftime('%H:%M:%S')})")
                        time.sleep(30)
                    else:
                        print(f"❌ Reached 11:00 PM without joining. Passing to new day.")
                        break
            
            # 3. Keep Chrome open until 1 AM if it was opened and successful
            if success and extractor.driver:
                wait_until_1am()
            
            # 4. Close Chrome after 1 AM or if failed
            if extractor.driver:
                try:
                    extractor.driver.quit()
                except:
                    pass
                extractor.driver = None
                print("👋 Chrome closed successfully.")

            print("💤 Sleeping until tomorrow's run...")
            first_run = False
            # Wait at least 5 minutes before checking wait_until_6pm again
            time.sleep(300) 
            
        except KeyboardInterrupt:
            print("\n👋 Scheduler stopped by user.")
            break
        except Exception as e:
            print(f"⚠️ Error in scheduler loop: {e}")
            print("🔄 Retrying in 5 minutes...")
            time.sleep(300)

