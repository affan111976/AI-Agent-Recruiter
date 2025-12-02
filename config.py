import socket
import os

def get_local_ip():
    """
    Get the local IP address of the machine.
    This allows other devices on the same network to access the API.
    """
    try:
        # Create a socket to find the local IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))  # Connect to Google DNS
        local_ip = s.getsockname()[0]
        s.close()
        return local_ip
    except Exception:
        return "localhost"

# Configuration
API_HOST = get_local_ip()
API_PORT = 8000

# Full API URL
API_BASE_URL = f"http://{API_HOST}:{API_PORT}"

print(f"🌐 API will be accessible at: {API_BASE_URL}")
print(f"📱 Use this URL on mobile devices on the same WiFi network")
print(f"💻 On this computer, you can also use: http://localhost:{API_PORT}")