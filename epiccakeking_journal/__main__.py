"""
Copyright 2022 epiccakeking

This file is part of epiccakeking_journal.

epiccakeking_journal is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version.

epiccakeking_journal is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.

You should have received a copy of the GNU General Public License along with epiccakeking_journal. If not, see <https://www.gnu.org/licenses/>.
"""
import gi

gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, Gio, GLib
from pkg_resources import resource_string
import datetime
from pathlib import Path
import traceback
import json
import string

APP_ID = 'io.github.epiccakeking.Journal'

letters = set(string.ascii_letters)


def strip_non_letters(s):
    for start, c in enumerate(s):
        if c in letters:
            break
    for end in range(len(s) - 1, start - 1, -1):
        if s[end] in letters:
            end += 1
            break
    return s[start:end]


def main():
    app = Gtk.Application(application_id=APP_ID)
    app.connect('activate', AltGui if settings.get('alt_gui') else MainWindow)
    app.run(None)


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

    def get_edited_days(self):
        for year_dir in self.path.iterdir():
            year = int(year_dir.name)
            for month_dir in year_dir.iterdir():
                month = int(month_dir.name)
                for day_file in month_dir.iterdir():
                    yield datetime.date(year=year, month=month, day=int(day_file.name))

    def search(self, term):
        """Each result will be yielded as a tuple: (date, line_number, line_content)
        """
        for day in self.get_edited_days():
            with open(self.get_date_path(day)) as f:
                for i, line in enumerate(f):
                    if term.lower() in line.lower():
                        yield day, i, line


class Settings:
    DEFAULTS = dict(
        date_format='',
        alt_gui=False,
    )

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
    page = None

    def __init__(self, app):
        super().__init__(application=app)

        self.connect('close-request', self.on_close_request)
        self.backward.connect('clicked', self.on_backward)
        self.forward.connect('clicked', self.on_forward)
        self.calendar_menu.connect('show', self.on_calendar_activate)
        self.calendar.connect('day-selected', self.on_calendar_select)
        self.setup_actions()
        self.backend = Backend(Path(GLib.get_user_data_dir()) / app.get_application_id() / 'journal')
        self.settings = settings

        self.change_day(datetime.date.today())
        # Add CSS
        css = Gtk.CssProvider()
        css.load_from_data(resource_string(__name__, 'css/main.css'))
        Gtk.StyleContext().add_provider_for_display(self.get_display(), css, Gtk.STYLE_PROVIDER_PRIORITY_USER)
        self.present()

    def setup_actions(self):
        self.set_action('settings', lambda *_: SettingsModal(self))
        self.set_action('about', lambda *_: AboutModal(self))
        self.set_action('search', lambda *_: SearchWindow(self))
        self.set_action('insert_line', lambda *_: self.page.insert_line())
        self.set_action('insert_header', lambda *_: self.page.insert_header())
        self.set_action('insert_code', lambda *_: self.page.insert_code())

    def set_action(self, name, handler):
        action = Gio.SimpleAction.new(name, None)
        action.connect('activate', handler)
        self.add_action(action)

    def on_close_request(self, *_):
        try:
            return not self.page.save()
        except Exception:
            traceback.print_exc()
            return True  # Saving has failed so don't close the window

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
            GLib.TimeZone.new_utc(),  # Timezone (seemingly) doesn't matter
            self.page.date.year,
            self.page.date.month,
            self.page.date.day,
            0, 0, 0  # Hours, minutes, and seconds are not used
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


class WordCloud(Gtk.ScrolledWindow):
    MAX_WORDS = 50

    def __init__(self, frequency_data=None, press_callback=None):
        """
        :param frequency_data: Iterable yielding (word, count) tuples
        """
        super().__init__(vexpand=True)
        self.press_callback = press_callback
        if frequency_data is not None:
            self.load(frequency_data)

    def load(self, frequency_data):
        box = Gtk.TextView(wrap_mode=2, editable=False, cursor_visible=False)
        buffer = box.get_buffer()
        words = sorted(frequency_data, key=lambda x: x[1], reverse=True)
        words = words[:self.MAX_WORDS]
        if words:
            avg = sum(x[1] ** .5 for x in words) / len(words)
        else:
            avg = 1
        words.sort(key=lambda x: x[0])
        for word, count in words:
            button = Gtk.Button(css_classes=('cloud_button',))
            label = Gtk.Label(
                margin_end=2,
                margin_start=2,
                yalign=1,
            )
            label.set_markup(f'<span font_desc="{10 * count ** .5 // avg}">{GLib.markup_escape_text(word)}</span>')
            button.connect('clicked', self.make_button_func(word))
            button.set_child(label)
            box.add_child_at_anchor(button, buffer.create_child_anchor(buffer.get_end_iter()))
        self.set_child(box)

    @classmethod
    def from_string(cls, s):
        """Generate a word cloud from a string"""
        word_dict = {}
        for word in s.split():
            word_dict.setdefault(word, 0)
            word_dict[word] += 1
        return cls(word_dict.items())

    def on_button_press(self, *_):
        print(*_)
        return True

    def make_button_func(self, word):
        def f(*_):
            self.press_callback(word)
            return True

        return f


