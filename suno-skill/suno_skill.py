#!/usr/bin/env python3
"""
Suno Music Skill — Generate songs via browser automation.

Suno has no public API. This skill uses Playwright to automate the web interface:
create songs from prompts, wait for generation, download the results.

Usage:
    python3 suno_skill.py login                    # One-time: log in visibly
    python3 suno_skill.py create "PROMPT"          # Generate a song
    python3 suno_skill.py create "PROMPT" --style "indie rock"
    python3 suno_skill.py list                     # List recent songs
    python3 suno_skill.py download URL             # Download a specific song
"""

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

SKILL_DIR = Path(__file__).parent
SESSION_DIR = SKILL_DIR / "sessions"
SESSION_FILE = SESSION_DIR / "suno.json"
OUTPUT_DIR = Path("./output")


def ensure_dirs():
    SESSION_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def get_browser(headless=True):
    """Get a Playwright browser with Suno session loaded."""
    from playwright.sync_api import sync_playwright

    p = sync_playwright().start()
    browser = p.chromium.launch(headless=headless)

    if SESSION_FILE.exists():
        context = browser.new_context(storage_state=str(SESSION_FILE))
    else:
        context = browser.new_context()

    return p, browser, context


def save_session(context):
    """Save browser session (cookies, localStorage) for reuse."""
    ensure_dirs()
    context.storage_state(path=str(SESSION_FILE))


def sanitize_filename(name: str) -> str:
    """Clean a string for use as a filename."""
    name = re.sub(r'[^\w\s-]', '', name)
    name = re.sub(r'\s+', '_', name.strip())
    return name[:80] or 'song'


# ============================================================================
# Commands
# ============================================================================

def cmd_login(args):
    """Open a visible browser for manual login. Session saved on close."""
    print("Opening Suno in a visible browser...")
    print("Log in with your account (Google/Discord/Apple).")
    print("Once logged in and you see the dashboard, press Enter here to save the session.")

    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        page.goto("https://suno.com/signin", wait_until="networkidle", timeout=60000)

        input("\n>>> Press Enter after you've logged in to Suno... ")

        # Save session
        save_session(context)
        browser.close()

    print(json.dumps({"success": True, "message": "Session saved. You can now use headless mode."}))


