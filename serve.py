# -*- coding: utf-8 -*-
"""支持 Range 请求的本地 HTTP 服务器（用于 audio/video 流式播放）
用法： python serve.py
访问： http://127.0.0.1:8765/
"""
import http.server
import socketserver
import os
import re
from functools import partial

class RangeHandler(http.server.SimpleHTTPRequestHandler):
    def send_head(self):
        path = self.translate_path(self.path)
        ctype = self.guess_type(path)
        try:
            fs = os.stat(path)
        except OSError:
            return self.send_error(404, "File not found")
        if fs.st_size is None:
            return self.send_error(404, "File not found")
        size = fs.st_size
        range_header = self.headers.get('Range')
        start = 0
        end = size - 1
        is_range = False
        if range_header:
            m = re.match(r'bytes=(\d*)-(\d*)', range_header.strip())
            if m:
                start = int(m.group(1)) if m.group(1) else 0
                end = int(m.group(2)) if m.group(2) else size - 1
                if end >= size:
                    end = size - 1
                if start > end or start >= size:
                    return self.send_error(416, "Range Not Satisfiable")
                is_range = True
        length = end - start + 1
        if is_range:
            self.send_response(206)
            self.send_header('Content-Range', f'bytes {start}-{end}/{size}')
        else:
            self.send_response(200)
        self.send_header('Content-Type', ctype)
        self.send_header('Accept-Ranges', 'bytes')
        self.send_header('Content-Length', str(length))
        self.end_headers()
        # 手动写分块，捕获客户端中止（浏览器 audio seek 完即断开）
        try:
            with open(path, 'rb') as f:
                f.seek(start)
                remaining = length
                while remaining > 0:
                    chunk = f.read(min(65536, remaining))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    remaining -= len(chunk)
        except (BrokenPipeError, ConnectionResetError):
            pass
        return None

    def log_message(self, fmt, *args):
        # 抑制连接重置刷屏，保留正常访问日志
        s = fmt % args
        if 'ConnectionResetError' in s or '10054' in s:
            return
        super().log_message(fmt, *args)

if __name__ == '__main__':
    PORT = 8765
    directory = os.path.dirname(os.path.abspath(__file__))
    handler = partial(RangeHandler, directory=directory)
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("127.0.0.1", PORT), handler) as httpd:
        print(f"Range-enabled server on http://127.0.0.1:{PORT}/ (dir: {directory})")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nserver stopped")
