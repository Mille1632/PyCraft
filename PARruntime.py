#!/usr/bin/env python3
import os
import sys
import zipfile
import json
import tempfile
import subprocess
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QPushButton,
    QFileDialog, QLabel, QMessageBox, QProgressDialog
)
from PyQt5.QtCore import QThread, pyqtSignal


def extract_par(par_path):
    temp_dir = tempfile.mkdtemp(prefix="par_")
    with zipfile.ZipFile(par_path, "r") as z:
        z.extractall(temp_dir)
    return temp_dir


def install_dependencies(temp_dir, config):
    reqs = os.path.join(temp_dir, "requirements.txt")
    apt_file = os.path.join(temp_dir, "apt.txt")

    if config.get("sudo", False):
        confirm = input("This script requires sudo privileges. Proceed? [y/N]: ")
        if confirm.lower() != "y":
            print("Aborted by user.")
            sys.exit(1)

    if os.path.exists(apt_file):
        subprocess.run(["sudo", "apt", "install", "-y", *open(apt_file).read().splitlines()])

    if os.path.exists(reqs):
        try:
            subprocess.run([sys.executable, "-m", "pip", "install", "--break-system-packages", "-r", reqs], check=True)
        except subprocess.CalledProcessError:
            venv_dir = os.path.join(temp_dir, "venv")
            subprocess.run([sys.executable, "-m", "venv", venv_dir], check=True)
            pip = os.path.join(venv_dir, "bin", "pip")
            python = os.path.join(venv_dir, "bin", "python")
            subprocess.run([pip, "install", "-r", reqs], check=True)
            return python

    return sys.executable


def run_par_logic(par_path):
    if not os.path.isfile(par_path):
        raise FileNotFoundError("PAR file not found.")

    temp_dir = extract_par(par_path)

    config_path = os.path.join(temp_dir, "par.json")
    config = {}
    if os.path.exists(config_path):
        with open(config_path) as f:
            config = json.load(f)

    python_exec = install_dependencies(temp_dir, config)

    entry = config.get("entry_point", "main.py")
    entry_script = os.path.join(temp_dir, entry)

    if not os.path.isfile(entry_script):
        raise FileNotFoundError(f"Entry script not found: {entry}")

    subprocess.run([python_exec, entry_script], cwd=temp_dir)


class RunParWorker(QThread):
    finished = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, par_path):
        super().__init__()
        self.par_path = par_path

    def run(self):
        try:
            run_par_logic(self.par_path)
            self.finished.emit()
        except Exception as e:
            self.error.emit(str(e))


class PARRunnerApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PAR runtime")
        self.setGeometry(200, 200, 400, 200)

        self.par_label = QLabel("Select a .par file to run", self)
        self.select_par_button = QPushButton("Select .par File", self)
        self.select_par_button.clicked.connect(self.select_par_file)

        self.run_button = QPushButton("Run .par File", self)
        self.run_button.clicked.connect(self.run_selected_par)

        layout = QVBoxLayout()
        layout.addWidget(self.par_label)
        layout.addWidget(self.select_par_button)
        layout.addWidget(self.run_button)
        self.setLayout(layout)

        self.selected_par_path = None
        self.worker = None

    def select_par_file(self):
        file, _ = QFileDialog.getOpenFileName(self, "Select .par file", "", "PAR Files (*.par)")
        if file:
            self.selected_par_path = file
            self.par_label.setText(f"Selected: {os.path.basename(file)}")

    def run_selected_par(self):
        if not self.selected_par_path:
            QMessageBox.warning(self, "No file selected", "Please select a .par file first.")
            return

        self.run_button.setEnabled(False)
        self.worker = RunParWorker(self.selected_par_path)
        self.worker.finished.connect(self.on_finished)
        self.worker.error.connect(self.on_error)
        self.worker.start()

    def on_finished(self):
        QMessageBox.information(self, "Done", "PAR file executed successfully.")
        self.run_button.setEnabled(True)

    def on_error(self, message):
        QMessageBox.critical(self, "Error", f"An error occurred:\n\n{message}")
        self.run_button.setEnabled(True)


def main():
    app = QApplication(sys.argv)
    window = PARRunnerApp()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