def cmd_create(args):
    """Generate a song from a prompt."""
    ensure_dirs()
    output_dir = Path(args.output) if args.output else OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    prompt = args.prompt
    style = args.style or ""
    instrumental = args.instrumental
    wait_time = args.wait

    if not SESSION_FILE.exists():
        print(json.dumps({"success": False, "error": "Not logged in. Run: python3 suno_skill.py login"}))
        return

    from playwright.sync_api import sync_playwright

    result = {
        "success": False,
        "prompt": prompt,
        "style": style,
        "instrumental": instrumental,
        "songs": [],
        "error": None,
    }

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(storage_state=str(SESSION_FILE))
        page = context.new_page()

        try:
            # Navigate to create page
            print("Navigating to Suno...", file=sys.stderr)
            page.goto("https://suno.com/create", wait_until="networkidle", timeout=30000)
            time.sleep(3)

            # Check if we're logged in (look for the create interface)
            if "signin" in page.url.lower():
                result["error"] = "Session expired. Run: python3 suno_skill.py login"
                print(json.dumps(result))
                return

            # Look for the prompt textarea
            # Suno's UI changes frequently — try multiple selectors
            textarea_selectors = [
                'textarea[placeholder*="song"]',
                'textarea[placeholder*="describe"]',
                'textarea[placeholder*="lyrics"]',
                'textarea[data-testid="create-prompt"]',
                'textarea',
            ]

            textarea = None
            for sel in textarea_selectors:
                try:
                    textarea = page.wait_for_selector(sel, timeout=5000)
                    if textarea:
                        break
                except:
                    continue

            if not textarea:
                # Try clicking "Create" tab first
                try:
                    page.click('text=Create', timeout=5000)
                    time.sleep(2)
                    for sel in textarea_selectors:
                        try:
                            textarea = page.wait_for_selector(sel, timeout=3000)
                            if textarea:
                                break
                        except:
                            continue
                except:
                    pass

            if not textarea:
                result["error"] = "Could not find prompt input. Suno UI may have changed."
                # Take screenshot for debugging
                page.screenshot(path=str(output_dir / "suno_debug.png"))
                result["debug_screenshot"] = str(output_dir / "suno_debug.png")
                print(json.dumps(result))
                return

            # Enter the prompt
            print(f"Entering prompt: {prompt[:60]}...", file=sys.stderr)
            textarea.fill(prompt)
            time.sleep(0.5)

            # Set style if provided
            if style:
                style_selectors = [
                    'input[placeholder*="style"]',
                    'input[placeholder*="genre"]',
                    'input[data-testid="style-input"]',
                ]
                for sel in style_selectors:
                    try:
                        style_input = page.wait_for_selector(sel, timeout=3000)
                        if style_input:
                            style_input.fill(style)
                            break
                    except:
                        continue

            # Toggle instrumental if requested
            if instrumental:
                try:
                    instrumental_toggle = page.wait_for_selector(
                        'text=Instrumental', timeout=3000
                    )
                    if instrumental_toggle:
                        instrumental_toggle.click()
                        time.sleep(0.5)
                except:
                    pass  # Not all UI versions have this toggle

            # Click the Create/Generate button
            create_selectors = [
                'button:text("Create")',
                'button:text("Generate")',
                'button[data-testid="create-button"]',
                'button[type="submit"]',
            ]

            clicked = False
            for sel in create_selectors:
                try:
                    btn = page.wait_for_selector(sel, timeout=3000)
                    if btn and btn.is_visible():
                        btn.click()
                        clicked = True
                        print("Generation started...", file=sys.stderr)
                        break
                except:
                    continue

            if not clicked:
                result["error"] = "Could not find Create button."
                page.screenshot(path=str(output_dir / "suno_debug.png"))
                print(json.dumps(result))
                return

            # Wait for generation to complete
            # Suno typically takes 30-90 seconds to generate
            print(f"Waiting up to {wait_time}s for generation...", file=sys.stderr)

            songs_found = False
            start_time = time.time()

            while time.time() - start_time < wait_time:
                time.sleep(5)
                elapsed = int(time.time() - start_time)
                print(f"  {elapsed}s elapsed...", file=sys.stderr)

                # Look for audio players / song cards that appeared after clicking Create
                # Suno shows generated songs as cards with play buttons
                try:
                    # Check for audio elements or download buttons
                    audio_elements = page.query_selector_all('audio source, a[download], a[href*=".mp3"], a[href*="cdn.suno"]')
                    if audio_elements:
                        songs_found = True
                        break

                    # Check for song cards
                    song_cards = page.query_selector_all('[data-testid*="song"], .song-card, [class*="SongCard"]')
                    if len(song_cards) >= 2:  # Suno generates 2 variations
                        songs_found = True
                        break
                except:
                    continue

            if not songs_found:
                # Take a screenshot to see what happened
                page.screenshot(path=str(output_dir / "suno_after_wait.png"))

                # Try to find any links to songs on the page
                all_links = page.evaluate('''
                    () => Array.from(document.querySelectorAll('a'))
                        .map(a => ({href: a.href, text: a.innerText?.substring(0, 50)}))
                        .filter(l => l.href.includes('suno.com/song') || l.href.includes('cdn'))
                ''')

                if all_links:
                    for link in all_links[:4]:
                        result["songs"].append({
                            "url": link.get("href", ""),
                            "title": link.get("text", "").strip() or "Untitled",
                        })
                    result["success"] = len(result["songs"]) > 0
                else:
                    result["error"] = f"Generation may still be in progress. Check suno.com manually."
                    result["debug_screenshot"] = str(output_dir / "suno_after_wait.png")

            else:
                # Try to extract song URLs and download audio
                song_links = page.evaluate('''
                    () => {
                        const links = [];
                        // Look for song page links
                        document.querySelectorAll('a[href*="/song/"]').forEach(a => {
                            links.push({href: a.href, text: a.innerText?.substring(0, 80)});
                        });
                        // Look for audio sources
                        document.querySelectorAll('audio source').forEach(s => {
                            links.push({href: s.src, text: 'audio'});
                        });
                        return links;
                    }
                ''')

                for i, link in enumerate(song_links[:4]):
                    song = {
                        "url": link.get("href", ""),
                        "title": link.get("text", "").strip() or f"song_{i+1}",
                    }

                    # Try to download the audio
                    audio_url = link.get("href", "")
                    if "cdn" in audio_url or ".mp3" in audio_url or ".wav" in audio_url:
                        filename = sanitize_filename(song["title"]) + ".mp3"
                        filepath = output_dir / filename
                        try:
                            response = page.request.get(audio_url)
                            filepath.write_bytes(response.body())
                            song["file"] = str(filepath)
                            song["audio_url"] = audio_url
                            print(f"  Downloaded: {filepath}", file=sys.stderr)
                        except Exception as e:
                            song["download_error"] = str(e)

                    result["songs"].append(song)

                result["success"] = len(result["songs"]) > 0

            # Save updated session
            save_session(context)

        except Exception as e:
            result["error"] = str(e)
            try:
                page.screenshot(path=str(output_dir / "suno_error.png"))
                result["debug_screenshot"] = str(output_dir / "suno_error.png")
            except:
                pass

        finally:
            browser.close()

    print(json.dumps(result, indent=2))


