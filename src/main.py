from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse
import os, json, base64, traceback, threading, time
from dotenv import load_dotenv
from src.llm_gen_code import generate_app_code, decode_attachments
from src.github_utility import (
    create_repo,
    create_or_update_file,
    create_or_update_binary_file,
    enable_pages,
    generate_mit_license,
    is_pages_enabled,
    wait_for_pages,
    batch_update_files,
    get_authenticated_username
)
from src.notification import notify_evaluation_server


USER_SECRET = os.getenv("SECRET_KEY")
USERNAME = os.getenv("GITHUB_USERNAME")
PROCESSED_PATH = "/tmp/processed_requests.json"

app = FastAPI()
_lock = threading.Lock()

# Default root endpoint with HTML form

@app.get("/")
def root():
    """Return a beautiful HTML form for API interaction."""
    html_content = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Prompt to App Generator</title>
        <style>
            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }
            body {
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                padding: 20px;
                display: flex;
                justify-content: center;
                align-items: center;
            }
            .container {
                background: white;
                border-radius: 20px;
                box-shadow: 0 20px 60px rgba(0,0,0,0.3);
                max-width: 900px;
                width: 100%;
                overflow: hidden;
            }
            .header {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 40px;
                text-align: center;
            }
            .header h1 {
                font-size: 2.5em;
                margin-bottom: 10px;
                text-shadow: 2px 2px 4px rgba(0,0,0,0.2);
            }
            .header p {
                font-size: 1.1em;
                opacity: 0.9;
            }
            .content {
                padding: 40px;
            }
            .form-group {
                margin-bottom: 25px;
            }
            label {
                display: block;
                margin-bottom: 8px;
                color: #333;
                font-weight: 600;
                font-size: 0.95em;
            }
            input, textarea, select {
                width: 100%;
                padding: 12px 15px;
                border: 2px solid #e0e0e0;
                border-radius: 8px;
                font-size: 1em;
                transition: all 0.3s ease;
                font-family: inherit;
            }
            input:focus, textarea:focus, select:focus {
                outline: none;
                border-color: #667eea;
                box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
            }
            input:invalid {
                border-color: #ff6b6b;
            }
            input:invalid:focus {
                box-shadow: 0 0 0 3px rgba(255, 107, 107, 0.1);
            }
            small {
                font-size: 0.85em;
                font-weight: normal;
            }
            textarea {
                min-height: 100px;
                resize: vertical;
            }
            .checks-container {
                background: #f8f9fa;
                padding: 15px;
                border-radius: 8px;
                margin-bottom: 15px;
            }
            .check-item {
                display: flex;
                gap: 10px;
                margin-bottom: 10px;
            }
            .check-item input {
                flex: 1;
            }
            .btn-remove {
                padding: 10px 15px;
                background: #ff6b6b;
                color: white;
                border: none;
                border-radius: 6px;
                cursor: pointer;
                font-size: 0.9em;
                transition: all 0.3s ease;
            }
            .btn-remove:hover {
                background: #ee5a52;
            }
            .btn-add {
                padding: 10px 20px;
                background: #51cf66;
                color: white;
                border: none;
                border-radius: 6px;
                cursor: pointer;
                font-size: 0.9em;
                transition: all 0.3s ease;
                margin-top: 10px;
            }
            .btn-add:hover {
                background: #40c057;
            }
            .btn-submit {
                width: 100%;
                padding: 15px;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                border: none;
                border-radius: 10px;
                font-size: 1.1em;
                font-weight: 600;
                cursor: pointer;
                transition: all 0.3s ease;
                margin-top: 20px;
            }
            .btn-submit:hover {
                transform: translateY(-2px);
                box-shadow: 0 10px 25px rgba(102, 126, 234, 0.4);
            }
            .btn-submit:active {
                transform: translateY(0);
            }
            .response {
                margin-top: 30px;
                padding: 20px;
                border-radius: 10px;
                display: none;
                animation: slideIn 0.3s ease;
            }
            .response.success {
                background: #d3f9d8;
                border: 2px solid #51cf66;
                color: #2b8a3e;
            }
            .response.error {
                background: #ffe3e3;
                border: 2px solid #ff6b6b;
                color: #c92a2a;
            }
            .response.processing {
                background: #fff3bf;
                border: 2px solid #fab005;
                color: #e67700;
            }
            @keyframes slideIn {
                from {
                    opacity: 0;
                    transform: translateY(-10px);
                }
                to {
                    opacity: 1;
                    transform: translateY(0);
                }
            }
            @keyframes spin {
                to { transform: rotate(360deg); }
            }
            .spinner {
                display: inline-block;
                width: 16px;
                height: 16px;
                border: 3px solid rgba(0,0,0,0.1);
                border-top-color: #e67700;
                border-radius: 50%;
                animation: spin 1s linear infinite;
                margin-right: 8px;
            }
            .github-link {
                display: inline-block;
                margin-top: 10px;
                padding: 10px 20px;
                background: #24292e;
                color: white;
                text-decoration: none;
                border-radius: 6px;
                transition: all 0.3s ease;
            }
            .github-link:hover {
                background: #0366d6;
                transform: translateY(-2px);
            }
            .info-box {
                background: #e7f5ff;
                border-left: 4px solid #339af0;
                padding: 15px;
                border-radius: 6px;
                margin-bottom: 25px;
            }
            .info-box h3 {
                color: #1864ab;
                margin-bottom: 8px;
            }
            .info-box p {
                color: #364fc7;
                font-size: 0.9em;
                line-height: 1.6;
            }
            .endpoint-url {
                background: #f1f3f5;
                padding: 10px 15px;
                border-radius: 6px;
                font-family: 'Courier New', monospace;
                font-size: 0.9em;
                margin-top: 10px;
                word-break: break-all;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🚀 Prompt to App Generator</h1>
                <p>Transform your ideas into GitHub Pages instantly</p>
            </div>
            
            <div class="content">
                <div class="info-box">
                    <h3>📋 How it works</h3>
                    <p>Fill out the form below to create a web application. Your app will be generated and deployed to GitHub Pages automatically.</p>
                    <div class="endpoint-url">POST https://debjithf-prompt-to-app.hf.space/endpoint</div>
                </div>

                <form id="apiForm">
                    <div class="form-group">
                        <label for="email">📧 Email Address *</label>
                        <input type="email" id="email" name="email" placeholder="your@email.com" required>
                    </div>

                    <div class="form-group">
                        <label for="secret">🔐 Secret Key *</label>
                        <input type="password" id="secret" name="secret" placeholder="Your secret key" required>
                    </div>

                    <div class="form-group">
                        <label for="task">📝 Task Name * <small style="color: #868e96;">(No spaces allowed)</small></label>
                        <input type="text" id="task" name="task" placeholder="e.g., Calculator-App" 
                               pattern="[A-Za-z0-9\-_.]+" 
                               title="Task name can only contain letters, numbers, hyphens (-), underscores (_), and periods (.)"
                               required>
                    </div>

                    <div class="form-group">
                        <label for="round">🔄 Round Number *</label>
                        <select id="round" name="round" required>
                            <option value="">Select round...</option>
                            <option value="1">Round 1 - Initial Creation</option>
                            <option value="2">Round 2 - Revision</option>
                        </select>
                    </div>

                    <div class="form-group">
                        <label for="nonce">🎲 Nonce <small style="color: #868e96;">(Optional)</small></label>
                        <input type="text" id="nonce" name="nonce" placeholder="e.g., abc123">
                    </div>

                    <div class="form-group">
                        <label for="brief">💡 App Brief *</label>
                        <textarea id="brief" name="brief" placeholder="Describe the app you want to create in detail..." required></textarea>
                    </div>

                    <div class="form-group">
                        <label>✅ Checks (Optional)</label>
                        <div class="checks-container" id="checksContainer">
                            <div class="check-item">
                                <input type="text" class="check-input" placeholder="Enter a check requirement">
                                <button type="button" class="btn-remove" onclick="removeCheck(this)">✖</button>
                            </div>
                        </div>
                        <button type="button" class="btn-add" onclick="addCheck()">+ Add Check</button>
                    </div>

                    <div class="form-group">
                        <label for="evaluation_url">🔗 Evaluation URL <small style="color: #868e96;">(Optional)</small></label>
                        <input type="url" id="evaluation_url" name="evaluation_url" placeholder="https://example.com/notify">
                    </div>

                    <button type="submit" class="btn-submit">🚀 Generate App</button>
                </form>

                <div id="response" class="response"></div>
            </div>
        </div>

        <script>
            // Prevent spaces in task name field
            document.getElementById('task').addEventListener('input', function(e) {
                // Replace spaces with hyphens automatically
                this.value = this.value.replace(/\s+/g, '-');
                // Remove any invalid characters
                this.value = this.value.replace(/[^A-Za-z0-9\-_.]/g, '');
            });

            function addCheck() {
                const container = document.getElementById('checksContainer');
                const checkItem = document.createElement('div');
                checkItem.className = 'check-item';
                checkItem.innerHTML = `
                    <input type="text" class="check-input" placeholder="Enter a check requirement">
                    <button type="button" class="btn-remove" onclick="removeCheck(this)">✖</button>
                `;
                container.appendChild(checkItem);
            }

            function removeCheck(button) {
                const container = document.getElementById('checksContainer');
                if (container.children.length > 1) {
                    button.parentElement.remove();
                }
            }

            document.getElementById('apiForm').addEventListener('submit', async (e) => {
                e.preventDefault();
                
                const responseDiv = document.getElementById('response');
                responseDiv.style.display = 'none';
                
                // Generate default values for optional fields
                const nonceValue = document.getElementById('nonce').value.trim() || 
                                  Math.random().toString(36).substring(2, 10);
                const evaluationUrlValue = document.getElementById('evaluation_url').value.trim() || 
                                          'https://example.com/notify';
                
                // Collect form data
                const formData = {
                    email: document.getElementById('email').value,
                    secret: document.getElementById('secret').value,
                    task: document.getElementById('task').value,
                    round: parseInt(document.getElementById('round').value),
                    nonce: nonceValue,
                    brief: document.getElementById('brief').value,
                    checks: Array.from(document.querySelectorAll('.check-input'))
                        .map(input => input.value.trim())
                        .filter(val => val !== ''),
                    evaluation_url: evaluationUrlValue
                };

                try {
                    const response = await fetch('/endpoint', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json'
                        },
                        body: JSON.stringify(formData)
                    });

                    const result = await response.json();
                    
                    responseDiv.style.display = 'block';
                    if (response.ok) {
                        responseDiv.className = 'response processing';
                        responseDiv.innerHTML = `
                            <h3><span class="spinner"></span>Processing...</h3>
                            <p><strong>Status:</strong> ${result.status}</p>
                            <p><strong>Note:</strong> ${result.note}</p>
                            <p style="margin-top: 10px;">⏳ Please wait while we generate your app and deploy it to GitHub Pages...</p>
                        `;
                        
                        // Start polling for status
                        pollStatus(formData.email, formData.task, formData.round, formData.nonce);
                    } else {
                        responseDiv.className = 'response error';
                        responseDiv.innerHTML = `
                            <h3>❌ Error</h3>
                            <p>${result.error || JSON.stringify(result)}</p>
                        `;
                    }
                } catch (error) {
                    responseDiv.style.display = 'block';
                    responseDiv.className = 'response error';
                    responseDiv.innerHTML = `
                        <h3>❌ Network Error</h3>
                        <p>${error.message}</p>
                    `;
                }
            });

            let pollInterval = null;
            
            function pollStatus(email, task, round, nonce) {
                // Clear any existing interval
                if (pollInterval) {
                    clearInterval(pollInterval);
                }
                
                // Poll every 3 seconds
                pollInterval = setInterval(async () => {
                    try {
                        const response = await fetch(`/status/${encodeURIComponent(email)}/${encodeURIComponent(task)}/${round}/${nonce}`);
                        const result = await response.json();
                        
                        if (result.status === 'completed') {
                            clearInterval(pollInterval);
                            const responseDiv = document.getElementById('response');
                            responseDiv.className = 'response success';
                            
                            let html = `
                                <h3>✅ Success! App Generated</h3>
                                <p><strong>Task:</strong> ${result.data.task}</p>
                                <p><strong>Round:</strong> ${result.data.round}</p>
                            `;
                            
                            if (result.data.repo_url) {
                                html += `<p><strong>Repository:</strong> <a href="${result.data.repo_url}" target="_blank" class="github-link">📦 View on GitHub</a></p>`;
                            }
                            
                            if (result.data.pages_url) {
                                html += `
                                    <p style="margin-top: 15px;"><strong>🌐 Your app is live!</strong></p>
                                    <a href="${result.data.pages_url}" target="_blank" class="github-link">🚀 Open GitHub Pages</a>
                                    <p style="margin-top: 10px; font-size: 0.9em; opacity: 0.8;">Note: It may take 1-2 minutes for GitHub Pages to fully deploy.</p>
                                `;
                            } else {
                                html += `<p style="margin-top: 10px;"><em>GitHub Pages is being set up. Please check your repository later.</em></p>`;
                            }
                            
                            responseDiv.innerHTML = html;
                        }
                    } catch (error) {
                        console.error('Polling error:', error);
                    }
                }, 3000); // Poll every 3 seconds
            }
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)



