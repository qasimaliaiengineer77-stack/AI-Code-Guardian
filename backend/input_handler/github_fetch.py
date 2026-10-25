import requests
import zipfile
import io
import os
import tempfile

class GithubFetchError(Exception):
    pass

def download_github_zip(url: str) -> str:
    clean_url = url.rstrip('/')
    if clean_url.endswith('.git'):
        clean_url = clean_url[:-4]
    parts = clean_url.split('/')
    if len(parts) < 2:
        raise GithubFetchError("Invalid GitHub URL")
    owner, repo = parts[-2], parts[-1]

    headers = {'User-Agent': 'Mozilla/5.0'}
    
    # Direct codeload URL bypasses API rate limits
    zip_url = f"https://codeload.github.com/{owner}/{repo}/zip/refs/heads/main"
    
    try:
        res = requests.get(zip_url, headers=headers, timeout=60)
        if res.status_code == 404:
            # Fallback to master branch if main doesn't exist
            zip_url = f"https://codeload.github.com/{owner}/{repo}/zip/refs/heads/master"
            res = requests.get(zip_url, headers=headers, timeout=60)
            
        if res.status_code != 200:
            raise GithubFetchError(f"GitHub returned status {res.status_code}. Repo must be Public.")
    except requests.RequestException as e:
        raise GithubFetchError(f"Network Error: {str(e)}")

    temp_dir = tempfile.mkdtemp()
    try:
        with zipfile.ZipFile(io.BytesIO(res.content)) as z:
            for info in z.infolist():
                is_symlink = (info.external_attr >> 16) & 0xA000 == 0xA000
                if is_symlink:
                    raise GithubFetchError(f"Security Block: Symlink not allowed: '{info.filename}'")
            z.extractall(temp_dir)
    except zipfile.BadZipFile:
        raise GithubFetchError("Downloaded file is not a valid zip archive")

    extracted_items = os.listdir(temp_dir)
    if not extracted_items:
        raise GithubFetchError("Empty repository")
        
    return os.path.join(temp_dir, extracted_items[0])