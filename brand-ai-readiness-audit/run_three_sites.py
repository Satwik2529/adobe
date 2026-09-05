import subprocess
import sys

def main():
    sites = [
        "https://example.com",
        "https://httpbin.org/html",
        "https://google.com"
    ]
    
    for site in sites:
        print(f"Executing validation for {site}...")
        result = subprocess.run([sys.executable, "validate_real_world.py", site], capture_output=True, text=True)
        if result.returncode != 0:
            print(f"Error for {site}:")
            print(result.stderr)
            sys.exit(result.returncode)
        else:
            print(result.stdout)
            
if __name__ == "__main__":
    main()
