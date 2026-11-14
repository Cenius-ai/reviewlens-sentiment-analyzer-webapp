"""Convenience entrypoint: ``python3 app.py`` behaves exactly like
``python3 -m app.main`` - schema + seed on the way up, then the Gradio UI on
0.0.0.0:$PORT (7860 by default)."""

from app.main import main

if __name__ == "__main__":
    main()
