import requests
import sys
import time

# Config
BASE_URL = "http://localhost:5002"
EMAIL = "api_test@example.com"
USERNAME = "apitestuser"
PASSWORD = "securepassword"

def log(msg):
    print(f"[TEST] {msg}")

def test_api_flow():
    session = requests.Session()

    # 1. Wait for service availability
    log("Waiting for service to be up...")
    retries = 5
    while retries > 0:
        try:
            resp = requests.get(f"{BASE_URL}/login")
            if resp.status_code == 200:
                log("Service is UP.")
                break
        except requests.ConnectionError:
            pass
        time.sleep(2)
        retries -= 1
    
    if retries == 0:
        log("Service not reachable. Exiting.")
        sys.exit(1)

    # 2. Register
    log("Testing Registration...")
    # Use a random RUT to avoid "User already exists" in repeated runs without cleanup
    # or just stick to a fixed one if we handle the error. 
    # Routes expect: email, rut, full_name, password
    target_rut = 99998888
    payload = {
        "email": EMAIL,
        "rut": target_rut,
        "full_name": "API Test User",
        "password": PASSWORD
    }
    resp = session.post(f"{BASE_URL}/register", data=payload)
    
    # Expect redirect to login or success message
    if resp.status_code == 200 and "login" in resp.url:
        log("Registration successful (Redirected to login).")
    elif resp.status_code == 200 and "User already exists" in resp.text:
        log("User already exists (expected if re-running). Proceeding to login.")
    else:
        # If we are strictly testing flow, failing registration might be critical, 
        # but for connectivity check, let's see if we can proceed or fail verbosely.
        log(f"Registration failed response. URL: {resp.url}. Text snippet: {resp.text[:100]}...") 
        # Don't exit yet, try login anyway just in case
        
    time.sleep(1)

    # 3. Login
    log("Testing Login...")
    login_payload = {
        "email": EMAIL,
        "password": PASSWORD
    }
    resp = session.post(f"{BASE_URL}/login", data=login_payload)
    
    if resp.status_code == 200 and "my-tickets" in resp.url:
        log("Login successful (Redirected to my-tickets).")
    else:
        log(f"Login failed. URL: {resp.url}")
        sys.exit(1)

    # 4. Access Protected Route
    log("Testing Protected Route (/my-tickets)...")
    resp = session.get(f"{BASE_URL}/my-tickets")
    
    if resp.status_code == 200 and "My Tickets" in resp.text:
        log("Protected route accessed successfully.")
    else:
        log("Failed to access protected route.")
        sys.exit(1)

    log("API Connectivity Test PASSED.")

if __name__ == "__main__":
    test_api_flow()
