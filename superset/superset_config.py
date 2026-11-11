import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env", override=False)
KEY = os.environ["SUPERSET_KEY"]

SUPERSET_HOME =Path.home() / ".superset"
SUPERSET_HOME.mkdir(exist_ok=True)
SQLALCHEMY_DATABASE_URI = f"sqlite:///{SUPERSET_HOME / 'superset.db'}"
SUPERSET_WEBSERVER_PORT = int(os.getenv("SUPERSET_PORT"))
FEATURE_FLAGS = {
    "DASHBOARD_NATIVE_FILTERS": True,
    "DASHBOARD_CROSS_FILTERS": True,
}