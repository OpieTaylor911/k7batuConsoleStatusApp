import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Pango

class SidebarNavigation(Gtk.Box):
    """Custom sidebar navigation with stack switching."""
    
    def __init__(self, stack=None):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        
        # Sidebar container
        self.sidebar = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.sidebar.set_size_request(180, -1)
        self.sidebar.get_style_context().add_class('sidebar')
        
        self.stack = stack
        self.pages = []  # Track pages for plugin integration
        
    def add_page(self, page_id: str, label: str, icon: str = None):
        """Add a navigation item for a stack page."""
        button = Gtk.Button(label=label if not icon else f'{icon}  {label}')
        button.set_halign(Gtk.Align.START)
        button.get_style_context().add_class('sidebar-item')
        
        # Store page info for plugin integration
        page_info = {'id': page_id, 'label': label, 'icon': icon, 'widget': None}
        self.pages.append(page_info)
        
        if self.stack:
            button.connect('clicked', lambda btn: self.stack.set_visible_child_name(page_id))
        
        self.sidebar.pack_start(button, False, False, 0)
        return button
    
    def add_plugin_page(self, plugin):
        """Add a page from a plugin."""
        page_info = {
            'id': plugin.get_id(),
            'label': plugin.get_name(),
            'icon': plugin.get_icon(),
            'widget': None
        }
        self.pages.append(page_info)
        
        button = Gtk.Button(label=plugin.get_name())
        button.set_halign(Gtk.Align.START)
        button.get_style_context().add_class('sidebar-item')
        
        if self.stack:
            button.connect('clicked', lambda btn: self.stack.set_visible_child_name(plugin.get_id()))
        
        self.sidebar.pack_start(button, False, False, 0)
        return button
    
    def get_sidebar(self):
        return self.sidebar


class MetricCard(Gtk.Box):
    """Compact metric display card."""
    
    def __init__(self, title=None, value="", subtitle=None, status="normal"):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.set_hexpand(True)
        self.get_style_context().add_class('dashboard-card')
        
        # Title
        if title:
            title_label = Gtk.Label(label=title.upper())
            title_label.get_style_context().add_class('section-title')
            self.pack_start(title_label, False, False, 0)
        
        # Value
        value_label = Gtk.Label(label=value)
        value_label.get_style_context().add_class('metric-value')
        self.pack_start(value_label, False, False, 0)
        
        # Status indicator
        status_dot = Gtk.EventBox()
        status_dot.set_size_request(12, 12)
        dot_ctx = status_dot.get_style_context()
        
        if status == "good":
            dot_ctx.add_class('status-good')
        elif status == "warning":
            dot_ctx.add_class('status-warning')
        elif status == "error":
            dot_ctx.add_class('status-error')
        else:
            dot_ctx.add_class('status-unknown')
        
        self.pack_start(status_dot, False, False, 0)
        
        # Subtitle
        if subtitle:
            sub_label = Gtk.Label(label=subtitle)
            sub_label.get_style_context().add_class('metric-subtitle')
            self.pack_start(sub_label, False, False, 0)


class StatusCard(Gtk.Box):
    """Status information card with icon and text."""
    
    def __init__(self, title="", status=None, icon="C"):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.set_hexpand(True)
        self.get_style_context().add_class('dashboard-card')
        
        # Title with icon
        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        
        icon_label = Gtk.Label(label=icon)
        icon_label.get_style_context().add_class('status-dot')
        hbox.pack_start(icon_label, False, False, 0)
        
        title_label = Gtk.Label(label=title)
        title_label.set_halign(Gtk.Align.START)
        hbox.pack_start(title_label, True, True, 0)
        
        self.pack_start(hbox, False, False, 0)
        
        # Status text
        if status:
            status_label = Gtk.Label(label=status)
            status_label.get_style_context().add_class('status-text')
            self.pack_start(status_label, False, False, 0)


class DeviceRow(Gtk.Box):
    """Compact device row with status dot."""
    
    def __init__(self, name="", value=None, status="unknown"):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.set_hexpand(True)
        
        # Status dot
        status_dot = Gtk.EventBox()
        status_dot.set_size_request(10, 10)
        dot_ctx = status_dot.get_style_context()
        
        if status == "online":
            dot_ctx.add_class('status-good')
        elif status == "warning":
            dot_ctx.add_class('status-warning')
        elif status == "error":
            dot_ctx.add_class('status-error')
        else:
            dot_ctx.add_class('status-unknown')
        
        self.pack_start(status_dot, False, False, 0)
        
        # Name
        name_label = Gtk.Label(label=name)
        name_label.set_halign(Gtk.Align.START)
        name_label.set_hexpand(True)
        self.pack_start(name_label, True, True, 0)
        
        # Value
        if value:
            value_label = Gtk.Label(label=value)
            value_label.get_style_context().add_class('device-value')
            self.pack_start(value_label, False, False, 0)