def cmd_list(args):
    """List recent song creations."""
    if not SESSION_FILE.exists():
        print(json.dumps({"success": False, "error": "Not logged in."}))
        return

    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(storage_state=str(SESSION_FILE))
        page = context.new_page()

        try:
            page.goto("https://suno.com/me", wait_until="networkidle", timeout=30000)
            time.sleep(3)

            # Extract song data from the page
            songs = page.evaluate('''
                () => {
                    const results = [];
                    document.querySelectorAll('a[href*="/song/"]').forEach(a => {
                        const title = a.innerText?.trim()?.substring(0, 100);
                        if (title && !results.find(r => r.url === a.href)) {
                            results.push({url: a.href, title: title});
                        }
                    });
                    return results.slice(0, ''' + str(args.limit) + ''');
                }
            ''')

            save_session(context)
            print(json.dumps({"success": True, "songs": songs, "count": len(songs)}, indent=2))

        except Exception as e:
            print(json.dumps({"success": False, "error": str(e)}))

        finally:
            browser.close()


def cmd_download(args):
    """Download a specific song by URL."""
    ensure_dirs()
    output_dir = Path(args.output) if args.output else OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    if not SESSION_FILE.exists():
        print(json.dumps({"success": False, "error": "Not logged in."}))
        return

    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(storage_state=str(SESSION_FILE))
        page = context.new_page()

        try:
            page.goto(args.url, wait_until="networkidle", timeout=30000)
            time.sleep(3)

            # Find audio source
            audio_url = page.evaluate('''
                () => {
                    const audio = document.querySelector('audio source');
                    if (audio) return audio.src;
                    // Try meta tags
                    const meta = document.querySelector('meta[property="og:audio"]');
                    if (meta) return meta.content;
                    return null;
                }
            ''')

            title = page.evaluate('() => document.title') or 'song'

            if audio_url:
                filename = sanitize_filename(title) + ".mp3"
                filepath = output_dir / filename
                response = page.request.get(audio_url)
                filepath.write_bytes(response.body())

                print(json.dumps({
                    "success": True,
                    "title": title,
                    "audio_url": audio_url,
                    "file": str(filepath),
                    "size_kb": filepath.stat().st_size // 1024,
                }, indent=2))
            else:
                print(json.dumps({
                    "success": False,
                    "error": "Could not find audio URL on page.",
                    "title": title,
                }))

            save_session(context)

        except Exception as e:
            print(json.dumps({"success": False, "error": str(e)}))

        finally:
            browser.close()


# ============================================================================
# Main
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description="Suno Music Skill")
    subparsers = parser.add_subparsers(dest="command")

    # login
    sub = subparsers.add_parser("login", help="Log in to Suno (visible browser)")
    sub.set_defaults(func=cmd_login)

    # create
    sub = subparsers.add_parser("create", help="Generate a song")
    sub.add_argument("prompt", help="Song description or lyrics")
    sub.add_argument("--style", "-s", default="", help="Musical style tags")
    sub.add_argument("--instrumental", "-i", action="store_true", help="Instrumental only")
    sub.add_argument("--output", "-o", default=None, help="Output directory")
    sub.add_argument("--wait", "-w", type=int, default=120, help="Max wait time (seconds)")
    sub.set_defaults(func=cmd_create)

    # list
    sub = subparsers.add_parser("list", help="List recent songs")
    sub.add_argument("--limit", "-l", type=int, default=10, help="Max songs to list")
    sub.set_defaults(func=cmd_list)

    # download
    sub = subparsers.add_parser("download", help="Download a song by URL")
    sub.add_argument("url", help="Suno song URL")
    sub.add_argument("--output", "-o", default=None, help="Output directory")
    sub.set_defaults(func=cmd_download)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return

    args.func(args)


if __name__ == "__main__":
    main()
