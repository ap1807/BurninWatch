"""
BurninWatch – Component Screening Anomaly Detection
Main Application Runner
"""

import sys
import os
import argparse
import uvicorn

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

def main():
    default_port = int(os.environ.get("PORT", 8000))
    default_host = "0.0.0.0" if "PORT" in os.environ else "127.0.0.1"

    parser = argparse.ArgumentParser(description="BurninWatch - Component Screening Anomaly Detection")
    parser.add_argument("--host", default=default_host, help=f"Host interface to bind (default: {default_host})")
    parser.add_argument("--port", type=int, default=default_port, help=f"Port to bind (default: {default_port})")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload for development")
    args = parser.parse_args()

    print("\n" + "=" * 70)
    print("  BurninWatch - Component Screening Anomaly Detection")
    print("  Liquid Glassmorphism UI | Unsupervised Degradation ML")
    print("=" * 70)
    print(f"  Starting server at: http://{args.host}:{args.port}")
    print("  Press CTRL+C to stop.\n" + "=" * 70 + "\n")

    uvicorn.run(
        "burninwatch.web.app:app",
        host=args.host,
        port=args.port,
        reload=args.reload
    )

if __name__ == "__main__":
    main()
