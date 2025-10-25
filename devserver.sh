#!/bin/sh
source .venv/bin/activate
flask --app main run --debug --port=${PORT:-5000} --extra-files templates --extra-files main.py --extra-files pdf_processing.py --exclude-patterns "*/static/images/*"
