#!/usr/bin/env python3
"""
Web server for Cable Tray Takeoff Tool

Serves the web interface and handles saving cable tray data to JSON.

Usage:
    python3 server.py --image path/to/plan.jpg [--output output.json] [--port 8000]
"""

import argparse
import json
import os
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import sys

class CableTrayHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, image_path=None, output_path="output.json", **kwargs):
        self.image_path = image_path
        self.output_path = output_path
        super().__init__(*args, **kwargs)
    
    def do_GET(self):
        """Handle GET requests"""
        parsed_path = urlparse(self.path)
        
        if parsed_path.path == '/' or parsed_path.path == '/index.html':
            # Serve the HTML file
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            
            html_path = os.path.join(os.path.dirname(__file__), 'web_takeoff.html')
            with open(html_path, 'rb') as f:
                self.wfile.write(f.read())
        elif parsed_path.path == '/image' and self.image_path:
            # Serve the image
            if os.path.exists(self.image_path):
                self.send_response(200)
                mime_type = 'image/jpeg'
                if self.image_path.lower().endswith('.png'):
                    mime_type = 'image/png'
                elif self.image_path.lower().endswith('.gif'):
                    mime_type = 'image/gif'
                self.send_header('Content-type', mime_type)
                self.end_headers()
                with open(self.image_path, 'rb') as f:
                    self.wfile.write(f.read())
            else:
                self.send_error(404, "Image not found")
        else:
            # Try to serve static files
            super().do_GET()
    
    def do_POST(self):
        """Handle POST requests for saving data"""
        if self.path == '/save':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            
            try:
                data = json.loads(post_data.decode('utf-8'))
                
                # Save to output file
                with open(self.output_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                
                response = {
                    'success': True,
                    'message': f'Saved {len(data.get("cable_trays", []))} cable trays to {self.output_path}',
                    'file': self.output_path
                }
                self.wfile.write(json.dumps(response).encode('utf-8'))
                
                print(f"\n✅ Saved {len(data.get('cable_trays', []))} cable trays to {self.output_path}")
                print(f"   Total points: {data.get('meta', {}).get('total_points', 0)}")
                print(f"   Total connections: {data.get('meta', {}).get('total_connections', 0)}")
                
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                response = {'success': False, 'error': str(e)}
                self.wfile.write(json.dumps(response).encode('utf-8'))
                print(f"Error saving data: {e}")
        else:
            self.send_error(404)
    
    def log_message(self, format, *args):
        """Override to customize logging"""
        if args[0].startswith('GET /') or args[0].startswith('POST /'):
            print(f"[{self.log_date_time_string()}] {args[0]}")


def create_handler(image_path, output_path):
    """Factory function to create handler with custom parameters"""
    def handler(*args, **kwargs):
        return CableTrayHandler(*args, image_path=image_path, output_path=output_path, **kwargs)
    return handler


def main():
    parser = argparse.ArgumentParser(
        description="Web server for Cable Tray Takeoff Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 server.py --image plan.jpg
  python3 server.py --image plan.jpg --output my_trays.json --port 8080

Then open your browser to: http://localhost:8000
        """
    )
    parser.add_argument('--image', help='Path to the electrical plan image')
    parser.add_argument('--output', default='output.json', help='Output JSON file path (default: output.json)')
    parser.add_argument('--port', type=int, default=8000, help='Port to run server on (default: 8000)')
    
    args = parser.parse_args()
    
    # Change to script directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    
    # Validate image path if provided
    if args.image and not os.path.exists(args.image):
        print(f"Warning: Image file not found: {args.image}")
        print("You can still load an image through the web interface.")
        args.image = None
    
    # Create handler with custom parameters
    handler = create_handler(args.image, args.output)
    
    # Start server
    server_address = ('', args.port)
    httpd = HTTPServer(server_address, handler)
    
    print(f"\n{'='*60}")
    print("Cable Tray Takeoff Tool - Web Server")
    print(f"{'='*60}")
    print(f"\nServer running at: http://localhost:{args.port}")
    if args.image:
        print(f"Image: {args.image}")
    print(f"Output: {args.output}")
    print(f"\nOpen your browser and navigate to: http://localhost:{args.port}")
    print("\nPress Ctrl+C to stop the server\n")
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n\nServer stopped.")
        sys.exit(0)


if __name__ == '__main__':
    main()

