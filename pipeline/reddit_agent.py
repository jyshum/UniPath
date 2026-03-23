import json
import time
import requests
import ollama
import pandas as pd
from datetime import datetime, timezone
from pathlib import Path
from sqlachemy.orm import Session

from database.models import Student, inti_dev, get_engine
from pipeline.normalize import normalize_row


HEADERS = {"User-Agent": "unipath-ai/1.0 (research project)"}

SUBREDDITS = ["OntarioGrade12s", "BCGrade12s"]

SEARCH_QUERIES = [
    "accepeted average",
    "rejected average",
    "admission results",
    "offer of admission",
    "got in",
    "decisions results"
]

REQUEST_DELAY = 2

