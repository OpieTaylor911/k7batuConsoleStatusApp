import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk

class SidebarNavigation(Gtk.Box):
    \"\"\"Custom sidebar navigation with stack switching.\"\"\"
    
    def __init__(self, stack=None):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        
        # Sidebar container
        self.sidebar = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.sidebar.set_size_request(180, -1)
        self.sidebar.get_style_context().add_class('sidebar')
        
        self.stack = stack
        
    def add_page(self, page_id: str, label: str, icon: str = None):
        \"\"\"Add a navigation item for a stack page.\"\"\"
        button = Gtk.Button(label=label if not icon else f'{icon}  {label}')
        button.set_halign(Gtk.Align.START)
        button.get_style_context().add_class('sidebar-item')
        
        if self.stack:
            button.connect('clicked', lambda btn: self.stack.set_visible_child_name(page_id))
        
        self.sidebar.pack_start(button, False, False, 0)
        return button
    
    def get_sidebar(self):
        return self.sidebar


class DashboardPage(Gtk.Box):
    \"\"\"Main dashboard with metrics and status cards.\"\"\"
    
    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.set_hexpand(True)
        self.set_vexpand(True)
        
        # Top row: CPU and Memory metrics
        top_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        
        cpu_card = MetricCard(label='CPU Load', value='24%', subtitle='Average over 60s')
        memory_card = MetricCard(label='Memory', value='2.3/8 GB', subtitle='Available: 5.7GB')
        
        top_row.pack_start(cpu_card, True, True, 0)
        top_row.pack_start(memory_card, True, True, 0)
        self.pack_start(top_row, False, False, 0)
        
        # Status section
        status_header = SectionHeader('System Status')
        self.pack_start(status_header, False, False, 0)
        
        wifi_status = StatusCard(title='Wi-Fi', status='Connected - wlan0', icon='📶')
        gps_status = StatusCard(title='GPS', status='3D Fix - 12 satellites', icon='📍')
        
        self.pack_start(wifi_status, False, False, 0)
        self.pack_start(gps_status, False, False, 0)
        
        # Device list
        device_header = SectionHeader('Connected Devices')
        self.pack_start(device_header, False, False, 0)
        
        devices_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        
        devices_box.pack_start(DeviceRow('USB Storage', '128GB'), False, False, 0)
        devices_box.pack_start(DeviceRow('GPS Module', 'u-blox 8'), False, False, 0)
        devices_box.pack_start(DeviceRow('SDR Transceiver', 'RTL-SDR v3'), False, False, 0)
        
        self.pack_start(devices_box, False, False, 0)
