"""
Copyright 2022 epiccakeking

This file is part of epiccakeking_journal.

epiccakeking_journal is free software: you can redistribute it and/or modify it under
the terms of the GNU General Public License as published by the
Free Software Foundation, either version 3 of the License, or (at your option) any later
version.

epiccakeking_journal is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.

You should have received a copy of the GNU General Public License along with
epiccakeking_journal. If not, see <https://www.gnu.org/licenses/>.
"""
import datetime
import json
from pathlib import Path


class Backend:
    def __init__(self, path):
        self.path = Path(path)

    def get_date_path(self, date):
        return self.path / date.isoformat().replace("-", "/")

    def get_day(self, date):
        file_path = self.get_date_path(date)
        if file_path.exists():
            return file_path.read_text()
        return ""

    def month_edited_days(self, date):
        path = self.get_date_path(date).parent
        if not path.exists():
            return []
        return sorted(int(x.name) for x in path.iterdir())

    def save_day(self, date, data):
        file_path = self.get_date_path(date)
        # For consistency ensure empty days don't have a file.
        if data == "" and file_path.exists():
            file_path.unlink()
            return True
        if data == self.get_day(date):
            return True
        file_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_file_path = file_path.with_suffix(file_path.suffix + ".new")
        tmp_file_path.write_text(data)
        tmp_file_path.rename(file_path)
        return True

    def get_edited_days(self):
        if not self.path.exists():
            return
        for year_dir in self.path.iterdir():
            year = int(year_dir.name)
            for month_dir in year_dir.iterdir():
                month = int(month_dir.name)
                for day_file in month_dir.iterdir():
                    yield datetime.date(year=year, month=month, day=int(day_file.name))

    def search(self, term):
        """Each result will be yielded as a tuple: (date, line_number, line_content)"""
        for day in self.get_edited_days():
            with open(self.get_date_path(day)) as f:
                for i, line in enumerate(f):
                    if term.lower() in line.lower():
                        yield day, i, line


class Settings:
    DEFAULTS = dict(date_format="", alt_gui=False, word_cloud_exclusions=[])

    def __init__(self, path):
        self.path = path
        self.settings = None
        self.reload()

    def reload(self):
        if self.path.exists():
            self.settings = json.loads(self.path.read_text())
        else:
            self.settings = {}

    def get(self, setting):
        return self.settings.get(setting, self.DEFAULTS[setting])

    def set(self, **settings):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp_file_path = self.path.with_suffix(self.path.suffix + ".new")
        temp_file_path.write_text(json.dumps(self.settings | settings))
        temp_file_path.rename(self.path)
        self.reload()
