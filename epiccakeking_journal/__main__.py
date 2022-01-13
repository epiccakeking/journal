"""
Copyright 2022 epiccakeking

This file is part of epiccakeking_journal.

epiccakeking_journal is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version.

epiccakeking_journal is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.

You should have received a copy of the GNU General Public License along with epiccakeking_journal. If not, see <https://www.gnu.org/licenses/>.
"""
import gi

gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, Gio, GLib, Gdk
from pkg_resources import resource_string
import datetime
from pathlib import Path
import traceback
import json


class Backend:
    def __init__(self, path):
        self.path = Path(path)

    def get_date_path(self, date):
        return self.path / date.isoformat().replace('-', '/')

    def get_day(self, date):
        file_path = self.get_date_path(date)
        if file_path.exists():
            return file_path.read_text()
        return ''

    def month_edited_days(self, date):
        path = self.get_date_path(date).parent
        if not path.exists():
            return []
        return sorted(int(x.name) for x in path.iterdir())

    def save_day(self, date, data):
        file_path = self.get_date_path(date)
        if data == '' and file_path.exists():
            file_path.unlink()
        if data == self.get_day(date):
            return True
        file_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_file_path = file_path.with_suffix(file_path.suffix + '.new')
        tmp_file_path.write_text(data)
        tmp_file_path.rename(file_path)
        return True


class Settings(dict):
    DEFAULTS = dict(
        date_format='',
    )

    def __init__(self, path):
        self.path = (path)
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
        temp_file_path = self.path.with_suffix(self.path.suffix + '.new')
        temp_file_path.write_text(json.dumps(self.settings | settings))
        temp_file_path.rename(self.path)
        self.reload()


def templated(c):
    return Gtk.Template(string=resource_string(__name__, f'ui/{c.__name__}.ui'))(c)


@templated
class MainWindow(Gtk.ApplicationWindow):
    __gtype_name__ = 'MainWindow'
    backward = Gtk.Template.Child('backward')
    forward = Gtk.Template.Child('forward')
    calendar_menu = Gtk.Template.Child('calendar_menu')
    calendar = Gtk.Template.Child('calendar')

    def __init__(self, app):
        super().__init__(application=app)
        self.page = None
        self.connect('close-request', self.on_close_request)
        self.backward.connect('clicked', self.on_backward)
        self.forward.connect('clicked', self.on_forward)
        self.calendar_menu.connect('show', self.on_calendar_activate)
        self.calendar.connect('day-selected', self.on_calendar_select)
        self.set_action('settings', lambda *_: SettingsModal(self))
        self.set_action('about', lambda *_: AboutModal(self))
        self.backend = Backend(Path(GLib.get_user_data_dir()) / app.get_application_id() / 'journal')
        self.settings = Settings(Path(GLib.get_user_config_dir()) / app.get_application_id() / 'settings.json')
        self.change_day(datetime.date.today())
        # Add CSS
        css=Gtk.CssProvider()
        css.load_from_data(resource_string(__name__, 'css/main.css'))
        Gtk.StyleContext().add_provider_for_display(self.get_display(), css,  Gtk.STYLE_PROVIDER_PRIORITY_USER)
        self.present()

    def set_action(self, name, handler):
        action = Gio.SimpleAction.new(name, None)
        action.connect('activate', handler)
        self.add_action(action)

    def on_close_request(self, *_):
        try:
            return not self.page.save()
        except:
            traceback.print_exc()
            return True

    def on_button(self, *_):
        self.close()

    def change_day(self, date):
        if self.page and not self.page.save():
            return False
        page = JournalPage(self.backend, date)
        self.set_child(page)
        self.page = page
        date_format = self.settings.get('date_format') or '%Y-%m-%d'
        self.set_title('Journal: ' + date.strftime(date_format))
        return True

    def on_backward(self, *_):
        self.change_day(self.page.date - datetime.timedelta(days=1))

    def on_forward(self, *_):
        self.change_day(self.page.date + datetime.timedelta(days=1))

    def on_calendar_activate(self, *_):
        # Set calendar
        self.calendar.select_day(GLib.DateTime(
            GLib.TimeZone.new_utc(),
            self.page.date.year,
            self.page.date.month,
            self.page.date.day,
            0, 0, 0
        ))
        self.calendar.clear_marks()
        for day in self.backend.month_edited_days(self.page.date):
            self.calendar.mark_day(day)

    def on_calendar_select(self, *_):
        date = self.calendar.get_date()
        self.change_day(datetime.date(
            day=date.get_day_of_month(),
            month=date.get_month(),
            year=date.get_year(),
        ))
        self.calendar.clear_marks()
        for day in self.backend.month_edited_days(self.page.date):
            self.calendar.mark_day(day)
        


