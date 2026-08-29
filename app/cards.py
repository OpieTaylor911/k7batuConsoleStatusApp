import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Pango

class MetricCard(Gtk.Box):
    def __init__(self, label: str, value: str, subtitle: str = None, icon: str = None):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.set_hexpand(True)
        self.get_style_context().add_class('metric-card')
        
        content = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        
        if icon:
            icon_label = Gtk.Label(label=icon)
            icon_label.set_margin_end(8)
            content.pack_start(icon_label, False, False, 0)
        
        info_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        self.value_label = Gtk.Label(label=value)
        self.value_label.get_style_context().add_class('metric-value')
        self.value_label.set_halign(Gtk.Align.START)
        info_box.pack_start(self.value_label, False, False, 0)
        
        if label:
            self.label_label = Gtk.Label(label=label)
            self.label_label.get_style_context().add_class('metric-label')
            self.label_label.set_halign(Gtk.Align.START)
            info_box.pack_start(self.label_label, False, False, 0)
        
        content.pack_start(info_box, True, True, 0)
        self.pack_start(content, True, True, 0)
        
        if subtitle:
            self.subtitle_label = Gtk.Label(label=subtitle)
            self.subtitle_label.set_halign(Gtk.Align.START)
            self.subtitle_label.modify_font(Pango.FontDescription.from_string('8pt'))
            self.subtitle_label.set_opacity(0.7)
            self.pack_start(self.subtitle_label, False, False, 0)
    
    def set_value(self, value: str):
        self.value_label.set_text(value)

class StatusCard(Gtk.Box):
    def __init__(self, title: str, status: str = None, icon: str = None):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.set_hexpand(True)
        self.get_style_context().add_class('status-card')
        
        title_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        
        if icon:
            icon_label = Gtk.Label(label=icon)
            icon_label.get_style_context().add_class('status-icon')
            title_row.pack_start(icon_label, False, False, 0)
        
        self.title_label = Gtk.Label(label=title)
        self.title_label.set_halign(Gtk.Align.START)
        self.title_label.modify_font(Pango.FontDescription.from_string('10pt bold'))
        title_row.pack_start(self.title_label, True, True, 0)
        self.pack_start(title_row, False, False, 0)
        
        if status:
            self.status_label = Gtk.Label(label=status)
            self.status_label.set_halign(Gtk.Align.START)
            self.status_label.modify_font(Pango.FontDescription.from_string('9pt'))
            self.status_label.set_opacity(0.8)
            self.pack_start(self.status_label, False, False, 0)

class DeviceRow(Gtk.Box):
    def __init__(self, name: str, value: str = None, status: str = None):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        self.set_hexpand(True)
        self.get_style_context().add_class('device-row')
        
        self.name_label = Gtk.Label(label=name)
        self.name_label.get_style_context().add_class('device-name')
        self.name_label.set_halign(Gtk.Align.START)
        self.pack_start(self.name_label, False, False, 0)
        
        if value is not None:
            self.value_label = Gtk.Label(label=value)
            self.value_label.get_style_context().add_class('device-value')
            self.value_label.set_halign(Gtk.Align.END)
            self.pack_end(self.value_label, False, False, 0)

class SectionHeader(Gtk.Box):
    def __init__(self, title: str):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        self.get_style_context().add_class('section-header')
        
        label = Gtk.Label(label=title)
        label.set_halign(Gtk.Align.START)
        self.pack_start(label, True, True, 0)

class ActionButton(Gtk.Button):
    def __init__(self, label: str = None, icon: str = None, callback=None):
        super().__init__()
        self.get_style_context().add_class('actionbutton')
        
        content_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        
        if icon:
            icon_label = Gtk.Label(label=icon)
            content_box.pack_start(icon_label, False, False, 0)
        
        if label:
            text_label = Gtk.Label(label=label)
            content_box.pack_start(text_label, True, True, 0)
        
        self.add(content_box)
        
        if callback:
            self.connect('clicked', callback)
