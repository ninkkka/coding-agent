# handler.py
import os
import time
import base64
import traceback 
import requests
import base64
from typing import List, Dict, Optional
from github import Github, UnknownObjectException, ContentFile
import google.generativeai as genai

# --- 1. INITIALIZE API CLIENTS ---
try:
    genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
    github_client = Github(os.getenv('GITHUB_PAT'))
    github_user = github_client.get_user()
except Exception as e:
    print(f"Error initializing API clients: {e}")

# --- 2. THE MAIN ORCHESTRATOR ---

# PASTE THIS IN handler.py

def handle_build_request(request_body):
    """Orchestrates the process, now with special logic for Round 2."""
    try:
        task_details = request_body
        print(f"Processing Task: {task_details['task']}, Round: {task_details['round']}")
        
        existing_code = None
        # --- LOGIC FOR ROUND 2 ---
        # If it's Round 2 or later, try to fetch the previous code.
        if int(task_details['round']) > 1:
            try:
                repo = github_user.get_repo(task_details['task'])
                content_file = repo.get_contents("index.html")
                existing_code = content_file.decoded_content.decode('utf-8')
                print("Found existing code from Round 1 to modify.")
            except Exception as e:
                print(f"Could not fetch existing code for Round 2, will generate from scratch. Error: {e}")
        # --- END OF ROUND 2 LOGIC ---

        # Step 1: Generate all necessary files using Gemini
        print("Step 1: Generating code with Gemini...")
        generated_files = generate_code_with_gemini(
            task_details['brief'],
            task_details.get('attachments', []),
            existing_code  # Pass the old code (or None) to the LLM
        )
        print("Step 1 complete.")

        # Step 2: Create a new repo or update an existing one
        print("Step 2: Creating/updating GitHub repo...")
        repo_info = create_or_update_repo(
            task_details['task'],
            generated_files,
            task_details['round']
        )
        print("Step 2 complete.")

        # Step 3: Enable GitHub Pages for the repository
        print("Step 3: Enabling GitHub Pages...")
        enable_github_pages(repo_info['owner'], repo_info['repo_name'])
        print("Step 3 complete.")
        
        # IMPORTANT: Wait for GitHub Pages to build and deploy
        print("Waiting 20 seconds for GitHub Pages to deploy...")
        time.sleep(20)

        # Step 4: Notify the evaluation server with the results
        print("Step 4: Notifying evaluation URL...")
        pages_url = f"https://{repo_info['owner']}.github.io/{repo_info['repo_name']}/"
        payload = {
            "email": task_details['email'],
            "task": task_details['task'],
            "round": task_details['round'],
            "nonce": task_details['nonce'],
            "repo_url": repo_info['repo_url'],
            "commit_sha": repo_info['commit_sha'],
            "pages_url": pages_url,
        }
        notify_evaluation_url(task_details['evaluation_url'], payload)
        print("Step 4 complete.")
        
        print(f"✅ Successfully completed task: {task_details['task']}")

    except Exception as e:
        # This will catch ANY error and print a detailed report
        print("\n" + "="*50)
        print("🚨 A FATAL ERROR occurred in the background thread! 🚨")
        print(f"Error Type: {type(e).__name__}")
        print(f"Error Details: {e}")
        print("\n--- Full Traceback ---")
        traceback.print_exc()
        print("="*50 + "\n")


# --- 3. HELPER FUNCTIONS ---

