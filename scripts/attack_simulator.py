import requests
import time
import random

BASE_URL = "http://localhost:8000"   # change if needed
LOGIN_ENDPOINT = f"{BASE_URL}/login"


def brute_force():
    print("\n[+] Starting BRUTE FORCE simulation...\n")
    passwords = ["123456", "password", "admin", "test", "qwerty", "letmein"]

    for i in range(50):
        data = {
            "username": "admin",
            "password": random.choice(passwords)
        }

        r = requests.post(LOGIN_ENDPOINT, json=data)
        print("BF attempt:", r.status_code)

        time.sleep(0.2)


def bot_behavior():
    print("\n[+] Starting BOT behavior simulation...\n")

    for i in range(80):
        data = {
            "username": "user1",
            "password": "wrong"
        }

        headers = {
            "User-Agent": f"bot-{random.randint(1000,9999)}"
        }

        requests.post(LOGIN_ENDPOINT, json=data, headers=headers)

        print("bot request sent")
        time.sleep(0.1)


def anomaly_spike():
    print("\n[+] Starting ANOMALY SPIKE...\n")

    # normal
    for _ in range(5):
        requests.post(LOGIN_ENDPOINT, json={"username": "user", "password": "wrong"})
        time.sleep(1)

    print("\n🔥 ATTACK SPIKE NOW\n")

    # spike
    for i in range(120):
        requests.post(
            LOGIN_ENDPOINT,
            json={"username": "admin", "password": f"pass{i}"},
            headers={"User-Agent": f"spike-{random.randint(1,9999)}"}
        )
        time.sleep(0.05)


if __name__ == "__main__":
    print("\n=== SentinelIQ ATTACK SIMULATOR ===\n")

    print("1. Brute Force")
    print("2. Bot Behavior")
    print("3. Anomaly Spike")
    print("4. Run ALL")

    choice = input("\nSelect mode: ")

    if choice == "1":
        brute_force()
    elif choice == "2":
        bot_behavior()
    elif choice == "3":
        anomaly_spike()
    else:
        brute_force()
        bot_behavior()
        anomaly_spike()