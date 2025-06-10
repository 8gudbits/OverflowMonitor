import sys
import psutil
import subprocess
import json
import os
from PyQt6.QtWidgets import (
    QApplication, QLabel,
    QWidget, QVBoxLayout, 
    QMenu
)
from PyQt6.QtCore import Qt, QTimer, QRectF, QPoint
from PyQt6.QtGui import (
    QPainter, QPainterPath,
    QColor, QPalette, 
    QAction, QIcon
)


def get_config_path():
    if getattr(sys, 'frozen', False):  # If app running as executable
        base_dir = os.path.dirname(sys.executable)  # Use executable directory
    else:
        base_dir = os.path.dirname(__file__)  # Use script directory

    return os.path.join(base_dir, "config.json")


CONFIG_FILE = get_config_path()
CONFIG_KEY = "OverflowMonitor"


def get_ram_info():
    try:
        if sys.platform.startswith("win"):
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE  # Ensures the PS window remains hidden

            cmd = ['powershell', '-Command', "Get-CimInstance -ClassName Win32_PhysicalMemory | Select-Object Capacity, Speed"]
            output = subprocess.run(cmd, capture_output=True, text=True, startupinfo=startupinfo).stdout.split("\n")
            
            capacities, speeds = [], []
            for line in output[3:]:
                parts = line.strip().split()
                if len(parts) >= 2:
                    capacities.append(int(parts[0]) / (1024**3))
                    speeds.append(parts[1] + "MHz")
            if capacities and speeds:
                return f"{sum(capacities):.1f} GB {speeds[0]} RAM"

        elif sys.platform.startswith("linux"):
            cmd = ['sudo', 'dmidecode', '--type', '17']
            output = subprocess.run(cmd, capture_output=True, text=True).stdout
            speed = "Unknown"
            for line in output.split("\n"):
                if "Speed:" in line:
                    speed = line.split(":")[1].strip()
            return f"{psutil.virtual_memory().total / (1024**3):.1f} GB {speed} RAM"

        elif sys.platform.startswith("darwin"):
            cmd = ['sysctl', 'hw.memsize']
            output = subprocess.run(cmd, capture_output=True, text=True).stdout.strip().split(":")[1].strip()
            return f"{int(output) / (1024**3):.1f} GB Unknown Speed"

    except Exception:
        return "RAM Info Unavailable"

    return "RAM Info Unavailable"


def load_config():
    default_config = {
        "always_on_top": True,
        "draggable": True,
        "track_ram_usage": False,
        "window_position": {"x": 100, "y": 100}
    }

    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r') as f:
                all_config = json.load(f)
                if CONFIG_KEY in all_config:
                    loaded_config = all_config[CONFIG_KEY]
                    # Validate loaded config
                    for key in default_config:
                        if key not in loaded_config:
                            loaded_config[key] = default_config[key]
                    return loaded_config
    except Exception:
        pass
    
    return default_config

def save_config(key, value):
    try:
        # Read existing config
        all_config = {}
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r') as f:
                all_config = json.load(f)
        
        # Update only needed part of the config
        if CONFIG_KEY not in all_config:
            all_config[CONFIG_KEY] = {}
        
        # Update specific value if key contains dot notation
        keys = key.split('.')
        current = all_config[CONFIG_KEY]
        for k in keys[:-1]:
            if k not in current:
                current[k] = {}
            current = current[k]
        current[keys[-1]] = value
        
        # Write back to file
        with open(CONFIG_FILE, 'w') as f:
            json.dump(all_config, f, indent=4)
    except Exception:
        pass

def update_config():
    """Update config file with current window position"""
    if hasattr(QApplication.instance(), 'activeWindow'):
        window = QApplication.instance().activeWindow()
        if window:
            pos = window.pos()
            save_config("window_position.x", pos.x())
            save_config("window_position.y", pos.y())

