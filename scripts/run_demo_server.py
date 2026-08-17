#!/usr/bin/env python3
import os

import uvicorn

os.environ.setdefault("CONTINUUM_DEMO_MODE", "1")
uvicorn.run("continuum.api:app", host="127.0.0.1", port=8080, reload=False)
