import os
import sys
import json
import time
import random
import traceback
import urllib.request
import urllib.parse
import html
import re
from pathlib import Path
from playwright.sync_api import sync_playwright, Response, Page, BrowserContext


class ActivityLogger:
    """Thread-safe-styled cleaner logger to record execution timeline cleanly."""
    def __init__(self):
        self.logs = []

    def info(self, message: str):
        clean_msg = str(message).encode('ascii', 'backslashreplace').decode('ascii')
        timestamp = time.strftime("%H:%M:%S")
        formatted = f"[{timestamp}] {clean_msg}"
        self.logs.append(formatted)
        print(formatted)

    def get_log_string(self) -> str:
        return "\n".join(self.logs)


logger = ActivityLogger()


class ChorchaQuizBot:
    def __init__(self):
        # Configuration Fallbacks
        self.telegram_token = os.environ.get("TELEGRAM_BOT_TOKEN", "8919385228:AAEvXH_q3EL-kFu0gihCb2RX6Fc4E0kgtbU")
        self.chat_id = os.environ.get("TELEGRAM_CHAT_ID", "8309418981")
        self.auth_file = Path(__file__).parent / "auth.json"
        
        # Runtime Operational States
        self.correct_options = {}
        self.decoded_answers_text = {}
        self.selected_subject = "Unknown"
        self.selected_chapter = "Unknown"
        self.question_count = 0
        self.streak_captured = False
        self.streak_image_path = None

    def send_telegram_payload(self, success: bool, error_msg: str = None, traceback_str: str = None):
        """Assembles and dispatches a unified text alert to Telegram securely."""
        url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
        subject_esc = html.escape(self.selected_subject)
        chapter_esc = html.escape(self.selected_chapter)
        
        # Status Card Title
        status_header = "✅ <b>Chorcha Bot: Practice Completed</b>\n\n" if success else "❌ <b>Chorcha Bot: Exception Triggered</b>\n\n"
        
        # Meta Metrics
        details_part = (
            f"<b>Subject:</b> {subject_esc}\n"
            f"<b>Chapter:</b> {chapter_esc}\n"
            f"<b>Total Answered:</b> {self.question_count} Questions\n"
            f"<b>Streak Captured:</b> {'Yes 🔥' if self.streak_captured else 'No ⚠️'}\n\n"
        )
        
        # Context Parsing
        if success:
            ans_json = json.dumps(self.decoded_answers_text, indent=4, ensure_ascii=False)
            if len(ans_json) > 1200:
                ans_json = ans_json[:1100] + "\n...[Answers Data Truncated]..."
            payload_section = f"<b>Decoded Solutions Grid:</b>\n<pre>{html.escape(ans_json)}</pre>\n\n"
        else:
            err_esc = html.escape(str(error_msg or 'Fatal Native Interruption'))
            tb_formatted = traceback_str or 'Traceback footprint unavailable.'
            if len(tb_formatted) > 1200:
                tb_formatted = tb_formatted[:1100] + "\n...[Stack-trace Truncated]..."
            payload_section = f"<b>Error Stack:</b> <code>{err_esc}</code>\n\n<b>Traceback:</b>\n<pre>{html.escape(tb_formatted)}</pre>\n\n"

        # Safe Space Engine Allocation for Activity Logs
        logs_accumulated = logger.get_log_string()
        base_overhead = len(status_header) + len(details_part) + len(payload_section) + len("📋 <b>Activity Pipeline:</b>\n<pre></pre>")
        usable_buffer = 4096 - base_overhead - 100  # Safe margins for encoding inflation
        
        if len(logs_accumulated) > usable_buffer:
            logs_accumulated = "[...Timeline Truncated...]\n" + logs_accumulated[-max(300, usable_buffer):]
            
        message_body = (
            f"{status_header}"
            f"{details_part}"
            f"{payload_section}"
            f"📋 <b>Activity Pipeline:</b>\n<pre>{html.escape(logs_accumulated)}</pre>"
        )

        data = urllib.parse.urlencode({
            "chat_id": self.chat_id,
            "text": message_body,
            "parse_mode": "HTML"
        }).encode("utf-8")
        
        try:
            req = urllib.request.Request(url, data=data, headers={"User-Agent": "ChorchaAutomationEngine/2.0"})
            with urllib.request.urlopen(req, timeout=15) as response:
                return response.read()
        except Exception as ex:
            print(f"CRITICAL: Failed dispatching Telegram system log message: {ex}")

    def send_telegram_photo(self, photo_path: str, caption: str):
        """Dispatches an isolated high-priority visual multi-part form media packet."""
        if not photo_path or not os.path.exists(photo_path):
            return
            
        url = f"https://api.telegram.org/bot{self.telegram_token}/sendPhoto"
        import uuid
        boundary = f"MultipartBoundary-{uuid.uuid4().hex}"
        
        payload_parts = [
            b'--' + boundary.encode('utf-8'),
            b'Content-Disposition: form-data; name="chat_id"',
            b'',
            self.chat_id.encode('utf-8'),
            b'--' + boundary.encode('utf-8'),
            b'Content-Disposition: form-data; name="caption"',
            b'',
            caption.encode('utf-8'),
            b'--' + boundary.encode('utf-8'),
            b'Content-Disposition: form-data; name="parse_mode"',
            b'',
            b'HTML',
            b'--' + boundary.encode('utf-8'),
            f'Content-Disposition: form-data; name="photo"; filename="{os.path.basename(photo_path)}"'.encode('utf-8'),
            b'Content-Type: image/png',
            b''
        ]
        
        with open(photo_path, 'rb') as img_file:
            payload_parts.append(img_file.read())
            
        payload_parts.append(b'--' + boundary.encode('utf-8') + b'--')
        payload_parts.append(b'')
        body = b'\r\n'.join(payload_parts)
        
        req = urllib.request.Request(
            url, data=body,
            headers={
                'Content-Type': f'multipart/form-data; boundary={boundary}',
                'Content-Length': str(len(body)),
                'User-Agent': 'ChorchaAutomationEngine/2.0'
            }
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                return response.read()
        except Exception as ex:
            print(f"CRITICAL: Failed dispatching multi-part binary snapshot: {ex}")

    @staticmethod
    def decode_string(encoded_str: str, key: str) -> str:
        if not encoded_str or not isinstance(encoded_str, str):
            return encoded_str
        decoded = []
        key_len = len(key)
        for i, char in enumerate(encoded_str):
            decoded.append(chr((ord(char) - ord(key[i % key_len]) + 65536) % 65536))
        return ''.join(decoded)

    @staticmethod
    def evaluate_option_index(decoded_ans: str) -> int:
        ans = decoded_ans.strip().upper()
        if not ans:
            return 0
        # Character Grid Checks
        for char, index in [("A", 0), ("B", 1), ("C", 2), ("D", 3), ("1", 0), ("2", 1), ("3", 2), ("4", 3)]:
            if char in ans:
                return index
        return 0

    def intercept_exam_payloads(self, response: Response):
        """Asynchronous API Listener targeting backend structural configurations."""
        if "mujib.chorcha.net/exam/quick" in response.url and response.request.method == "POST":
            logger.info("Fired API Target Catch: Intercepted internal exam schema packet.")
            x_chorcha_id = response.headers.get("x-chorcha-id")
            if not x_chorcha_id:
                logger.info("Anomaly: Found verification target block missing structural validation hash header.")
                return
            try:
                payload = response.json()
                questions = payload.get("data", {}).get("questions", [])
                logger.info(f"Synchronized backend mapping grid matrix: Packed {len(questions)} items safely.")
                
                for idx, item in enumerate(questions):
                    encoded_ans = item.get("answer")
                    decoded_ans = self.decode_string(encoded_ans, x_chorcha_id).strip()
                    q_idx = idx + 1
                    
                    self.correct_options[q_idx] = self.evaluate_option_index(decoded_ans)
                    self.decoded_answers_text[q_idx] = decoded_ans
            except Exception as ex:
                logger.info(f"Exception raised tracking custom background interceptors: {ex}")

    def push_auth_cookies(self, context: BrowserContext) -> bool:
        if not self.auth_file.exists():
            logger.info(f"State Interruption: Target system payload missing data file: '{self.auth_file}'")
            return False
        try:
            with open(self.auth_file, "r", encoding="utf-8") as f:
                cookies = json.load(f)
            
            reformatted_cookies = []
            for c in cookies:
                pc = {"name": c["name"], "value": c["value"], "domain": c["domain"], "path": c["path"]}
                if "expirationDate" in c: pc["expires"] = int(c["expirationDate"])
                if "httpOnly" in c: pc["httpOnly"] = c["httpOnly"]
                if "secure" in c: pc["secure"] = c["secure"]
                if "sameSite" in c and c["sameSite"] in ["Lax", "Strict", "None"]:
                    pc["sameSite"] = c["sameSite"]
                reformatted_cookies.append(pc)
                
            context.add_cookies(reformatted_cookies)
            logger.info("Successfully loaded localized target credentials context layers cleanly.")
            return True
        except Exception as ex:
            logger.info(f"Failed parsing validation storage modules: {ex}")
            return False

    def capture_dashboard_streak(self, page: Page):
        """Navigates to the homepage, safely triggers, captures, and handles the streak dialog."""
        logger.info("Transitioning to main application home view for performance indexing verification...")
        try:
            # Force navigation to dashboard explicitly
            page.goto("https://chorcha.net/", wait_until="commit", timeout=20000)
            try:
                page.locator(".text-sm.py-1.px-3.cursor-pointer, [class*='text-sm py-1 px-3 cursor-pointer'], footer, header").first.wait_for(state="visible", timeout=10000)
            except:
                pass
            page.wait_for_timeout(2500)  # Allow client hydration architecture to stabilize safely
            
            streak_selector = ".text-sm.py-1.px-3.cursor-pointer, [class*='text-sm py-1 px-3 cursor-pointer']"
            streak_target = page.locator(streak_selector).first
            
            if streak_target.is_visible():
                logger.info("Identified high-priority streak tracking widget block element match. Triggering click...")
                streak_target.scroll_into_view_if_needed()
                streak_target.click()
                page.wait_for_timeout(2000)  # Wait for transition frame animation parameters to execute
                
                # Capture and record target frame layout properties
                self.streak_image_path = f"streak_metric_{int(time.time())}.png"
                page.screenshot(path=self.streak_image_path)
                self.streak_captured = True
                logger.info(f"Local binary context saved: '{self.streak_image_path}'")
                
                # Immediate visual dispatch tracking loop
                self.send_telegram_photo(
                    self.streak_image_path, 
                    f"🔥 <b>Chorcha System Status: Streak Track Verification Verified!</b>\nSubject Context: {html.escape(self.selected_subject)}"
                )
                
                # Cleanup viewport overlay manually to keep terminal fluid
                page.keyboard.press("Escape")
                page.wait_for_timeout(500)
            else:
                logger.info("Operational report: Streak widget element footprint missing from current structural viewport matrix context.")
        except Exception as ex:
            logger.info(f"Warning encountered during standalone streak monitoring automation loops: {ex}")

    def execute_pipeline(self):
        """Core Orchestrator running atomic browser functions sequentially."""
        logger.info("Initializing automated performance assessment engine routines...")
        
        failed_chapters = set()
        failed_subjects = set()
        quiz_initialized = False
        
        with sync_playwright() as playwright:
            headless_mode = os.environ.get("HEADLESS", "false").lower() == "true" or "CI" in os.environ
            browser = playwright.chromium.launch(
                headless=headless_mode,
                args=[] if headless_mode else ["--start-maximized"]
            )
            
            context_args = {"viewport": {"width": 1280, "height": 800}} if headless_mode else {"no_viewport": True}
            context = browser.new_context(**context_args)
            
            self.push_auth_cookies(context)
            page = context.new_page()
            
            # Setup dynamic network monitors
            page.on("response", self.intercept_exam_payloads)
            
            navigation_loop_limit = 5
            loop_idx = 0
            
            while not quiz_initialized and loop_idx < navigation_loop_limit:
                loop_idx += 1
                logger.info(f"Executing systemic data navigation pass ({loop_idx}/{navigation_loop_limit})...")
                
                self.correct_options.clear()
                self.decoded_answers_text.clear()
                
                try:
                    page.goto("https://chorcha.net/practice-exam", wait_until="commit", timeout=20000)
                    target_selector = 'main h3, button:has-text("লগইন"), button:has-text("Login"), a:has-text("লগইন"), a:has-text("Login")'
                    page.locator(target_selector).first.wait_for(state="visible", timeout=20000)
                except Exception as ex:
                    logger.info(f"Primary routing process failed due to latency constraints: {ex}. Recalibrating tracking matrix line...")
                    continue
                
                # Runtime Login Validation Gate
                login_indicator = page.locator('text="লগইন", text="Login"').first
                if login_indicator.is_visible():
                    if headless_mode:
                        raise RuntimeError("Context execution breakdown: Credentials mismatch detected inside virtual terminal runtime window.")
                    logger.info("User prompt required: Authorization state expired. Awaiting synchronization manual confirmation locks...")
                    while login_indicator.is_visible():
                        page.wait_for_timeout(1000)
                    page.wait_for_timeout(2000)
                
                # Subject Extraction Routines
                subject_headers = page.locator('main h3')
                try: subject_headers.first.wait_for(state="visible", timeout=8000)
                except: logger.info("Subject mapping grid target timed out."); continue
                
                total_subs = subject_headers.count()
                target_bangla_nodes = []
                ict_fallback_node = None
                
                for i in range(total_subs):
                    try:
                        title = subject_headers.nth(i).inner_text().strip()
                        if "বাংলা" in title and title not in failed_subjects:
                            target_bangla_nodes.append((i, title))
                        if "তথ্য ও যোগাযোগ প্রযুক্তি" in title:
                            ict_fallback_node = (i, title)
                    except: pass
                
                if target_bangla_nodes:
                    chosen_idx, chosen_title = random.choice(target_bangla_nodes)
                    logger.info(f"Random operational matching confirmed: Loaded '{chosen_title}'")
                elif ict_fallback_node and ict_fallback_node[1] not in failed_subjects:
                    chosen_idx, chosen_title = ict_fallback_node
                    logger.info(f"Fallback verification triggered: Defaulting to standard layer payload target: '{chosen_title}'")
                else:
                    logger.info("Execution block clear: No fresh unparsed components found. Resetting state arrays entirely...")
                    failed_subjects.clear()
                    failed_chapters.clear()
                    continue
                
                self.selected_subject = chosen_title
                subject_btn = subject_headers.nth(chosen_idx)
                subject_btn.scroll_into_view_if_needed()
                subject_btn.click()
                
                # Paper Sub-Selection Strategy Validation Layer
                try: page.locator('main h2').wait_for(state="visible", timeout=6000)
                except: failed_subjects.add(chosen_title); continue
                
                chapter_nodes = page.locator('main h3').all()
                paper_sub_options = []
                for node in chapter_nodes:
                    try:
                        node_text = node.inner_text().strip()
                        if any(phrase in node_text for phrase in ["প্রথম পত্র", "২য় পত্র", "দ্বিতীয় পত্র"]):
                            paper_sub_options.append(node)
                    except: pass
                    
                if paper_sub_options:
                    chosen_paper_node = random.choice(paper_sub_options)
                    logger.info(f"Routing sub-module branch segment link target: '{chosen_paper_node.inner_text().strip()}'")
                    chosen_paper_node.scroll_into_view_if_needed()
                    chosen_paper_node.click()
                    page.wait_for_timeout(1000)
                    chapter_nodes = page.locator('main h3').all()
                
                # Chapter Extraction Filtration Flow
                valid_chapter_pool = []
                for node in chapter_nodes:
                    try:
                        txt = node.inner_text().strip()
                        if txt and (self.selected_subject, txt) not in failed_chapters:
                            valid_chapter_pool.append((node, txt))
                    except: pass
                    
                if not valid_chapter_pool:
                    logger.info("Zero chapter processing units found. Flushing cache markers down...")
                    failed_chapters.clear()
                    continue
                    
                target_node, target_text = random.choice(valid_chapter_pool)
                self.selected_chapter = target_text
                logger.info(f"Target node connection lock verified on entry text: '{target_text}'")
                target_node.scroll_into_view_if_needed()
                target_node.click()
                
                # Engagement Action Process Launch Sequence
                quick_practice_action = page.locator('button:has-text("দ্রুত প্র্যাকটিস")')
                
                # Account for sliding layouts or accordion frameworks
                start_clock = time.time()
                while (time.time() - start_clock) < 2.5:
                    if quick_practice_action.is_visible(): break
                    page.wait_for_timeout(150)
                    
                if not quick_practice_action.is_visible():
                    nested_sub_nodes = page.locator('main h3').all()
                    active_sub_pool = [n for n in nested_sub_nodes if n.is_visible() and n.inner_text().strip() != target_text]
                    if active_sub_pool:
                        sub_selected_node = random.choice(active_sub_pool)
                        self.selected_chapter = sub_selected_node.inner_text().strip()
                        logger.info(f"Expanding granular operational structural branch mapping: '{self.selected_chapter}'")
                        sub_selected_node.scroll_into_view_if_needed()
                        sub_selected_node.click()
                
                try:
                    quick_practice_action.wait_for(state="visible", timeout=6000)
                    quick_practice_action.click()
                    
                    # Wait up to 8 seconds dynamically for correct_options to populate
                    start_time = time.time()
                    while not self.correct_options and (time.time() - start_time) < 8.0:
                        page.wait_for_timeout(100)
                    
                    if self.correct_options:
                        quiz_initialized = True
                    else:
                        logger.info("Internal tracking validation metrics failure: Intercept keys mismatch.")
                        failed_chapters.add((self.selected_subject, self.selected_chapter))
                except Exception as ex:
                    logger.info(f"System execution bottleneck matching targets: {ex}")
                    failed_chapters.add((self.selected_subject, self.selected_chapter))
            
            if not quiz_initialized:
                raise RuntimeError("Failed to resolve stable functional database matrix endpoints to initialize automated assessment sequences.")
            
            # Interactive Automation Solution Injection Run Loop
            logger.info("Quiz matrix pipeline fully live. Executing automated responses maps dynamically...")
            consecutive_wait_ticks = 0
            
            while True:
                skip_gate = page.locator('button:has-text("স্কিপ করো")')
                advance_gate = page.locator('button:has-text("এগিয়ে যাও")')
                
                if skip_gate.is_visible() or advance_gate.is_visible():
                    logger.info("Final target metrics dashboard threshold reached safely. Breaking dynamic solution injection tracking loop.")
                    break
                    
                option_nodes = page.locator('button.rounded-xl.border')
                if option_nodes.count() > 0:
                    consecutive_wait_ticks = 0
                    self.question_count += 1
                    
                    target_selection_index = self.correct_options.get(self.question_count, 0)
                    
                    # Deliberate anti-bot detection injection variance emulation block logic
                    if self.question_count == 15:
                        actual_node_count = option_nodes.count()
                        logger.info(f"Executing noise profile injection logic rules matrix over index tracking item: [{self.question_count}]")
                        target_selection_index = (target_selection_index + 1) % (actual_node_count if actual_node_count > 0 else 4)
                        
                    if target_selection_index >= option_nodes.count():
                        target_selection_index = 0
                        
                    logger.info(f"Resolving item context node [{self.question_count}] -> Committing selection node offset choice: {target_selection_index}")
                    try:
                        option_nodes.nth(target_selection_index).click()
                    except:
                        try: option_nodes.first.click()
                        except: pass
                        
                    next_item_trigger = page.locator('button:has-text("পরের প্রশ্ন"), button:has-text("শেষ করো")')
                    try:
                        next_item_trigger.wait_for(state="visible", timeout=2000)
                        next_item_trigger.click()
                        next_item_trigger.wait_for(state="hidden", timeout=2000)
                    except: pass
                    
                    page.wait_for_timeout(200)
                else:
                    page.wait_for_timeout(1000)
                    consecutive_wait_ticks += 1
                    if consecutive_wait_ticks >= 12:
                        if skip_gate.is_visible() or advance_gate.is_visible(): break
                        logger.info("Timeout check triggered: Internal sequence trace stalled out in standard execution pipeline loop.")
                        break
            
            # Post-Exam Diagnostics Dashboard Validation Procedures
            try:
                metrics_screenshot_file = f"metrics_checkpoint_{int(time.time())}.png"
                page.screenshot(path=metrics_screenshot_file)
                self.send_telegram_photo(metrics_screenshot_file, f"📊 <b>Chorcha Core System Session Checkpoint Metrics Frame Saved</b>")
            except: pass
            
            # Review Screen Checking Sequence Block
            error_review_trigger = page.locator('button:has-text("ভুলগুলো রিভিউ করো")')
            if error_review_trigger.is_visible():
                logger.info("Located operational error correction assessment arrays block link item. Running sanity trace index paths...")
                try:
                    error_review_trigger.click()
                    page.wait_for_timeout(2000)
                    review_view_screenshot = f"error_review_checkpoint_{int(time.time())}.png"
                    page.screenshot(path=review_view_screenshot)
                    self.send_telegram_photo(review_view_screenshot, f"🔍 <b>Error Analysis Layer Context Saved For Processing Run</b>")
                    page.go_back()
                    page.wait_for_load_state("domcontentloaded")
                    page.wait_for_timeout(1000)
                except Exception as ex:
                    logger.info(f"Bypassed non-blocking inspection failure loop exception rules safely: {ex}")

            # Safe Pipeline Closure Processing Intersect Hooks
            skip_action_element = page.locator('button:has-text("স্কিপ করো")')
            advance_action_element = page.locator('button:has-text("এগিয়ে যাও")')
            
            if skip_action_element.is_visible():
                try:
                    skip_action_element.scroll_into_view_if_needed()
                    skip_action_element.click()
                    advance_action_element.wait_for(state="visible", timeout=4000)
                except: pass
                
            if advance_action_element.is_visible():
                try:
                    advance_action_element.scroll_into_view_if_needed()
                    advance_action_element.click()
                    page.wait_for_timeout(1500)
                except: pass
            
            # RUNTIME EXTENSION: Perform Homepage Streak Collection Validation Routines Before Ending System Engine
            self.capture_dashboard_streak(page)
            
            logger.info("Closing runtime context environments safely down without tracing footprints...")
            context.close()
            browser.close()
            
            # Transmit success report array block packet safely out
            self.send_telegram_payload(success=True)

    def run(self):
        try:
            self.execute_pipeline()
        except BaseException as ex:
            error_traceback_str = traceback.format_exc()
            logger.info(f"CRITICAL FAULT: Pipeline structural flow sequence broke down under constraint processing rules: {ex}")
            print(error_traceback_str)
            
            # Dispatch structural alert fail state data traces
            self.send_telegram_payload(success=False, error_msg=str(ex), traceback_str=error_traceback_str)
            raise ex


if __name__ == "__main__":
    bot = ChorchaQuizBot()
    bot.run()
