# src/llm_gen_code.py
import os
import base64
import requests
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv
from openai import OpenAI

# Load environment variables
load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAPI_BASE_URL = "https://aipipe.org/openai/v1"
# Initialize OpenAI client safely
try:
    client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None
except Exception as e:
    print(f"⚠️ Warning: Could not initialize OpenAI client: {e}")
    client = None

TMP_DIR = Path("/tmp/llm_attachments")
TMP_DIR.mkdir(parents=True, exist_ok=True)


def _call_openai_api(prompt: str, api_key: str) -> Optional[str]:
    """Call the AIPipe-compatible LLM API and return raw response text"""
    try:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }

        payload = {
            "model": "gpt-4.1-mini",  # or your chosen model
            "messages": [
                {"role": "system", "content": "You are a coding assistant that writes complete applications."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.2
        }

        response = requests.post(f"{OPENAPI_BASE_URL}/chat/completions", headers=headers, json=payload)
        response.raise_for_status()

        data = response.json()
        return data["choices"][0]["message"]["content"]

    except Exception as e:
        print(f"API call failed: {str(e)}")
        # Print more detailed error info for debugging
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response status: {e.response.status_code}")
            print(f"Response content: {e.response.text[:500]}")
        return None


def decode_attachments(attachments):
    """
    Decode base64 attachments from data URLs and save them to /tmp/llm_attachments
    Returns list of dicts: {"name", "path", "mime", "size"}
    """
    saved = []
    for att in attachments or []:
        name = att.get("name", "attachment")
        url = att.get("url", "")
        if not url.startswith("data:"):
            continue
        try:
            header, b64data = url.split(",", 1)
            mime = header.split(";")[0].replace("data:", "")
            data = base64.b64decode(b64data)
            path = TMP_DIR / name
            with open(path, "wb") as f:
                f.write(data)
            saved.append({"name": name, "path": str(path), "mime": mime, "size": len(data)})
        except Exception as e:
            print(f"⚠ Failed to decode attachment {name}: {e}")
    return saved


def summarize_attachment_meta(saved):
    """
    Returns a human-readable summary for attachments.
    """
    summaries = []
    for s in saved:
        nm, p, mime = s["name"], s["path"], s.get("mime", "")
        try:
            if mime.startswith("text") or nm.endswith((".md", ".txt", ".json", ".csv")):
                with open(p, "r", encoding="utf-8", errors="ignore") as f:
                    if nm.endswith(".csv"):
                        lines = [next(f).strip() for _ in range(3)]
                        preview = "\n".join(lines)
                    else:
                        preview = f.read(1000).replace("\n", " ")[:1000]
                summaries.append(f"- {nm} ({mime}): preview: {preview}")
            else:
                summaries.append(f"- {nm} ({mime}): {s['size']} bytes")
        except Exception as e:
            summaries.append(f"- {nm} ({mime}): (could not read preview: {e})")
    return "\n".join(summaries)


def _strip_code_block(text: str) -> str:
    """Remove surrounding triple-backticks if present"""
    text = text.strip()
    if text.startswith("```") and text.endswith("```"):
        # Remove only the outer triple backticks and optional language tag
        lines = text.splitlines()
        # Remove first line if it starts with ```
        if lines[0].startswith("```"):
            lines = lines[1:]
        # Remove last line if it ends with ```
        if lines[-1].endswith("```"):
            lines = lines[:-1]
        return "\n".join(lines).strip()
    return text



def generate_readme_fallback(brief, checks=None, attachments_meta=None, round_num=1):
    """Fallback README if OpenAI API fails"""
    checks_text = "\n".join(checks or [])
    att_text = attachments_meta or ""
    return f"""# Auto-generated README (Round {round_num})

**Project brief:** {brief}

**Attachments:**
{att_text}

**Checks to meet:**
{checks_text}

## Setup
1. Open `index.html` in a browser.
2. No build steps required.

## Notes
This README was generated as a fallback because OpenAI did not return an explicit README.
"""


def generate_app_code(brief, attachments=None, checks=None, round_num=1, prev_readme=None, prev_code=None):
    """
    Generate or revise an app using OpenAI Responses API.
    round_num=1: build from scratch
    round_num=2: revise based on previous code/README
    Returns: {"files": {"index.html": ..., "README.md": ...}, "attachments": [...]}
    """
    saved = decode_attachments(attachments or [])
    attachments_meta = summarize_attachment_meta(saved)

    context_note = "" 
    if round_num == 2 and prev_readme and prev_code:
        context_note = f"\n### Previous README.md:\n{prev_readme}\n\n### Previous index.html:\n{prev_code}\n\nRevise and enhance this project according to the new brief below.\n"

    user_prompt = f"""
You are a professional web developer assistant.

### Round
{round_num}

### Task
{brief}

{context_note}

### Attachments (if any)
{attachments_meta}

### Evaluation checks
{checks or []}

### CRITICAL OUTPUT FORMAT REQUIREMENTS:
1. Generate a complete, working web application that satisfies the brief
2. Your response MUST contain EXACTLY two parts separated by "---README.md---":
   
   Part 1: Complete HTML/CSS/JavaScript code (before the separator)
   Part 2: Professional README.md content (after the separator)

3. The README.md MUST include:
   - # Project Title
   - ## Overview (what the app does)
   - ## Setup (how to run it)
   - ## Usage (how to use it)
   - ## Features (key functionality)
   - If Round 2: ## Improvements (changes from previous version)

4. Example format:
   ```
   <html>...your app code...</html>
   
   ---README.md---
   
   # Project Name
   
   ## Overview
   Brief description of what this application does...
   
   ## Setup
   1. Download the files
   2. Open index.html in a web browser
   
   ## Usage
   Instructions on how to use the application...
   ```

5. Do NOT include any other commentary or explanations outside these two sections.
"""

    try:
        if not OPENAI_API_KEY:
            raise Exception("OpenAI API key not available")

        text = _call_openai_api(user_prompt, OPENAI_API_KEY)
        if text:
            print("✅ Generated code using AIPipe-compatible API.")
            
            # Try multiple separators and formats
            separators = ["---README.md---", "## README.md", "# README.md", "README.md:", "```markdown", "---readme---", "---README---"]
            
            code_part = text
            readme_part = None
            
            print(f"🔍 Searching for README in response (length: {len(text)})")
            
            for separator in separators:
                if separator in text:
                    parts = text.split(separator, 1)
                    if len(parts) == 2 and parts[1].strip():
                        code_part = parts[0].strip()
                        readme_part = parts[1].strip()
                        print(f"✅ Found README using separator: {separator} (readme length: {len(readme_part)})")
                        break
                    else:
                        print(f"⚠ Found separator {separator} but second part is empty")
            
            # If no separator found, try to extract README from the end if it looks like markdown
            if not readme_part:
                lines = text.split('\n')
                readme_start = -1
                for i, line in enumerate(lines):
                    if line.strip().startswith('#') and ('readme' in line.lower() or 'setup' in line.lower() or 'overview' in line.lower()):
                        readme_start = i
                        break
                
                if readme_start >= 0:
                    code_part = '\n'.join(lines[:readme_start]).strip()
                    readme_part = '\n'.join(lines[readme_start:]).strip()
                    print("✅ Extracted README from markdown-like content")
            
            # If still no README, generate one from LLM response context
            if not readme_part or len(readme_part.strip()) < 10:
                print("⚠ No README found in LLM response, generating contextual README")
                project_name = brief.split('.')[0].strip().title()
                if not project_name or len(project_name) < 3:
                    project_name = "Generated Application"
                
                readme_part = f"""# {project_name}

## Overview
This application was generated based on the brief: {brief}

## Setup
1. Download or clone this repository
2. Open `index.html` in a web browser
3. No additional setup or installation required

## Usage  
The application should work out of the box. Please refer to the interface and code comments for specific functionality.

## Features
- Web-based application
- No server requirements
- Cross-platform compatibility

## Requirements
{chr(10).join(['- ' + check for check in (checks or [])]) if checks else '- Modern web browser'}

## Development
This project was generated using AI assistance on iteration {round_num}.

*Last updated: Generated automatically*
"""

            code_part = _strip_code_block(code_part)
            readme_part = _strip_code_block(readme_part)
            
        else:
            raise Exception("API returned empty response")
            
    except Exception as e:
        print(f"⚠ OpenAI API failed, using fallback: {e}")
        text = f"""
<html>
  <head><title>Fallback App</title></head>
  <body>
    <h1>Hello (fallback)</h1>
    <p>This app was generated as a fallback because OpenAI failed. Brief: {brief}</p>
  </body>
</html>

---README.md---
{generate_readme_fallback(brief, checks, attachments_meta, round_num)}
"""
        
        code_part, readme_part = text.split("---README.md---", 1)
        code_part = _strip_code_block(code_part)
        readme_part = _strip_code_block(readme_part)

    return {"files": {"index.html": code_part, "README.md": readme_part}, "attachments": saved}
