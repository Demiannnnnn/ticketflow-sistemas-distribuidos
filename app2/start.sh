#!/bin/bash

# Start the Flask web server in the background
export FLASK_APP=run.py
flask run --host=0.0.0.0 --port=5002 &

# Start the Socket Listener in the foreground
python -u run_listener.py
