import os
import json
import sys
import requests

# Set colors for clean terminal output
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
RESET = "\033[0m"


def load_local_env():
    """Loads environment variables from local.env located in the repository root."""
    env_vars = {}
    script_dir = os.path.dirname(os.path.abspath(__file__))
    # Resolve the root-level local.env file
    env_path = os.path.abspath(os.path.join(script_dir, "..", "local.env"))
    
    if os.path.exists(env_path):
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    # Skip empty lines and comments
                    if line and not line.startswith("#") and "=" in line:
                        key, val = line.split("=", 1)
                        # Clean up quotes if present
                        env_vars[key.strip()] = val.strip().strip('"').strip("'")
            print(f"{GREEN}✔ Loaded local configurations from 'local.env'{RESET}")
        except Exception as e:
            print(f"{RED}⚠ Failed to read 'local.env': {e}{RESET}")
    return env_vars


def print_step(message):
    print(f"\n{YELLOW}➔ {message}{RESET}")


def print_success(message):
    print(f"{GREEN}✔ {message}{RESET}")


def print_error(message):
    print(f"{RED}✘ {message}{RESET}")


def setup_cronjobs():
    print("=" * 60)
    print("🌌 Command Center: cron-job.org Automated API Setup")
    print("=" * 60)

    # Step 1: Gather Inputs
    print_step("Gathering Credentials")
    
    # Try loading from local.env file first, fall back to environment, then fall back to input
    env = load_local_env()
    
    github_pat = env.get("GITHUB_PAT") or os.environ.get("GITHUB_PAT")
    if not github_pat:
        github_pat = input("1. Enter your GitHub Personal Access Token (PAT): ").strip()
    if not github_pat:
        print_error("GitHub PAT is required.")
        sys.exit(1)

    cjo_api_key = env.get("CRON_JOB_API_KEY") or os.environ.get("CRON_JOB_API_KEY")
    if not cjo_api_key:
        cjo_api_key = input("2. Enter your cron-job.org API Key: ").strip()
    if not cjo_api_key:
        print_error("cron-job.org API Key is required. (Get this under Console -> Settings -> API)")
        sys.exit(1)

    github_repo = "hariharen9/hh-ntfy"

    # Step 2: Define Job Specifications
    # 0 = GET, 1 = POST
    headers = {
        "User-Agent": "cron-job-trigger",
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {github_pat}",
        "Content-Type": "application/json",
    }
    body = '{"ref": "main"}'

    jobs = [
        {
            "title": "CrackWatch Denuvo Trigger",
            "url": f"https://api.github.com/repos/{github_repo}/actions/workflows/crackwatch.yml/dispatches",
            "schedule": {
                "timezone": "UTC",
                "minutes": [0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55],
                "hours": [-1],
                "mdays": [-1],
                "months": [-1],
                "wdays": [-1],
            },
        },
        {
            "title": "Multi-Site Uptime Trigger",
            "url": f"https://api.github.com/repos/{github_repo}/actions/workflows/uptime.yml/dispatches",
            "schedule": {
                "timezone": "UTC",
                "minutes": [0, 15, 30, 45],
                "hours": [-1],
                "mdays": [-1],
                "months": [-1],
                "wdays": [-1],
            },
        },
    ]

    # Step 3: Trigger API calls
    cjo_url = "https://api.cron-job.org/jobs"
    cjo_headers = {
        "Authorization": f"Bearer {cjo_api_key}",
        "Content-Type": "application/json",
    }

    for job_spec in jobs:
        print_step(f"Registering '{job_spec['title']}'...")

        payload = {
            "job": {
                "title": job_spec["title"],
                "url": job_spec["url"],
                "enabled": True,
                "saveResponses": True,
                "requestMethod": 1,  # 1 represents POST
                "requestHeaders": headers,
                "requestBody": body,
                "schedule": job_spec["schedule"],
            }
        }

        try:
            response = requests.put(cjo_url, json=payload, headers=cjo_headers, timeout=15)
            result = response.json()

            if response.status_code in [200, 201]:
                job_id = result.get("jobId")
                print_success(f"Successfully created! Job ID: {job_id}")
            else:
                print_error(f"Failed to create job. Status {response.status_code}")
                print(json.dumps(result, indent=2))
        except Exception as e:
            print_error(f"Network error: {e}")

    print("\n" + "=" * 60)
    print("🎉 Automated API Setup Complete!")
    print("=" * 60)


if __name__ == "__main__":
    setup_cronjobs()