@templated
class AltGui(Gtk.ApplicationWindow):
    __gtype_name__ = 'AltGui'
    backward = Gtk.Template.Child('backward')
    forward = Gtk.Template.Child('forward')
    calendar = Gtk.Template.Child('calendar')
    pane = Gtk.Template.Child('pane')
    box = Gtk.Template.Child('box')
    search = Gtk.Template.Child('search')
    stack = Gtk.Template.Child('stack')
    search_scroller = Gtk.Template.Child('search_scroller')
    page = None

    def __init__(self, app):
        Gtk.ApplicationWindow.__init__(self, application=app)

        self.connect('close-request', self.on_close_request)
        self.backward.connect('clicked', self.on_backward)
        self.forward.connect('clicked', self.on_forward)
        self.calendar.connect('day-selected', self.on_calendar_select)
        self.search.connect('changed', self.on_search_input)
        MainWindow.setup_actions(self)
        self.backend = Backend(Path(GLib.get_user_data_dir()) / app.get_application_id() / 'journal')
        self.settings = Settings(Path(GLib.get_user_config_dir()) / app.get_application_id() / 'settings.json')
        self.cloud = WordCloud(press_callback=self.search.set_text)

        self.change_day(datetime.date.today())
        MainWindow.on_calendar_activate(self)
        self.update_cloud()
        self.stack.add_child(self.cloud)
        self.stack.set_visible_child(self.cloud)
        # Add CSS
        css = Gtk.CssProvider()
        css.load_from_data(resource_string(__name__, 'css/main.css'))
        Gtk.StyleContext().add_provider_for_display(self.get_display(), css, Gtk.STYLE_PROVIDER_PRIORITY_USER)
        self.present()

    on_close_request = MainWindow.on_close_request
    on_calendar_select = MainWindow.on_calendar_select
    set_action = MainWindow.set_action

    def on_backward(self, *_):
        MainWindow.on_backward(self)
        MainWindow.on_calendar_activate(self)

    def on_forward(self, *_):
        MainWindow.on_forward(self)
        MainWindow.on_calendar_activate(self)

    def change_day(self, date):
        if self.page and not self.page.save():
            return False
        page = JournalPage(self.backend, date)
        self.pane.set_end_child(page)
        self.page = page
        date_format = self.settings.get('date_format') or '%Y-%m-%d'
        self.set_title('Journal: ' + date.strftime(date_format))
        self.update_cloud()
        return True

    def update_cloud(self):
        word_dict = {}
        for day in self.backend.get_edited_days():
            for word in self.backend.get_day(day).split():
                word = strip_non_letters(word)
                if word:
                    word_dict.setdefault(word, 0)
                    word_dict[word] += 1
        self.cloud.load(word_dict.items())

    def on_search_input(self, *_):
        text = self.search.get_text()
        if not text:
            self.stack.set_visible_child(self.cloud)
            return
        # Remove any existing results
        results_box = Gtk.Box(orientation=1, vexpand=True)
        for result in self.backend.search(text):
            results_box.append(SearchResult(self, *result))
        self.search_scroller.set_child(results_box)
        self.stack.set_visible_child(self.search_scroller)


@templated
class SearchWindow(Gtk.Dialog):
    __gtype_name__ = 'SearchWindow'
    search = Gtk.Template.Child('search')
    results_scroller = Gtk.Template.Child('results_scroller')

    def __init__(self, parent):
        super().__init__(modal=True, transient_for=parent)
        self.parent = parent
        self.search.connect('activate', self.on_search)
        self.present()

    def on_search(self, *_):
        result_box = Gtk.Box(orientation=1, vexpand=True)
        for result in self.parent.backend.search(self.search.get_text()):
            result_box.append(SearchResult(self, *result))
        self.results_scroller.set_child(result_box)

    def change_day(self, date):
        self.parent.change_day(date)
        self.close()


