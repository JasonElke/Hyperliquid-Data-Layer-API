import re
import time
import os
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.action_chains import ActionChains
from dotenv import load_dotenv, set_key
from .browser_manager import BrowserManager
from .gmail_service import GmailService

class KeyExtractor:
    """Handles the 14-step flow to extract API keys from Zoom streams."""

    def __init__(self):
        self.browser_mgr = BrowserManager()
        self.gmail_svc = GmailService()
        self.driver = None
        self.wait = None
        self.env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
        self.external_env_path = "/Users/thuongthai/work/zzu-traders/.env"

    def setup(self):
        """Setup driver and wait utility."""
        self.driver = self.browser_mgr.get_driver()
        self.wait = WebDriverWait(self.driver, 20)

    def _write_to_env_file(self, path, key_name, key_value):
        """Helper to write key to a specific .env file."""
        if not os.path.exists(path):
            # Create parent directory if it doesn't exist
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, 'w') as f:
                f.write("")
        
        env_lines = []
        key_exists = False
        with open(path, 'r') as f:
            for line in f:
                if line.startswith(f"{key_name}="):
                    env_lines.append(f"{key_name}={key_value}\n")
                    key_exists = True
                else:
                    env_lines.append(line)
        
        if not key_exists:
            env_lines.append(f"{key_name}={key_value}\n")
            
        with open(path, 'w') as f:
            f.writelines(env_lines)
        print(f"✅ Updated {path}: {key_name}={key_value}")

    def update_env(self, key_name, key_value):
        """Updates or adds a key to both .env files without quotes."""
        # 1. Update local .env
        self._write_to_env_file(self.env_path, key_name, key_value)
        
        # 2. Update external .env (zzu-traders)
        try:
            self._write_to_env_file(self.external_env_path, key_name, key_value)
        except Exception as e:
            print(f"⚠️ Could not update external .env at {self.external_env_path}: {e}")

    def run_flow(self, test_meeting_id=None, wait_timeout_mins=15):
        """Execute the full extraction sequence. Returns True if successful."""
        try:
            meeting_id = None
            if test_meeting_id:
                print(f"🧪 TEST MODE: Using provided Meeting ID: {test_meeting_id}")
                meeting_id = test_meeting_id.replace(" ", "")
            else:
                # 1-3. Use Gmail API instead of Selenium for Gmail
                print("📧 Fetching stream link via Gmail API...")
                try:
                    stream_url = self.gmail_svc.get_stream_link()
                except Exception as auth_error:
                    print(f"❌ Gmail API Error: {auth_error}")
                    print("💡 Try deleting auto_keys/token.json and run again to re-authenticate.")
                    return False
                
                if not stream_url:
                    print("❌ Aborting: Could not find stream link.")
                    return False

                # Now start Selenium for the rest of the flow
                self.setup()

                # 4. Navigate to stream page and get Zoom link
                print(f"🔗 Opening stream page: {stream_url}")
                
                # Retry loop for the redirect page
                zoom_url = None
                for attempt in range(3):
                    try:
                        self.driver.get(stream_url)
                        # Increased timeout and added multiple patterns for the zoom link
                        zoom_link_xpath = "//a[contains(@href, 'zoom.us/j/')]"
                        zoom_element = WebDriverWait(self.driver, 30).until(
                            EC.presence_of_element_located((By.XPATH, zoom_link_xpath))
                        )
                        zoom_url = zoom_element.get_attribute("href")
                        if zoom_url:
                            break
                    except Exception as e:
                        print(f"⚠️ Attempt {attempt+1} to load stream page failed: {e}")
                        time.sleep(5)
                
                if not zoom_url:
                    print("❌ Timeout: Could not find Zoom link on the stream page after 3 attempts.")
                    self.driver.save_screenshot("debug_stream_page_error.png")
                    return False
                
                # 5. Extract Meeting ID from zoom link
                meeting_id = re.search(r'/j/(\d+)', zoom_url).group(1)

            if not self.driver:
                self.setup()

            print(f"🆔 Zoom Meeting ID: {meeting_id}")

            # 6. Go to Zoom Web Join page
            print("🚀 Joining Zoom via Web Client...")
            self.driver.get("https://app.zoom.us/wc/join")

            # 8. Input Room ID
            id_input = self.wait.until(EC.presence_of_element_located((By.CLASS_NAME, "join-meetingId")))
            id_input.send_keys(meeting_id)
            
            join_btn = self.wait.until(EC.element_to_be_clickable((By.CLASS_NAME, "btn-join")))
            join_btn.click()

            # 9. Handle permission modals
            print("🛡 Checking for permission modals...")
            try:
                # Zoom sometimes shows multiple modals or a single one. 
                # We wait specifically for the "Continue without microphone and camera" button
                bypass_btn_xpath = "//span[contains(text(), 'Continue without microphone and camera') or contains(text(), 'Tiếp tục mà không có micrô và camera')]"
                time.sleep(3) 
                
                bypass_elements = self.driver.find_elements(By.XPATH, bypass_btn_xpath)
                if bypass_elements:
                    print("🔘 Clicking 'Continue without microphone and camera'...")
                    bypass_elements[0].click()
                else:
                    # Fallback: find any button that might be a bypass in the modal
                    alternatives = self.driver.find_elements(By.CLASS_NAME, "pepc-permission-dialog__footer-button")
                    if alternatives:
                        alternatives[0].click()
                        print("🔘 Clicked alternative bypass button.")
            except Exception as e:
                print(f"⚠️ Error handling modal: {str(e)}")

            # 9.5 Disable Mic and Cam before joining
            print("🔇 Ensuring Mic and Cam are disabled (Vietnamese UI)...")
            time.sleep(5) 
            try:
                # Zoom web client can sometimes be inside an iframe
                iframes = self.driver.find_elements(By.TAG_NAME, "iframe")
                for i, frame in enumerate(iframes):
                    print(f"🌐 Checking iframe {i}...")
                    self.driver.switch_to.frame(frame)
                    if self.driver.find_elements(By.ID, "preview-audio-control-button"):
                        print(f"✅ Found controls inside iframe {i}")
                        break
                    self.driver.switch_to.default_content()

                short_wait = WebDriverWait(self.driver, 10)
                
                # Disable Audio if enabled
                audio_btn = short_wait.until(EC.presence_of_element_located((By.ID, "preview-audio-control-button")))
                audio_label = (audio_btn.get_attribute("aria-label") or "").lower()
                audio_text = audio_btn.text.lower()
                print(f"🎤 Mic status: label='{audio_label}', text='{audio_text}'")
                
                # "Tắt tiếng" means it's currently ON
                if any(x in audio_label or x in audio_text for x in ["mute", "tắt tiếng", "ngắt tiếng"]):
                    print("🎤 Mic is ON, muting now...")
                    self.driver.execute_script("arguments[0].click();", audio_btn)
                else:
                    print("✅ Mic is already muted.")

                # Disable Video if enabled
                video_btn = short_wait.until(EC.presence_of_element_located((By.ID, "preview-video-control-button")))
                video_label = (video_btn.get_attribute("aria-label") or "").lower()
                video_text = video_btn.text.lower()
                print(f"📷 Cam status: label='{video_label}', text='{video_text}'")
                
                # "Dừng video" or "Tắt video" means it's currently ON
                if any(x in video_label or x in video_text for x in ["stop", "dừng", "tắt video", "ngắt video"]):
                    print("📷 Cam is ON, stopping video now...")
                    self.driver.execute_script("arguments[0].click();", video_btn)
                else:
                    print("✅ Cam is already off.")
            except Exception as e:
                print(f"⚠️ Could not verify Mic/Cam status: {str(e)}")

            # 10. Input Name and Join
            print("📝 Entering name 'Thuongzzu'...")
            try:
                name_input = self.wait.until(EC.presence_of_element_located((By.ID, "input-for-name")))
                self.driver.execute_script("arguments[0].scrollIntoView(true);", name_input)
                time.sleep(1)
                
                # Clear and type name slowly to trigger UI updates
                name_input.clear()
                for char in "Thuongzzu":
                    name_input.send_keys(char)
                    time.sleep(0.1)
                print("✅ Entered name.")
                
                # Try to click "Remember my name" (Ghi nhớ tên)
                try:
                    remember_cb = self.driver.find_element(By.CLASS_NAME, "preview-remember-name")
                    remember_cb.click()
                except:
                    pass

                # Wait for join button (Tham gia) to be enabled
                print("⏳ Waiting for 'Tham gia' button to be enabled...")
                final_join_xpath = "//button[contains(@class, 'preview-join-button')]"
                final_join_btn = self.wait.until(EC.presence_of_element_located((By.XPATH, final_join_xpath)))
                
                # Wait loop for the button to not be disabled
                for _ in range(10):
                    is_disabled = "disabled" in (final_join_btn.get_attribute("class") or "")
                    if not is_disabled:
                        print("✨ 'Tham gia' button is now enabled!")
                        break
                    time.sleep(1)
                
                print("🔘 Clicking 'Tham gia'...")
                self.driver.execute_script("arguments[0].click();", final_join_btn)
                print("✅ Join sequence complete.")
            except Exception as e:
                print(f"❌ Failed to join: {str(e)}")
                raise

            # 11. Wait for host to accept (Wait loop)
            print("⏳ Waiting for host to accept and room to load...")
            self.driver.switch_to.default_content()
            
            # Wait for the loading overlay to disappear
            try:
                WebDriverWait(self.driver, 45).until(
                    EC.invisibility_of_element_located((By.ID, "wc-loading"))
                )
                print("✨ Loading overlay gone.")
            except:
                print("⚠️ Warning: Loading overlay timeout, checking page content...")

            # Room entry monitoring loop
            print("⏳ Monitoring room entry indicators...")
            target_frame_index = -1 # -1 means main content
            
            # 15 minutes = 180 attempts (180 * 5s = 900s)
            max_attempts = int(wait_timeout_mins * 60 / 5)
            
            for attempt in range(max_attempts):
                try:
                    self.driver.switch_to.default_content()
                    
                    # Find all iframes
                    iframes = self.driver.find_elements(By.TAG_NAME, "iframe")
                    # We'll check main content (index -1) and each iframe index
                    indices_to_check = [-1] + list(range(len(iframes)))
                    
                    in_room = False
                    for idx in indices_to_check:
                        try:
                            self.driver.switch_to.default_content()
                            if idx != -1:
                                # Re-find iframes to avoid staleness
                                current_iframes = self.driver.find_elements(By.TAG_NAME, "iframe")
                                if idx < len(current_iframes):
                                    self.driver.switch_to.frame(current_iframes[idx])
                                else:
                                    continue

                            # 1. Handle "Join Audio" popup inside this frame
                            audio_popup = self.driver.find_elements(By.XPATH, "//button[contains(text(), 'Join Audio') or contains(text(), 'Kết nối âm thanh') or contains(text(), 'Hủy bỏ')]")
                            if audio_popup:
                                try:
                                    self.driver.execute_script("arguments[0].click();", audio_popup[0])
                                    print(f"🔊 Cleared Audio popup in frame {idx}")
                                except:
                                    pass

                            # 2. Check for Chat/Footer indicators
                            # Exact label from user's HTML: "Chat" or "Trò chuyện"
                            chat_selectors = [
                                "//button[contains(@aria-label, 'chat panel')]",
                                "//button[contains(@aria-label, 'Trò chuyện')]",
                                "//span[contains(text(), 'Trò chuyện')]",
                                "//span[contains(text(), 'Chat')]",
                                "//button[contains(., 'Trò chuyện')]",
                                "#wc-footer",
                                ".footer-chat-button",
                                ".footer-button__button"
                            ]
                            
                            source = self.driver.page_source
                            source_lower = source.lower()
                            
                            # PRIORITIZE finding room indicators
                            found_room_indicator = False
                            for selector in chat_selectors:
                                try:
                                    if selector.startswith("//"):
                                        els = self.driver.find_elements(By.XPATH, selector)
                                    else:
                                        els = self.driver.find_elements(By.CSS_SELECTOR, selector)
                                    
                                    if els:
                                        if "trò chuyện" in source_lower or "chat" in source_lower or "wc-footer" in source_lower:
                                            in_room = True
                                            target_frame_index = idx
                                            print(f"✅ Found room indicator in frame {idx}: {selector}")
                                            found_room_indicator = True
                                            break
                                except:
                                    continue
                            
                            if found_room_indicator:
                                break

                            # ONLY if no room indicator, check if we are in Waiting Room
                            waiting_room_indicators = [
                                "Người chủ trì sẽ chấp nhận bạn",
                                "khi họ sẵn sàng",
                                "Please wait, the meeting host will let you in soon",
                                "Đang chờ người chủ trì bắt đầu cuộc họp",
                                "waiting-room-video-container",
                                "waiting-room-content-container",
                                "wr-information",
                                "wr-topic"
                            ]
                            
                            is_in_waiting_room = any(wi in source for wi in waiting_room_indicators)
                            if is_in_waiting_room:
                                in_room = False
                            
                            if in_room:
                                break
                        except Exception:
                            # Frame might be inaccessible or reloaded
                            continue
                            # Frame might be inaccessible or reloaded
                            continue
                    
                    if in_room:
                        # Final check: are we still in the "Waiting for host" screen?
                        source = self.driver.page_source.lower()
                        # If we see "vui lòng chờ" or similar AND no chat button label in text, we might be in waiting room
                        waiting_texts = ["vui lòng chờ", "waiting for the host"]
                        if any(wt in source for wt in waiting_texts) and "chat" not in source and "trò chuyện" not in source:
                            in_room = False 
                        
                    if in_room:
                        print(f"🎉 Successfully entered the meeting room (Frame index: {target_frame_index})!")
                        break
                    
                    if attempt % 5 == 0:
                        # Log iframes found for debugging
                        try:
                            iframe_ids = [f.get_attribute('id') or f.get_attribute('class') or str(i) for i, f in enumerate(iframes)]
                            print(f"⏳ Waiting... (Attempt {attempt+1}/{max_attempts}). Iframes found: {iframe_ids}")
                        except:
                            print(f"⏳ Waiting... (Attempt {attempt+1}/{max_attempts})")
                    
                except Exception as e:
                    # Ignore common polling errors like stale elements or missing frames
                    if "no such element" not in str(e).lower() and "stale element" not in str(e).lower():
                        print(f"⚠️ Monitoring loop error: {str(e)}")
                
                time.sleep(5)
            
            # 12. Open Chat
            print("💬 Opening chat panel...")
            time.sleep(3) # Give UI time to settle
            try:
                def find_chat_button():
                    chat_selectors = [
                        "//button[contains(@aria-label, 'chat panel')]",
                        "//button[contains(@aria-label, 'Trò chuyện')]",
                        "//span[contains(text(), 'Trò chuyện')]/ancestor::button",
                        "//span[contains(text(), 'Chat')]/ancestor::button",
                        "//div[contains(@class, 'footer-chat-button')]//button",
                        ".footer-button__button[aria-label*='chat']",
                        "button.footer-button-base__button"
                    ]
                    
                    for selector in chat_selectors:
                        try:
                            elements = self.driver.find_elements(By.XPATH, selector) if selector.startswith("//") else self.driver.find_elements(By.CSS_SELECTOR, selector)
                            for el in elements:
                                label = (el.get_attribute("aria-label") or "").lower()
                                text = (el.text or "").lower()
                                if "chat" in label or "trò chuyện" in label or "chat" in text or "trò chuyện" in text:
                                    return el
                        except:
                            continue
                    return None

                # Try the identified frame first
                self.driver.switch_to.default_content()
                if target_frame_index != -1:
                    iframes = self.driver.find_elements(By.TAG_NAME, "iframe")
                    if target_frame_index < len(iframes):
                        self.driver.switch_to.frame(iframes[target_frame_index])
                
                chat_btn = find_chat_button()
                
                # If not found, re-scan all frames
                if not chat_btn:
                    print("⚠️ Chat button not found at stored index, re-scanning frames...")
                    self.driver.switch_to.default_content()
                    iframes = self.driver.find_elements(By.TAG_NAME, "iframe")
                    for i, frame in enumerate(iframes):
                        try:
                            self.driver.switch_to.default_content()
                            self.driver.switch_to.frame(frame)
                            chat_btn = find_chat_button()
                            if chat_btn:
                                target_frame_index = i
                                print(f"✅ Found chat button in frame {i} after re-scan.")
                                break
                        except:
                            continue
                
                if chat_btn:
                    # Check if already open (label starts with "close" or "đóng")
                    label = (chat_btn.get_attribute("aria-label") or "").lower()
                    if "close" in label or "đóng" in label:
                        print("✅ Chat panel is already open.")
                    else:
                        # Move mouse to footer to make it fade in
                        try:
                            footer = self.driver.find_element(By.ID, "wc-footer")
                            actions = ActionChains(self.driver)
                            actions.move_to_element(footer).perform()
                            time.sleep(1)
                        except:
                            pass
                        self.driver.execute_script("arguments[0].click();", chat_btn)
                        print("✅ Chat panel opened.")
                else:
                    print("❌ Could not find Chat button.")
                    self.driver.save_screenshot("debug_chat_not_found.png")
                    raise Exception("Chat button not found after multiple attempts")
            except Exception as e:
                print(f"❌ Failed to open chat: {str(e)}")
                return False

            # 13. Wait and extract API key
            print("🔑 Monitoring chat content for API key...")
            api_key_pattern = r"moonstream_[a-f0-9]+"
            
            seen_texts = set()
            extracted_key = None
            timeout = 3600
            start_time = time.time()
            
            while time.time() - start_time < timeout:
                try:
                    # Switch to the correct frame for scanning
                    self.driver.switch_to.default_content()
                    if target_frame_index != -1:
                        iframes = self.driver.find_elements(By.TAG_NAME, "iframe")
                        if target_frame_index < len(iframes):
                            self.driver.switch_to.frame(iframes[target_frame_index])

                    text_boxes = self.driver.find_elements(By.CLASS_NAME, "new-chat-message__text-box")
                    
                    for box in text_boxes:
                        content = box.text.strip()
                        if not content or content in seen_texts:
                            continue
                        
                        seen_texts.add(content)
                        # Optional: Print raw content to terminal for visibility
                        # print(f"📩 Chat: {content[:100]}...") 

                        # Check for API key pattern
                        match = re.search(api_key_pattern, content)
                        if match:
                            extracted_key = match.group(0)
                            print(f"\n🎯 FOUND API KEY: {extracted_key}")
                            print(f"📄 Full message: {content}\n")
                            break
                    
                    if extracted_key:
                        break
                        
                except Exception as e:
                    # Silently ignore minor DOM update errors during scan
                    pass
                
                time.sleep(2) # Scan every 2 seconds

            if extracted_key:
                self.update_env("MOON_DEV_API_KEY", extracted_key)
                return True
            else:
                print("❌ Timeout: API key not found in chat content within 1 hour.")
                return False

        except Exception as e:
            print(f"❌ Error during flow: {str(e)}")
            return False
        # Driver quit is now handled by the caller to allow keeping it open

if __name__ == "__main__":
    extractor = KeyExtractor()
    # Test Meeting ID: 869 2524 0050
    extractor.run_flow(test_meeting_id="869 2524 0050")

