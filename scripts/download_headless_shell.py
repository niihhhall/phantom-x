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
        sys.stdout.write(f"\rDownloading Headless Shell 1169... {percent}% ({downloaded / (1024*1024):.1f} MB / {total_size / (1024*1024):.1f} MB)")
        sys.stdout.flush()

def main():
    target_dir = Path(os.environ.get("LOCALAPPDATA")) / "ms-playwright" / "chromium_headless_shell-1169"
    zip_path = target_dir / "chromium_headless_shell-win64.zip"
    
    print(f"[*] Preparing directory: {target_dir}")
    if target_dir.exists():
        shutil.rmtree(target_dir, ignore_errors=True)
    
    lock_file = target_dir.parent / "__dirlock"
    if lock_file.exists():
        try:
            os.remove(lock_file)
        except Exception:
            pass
            
    os.makedirs(target_dir, exist_ok=True)
    
    # Akamai mirror for headless shell
    mirror_url = "https://playwright-akamai.azureedge.net/builds/chromium/1169/chromium_headless_shell-win64.zip"
    
    print(f"[*] Starting resilient download from: {mirror_url}")
    try:
        urllib.request.urlretrieve(mirror_url, str(zip_path), reporthook=report_progress)
        print("\n[*] Download complete! Extracting archive...")
        
        with zipfile.ZipFile(str(zip_path), 'r') as zip_ref:
            zip_ref.extractall(str(target_dir))
            
        print("[*] Extraction complete.")
    except Exception as e:
        cleaned_error = str(e).encode('ascii', 'ignore').decode('ascii')
        print(f"\n[!] Download or extraction failed: {cleaned_error}")
        return
    finally:
        if zip_path.exists():
            os.remove(zip_path)
            
    print("\n=========================================================")
    print(" SUCCESS! Headless Shell build 1169 is perfectly installed.")
    print("=========================================================")

if __name__ == "__main__":
    main()