@templated
class JournalPage(Gtk.ScrolledWindow):
    __gtype_name__ = 'JournalPage'
    text_area = Gtk.Template.Child('text_area')

    def __init__(self, backend, date):
        super().__init__()
        self.backend = backend
        self.date = date
        self.buffer = self.text_area.get_buffer()
        self.tags={
            'title': self.buffer.create_tag(
                'title',
                foreground='pink',
                font='Sans 20',
            ),
            'bullet': self.buffer.create_tag(
                'bullet',
                foreground='green',
            ),
            'code': self.buffer.create_tag(
                'code',
                font='Monospace',
            ),
            'rule': self.buffer.create_tag(
                'rule',
                foreground='green',
            ),
        }
        self.buffer.connect('changed', lambda *_: self.format())
        self.buffer.set_text(self.backend.get_day(self.date))

    def save(self):
        buffer = self.text_area.get_buffer()
        return self.backend.save_day(self.date, self.buffer.get_text(*self.buffer.get_bounds(), True))

    def format(self):
        self.buffer.remove_all_tags(*self.buffer.get_bounds())
        code=False
        for i in range(self.buffer.get_line_count()):
            start=self.buffer.get_iter_at_line(i)[1]
            end=start.copy()
            end.forward_to_line_end()
            text=self.buffer.get_text(start, end, True)
            if text=='```':
                code^=True
                self.buffer.apply_tag(self.tags['code'], start, end)
            elif code:
                self.buffer.apply_tag(self.tags['code'], start, end)
            elif text.startswith('# '):
                self.buffer.apply_tag(self.tags['title'], start, end)
            elif text == '====================':
                self.buffer.apply_tag(self.tags['rule'], start, end)
            elif text.startswith('* '):
                bullet_end=start.copy()
                bullet_end.forward_char()
                self.buffer.apply_tag(self.tags['bullet'], start, bullet_end)


class AboutModal(Gtk.AboutDialog):
    def __init__(self, parent):
        super().__init__(
            authors=(
                'epiccakeking',
            ),
            copyright='Copyright 2022 epiccakeking',
            license_type='GTK_LICENSE_GPL_3_0',
            program_name='Journal',
        )
        self.set_logo_icon_name('io.github.epiccakeking.Journal')
        self.set_modal(True)
        self.set_transient_for(parent)
        self.present()


@templated
class SettingsModal(Gtk.Dialog):
    __gtype_name__ = 'SettingsModal'
    date_format = Gtk.Template.Child('date_format')

    def __init__(self, parent):
        super().__init__()
        self.set_modal(True)
        self.set_transient_for(parent)
        self.parent = parent
        self.date_format.set_text(self.parent.settings.get('date_format'))
        self.connect('close-request', self.on_close_request)
        self.present()

    def on_close_request(self, *_):
        try:
            self.save_changes()
        except:
            traceback.print_exc()
            return True

    def save_changes(self):
        self.parent.settings.set(
            date_format=self.date_format.get_text(),
        )
        pass


app = Gtk.Application(application_id='io.github.epiccakeking.Journal')
app.connect('activate', MainWindow)
app.run(None)