@templated
class SearchResult(Gtk.Button):
    __gtype_name__ = 'SearchResult'
    date_label = Gtk.Template.Child('date_label')
    preview = Gtk.Template.Child()

    def __init__(self, parent, date, line_number, text):
        super().__init__()
        self.parent = parent
        self.date = date
        self.connect('clicked', self.on_click)
        self.date_label.set_label(date.isoformat() + ': ')
        self.preview.set_label(text.rstrip())

    def on_click(self, *_):
        self.parent.change_day(self.date)


@templated
class JournalPage(Gtk.ScrolledWindow):
    __gtype_name__ = 'JournalPage'
    text_area = Gtk.Template.Child('text_area')

    def __init__(self, backend, date):
        super().__init__()
        self.backend = backend
        self.date = date
        self.buffer = self.text_area.get_buffer()
        self.tags = {
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
        self.add_shortcut(Gtk.Shortcut.new(
            Gtk.ShortcutTrigger.parse_string('<Control>space'),
            Gtk.CallbackAction.new(lambda *_: self.insert_line()),
        ))
        self.add_shortcut(Gtk.Shortcut.new(
            Gtk.ShortcutTrigger.parse_string('<Control>H'),
            Gtk.CallbackAction.new(lambda *_: self.insert_header()),
        ))
        self.add_shortcut(Gtk.Shortcut.new(
            Gtk.ShortcutTrigger.parse_string('<Control>M'),
            Gtk.CallbackAction.new(lambda *_: self.insert_code()),
        ))
        self.buffer.set_text(self.backend.get_day(self.date))

    def save(self):
        return self.backend.save_day(self.date, self.buffer.get_text(*self.buffer.get_bounds(), True))

    def format(self):
        self.buffer.remove_all_tags(*self.buffer.get_bounds())
        code = False
        for i in range(self.buffer.get_line_count()):
            start = self.buffer.get_iter_at_line(i)[1]
            end = start.copy()
            end.forward_to_line_end()
            text = self.buffer.get_text(start, end, True)
            if text == '```':
                code ^= True
                self.buffer.apply_tag(self.tags['code'], start, end)
            elif code:
                self.buffer.apply_tag(self.tags['code'], start, end)
            elif text.startswith('# '):
                self.buffer.apply_tag(self.tags['title'], start, end)
            elif text == '====================':
                self.buffer.apply_tag(self.tags['rule'], start, end)
            elif text.startswith('* '):
                bullet_end = start.copy()
                bullet_end.forward_char()
                self.buffer.apply_tag(self.tags['bullet'], start, bullet_end)

    def insert_line(self):
        self.buffer.insert_at_cursor('\n====================\n')

    def insert_header(self):
        iter = self.buffer.get_iter_at_offset(self.buffer.get_property('cursor-position'))
        iter.set_line_offset(0)
        iter2 = iter.copy()
        iter2.set_line_offset(2)
        if self.buffer.get_text(iter, iter2, True) == '# ':
            self.buffer.delete(iter, iter2)
        else:
            self.buffer.insert(iter, '# ')

    def insert_code(self):
        self.buffer.begin_user_action()
        bounds = self.buffer.get_selection_bounds()
        if bounds:
            self.buffer.insert(bounds[0], '```\n' if bounds[0].starts_line() else '\n```\n')
            # Insertion invalidated the iters, so a new one is needed
            bounds = self.buffer.get_selection_bounds()
            self.buffer.insert(bounds[1], '\n```' if bounds[1].ends_line() else '\n```\n')
        else:
            self.buffer.insert_at_cursor('\n```\n')
            offset = self.buffer.get_property('cursor-position')
            self.buffer.insert_at_cursor('\n```\n')
            self.buffer.place_cursor(self.buffer.get_iter_at_offset(offset))
        self.format()
        self.buffer.end_user_action()


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
    alt_gui = Gtk.Template.Child('alt_gui')

    def __init__(self, parent):
        super().__init__()
        self.set_modal(True)
        self.set_transient_for(parent)
        self.parent = parent
        self.date_format.set_text(self.parent.settings.get('date_format'))
        self.alt_gui.set_active(self.parent.settings.get('alt_gui'))
        self.connect('close-request', self.on_close_request)
        self.present()

    def on_close_request(self, *_):
        try:
            self.save_changes()
        except Exception:
            traceback.print_exc()
            return True

    def save_changes(self):
        self.parent.settings.set(
            date_format=self.date_format.get_text(),
            alt_gui=self.alt_gui.get_active(),
        )


if __name__ == '__main__':
    settings = Settings(Path(GLib.get_user_config_dir()) / APP_ID / 'settings.json')
    main()