# === Persistence for processed requests ===
def load_processed():
    if os.path.exists(PROCESSED_PATH):
        try:
            with open(PROCESSED_PATH, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}
    return {}

def save_processed(data):
    with _lock:
        with open(PROCESSED_PATH, "w") as f:
            json.dump(data, f, indent=2)

# === Background task ===
def process_request(data):
    try:
        round_num = data.get("round", 1)
        task_id = data["task"]
        print(f"⚙ Starting background process for task {task_id} (round {round_num})")

        attachments = data.get("attachments", [])
        saved_attachments = decode_attachments(attachments)
        print("Attachments saved:", saved_attachments)

        # Step 1: Get or create repo early
        repo = create_repo(task_id, description=f"Auto-generated app from LLM Prompt")
        
        # If repo was just created with auto_init, wait for GitHub to initialize it
        if round_num == 1:
            try:
                # Check if repo is newly created by checking commit count
                commits = list(repo.get_commits())
                if len(commits) == 1:  # Only the initial commit exists
                    print("⏳ Waiting for GitHub to initialize the repository...")
                    time.sleep(2)
            except Exception as e:
                print(f"⚠ Could not check repo initialization status: {e}")
                time.sleep(1)  # Wait a bit anyway

        # Step 2: Optional previous README and CODE for round 2
        prev_readme = None
        if round_num == 2:
            try:
                readme = repo.get_contents("README.md")
                prev_readme = readme.decoded_content.decode("utf-8", errors="ignore")
                prev_code = repo.get_contents("index.html").decoded_content.decode("utf-8", errors="ignore")
                print("📖 Loaded previous README and index.html for round 2 context.")
            except Exception:
                pass

        gen = generate_app_code(
            data["brief"],
            attachments=attachments,
            checks=data.get("checks", []),
            round_num=round_num,
            prev_readme=prev_readme,
            prev_code=prev_code if round_num == 2 else None
        )

        files = gen.get("files", {})
        saved_info = gen.get("attachments", [])

        # Step 3: Round logic
        if round_num == 1:
            print("🏗 Round 1: Building fresh repo...")
            # Add attachments
            for att in saved_info:
                path = att["name"]
                try:
                    with open(att["path"], "rb") as f:
                        content_bytes = f.read()

                    if att["mime"].startswith("text") or att["name"].endswith((".md", ".csv", ".json", ".txt")):
                        text = content_bytes.decode("utf-8", errors="ignore")
                        create_or_update_file(repo, path, text, f"Add attachment {path}")
                    else:
                        create_or_update_binary_file(repo, path, content_bytes, f"Add binary {path}")
                        b64 = base64.b64encode(content_bytes).decode("utf-8")
                        create_or_update_file(repo, f"attachments/{att['name']}.b64", b64, f"Backup {att['name']}.b64")
                except Exception as e:
                    print("⚠ Attachment commit failed:", e)
            
            # Step 4: Add generated files individually for round 1
            for fname, content in files.items():
                create_or_update_file(repo, fname, content, f"Add/Update {fname}")

            mit_text = generate_mit_license()
            create_or_update_file(repo, "LICENSE", mit_text, "Add MIT license")
        else:
            print("🔁 Round 2: Revising existing repo with batch update...")
            # Batch all file updates including LICENSE into a single commit
            batch_files = {}
            for fname, content in files.items():
                batch_files[fname] = content
            
            # Add LICENSE to batch
            mit_text = generate_mit_license()
            batch_files["LICENSE"] = mit_text
            
            # Perform single batch update
            batch_update_files(repo, batch_files, "Update files for round 2")

        # Step 5: GitHub Pages
        pages_ok = False
        if round_num == 1:
            # Give GitHub more time to process the commits and sync
            print("⏳ Waiting for GitHub to fully process and sync commits before enabling Pages...")
            time.sleep(2)  
            
            if not is_pages_enabled(task_id):
                pages_ok = enable_pages(task_id)
                if pages_ok:
                    pages_ok = wait_for_pages(task_id)
            else:
                print(f"✅ GitHub Pages already enabled for {task_id}")
                pages_ok = True
        else:
            # Round 2: only confirm Pages, do not re-enable
            pages_ok = is_pages_enabled(task_id)
            if pages_ok:
                print(f"✅ GitHub Pages confirmed enabled for round 2")
            else:
                print(f"⚠ Pages still not active; skipping re-enable to avoid multiple builds")

        # Use authenticated username for pages URL
        github_username = get_authenticated_username()
        pages_url = f"https://{github_username}.github.io/{task_id}/" if pages_ok else None
        # Step 6: Commit SHA and notify
        try:
            commit_sha = repo.get_commits()[0].sha
        except Exception:
            commit_sha = None

        payload = {
            "email": data["email"],
            "task": data["task"],
            "round": round_num,
            "nonce": data["nonce"],
            "repo_url": repo.html_url,
            "commit_sha": commit_sha,
            "pages_url": pages_url,
        }

        notify_evaluation_server(data["evaluation_url"], payload)

        # Step 7: Record processed
        processed = load_processed()
        key = f"{data['email']}::{data['task']}::round{round_num}::nonce{data['nonce']}"
        processed[key] = payload
        save_processed(processed)

        print(f"✅ Finished round {round_num} for {task_id}")

    except Exception as e:
        print("❌ Background task failed:", e)
        traceback.print_exc()


