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
    parser = argparse.ArgumentParser(description="BurninWatch - Component Screening Anomaly Detection")
    parser.add_argument("--host", default="127.0.0.1", help="Host interface to bind (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind (default: 8000)")
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
