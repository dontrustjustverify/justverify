#!/usr/bin/python3
"""HTTP discovery only: never accept credentials or serve the management UI."""
from http.server import BaseHTTPRequestHandler, HTTPServer
class Redirect(BaseHTTPRequestHandler):
    timeout = 5
    def do_GET(self):
        self.send_response(302)
        self.send_header('Location', 'https://justverify.local/')
        self.send_header('Content-Length', '0')
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
    do_HEAD = do_GET
    def do_POST(self):
        self.send_error(405, 'Use HTTPS')
        self.close_connection = True
    def log_message(self, *args):
        pass
if __name__ == '__main__':
    HTTPServer(('0.0.0.0', 80), Redirect).serve_forever()
