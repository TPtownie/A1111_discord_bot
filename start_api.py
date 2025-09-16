#!/usr/bin/env python3
"""
Start the API server for Discord Bot A1111 Integration

Usage:
    python start_api.py [--host HOST] [--port PORT] [--reload]
"""

import argparse
import uvicorn
import sys
import os

# Add the current directory to the path so we can import from api
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def main():
    parser = argparse.ArgumentParser(description="Start Discord Bot A1111 API Server")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind to (default: 8000)")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload for development")
    parser.add_argument("--a1111-url", default="http://127.0.0.1:7860", help="A1111 WebUI URL")
    
    args = parser.parse_args()
    
    print(f"Starting Discord Bot A1111 API Server...")
    print(f"API will be available at: http://{args.host}:{args.port}")
    print(f"A1111 WebUI URL: {args.a1111_url}")
    print(f"Documentation: http://{args.host}:{args.port}/docs")
    print(f"OpenAPI spec: http://{args.host}:{args.port}/openapi.json")
    
    # Set environment variable for A1111 URL
    os.environ["A1111_URL"] = args.a1111_url
    
    # Start the server
    uvicorn.run(
        "api.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info"
    )

if __name__ == "__main__":
    main()