# === Main endpoint ===
@app.post("/endpoint")
async def receive_request(request: Request, background_tasks: BackgroundTasks):
    data = await request.json()
    print("📩 Received request:", data)

    # Step 0: Verify secret
    if data.get("secret") != USER_SECRET:
        print("❌ Invalid secret received.")
        return {"error": "Invalid secret"}

    processed = load_processed()
    key = f"{data['email']}::{data['task']}::round{data['round']}::nonce{data['nonce']}"

    # Duplicate detection
    if key in processed:
        print(f"⚠ Duplicate request detected for {key}. Re-notifying only.")
        prev = processed[key]
        notify_evaluation_server(data.get("evaluation_url"), prev)
        return {"status": "ok", "note": "duplicate handled & re-notified"}

    # Schedule background task
    background_tasks.add_task(process_request, data)
    return {"status": "accepted", "note": f"processing round {data['round']} started"}


# === Status endpoint ===
@app.get("/status/{email}/{task}/{round}/{nonce}")
async def get_status(email: str, task: str, round: int, nonce: str):
    """Check the status of a submitted task."""
    processed = load_processed()
    key = f"{email}::{task}::round{round}::nonce{nonce}"
    
    if key in processed:
        result = processed[key]
        return {
            "status": "completed",
            "data": result
        }
    else:
        return {
            "status": "processing",
            "message": "Task is still being processed. Please wait..."
        }