def generate_code_with_gemini(brief: str,
                              attachments: Optional[List[Dict]] = None,
                              existing_code: Optional[str] = None) -> Dict[str, str]:
    """
    Generates (or updates) a single-file `index.html` using Gemini.
    - If `existing_code` is provided, the assistant is asked to modify that file to meet the new brief.
    - If `existing_code` is None, the assistant is asked to create a complete index.html from scratch.
    This function:
      * Safely parses attachments (text vs binary).
      * Builds a robust prompt for the LLM.
      * Calls Gemini and returns a dict with 'index.html', 'README.md', and 'LICENSE'.
    The function is defensive: any errors contacting the model will fall back to a minimal HTML
    file containing an error message (so the function never raises due to LLM issues).
    """
    # --- Process attachments ---
    attachment_content = "No attachments provided."
    if attachments:
        content_parts = []
        for att in attachments:
            # Basic validation for expected keys
            name = att.get("name", "unnamed")
            url = att.get("url", "")
            try:
                header, encoded = url.split(",", 1)
            except Exception:
                # Malformed or missing data URL — describe as binary
                content_parts.append(
                    f"File name: {name}\nFile content:\n[Attachment present but could not be parsed ({name}).]"
                )
                continue

            # Decide if file is text-like (we treat many common text MIME types as text)
            header_lower = header.lower()
            is_text_like = any(tok in header_lower for tok in ("text", "json", "csv", "xml", "javascript", "html"))
            is_base64 = "base64" in header_lower

            if is_text_like and is_base64:
                # try decode as utf-8, fallback to latin1 if necessary
                try:
                    decoded_bytes = base64.b64decode(encoded)
                    try:
                        decoded_content = decoded_bytes.decode("utf-8")
                    except UnicodeDecodeError:
                        decoded_content = decoded_bytes.decode("latin-1")
                    content_parts.append(
                        f"File name: {name}\nFile content:\n```\n{decoded_content}\n```"
                    )
                except Exception:
                    # If decoding fails, fall back to describing the attachment
                    content_parts.append(
                        f"File name: {name}\nFile content:\n[Attachment could not be decoded as text ({name}).]"
                    )
            else:
                # For binary files (images, pdfs, etc.) or non-base64 text, describe them
                content_parts.append(
                    f"File name: {name}\nFile content:\n[Content of binary or non-text file ({name}) is attached but not displayed here.]"
                )

        attachment_content = "\n\n".join(content_parts) if content_parts else attachment_content

    # --- Build prompt (dynamic based on whether we're updating existing code) ---
    # We ask the model to output ONLY the raw index.html contents (no markdown/explanations).
    if existing_code:
        prompt = f"""
You are an expert web developer who modifies and improves single-file web apps.
A user provided ORIGINAL CODE for `index.html` and a NEW BRIEF. Modify the ORIGINAL CODE
to implement the NEW BRIEF while preserving ALL existing functionality unless the brief
explicitly says to remove or replace it. Fix bugs, improve accessibility, and make the
file production-ready (HTML/CSS/JS in one file). Keep the structure and comments where possible.

--- ORIGINAL CODE (index.html) START ---
{existing_code}
--- ORIGINAL CODE (index.html) END ---

BRIEF:
{brief}

ATTACHMENTS:
{attachment_content}

INSTRUCTIONS:
- Return ONLY the raw contents of the updated `index.html` file. Do NOT include any surrounding
  explanation, Markdown, or code fences.
- The returned HTML must be a valid, standalone single-file web page (contains <!doctype html> etc.).
- If you add or change functionality, keep backward compatibility and do not remove previously working features.
- If an attachment contains text, consider its content and incorporate it when appropriate.
"""
    else:
        prompt = f"""
You are an expert web developer creating single-file applications.
Based on the brief and attachments, create a complete `index.html` file.
The code must be production-ready and contain all HTML, CSS, and JavaScript.

BRIEF:
{brief}

ATTACHMENTS:
{attachment_content}

INSTRUCTIONS:
- Return ONLY the raw contents of the `index.html` file. Do NOT include explanations, notes, or Markdown formatting.
- The HTML must be a valid, standalone file (include <!doctype html>, charset meta, responsive viewport, and any inline CSS/JS required).
"""

    # --- Call the Gemini model and handle possible failures gracefully ---
    code = None
    try:
        model = genai.GenerativeModel("models/gemini-pro-latest")
        response = model.generate_content(prompt)
        # prefer .text, but tolerate other shapes
        code = getattr(response, "text", None) or getattr(response, "content", None) or str(response)
        # Some LLM outputs may include accidental surrounding fences; strip them if present
        if code.strip().startswith("```") and "html" in code.splitlines()[0].lower():
            # remove first fence line and last fence if present
            lines = code.splitlines()
            # drop first line
            lines = lines[1:]
            # if final line is fence, drop it
            if lines and lines[-1].strip().startswith("```"):
                lines = lines[:-1]
            code = "\n".join(lines)
    except Exception as e:
        # Fail-safe: produce a minimal but valid index.html that includes an HTML comment about the error.
        safe_error_html = (
            "<!doctype html>\n"
            "<html lang=\"en\">\n"
            "<head>\n"
            "  <meta charset=\"utf-8\">\n"
            "  <meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">\n"
            "  <title>Generated Project (Error)</title>\n"
            "</head>\n"
            "<body>\n"
            "  <!-- Gemini generation failed; falling back to minimal placeholder page. -->\n"
            f"  <!-- Error: {str(e)[:300]} -->\n"
            "  <main>\n"
            "    <h1>Auto-generation failed</h1>\n"
            "    <p>The automated generation service returned an error. Please try again.</p>\n"
            "  </main>\n"
            "</body>\n"
            "</html>\n"
        )
        code = safe_error_html

    # Ensure we always return a string for index.html
    if not isinstance(code, str):
        code = str(code or "")

    # --- Build README and LICENSE (unchanged behavior, kept for compatibility) ---
    readme_content = f"""# Project: {brief[:50]}...
## Summary
This project was automatically generated to solve the task: "{brief}".
It was created/updated by an automated assistant (Gemini).
## How to use
Open `index.html` in a browser to view the single-file application.
## License
This project is licensed under the MIT License. See the LICENSE file for details.
"""

    license_content = (
        "MIT License\n\n"
        "Copyright (c) 2025 Aditya Kumar\n\n"
        "Permission is hereby granted, free of charge, to any person obtaining a copy of this software "
        "and associated documentation files (the \"Software\"), to deal in the Software without restriction, "
        "including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, "
        "and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, "
        "subject to the following conditions:\n\n"
        "The above copyright notice and this permission notice shall be included in all copies or substantial "
        "portions of the Software.\n\n"
        "THE SOFTWARE IS PROVIDED \"AS IS\", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT "
        "LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN "
        "NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, "
        "WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE "
        "SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE."
    )

    return {
        "index.html": code,
        "README.md": readme_content,
        "LICENSE": license_content,
    }

