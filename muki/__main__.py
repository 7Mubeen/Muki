"""Run MUKI with: python3 -m muki"""
from pathlib import Path
import os

from muki.database import Database
from muki.ui.app import MukiApp


def main() -> None:
    # Tk uses XIM on Linux; Fcitx5 exposes its XIM bridge as fcitx.
    os.environ.setdefault("XMODIFIERS", "@im=fcitx")
    data_home = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    app_dir = data_home / "muki"
    app_dir.mkdir(parents=True, exist_ok=True)
    database_path = app_dir / "muki.sqlite3"
    # Do not create a meaningless empty snapshot on a first-ever launch.
    # Existing databases are backed up after Database has opened successfully.
    startup_backup = database_path.is_file() and database_path.stat().st_size > 0
    database = Database(database_path)
    MukiApp(database, startup_backup=startup_backup).mainloop()


if __name__ == "__main__":
    main()
