# src/github_utility.py
import os
import base64
import httpx
import traceback
from urllib.parse import quote
from github import Github, GithubException
from dotenv import load_dotenv
from datetime import datetime
import time



GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
USERNAME = os.getenv("GITHUB_USERNAME")
g = Github(GITHUB_TOKEN)

def get_authenticated_username():
    """Get the username of the authenticated GitHub user."""
    try:
        user = g.get_user()
        return user.login
    except Exception as e:
        print(f"⚠ Could not get authenticated username: {e}")
        return USERNAME  # Fallback to env variable

def create_repo(repo_name: str, description: str = ""):
    """Create or fetch a public repository."""
    user = g.get_user()
    description = " ".join(description.split()[:340]) + ("..." if len(description.split()) > 340 else "")
    
    try:
        repo = user.get_repo(repo_name)
        print("Repo already exists:", repo.full_name)
        return repo
    except GithubException as e:
        if e.status != 404:
            raise
    repo = user.create_repo(
        name=repo_name,
        description=description,
        private=False,
        auto_init=True
    )
    print("Created repo:", repo.full_name)
    return repo


def create_or_update_file(repo, path: str, content: str, message: str):
    """Create a text file or update it if it exists."""
    try:
        current = repo.get_contents(path)
        repo.update_file(path, message, content, current.sha)
        print(f"Updated {path} in {repo.full_name}")
    except GithubException as e:
        if e.status == 404:
            repo.create_file(path, message, content)
            print(f"Created {path} in {repo.full_name}")
        else:
            raise


def create_or_update_binary_file(repo, path: str, binary_content: bytes, commit_message: str):
    """
    Safely create or update a binary file (e.g., image, zip).
    GitHub API only supports base64-encoded strings, so encode manually.
    """
    encoded = base64.b64encode(binary_content).decode("utf-8")
    try:
        current = repo.get_contents(path)
        repo.update_file(path, commit_message, encoded, current.sha, branch="main", encoding="base64")
        print(f"Updated binary file {path} in {repo.full_name}")
    except GithubException as e:
        if e.status == 404:
            repo.create_file(path, commit_message, encoded, branch="main", encoding="base64")
            print(f"Created binary file {path} in {repo.full_name}")
        else:
            print(f"Error updating binary file {path}: {e}")
            raise
def is_pages_enabled(repo_name: str):
    """
    Check if GitHub Pages is already enabled for a repository.
    Returns True if enabled, False otherwise.
    """
    username = get_authenticated_username()
    # URL encode the repo name to handle spaces and special characters
    encoded_repo_name = quote(repo_name, safe='')
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }
    try:
        response = httpx.get(
            f"https://api.github.com/repos/{username}/{encoded_repo_name}/pages",
            headers=headers,
            timeout=30.0
        )
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Exception while checking Pages status: {e}")
        return False
def wait_for_pages(repo_name: str, timeout=120, interval=5):
    start = time.time()
    while time.time() - start < timeout:
        if is_pages_enabled(repo_name):
            return True
        time.sleep(interval)
    return False

def enable_pages(repo_name: str, branch: str = "main", max_retries: int = 3):
    """
    Enable GitHub Pages for a repository with retry logic.
    Returns True if enabled successfully, False otherwise.
    """
    username = get_authenticated_username()
    # URL encode the repo name to handle spaces and special characters
    encoded_repo_name = quote(repo_name, safe='')
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }
    payload = {"source": {"branch": branch, "path": "/"}}
    
    # First, verify the repository and branch exist
    try:
        repo_response = httpx.get(
            f"https://api.github.com/repos/{username}/{encoded_repo_name}",
            headers=headers,
            timeout=10.0
        )
        print(f"🔍 Repository check for {username}/{repo_name} (encoded: {encoded_repo_name}): {repo_response.status_code}")
        
        branch_response = httpx.get(
            f"https://api.github.com/repos/{username}/{encoded_repo_name}/branches/{branch}",
            headers=headers,
            timeout=10.0
        )
        print(f"🔍 Branch '{branch}' check: {branch_response.status_code}")
    except Exception as e:
        print(f"⚠ Pre-check failed: {e}")

    for attempt in range(max_retries):
        try:
            # Small delay to ensure commits are fully processed by GitHub
            if attempt > 0:
                wait_time = 2 ** attempt  # Exponential backoff: 2, 4, 8 seconds
                print(f"⏳ Waiting {wait_time}s before retry {attempt + 1}/{max_retries}...")
                time.sleep(wait_time)
            
            response = httpx.post(
                f"https://api.github.com/repos/{username}/{encoded_repo_name}/pages",
                headers=headers,
                json=payload,
                timeout=30.0
            )
            if response.status_code in (201, 202):  # 202 Accepted while GitHub builds pages
                print(f"✅ GitHub Pages enabled for {repo_name}")
                return True
            elif response.status_code == 409:
                # Pages already exists
                print(f"✅ GitHub Pages already enabled for {repo_name}")
                return True
            else:
                error_msg = response.text
                print(f"⚠ Failed to enable GitHub Pages (attempt {attempt + 1}/{max_retries}): {response.status_code} - {error_msg}")
                
                # If it's a 404, the branch might not be ready yet, retry
                if response.status_code == 404 and attempt < max_retries - 1:
                    continue
                elif attempt == max_retries - 1:
                    return False
        except Exception as e:
            print(f"❌ Exception while enabling GitHub Pages (attempt {attempt + 1}/{max_retries}): {e}")
            if attempt == max_retries - 1:
                return False
    
    return False



def batch_update_files(repo, files_dict: dict, commit_message: str):
    """
    Update multiple files in a single commit using GitHub's Tree API.
    files_dict: {path: content_string}
    """
    try:
        from github import InputGitTreeElement
        
        # Get the current commit
        main_branch = repo.get_branch("main")
        base_commit = repo.get_commit(main_branch.commit.sha)
        base_tree = base_commit.commit.tree
        
        # Create blobs for each file
        tree_elements = []
        for path, content in files_dict.items():
            # Create blob
            blob = repo.create_git_blob(content, "utf-8")
            # Create InputGitTreeElement object
            element = InputGitTreeElement(
                path=path,
                mode="100644",  # file mode
                type="blob",
                sha=blob.sha
            )
            tree_elements.append(element)
        
        # Create new tree
        new_tree = repo.create_git_tree(tree_elements, base_tree)
        
        # Create commit
        new_commit = repo.create_git_commit(
            commit_message,
            new_tree,
            [base_commit.commit]
        )
        
        # Update branch reference
        main_ref = repo.get_git_ref("heads/main")
        main_ref.edit(new_commit.sha)
        
        print(f"✅ Batch updated {len(files_dict)} files in a single commit")
        return True
    except Exception as e:
        print(f"❌ Batch update failed: {e}")
        traceback.print_exc()
        return False


def generate_mit_license(owner_name=None):
    year = datetime.utcnow().year
    owner = owner_name or USERNAME or "Owner"
    return f"""MIT License

Copyright (c) {year} {owner}

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

"""
