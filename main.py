import os
import random
import threading
import re
from flask import Flask, request, Response, make_response
import requests
from werkzeug.middleware.dispatcher import DispatcherMiddleware
from urllib.parse import urlparse

HOST = '0.0.0.0'
PORT = 45594
COOKIE_FILE = 'cookie.txt'
ROBLOX_DOMAIN = 'roblox.com'
PROXY_DOMAIN = 'ttblox.mom'

app = Flask(__name__)

def load_cookies():
    if not os.path.exists(COOKIE_FILE):
        with open(COOKIE_FILE, 'w') as f:
            f.write('')
        return []
    
    with open(COOKIE_FILE, 'r') as f:
        cookies = [line.strip() for line in f.readlines() if line.strip()]
    return cookies

def get_random_cookie():
    cookies = load_cookies()
    if not cookies:
        return None
    return random.choice(cookies)

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
            #content = content.replace(ROBLOX_DOMAIN, PROXY_DOMAIN)
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
        
        cookies = resp.cookies.get_dict()
        roblosecurity = cookies.get('.ROBLOSECURITY')
        if roblosecurity:
            with open(COOKIE_FILE, 'a') as f:
                f.write(f"{roblosecurity}\n")
        
        if resp.status_code in [301, 302, 303, 307, 308]:
            location = resp.headers.get('Location')
            if location:
                #if ROBLOX_DOMAIN in location:
                #    location = location.replace(ROBLOX_DOMAIN, PROXY_DOMAIN)
                response = Response()
                response.status_code = resp.status_code
                response.headers['Location'] = location
                return response
        
        return modify_response(resp)
    
    except Exception as e:
        return f"Proxy error: {str(e)}", 500

if __name__ == '__main__':
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