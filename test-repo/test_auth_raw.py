import traceback
import sys
from auth import login_user

def run_tests():
    print("Running CI Test Suite...")
    try:
        # Expected success
        assert login_user("admin", "admin123") == "JWT-TOKEN-123"
        print("✓ login_user() success path")
        
        # Expected failure due to bug
        print("Running service account test...")
        login_user(None, "service-token")
        
    except Exception as e:
        print("FAILED!")
        print("=============================")
        print(f"E   {type(e).__name__}: {str(e)}")
        traceback.print_exc()
        print("=============================")
        sys.exit(1)

if __name__ == "__main__":
    run_tests()