class SectionHeader(Gtk.Box):
    """Section divider header."""
    
    def __init__(self, title=""):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        self.get_style_context().add_class('section-title')
        
        label = Gtk.Label(label=title.upper())
        label.set_halign(Gtk.Align.START)
        self.pack_start(label, False, False, 0)


class ActionButton(Gtk.Button):
    """Compact action button with optional icon."""
    
    def __init__(self, label=None, icon=None, subtitle=None):
        super().__init__()
        self.get_style_context().add_class('action-button')
        
        # Create content box
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        
        if icon:
            icon_label = Gtk.Label(label=icon)
            icon_label.set_halign(Gtk.Align.CENTER)
            content.pack_start(icon_label, False, False, 0)
        
        if label:
            label_widget = Gtk.Label(label=label)
            label_widget.get_style_context().add_class('action-button-title')
            label_widget.set_halign(Gtk.Align.CENTER)
            content.pack_start(label_widget, False, False, 0)
        
        if subtitle:
            sub_label = Gtk.Label(label=subtitle)
            sub_label.get_style_context().add_class('action-button-subtitle')
            sub_label.set_halign(Gtk.Align.CENTER)
            content.pack_start(sub_label, False, False, 0)
        
        self.add(content)


class DashboardPage(Gtk.Box):
    """Main dashboard with metrics and status cards."""
    
    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.set_hexpand(True)
        self.set_vexpand(True)
        
        # SYSTEM section - metric cards
        system_header = SectionHeader('System')
        self.pack_start(system_header, False, False, 0)
        
        system_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        
        cpu_card = MetricCard(
            title='CPU',
            value='18%',
            subtitle='4 cores',
            status='good'
        )
        mem_card = MetricCard(
            title='Memory',
            value='42%',
            subtitle='3.4GB / 8GB',
            status='good'
        )
        temp_card = MetricCard(
            title='Temp',
            value='47C',
            subtitle='Normal operation',
            status='good'
        )
        
        system_row.pack_start(cpu_card, True, True, 0)
        system_row.pack_start(mem_card, True, True, 0)
        system_row.pack_start(temp_card, True, True, 0)
        self.pack_start(system_row, False, False, 0)
        
        # HARDWARE section - status card
        hardware_header = SectionHeader('Hardware')
        self.pack_start(hardware_header, False, False, 0)
        
        hardware_card = StatusCard(
            title='HackerGadgets AIO Board v1.41',
            status='ClockworkPi uConsole / CM5',
            icon='C'
        )
        self.pack_start(hardware_card, False, False, 0)
        
        # Device rows
        devices_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        devices_box.set_margin_left(12)
        devices_box.set_margin_right(12)
        
        device_rows = [
            ('GPS', '/dev/ttyAMA0', 'online'),
            ('RTL-SDR', 'RTL2838', 'online'),
            ('WiFi', 'AC1200', 'online'),
            ('RTC', 'Detected', 'active'),
            ('ESP32', 'Detected', 'active'),
        ]
        
        for name, value, status in device_rows:
            devices_box.pack_start(DeviceRow(name, value, status), False, False, 0)
        
        self.pack_start(devices_box, False, False, 0)
        
        # QUICK ACTIONS section
        actions_header = SectionHeader('Quick Actions')
        self.pack_start(actions_header, False, False, 0)
        
        actions_grid = Gtk.Grid()
        actions_grid.set_row_spacing(8)
        actions_grid.set_column_spacing(8)
        actions_grid.set_margin_top(8)
        
        # Action buttons
        actions = [
            ('SDR++', 'S'),
            ('GPS', 'G'),
            ('ADS-B', 'A'),
            ('Gpredict', 'P'),
            ('GNU Radio', 'N'),
            ('Cockpit', 'C'),
            ('AIO Control', 'X'),
        ]
        
        row = 0
        col = 0
        for label, icon in actions:
            btn = ActionButton(label=label, icon=icon)
            btn.set_hexpand(True)
            actions_grid.attach(btn, col, row, 1, 1)
            
            col += 1
            if col > 2:
                col = 0
                row += 1
        
        self.pack_start(actions_grid, False, False, 0)
