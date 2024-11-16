import asyncio
import aiohttp
import time
import uuid
import json
import os
from loguru import logger

# Constants
PING_INTERVAL = 60
RETRIES = 3
PROXY_FILE = 'proxies.txt'
SESSION_FILE = 'session.json'

DOMAIN_API = {
    "SESSION": "http://api.nodepay.ai/api/auth/session",
    "PING": "https://nw.nodepay.org/api/network/ping"
}

CONNECTION_STATES = {
    "CONNECTED": 1,
    "DISCONNECTED": 2,
    "NONE_CONNECTION": 3
}

status_connect = CONNECTION_STATES["NONE_CONNECTION"]
browser_id = None
account_info = {}
last_ping_time = {}

# Logger setup
logger.add("app.log", rotation="1 MB", level="INFO")

# Function to generate UUID
def uuidv4():
    return str(uuid.uuid4())

# Validate API response
def valid_resp(resp):
    if not resp or "code" not in resp or resp["code"] < 0:
        raise ValueError("Invalid response")
    return resp

# Show warning message
def show_warning():
    confirm = input("Nodepay Autofarmer by IM-Hanzou: github.com/im-hanzou\n\nBy using this tool means you understand the risks. Do it at your own risk! Press Enter to continue or Ctrl+C to cancel... ")
    if confirm.strip() == "":
        logger.info("Proceeding with the tool...")
    else:
        logger.info("Exiting...")
        exit()

# Load proxies from file
def load_proxies(proxy_file):
    try:
        with open(proxy_file, 'r') as file:
            proxies = file.read().splitlines()
        logger.info(f"Loaded {len(proxies)} proxies.")
        return proxies
    except Exception as e:
        logger.error(f"Failed to load proxies: {e}")
        raise SystemExit("Exiting due to failure in loading proxies.")

# Load session info from file
def load_session_info():
    if os.path.exists(SESSION_FILE):
        try:
            with open(SESSION_FILE, 'r') as f:
                session_data = json.load(f)
                logger.info("Loaded session data.")
                return session_data
        except Exception as e:
            logger.error(f"Error loading session data: {e}")
            return None
    return None

# Save session info to file
def save_session_info(data):
    with open(SESSION_FILE, 'w') as f:
        json.dump(data, f)
    logger.info(f"Session data saved for UID: {data.get('uid')}")

# Validate if a proxy is working
async def is_valid_proxy(proxy, token):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(DOMAIN_API["PING"], headers={"Authorization": f"Bearer {token}"}, proxy=f"http://{proxy}", timeout=10) as response:
                if response.status == 200:
                    return True
                else:
                    logger.warning(f"Proxy {proxy} failed with status {response.status}")
    except Exception as e:
        logger.warning(f"Proxy {proxy} is invalid: {e}")
    return False

# Handle successful ping
async def handle_ping(proxy, token):
    global status_connect, browser_id, account_info

    try:
        data = {
            "id": account_info.get("uid"),
            "browser_id": browser_id,
            "timestamp": int(time.time()),
            "version": "2.2.7"
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(DOMAIN_API["PING"], json=data, headers={"Authorization": f"Bearer {token}"}, proxy=f"http://{proxy}") as response:
                if response.status == 200:
                    json_resp = await response.json()
                    valid_resp(json_resp)
                    if json_resp["code"] == 0:
                        logger.info(f"Ping successful via proxy {proxy}")
                        status_connect = CONNECTION_STATES["CONNECTED"]
                        return True
                    else:
                        logger.error(f"Ping failed via proxy {proxy}: {json_resp}")
                else:
                    logger.error(f"Failed to ping via proxy {proxy}, status: {response.status}")
    except Exception as e:
        logger.error(f"Error pinging proxy {proxy}: {e}")
    return False

# Render and maintain session info
async def render_profile_info(proxy, token):
    global browser_id, account_info

    session_info = load_session_info()
    if session_info:
        account_info = session_info
        browser_id = account_info.get("browser_id")
    else:
        browser_id = uuidv4()
        async with aiohttp.ClientSession() as session:
            async with session.post(DOMAIN_API["SESSION"], json={}, headers={"Authorization": f"Bearer {token}"}, proxy=f"http://{proxy}") as response:
                if response.status == 200:
                    json_resp = await response.json()
                    valid_resp(json_resp)
                    account_info = json_resp.get("data", {})
                    if account_info.get("uid"):
                        save_session_info(account_info)
                        logger.info(f"New session created for UID: {account_info['uid']}")
                    else:
                        logger.error("Failed to create session.")
                else:
                    logger.error("Session creation failed, invalid proxy?")
    return account_info

# Main async loop to handle proxies and pings
async def main():
    all_proxies = load_proxies(PROXY_FILE)
    token = input("Nodepay token: ").strip()
    if not token:
        logger.error("Token cannot be empty. Exiting the program.")
        exit()

    active_proxies = []
    for proxy in all_proxies:
        if await is_valid_proxy(proxy, token):
            active_proxies.append(proxy)

    if not active_proxies:
        logger.error("No valid proxies available. Exiting...")
        exit()

    logger.info(f"Using {len(active_proxies)} valid proxies.")

    tasks = {}
    for proxy in active_proxies:
        tasks[proxy] = asyncio.create_task(render_profile_info(proxy, token))

    while True:
        done, pending = await asyncio.wait(tasks.values(), return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            proxy = tasks[task]
            if task.result() is None:
                logger.warning(f"Proxy {proxy} failed. Removing and replacing...")
                active_proxies.remove(proxy)
                new_proxy = all_proxies.pop(0)
                active_proxies.append(new_proxy)
                tasks[new_proxy] = asyncio.create_task(render_profile_info(new_proxy, token))
            tasks.pop(task)

        for proxy in active_proxies:
            if proxy not in tasks:
                tasks[proxy] = asyncio.create_task(render_profile_info(proxy, token))

        await asyncio.sleep(PING_INTERVAL)

# Start program
if __name__ == '__main__':
    show_warning()
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Program terminated by user.")
