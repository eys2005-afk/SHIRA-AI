"""טעינת ההגדרות מ-config.yaml + .env, עם נתיבים מנורמלים."""

import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

PROJECT_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_DIR / "config.yaml"

load_dotenv(PROJECT_DIR / ".env")


def load_config() -> dict:
    with open(CONFIG_PATH, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    for section in ("shira", "verbit"):
        profile = cfg.get(section, {}).get("profile_dir")
        if profile:
            cfg[section]["profile_dir"] = str(Path(profile).expanduser())

    data_dir = PROJECT_DIR / cfg.get("storage", {}).get("data_dir", "data")
    data_dir.mkdir(parents=True, exist_ok=True)
    cfg["storage"]["data_dir"] = str(data_dir)

    cfg["verbit"]["api"]["token"] = os.environ.get("VERBIT_API_TOKEN", "")
    return cfg
