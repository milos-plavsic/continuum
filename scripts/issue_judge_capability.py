#!/usr/bin/env python3
"""Issue an expiring judge capability from a secret supplied outside source."""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import os

from continuum.judge_access import issue_judge_token


parser = argparse.ArgumentParser()
parser.add_argument("--jti", required=True)
parser.add_argument("--hours", type=int, default=24 * 30)
parser.add_argument("--max-runs", type=int, default=3)
args = parser.parse_args()
secret = os.environ.get("CONTINUUM_JUDGE_HMAC_SECRET", "")
expires = int((datetime.now(timezone.utc) + timedelta(hours=args.hours)).timestamp())
print(issue_judge_token(secret=secret, jti=args.jti, expires_at=expires,
                        max_runs=args.max_runs))
