import os
import sys
import glob
import subprocess

def run_tests_isolated():
    tests_dir = os.path.join(os.path.dirname(__file__), "tests", "test_audit_shared")
    test_files = glob.glob(os.path.join(tests_dir, "test_*.py"))
    
    # Sort files to ensure predictable order
    test_files.sort()
    
    total_tests = len(test_files)
    failed_tests = []
    
    for i, test_file in enumerate(test_files, 1):
        test_name = os.path.basename(test_file)
        print(f"\n[{i}/{total_tests}] Running {test_name} in isolated process...")
        
        result = subprocess.run([sys.executable, "-m", "pytest", test_file, "-v"])
        
        if result.returncode != 0:
            print(f"FAILED: {test_name}")
            failed_tests.append(test_name)
        else:
            print(f"PASSED: {test_name}")
            
    print("\n" + "="*50)
    print("ISOLATED TEST RUN SUMMARY")
    print("="*50)
    
    if not failed_tests:
        print(f"All {total_tests} test files passed successfully.")
        sys.exit(0)
    else:
        print(f"{len(failed_tests)}/{total_tests} test files failed:")
        for failed in failed_tests:
            print(f"  - {failed}")
        sys.exit(1)

if __name__ == "__main__":
    run_tests_isolated()
