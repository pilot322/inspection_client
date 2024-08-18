import os
from PyQt5.QtWidgets import (QApplication, QMainWindow, QLabel, QVBoxLayout, QWidget, QPushButton, QComboBox, 
                             QFileDialog, QTableWidget, QTableWidgetItem, QCheckBox, QAbstractItemView)
from PyQt5.QtCore import Qt, QUrl
from PyQt5.QtGui import QDragEnterEvent, QDropEvent, QColor, QMouseEvent
from resources.database import get_folder_state

class SelectionTable(QTableWidget):
    def __init__(self, parent_page):
        super().__init__(0, 3)
        self.setHorizontalHeaderLabels(["Folder Name", "C", "I"])
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.parent_page = parent_page

        # Set column widths
        self.setColumnWidth(0, 600)
        self.setColumnWidth(1, 30)  # Fixed width for Checkbox 1
        self.setColumnWidth(2, 30)  # Fixed width for Checkbox 2

        # Set QSS for the table
        self.setStyleSheet("""
            QTableWidget::item {
                padding: 5px;
            }
            QTableWidget QHeaderView::section {
                background-color: #f0f0f0;
                padding: 4px;
                border: 1px solid #d3d3d3;
            }
        """)

    def addFolder(self, folder):
        item = QTableWidgetItem(folder)
        state = get_folder_state(os.path.basename(folder))

        if state == 'processed':
            item.setForeground(Qt.red)
        elif state == 'inspected':
            item.setForeground(QColor("#008080"))
        elif state == 'opened':
            item.setForeground(Qt.purple)
        elif state == 'passed':
            item.setForeground(Qt.green)
        else:
            item.setForeground(Qt.gray)
        
        cut_checkbox = QCheckBox()
        inspect_checkbox = QCheckBox()

        checkbox_style = lambda color : f"""
        QCheckBox::indicator {{
            width: 20px;
            height: 20px;
        }}
        QCheckBox::indicator:unchecked {{
            background-color: lightgray;
            border: 2px solid {color};
        }}
        QCheckBox::indicator:checked {{
            background-color: {color};
            border: 2px solid {color};
        }}
        """
        cut_checkbox.setStyleSheet(checkbox_style('red'))
        inspect_checkbox.setStyleSheet(checkbox_style('#008080'))

        # Connect stateChanged signal to custom slot
        cut_checkbox.stateChanged.connect(lambda state, cb=cut_checkbox: self.syncCheckboxes(state, cb, 1))
        inspect_checkbox.stateChanged.connect(lambda state, cb=inspect_checkbox: self.syncCheckboxes(state, cb, 2))

        index = self.rowCount()
        self.insertRow(index)

        self.setItem(index, 0, item)
        self.setCellWidget(index, 1, cut_checkbox)
        self.setCellWidget(index, 2, inspect_checkbox)

        self.sortItems(0, Qt.AscendingOrder)

    def syncCheckboxes(self, state, origin_checkbox, column):
        for idx in self.selectionModel().selectedRows():
            row = idx.row()
            checkbox = self.cellWidget(row, column)
            if checkbox is not origin_checkbox:
                checkbox.setChecked(state == Qt.Checked)
