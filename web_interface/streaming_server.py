#!/usr/bin/python3

import io
import logging
import socketserver
from http import server
from threading import Condition
from picamera2 import Picamera2
from picamera2.encoders import MJPEGEncoder
from picamera2.outputs import FileOutput

PAGE = """\
<html>
<head>
<title>picamera2 MJPEG streaming demo</title>
</head>
<body>
<h1>Picamera2 MJPEG Streaming Demo</h1>
<img src="stream.mjpg" width="1280" height="720" />
</body>
</html>
"""

streaming = False
output = None
picam2 = None

class StreamingOutput(io.BufferedIOBase):
    def __init__(self):
        self.frame = None
        self.condition = Condition()

    def write(self, buf):
        with self.condition:
            self.frame = buf
            self.condition.notify_all()

class StreamingHandler(server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            self.send_response(301)
            self.send_header('Location', '/index.html')
            self.end_headers()
        elif self.path == '/index.html':
            content = PAGE.encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.send_header('Content-Length', len(content))
            self.end_headers()
            self.wfile.write(content)
        elif self.path == '/stream.mjpg':
            self.send_response(200)
            self.send_header('Age', 0)
            self.send_header('Cache-Control', 'no-cache, private')
            self.send_header('Pragma', 'no-cache')
            self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=FRAME')
            self.end_headers()
            try:
                while True:
                    with output.condition:
                        output.condition.wait()
                        frame = output.frame
                    self.wfile.write(b'--FRAME\r\n')
                    self.send_header('Content-Type', 'image/jpeg')
                    self.send_header('Content-Length', len(frame))
                    self.end_headers()
                    self.wfile.write(frame)
                    self.wfile.write(b'\r\n')
            except Exception as e:
                logging.warning(
                    'Removed streaming client %s: %s',
                    self.client_address, str(e))
        else:
            self.send_error(404)
            self.end_headers()

class StreamingServer(socketserver.ThreadingMixIn, server.HTTPServer):
    allow_reuse_address = True
    daemon_threads = True

def start_streaming_server():
    global streaming
    global output
    global picam2
    picam2 = Picamera2()
    output = StreamingOutput()
    picam2.configure(picam2.create_video_configuration(main={"size": (1920, 1080)}))
    picam2.set_controls({"FrameDurationLimits":(33333,100000),"ExposureValue":6.0, "Brightness":0.1})
    picam2.start_recording(MJPEGEncoder(), FileOutput(output))

    try:
        address = ('0.0.0.0', 8080) # Replace 0.0.0.0 with the IP adress of your WALL-E in your network 
        streaming_server = StreamingServer(address, StreamingHandler)
        streaming_server.serve_forever()
    except KeyboardInterrupt:
        streaming_server.shutdown()
    finally:
        picam2.stop_recording()
        picam2.close()

if __name__ == "__main__":
    start_streaming_server()
