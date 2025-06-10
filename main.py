import sys
import psutil
import subprocess
from PyQt6.QtWidgets import QApplication, QLabel, QWidget, QVBoxLayout, QHBoxLayout, QSizePolicy
from PyQt6.QtCore import Qt, QTimer, QRectF
from PyQt6.QtGui import QPainter, QPainterPath, QColor

def get_ram_info():
    try:
        if sys.platform.startswith("win"):
            cmd = ['powershell', '-Command', "Get-CimInstance -ClassName Win32_PhysicalMemory | Select-Object Capacity, Speed"]
            output = subprocess.run(cmd, capture_output=True, text=True).stdout.split("\n")
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
    except Exception as e:
        return f"RAM Info Unavailable ({str(e)})"
    return "RAM Info Unavailable"

class OverflowMonitor(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMinimumSize(400, 160)
        self.resize(400, 160)

        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)
        self.setLayout(main_layout)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(15)

        ram_label = QLabel(get_ram_info())
        ram_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        ram_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ram_label.setStyleSheet("QLabel { font-size: 16px; color: #ffffff; padding: 5px 0; }")
        header.addWidget(ram_label)

        self.close_btn = QLabel("✕")
        self.close_btn.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.close_btn.setStyleSheet("""
            QLabel {
                font-size: 16px;
                color: #aaaaaa;
                font-weight: bold;
                padding: 2px 8px;
                margin: 0;
                min-width: 30px;
                min-height: 24px;
                qproperty-alignment: 'AlignCenter';
            }
            QLabel:hover {
                color: #ffffff;
                background-color: #ff5555;
                border-radius: 12px;
            }
        """)
        self.close_btn.mousePressEvent = self.close_app
        header.addWidget(self.close_btn)

        main_layout.addLayout(header)

        self.label = QLabel("Swap Usage: 0.00% of 0.00 GB")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setStyleSheet("QLabel { font-size: 16px; color: #ffffff; font-weight: 500; padding: 10px 0; }")
        main_layout.addWidget(self.label)

        self.setStyleSheet("QWidget { background-color: rgba(30, 30, 30, 230); border: 1px solid #444; border-radius: 15px; }")

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_swap_usage)
        self.timer.start(1000)
        self.update_swap_usage()
        self.drag_position = None

    def update_swap_usage(self):
        try:
            swap = psutil.swap_memory()
            percentage = swap.percent
            total_gb = swap.total / (1024**3)
            used_gb = swap.used / (1024**3)
            self.label.setText(f"Swap Usage: {used_gb:.2f} GB / {total_gb:.2f} GB ({percentage:.1f}%)")
        except Exception as e:
            print(f"Error updating swap usage: {e}")

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton and self.drag_position:
            self.move(event.globalPosition().toPoint() - self.drag_position)
            event.accept()

    def close_app(self, event=None):
        if self.timer.isActive():
            self.timer.stop()
        self.close()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect().adjusted(1, 1, -1, -1)), 15, 15)
        painter.fillPath(path, QColor(30, 30, 30, 230))
        pen = painter.pen()
        pen.setColor(QColor(60, 60, 60, 150))
        painter.setPen(pen)
        painter.drawPath(path)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    window = OverflowMonitor()
    window.show()
    sys.exit(app.exec())
