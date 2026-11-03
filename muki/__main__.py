"""Run MUKI with: python3 -m muki"""
from pathlib import Path
import os

from muki.database import Database
from muki.ui.app import MukiApp


def main() -> None:
    data_home = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    app_dir = data_home / "muki"
    app_dir.mkdir(parents=True, exist_ok=True)
    database = Database(app_dir / "muki.sqlite3")
    MukiApp(database).mainloop()


if __name__ == "__main__":
    main()
