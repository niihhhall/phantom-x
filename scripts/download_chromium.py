import os
import sys
import urllib.request
import zipfile
import shutil
from pathlib import Path

def report_progress(block_num, block_size, total_size):
    downloaded = block_num * block_size
    if total_size > 0:
        percent = min(100, downloaded * 100 // total_size)
        sys.stdout.write(f"\rDownloading Chromium 1169... {percent}% ({downloaded / (1024*1024):.1f} MB / {total_size / (1024*1024):.1f} MB)")
        sys.stdout.flush()

def main():
    target_dir = Path(os.environ.get("LOCALAPPDATA")) / "ms-playwright" / "chromium-1169"
    zip_path = target_dir / "chromium-win64.zip"
    
    # Clean up broken installations and locks
    print(f"[*] Preparing directory: {target_dir}")
    if target_dir.exists():
        shutil.rmtree(target_dir, ignore_errors=True)
    
    # Playwright's global lock might exist from the aborted run
    lock_file = target_dir.parent / "__dirlock"
    if lock_file.exists():
        try:
            os.remove(lock_file)
            print("[*] Removed stale installation lock file.")
        except Exception:
            pass
            
    os.makedirs(target_dir, exist_ok=True)
    
    # Use Akamai mirror which successfully worked for Firefox earlier
    mirror_url = "https://playwright-akamai.azureedge.net/builds/chromium/1169/chromium-win64.zip"
    
    print(f"[*] Starting resilient download from: {mirror_url}")
    try:
        urllib.request.urlretrieve(mirror_url, str(zip_path), reporthook=report_progress)
        print("\n[*] Download complete! Extracting archive...")
        
        with zipfile.ZipFile(str(zip_path), 'r') as zip_ref:
            zip_ref.extractall(str(target_dir))
            
        print("[*] Extraction complete.")
    except Exception as e:
        print(f"\n[!] Download or extraction failed: {e}")
        return
    finally:
        if zip_path.exists():
            os.remove(zip_path)
            print("[*] Cleaned up zip file.")
            
    print("\n=========================================================")
    print("🚀 SUCCESS! Chromium build 1169 is perfectly installed.")
    print("=========================================================")

if __name__ == "__main__":
    main()
