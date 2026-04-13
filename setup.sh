#!/bin/bash

python3 -m venv server/venv
source server/venv/bin/activate
pip install -r server/requirements.txt
deactivate