class OverflowMonitor(QWidget):
    def __init__(self):
        super().__init__()
        self.config = load_config()
        
        self.always_on_top = self.config["always_on_top"]
        self.draggable = self.config["draggable"]
        self.track_ram_usage = self.config["track_ram_usage"]
        self.ram_info = get_ram_info()
        
        self.init_ui()
        self.init_context_menu()
        
        # Set initial position from config
        pos = self.config["window_position"]
        self.move(QPoint(pos["x"], pos["y"]))

        # Position tracking timer
        self.pos_timer = QTimer()
        self.pos_timer.timeout.connect(update_config)
        self.pos_timer.start(1000) # Update position every second

    def init_ui(self):
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool | 
            (Qt.WindowType.WindowStaysOnTopHint if self.always_on_top else Qt.WindowType.Widget))
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMinimumSize(400, 120)
        self.resize(400, 120)

        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(10)
        self.setLayout(main_layout)

        self.ram_label = QLabel(self.ram_info if not self.track_ram_usage else "RAM Usage: 0.00 GB / 0.00 GB (0.0%)")
        self.ram_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.ram_label.setStyleSheet("""
            QLabel {
                font-size: 16px;
                color: #ffffff;
                padding: 5px 0;
            }
        """)
        main_layout.addWidget(self.ram_label)

        self.swap_label = QLabel("Swap Usage: 0.00% of 0.00 GB")
        self.swap_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.swap_label.setStyleSheet("""
            QLabel {
                font-size: 16px;
                color: #ffffff;
                font-weight: 500;
                padding: 5px 0;
            }
        """)
        main_layout.addWidget(self.swap_label)

        self.setStyleSheet("""
            QWidget {
                background-color: rgba(45, 45, 45, 180);
                border: 1px solid rgba(255, 255, 255, 20);
                border-radius: 8px;
            }
        """)

        self.usage_timer = QTimer()
        self.usage_timer.timeout.connect(self.update_usage)
        self.usage_timer.start(1000)
        self.update_usage()
        self.drag_position = None

    def init_context_menu(self):
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)

    def show_context_menu(self, pos):
        menu = QMenu(self)
        
        always_top_action = QAction("Always on Top", self)
        always_top_action.setCheckable(True)
        always_top_action.setChecked(self.always_on_top)
        always_top_action.triggered.connect(self.toggle_always_on_top)
        menu.addAction(always_top_action)
        
        draggable_action = QAction("Mouse Draggable", self)
        draggable_action.setCheckable(True)
        draggable_action.setChecked(self.draggable)
        draggable_action.triggered.connect(self.toggle_draggable)
        menu.addAction(draggable_action)
        
        ram_tracking_action = QAction("RAM Usage Tracking", self)
        ram_tracking_action.setCheckable(True)
        ram_tracking_action.setChecked(self.track_ram_usage)
        ram_tracking_action.triggered.connect(self.toggle_ram_tracking)
        menu.addAction(ram_tracking_action)
        
        close_action = QAction("Close Widget", self)
        close_action.triggered.connect(self.close)
        menu.addAction(close_action)
        
        menu.exec(self.mapToGlobal(pos))

    def toggle_always_on_top(self, checked):
        self.always_on_top = checked
        save_config("always_on_top", checked)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | 
            (Qt.WindowType.WindowStaysOnTopHint if checked else Qt.WindowType.Widget))
        self.show()

    def toggle_draggable(self, checked):
        self.draggable = checked
        save_config("draggable", checked)

    def toggle_ram_tracking(self, checked):
        self.track_ram_usage = checked
        save_config("track_ram_usage", checked)
        if not checked:
            self.ram_label.setText(self.ram_info)

    def update_usage(self):
        try:
            swap = psutil.swap_memory()
            percentage = swap.percent
            total_gb = swap.total / (1024**3)
            used_gb = swap.used / (1024**3)
            self.swap_label.setText(f"Swap Usage: {used_gb:.2f} GB / {total_gb:.2f} GB ({percentage:.1f}%)")
        except Exception:
            pass
        
        if self.track_ram_usage:
            try:
                ram = psutil.virtual_memory()
                percentage = ram.percent
                total_gb = ram.total / (1024**3)
                used_gb = ram.used / (1024**3)
                self.ram_label.setText(f"RAM Usage: {used_gb:.2f} GB / {total_gb:.2f} GB ({percentage:.1f}%)")
            except Exception:
                pass

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.draggable:
            self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton and self.drag_position and self.draggable:
            self.move(event.globalPosition().toPoint() - self.drag_position)
            event.accept()

    def closeEvent(self, event):
        # Save final position
        save_config("window_position.x", self.pos().x())
        save_config("window_position.y", self.pos().y())
        self.pos_timer.stop()
        event.accept()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect().adjusted(1, 1, -1, -1)), 8, 8)
        painter.fillPath(path, QColor(45, 45, 45, 180))
        pen = painter.pen()
        pen.setColor(QColor(255, 255, 255, 20))
        pen.setWidth(1)
        painter.setPen(pen)
        painter.drawPath(path)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    
    palette = app.palette()
    palette.setColor(QPalette.ColorRole.Window, QColor(30, 30, 30))
    palette.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.white)
    app.setPalette(palette)
    
    window = OverflowMonitor()
    window.show()
    sys.exit(app.exec())