def create_or_update_repo(task_name, files, round_num):
    """Manages GitHub repository creation and file updates robustly."""
    repo_name = task_name
    is_new_repo = False # A flag to track if we just created the repo

    try:
        repo = github_user.get_repo(repo_name)
        print(f"Repo '{repo_name}' already exists. Updating files.")
    except UnknownObjectException:
        print(f"Repo '{repo_name}' not found. Creating a new public repo.")
        repo = github_user.create_repo(repo_name, private=False)
        is_new_repo = True # Set the flag to true since we just made it

    commit_message = f"feat: Round {round_num} update"
    
    # --- THIS IS THE FIX ---
    # For a brand new repo, we MUST create the first file to initialize the main branch.
    # We can't update a file that doesn't exist yet.
    if is_new_repo:
        first_file_path = list(files.keys())[0]
        first_file_content = files.pop(first_file_path) # Remove it from the dictionary
        print(f"Creating initial file: {first_file_path}")
        repo.create_file(first_file_path, f"{commit_message} for {first_file_path}", first_file_content)

    # Now, update the rest of the files (or all of them if the repo wasn't new)
    for path, content in files.items():
        try:
            existing_file = repo.get_contents(path)
            print(f"Updating existing file: {path}")
            repo.update_file(path, f"{commit_message} for {path}", content, existing_file.sha)
        except UnknownObjectException:
            print(f"Creating new file: {path}")
            repo.create_file(path, f"{commit_message} for {path}", content)
    # --- END OF FIX ---

    latest_commit_sha = repo.get_branch('main').commit.sha
    print(f"Pushed files to repo. Commit SHA: {latest_commit_sha}")
    
    return {
        "owner": github_user.login,
        "repo_name": repo_name,
        "repo_url": repo.html_url,
        "commit_sha": latest_commit_sha,
    }

def enable_github_pages(owner, repo_name):
    """Activates the GitHub Pages site for the repo."""
    # --- THIS IS THE FIX ---
    # The URL must be a clean f-string without any markdown formatting.
    url = f"https://api.github.com/repos/{owner}/{repo_name}/pages"
    # --- END OF FIX ---

    headers = {
        "Authorization": f"token {os.getenv('GITHUB_PAT')}",
        "Accept": "application/vnd.github.v3+json",
    }
    payload = {"source": {"branch": "main", "path": "/"}}

    response = requests.post(url, headers=headers, json=payload)

    if 200 <= response.status_code < 300:
        print(f"Successfully enabled GitHub Pages for {owner}/{repo_name}")
    elif response.status_code == 409:
        print(f"GitHub Pages already enabled for {owner}/{repo_name}")
    else:
        print(f"Error enabling GitHub Pages: {response.status_code} - {response.text}")
        response.raise_for_status()

def notify_evaluation_url(url, payload):
    """Sends final data to the evaluation URL with exponential backoff retries."""
    for i in range(5): # Try up to 5 times
        try:
            delay = 2**i # 1, 2, 4, 8, 16 seconds
            print(f"Attempt {i+1}: POSTing to evaluation URL... (waiting {delay}s)")
            time.sleep(delay)
            response = requests.post(url, json=payload, headers={'Content-Type': 'application/json'}, timeout=15)
            if response.status_code == 200:
                print("Successfully notified evaluation URL.")
                return
            print(f"Notification attempt failed with status: {response.status_code}")
        except requests.exceptions.RequestException as e:
            print(f"Notification attempt failed with error: {e}")
    raise Exception("Could not notify evaluation URL after multiple attempts.")
