import sys
import os
import re  # ДОБАВИТЬ
from datetime import datetime
from PyQt6 import QtCore
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QTextEdit, QVBoxLayout, QWidget,
    QToolBar, QStatusBar, QMessageBox, QFileDialog,
    QSplitter, QTableWidget, QTableWidgetItem, QHBoxLayout,
    QComboBox, QPushButton, QLabel, QGroupBox, QHeaderView,
    QStyle, QLineEdit  # ДОБАВИТЬ QLineEdit
)
from PyQt6.QtGui import QAction, QCloseEvent, QTextCursor, QFont, QKeySequence, QTextCharFormat, QColor
from PyQt6.QtCore import Qt
from typing import Optional

from scanner import analyze_text, TokenType
from parser import Parser, ParserError



class TextEditor(QMainWindow):
    def __init__(self):
        super().__init__()
        self.current_file = None
        self.is_modified = False
        self._updating = False  # ДОБАВИТЬ флаг защиты от рекурсии
        
        # Инициализируем атрибуты для таблиц
        self.output_table = None
        
        self.init_ui()
        self.connect_signals()

    def connect_signals(self):
        """Подключение сигналов"""
        self.editor.textChanged.connect(self.on_text_changed)

    def init_ui(self):
        """Инициализация интерфейса"""
        self.setWindowTitle("Новый документ - Текстовый редактор")
        self.setGeometry(100, 100, 1200, 800)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget)

        # Создаем вертикальный сплиттер
        main_splitter = QSplitter(Qt.Orientation.Vertical)
        
        # Верхняя часть: редактор и панель поиска
        top_widget = QWidget()
        top_layout = QVBoxLayout(top_widget)
        top_layout.setContentsMargins(0, 0, 0, 0)
        
        # Редактор текста
        self.editor = QTextEdit()
        self.editor.setFont(QFont("Courier New", 11))
        top_layout.addWidget(self.editor)
        self.parse_button = QPushButton("Синтаксический анализ")

        self.parse_button.setMinimumHeight(40)

        self.parse_button.clicked.connect(self.run_parser)

        top_layout.addWidget(self.parse_button)
        main_splitter.addWidget(top_widget)
        
        
        # Создаем третий виджет для таблицы вывода парсера
        bottom_widget = QWidget()
        bottom_layout = QVBoxLayout(bottom_widget)
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        
        # Таблица для вывода результатов парсинга
        self.output_table = QTableWidget()

        self.output_table.horizontalHeader().setSectionResizeMode(
            0,
            QHeaderView.ResizeMode.ResizeToContents
        )

        self.output_table.horizontalHeader().setSectionResizeMode(
            1,
            QHeaderView.ResizeMode.ResizeToContents
        )

        self.output_table.horizontalHeader().setSectionResizeMode(
            2,
            QHeaderView.ResizeMode.Stretch
        )

        self.output_table.setColumnCount(3)

        self.output_table.setHorizontalHeaderLabels([
            "Неверный фрагмент",
            "Местоположение",
            "Описание ошибки"
        ])
        self.output_table.setAlternatingRowColors(True)
        self.output_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.output_table.cellClicked.connect(self.on_error_clicked)
        bottom_layout.addWidget(self.output_table)
        
        main_splitter.addWidget(bottom_widget)
        
        main_splitter.setSizes([500, 250])
        main_layout.addWidget(main_splitter)

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Готов к работе")

        self.create_menu()
        self.create_toolbar()
        self.update_window_title()

    def on_text_changed(self):
        """Обработчик изменения текста"""
        if self._updating:
            return
        
        self._updating = True
        
        try:
            if not self.is_modified:
                self.is_modified = True
                self.update_window_title()
                self.status_bar.showMessage("✎ Изменено")
        finally:
            self._updating = False
    
    # Остальные методы остаются без изменений
    def update_window_title(self):
        """Обновление заголовка окна с учетом статуса изменений"""
        if self.current_file:
            file_name = os.path.basename(self.current_file)
        else:
            file_name = "Новый документ"
        
        modified_mark = " *" if self.is_modified else ""
        self.setWindowTitle(f"{file_name}{modified_mark} - Текстовый редактор")

    def check_save_before_action(self, action_name="продолжить"):
        """
        Проверка необходимости сохранения перед действием
        
        Возвращает:
            True - можно продолжать (сохранено или отмена не нужна)
            False - пользователь отменил действие
        """
        if not self.is_modified:
            return True  
        
        reply = QMessageBox.question(
            self,
            "Несохраненные изменения",
            f"Документ был изменен. Сохранить изменения перед {action_name}?",
            QMessageBox.StandardButton.Save | 
            QMessageBox.StandardButton.Discard | 
            QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Save
        )
        
        if reply == QMessageBox.StandardButton.Save:
            return self.save_file()
        elif reply == QMessageBox.StandardButton.Discard:
            return True
        else:
            return False

    def closeEvent(self, event: Optional[QCloseEvent]) -> None:
        """Обработчик закрытия окна (выход из программы)"""
        if self.check_save_before_action("выходом"):
            if event:
                event.accept()
        else:
            if event:
                event.ignore()
    
    def on_error_clicked(self, row, column):

        pos_item = self.output_table.item(row, 1)

        if not pos_item:
            return

        pos_text = pos_item.text()

        if ':' not in pos_text:
            return

        try:

            line, pos = pos_text.split(':')

            self.navigate_to_error_absolute(
                int(line),
                int(pos)
            )

        except:
            pass

    def navigate_to_error_absolute(self, line: int, position: int):
        """
        Перемещает курсор в редакторе на указанную позицию через абсолютные координаты
        с защитой от выхода за границы
        """
        text = self.editor.toPlainText()
        lines = text.splitlines(True)
        editor_line_count = self.editor.document().blockCount()
        print(f"Строк в редакторе: {editor_line_count}, запрошена строка: {line}")
        
        if line < 1:
            line = 1
        elif line > editor_line_count:
            print(f"Строка {line} вне диапазона. Используем последнюю строку ({editor_line_count})")
            line = editor_line_count
        
        text_lines = text.split('\n')
        
        if line < 1 or line > len(text_lines):
            print(f"Строка {line} вне диапазона text_lines (всего: {len(text_lines)})")
            cursor = self.editor.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.End)
            self.editor.setTextCursor(cursor)
            self.editor.setFocus()
            self.editor.ensureCursorVisible()
            self.status_bar.showMessage(f"Не удалось найти строку {line}, переход в конец")
            return
        
        abs_pos = 0
        for i in range(line - 1):
            abs_pos += len(text_lines[i]) + 1 
        
        max_pos = len(text_lines[line - 1])
        if position > max_pos:
            print(f"Позиция {position} больше длины строки ({max_pos}). Используем {max_pos}")
            position = max_pos
        
        abs_pos += position
        
        print(f"Переход: строка {line}, позиция {position}, абсолютная позиция: {abs_pos}")
        
        cursor = self.editor.textCursor()
        cursor.setPosition(abs_pos)
        self.editor.setTextCursor(cursor)
        self.editor.setFocus()
        self.editor.ensureCursorVisible()
        
        self.status_bar.showMessage(f"Переход к ошибке: строка {line}, позиция {position}")


    def new_file(self):

        if not self.check_save_before_action(
            "созданием нового документа"
        ):
            return

        self.editor.clear()

        self.output_table.setRowCount(0)

        self.current_file = None

        self.is_modified = False

        self.update_window_title()

        self.status_bar.showMessage(
            "Новый документ создан"
        )
    
    def open_file(self):
        """Открыть файл"""
        if not self.check_save_before_action("открытием другого файла"):
            return
        
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Открыть файл", "",
            "Текстовые файлы (*.txt);;Все файлы (*.*)"
        )
        
        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as file:
                    text = file.read()
                
                self.editor.setText(text)
                self.current_file = file_path
                self.is_modified = False
                self.update_window_title()
                
                self.status_bar.showMessage(f"Открыт файл: {os.path.basename(file_path)}")
                
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось открыть файл:\n{str(e)}")

    def save_file(self):
        """Сохранить файл"""
        if self.current_file:
            try:
                text = self.editor.toPlainText()
                with open(self.current_file, 'w', encoding='utf-8') as file:
                    file.write(text)
                
                self.is_modified = False
                self.update_window_title()
                
                self.status_bar.showMessage(f"Файл сохранен: {os.path.basename(self.current_file)}")
                return True
                
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить файл:\n{str(e)}")
                return False
        else:
            return self.save_file_as()
        
    def save_file_as(self):
        """Сохранить файл с новым именем"""
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Сохранить файл как",
            "",
            "Текстовые файлы (*.txt);;Все файлы (*.*)"
        )
        
        if file_path:
            if not file_path.endswith('.txt'):
                file_path += '.txt'
            
            self.current_file = file_path
            return self.save_file()
        
        return False

    def delete_text(self):

        cursor = self.editor.textCursor()

        if cursor.hasSelection():
            cursor.removeSelectedText()

    def create_menu(self):
        """Создание меню"""
        menubar = self.menuBar()

        file_menu = menubar.addMenu("Файл")
        
        new_action = QAction("Создать", self)
        new_action.setShortcut(QKeySequence.StandardKey.New)
        new_action.triggered.connect(self.new_file)
        file_menu.addAction(new_action)
        
        open_action = QAction("Открыть", self)
        open_action.setShortcut(QKeySequence.StandardKey.Open)
        open_action.triggered.connect(self.open_file)
        file_menu.addAction(open_action)
        
        save_action = QAction("Сохранить", self)
        save_action.setShortcut(QKeySequence.StandardKey.Save)
        save_action.triggered.connect(self.save_file)
        file_menu.addAction(save_action)
        
        save_as_action = QAction("Сохранить как", self)
        save_as_action.setShortcut(QKeySequence.StandardKey.SaveAs)
        save_as_action.triggered.connect(self.save_file_as)
        file_menu.addAction(save_as_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction("Выход", self)
        exit_action.setShortcut(QKeySequence.StandardKey.Quit)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        edit_menu = menubar.addMenu("Правка")
        
        undo_action = QAction("Отменить", self)
        undo_action.setShortcut(QKeySequence.StandardKey.Undo)
        undo_action.triggered.connect(self.editor.undo)
        edit_menu.addAction(undo_action)
        
        redo_action = QAction("Повторить", self)
        redo_action.setShortcut(QKeySequence.StandardKey.Redo)
        redo_action.triggered.connect(self.editor.redo)
        edit_menu.addAction(redo_action)
        
        edit_menu.addSeparator()
        
        cut_action = QAction("Вырезать", self)
        cut_action.setShortcut(QKeySequence.StandardKey.Cut)
        cut_action.triggered.connect(self.editor.cut)
        edit_menu.addAction(cut_action)
        
        copy_action = QAction("Копировать", self)
        copy_action.setShortcut(QKeySequence.StandardKey.Copy)
        copy_action.triggered.connect(self.editor.copy)
        edit_menu.addAction(copy_action)
        
        paste_action = QAction("Вставить", self)
        paste_action.setShortcut(QKeySequence.StandardKey.Paste)
        paste_action.triggered.connect(self.editor.paste)
        edit_menu.addAction(paste_action)
        
        delete_action = QAction("Удалить", self)
        delete_action.setShortcut(QKeySequence.StandardKey.Delete)
        delete_action.triggered.connect(self.delete_text)
        edit_menu.addAction(delete_action)
        
        edit_menu.addSeparator()
        
        select_all_action = QAction("Выделить все", self)
        select_all_action.setShortcut(QKeySequence.StandardKey.SelectAll)
        select_all_action.triggered.connect(self.editor.selectAll)
        edit_menu.addAction(select_all_action)

        text_menu = menubar.addMenu("Текст")
        text_menu.addAction("Постановка задачи", lambda: self.show_info("Постановка задачи"))
        text_menu.addAction("Грамматика", lambda: self.show_info("Грамматика"))
        text_menu.addAction("Классификация грамматики", lambda: self.show_info("Классификация грамматики"))
        text_menu.addAction("Метод анализа", lambda: self.show_info("Метод анализа"))
        text_menu.addAction("Тестовый пример", lambda: self.show_info("Тестовый пример"))
        text_menu.addAction("Список литературы", lambda: self.show_info("Список литературы"))
        text_menu.addAction("Исходный код программы", lambda: self.show_info("Исходный код программы"))

        start_menu = menubar.addMenu("Пуск")
        start_action = QAction("Запустить синтаксический анализ", self)
        start_action.triggered.connect(self.run_parser)
        start_menu.addAction(start_action)

        help_menu = menubar.addMenu("Справка")
        help_action = QAction("Вызов справки", self)
        help_action.triggered.connect(self.show_help)
        help_menu.addAction(help_action)
        
        about_action = QAction("О программе", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

    def create_toolbar(self):
        """Создание панели инструментов с иконками"""
        toolbar = QToolBar("Панель инструментов")
        toolbar.setIconSize(QtCore.QSize(24, 24))
        self.addToolBar(toolbar)

        new_icon = self.style().standardIcon(QStyle.StandardPixmap.SP_FileIcon)
        new_action = QAction(new_icon, "Создать", self)
        new_action.setShortcut(QKeySequence.StandardKey.New)
        new_action.triggered.connect(self.new_file)
        toolbar.addAction(new_action)

        open_icon = self.style().standardIcon(QStyle.StandardPixmap.SP_DialogOpenButton)
        open_action = QAction(open_icon, "Открыть", self)
        open_action.setShortcut(QKeySequence.StandardKey.Open)
        open_action.triggered.connect(self.open_file)
        toolbar.addAction(open_action)
    
        save_icon = self.style().standardIcon(QStyle.StandardPixmap.SP_DialogSaveButton)
        save_action = QAction(save_icon, "Сохранить", self)
        save_action.setShortcut(QKeySequence.StandardKey.Save)
        save_action.triggered.connect(self.save_file)
        toolbar.addAction(save_action)
    
        toolbar.addSeparator()
    
        undo_icon = self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowBack)
        undo_action = QAction(undo_icon, "Отменить", self)
        undo_action.setShortcut(QKeySequence.StandardKey.Undo)
        undo_action.triggered.connect(self.editor.undo)
        toolbar.addAction(undo_action)

        redo_icon = self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowForward)
        redo_action = QAction(redo_icon, "Повторить", self)
        redo_action.setShortcut(QKeySequence.StandardKey.Redo)
        redo_action.triggered.connect(self.editor.redo)
        toolbar.addAction(redo_action)
    
        toolbar.addSeparator()

        copy_icon = self.style().standardIcon(QStyle.StandardPixmap.SP_FileIcon) 
        copy_action = QAction(copy_icon, "Копировать", self)
        copy_action.setShortcut(QKeySequence.StandardKey.Copy)
        copy_action.triggered.connect(self.editor.copy)
        toolbar.addAction(copy_action)
    
        cut_icon = self.style().standardIcon(QStyle.StandardPixmap.SP_FileIcon) 
        cut_action = QAction(cut_icon, "Вырезать", self)
        cut_action.setShortcut(QKeySequence.StandardKey.Cut)
        cut_action.triggered.connect(self.editor.cut)
        toolbar.addAction(cut_action)
    
        paste_icon = self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogStart) 
        paste_action = QAction(paste_icon, "Вставить", self)
        paste_action.setShortcut(QKeySequence.StandardKey.Paste)
        paste_action.triggered.connect(self.editor.paste)
        toolbar.addAction(paste_action)
    
        toolbar.addSeparator()


        toolbar.addSeparator()

        run_icon = self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay)
        run_action = QAction(run_icon, "Синтаксический анализ", self)
        run_action.triggered.connect(self.run_parser)
        toolbar.addAction(run_action)
    
        toolbar.addSeparator()

        help_icon = self.style().standardIcon(QStyle.StandardPixmap.SP_DialogHelpButton)
        help_action = QAction(help_icon, "Справка", self)
        help_action.setShortcut(QKeySequence.StandardKey.HelpContents)
        help_action.triggered.connect(self.show_help)
        toolbar.addAction(help_action)

        info_icon = self.style().standardIcon(QStyle.StandardPixmap.SP_MessageBoxInformation)
        info_action = QAction(info_icon, "О программе", self)
        info_action.triggered.connect(self.show_about)
        toolbar.addAction(info_action)

        toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)

    def show_info(self, item_name):

        QMessageBox.information(
            self,
            "Информация",
            item_name
        )

    def run_parser(self):

        text = self.editor.toPlainText()

        if not text.strip():

            QMessageBox.warning(
                self,
                "Предупреждение",
                "Введите текст для анализа"
            )

            return

        self.output_table.setRowCount(0)

        tokens, lex_errors = analyze_text(text)

        parser = Parser(tokens)

        _, syntax_errors = parser.parse()

        all_errors = []

        # Лексические ошибки

        for token in tokens:

            if token.type.name == "ERROR":

                all_errors.append({
                    "fragment": token.value,
                    "position": f"{token.line}:{token.start_pos}",
                    "message": "Недопустимый символ"
                })

        # Синтаксические ошибки

        for error in syntax_errors:

            all_errors.append({
                "fragment": error.fragment,
                "position": f"{error.line}:{error.position}",
                "message": error.message
            })

        # Вывод ошибок

        for row, error in enumerate(all_errors):

            self.output_table.insertRow(row)

            self.output_table.setItem(
                row,
                0,
                QTableWidgetItem(error["fragment"])
            )

            self.output_table.setItem(
                row,
                1,
                QTableWidgetItem(error["position"])
            )

            self.output_table.setItem(
                row,
                2,
                QTableWidgetItem(error["message"])
            )

        # Итог

        if len(all_errors) == 0:

            QMessageBox.information(
                self,
                "Результат",
                "Ошибок не обнаружено"
            )

            self.status_bar.showMessage(
                "Синтаксический анализ завершён успешно"
            )

        else:

            QMessageBox.warning(
                self,
                "Ошибки",
                f"Найдено ошибок: {len(all_errors)}"
            )

            self.status_bar.showMessage(
                f"Найдено ошибок: {len(all_errors)}"
            )
    
    def show_help(self):

        help_text = """
    РУКОВОДСТВО ПОЛЬЗОВАТЕЛЯ

    1. Введите текст программы F#

    2. Нажмите кнопку
    "Синтаксический анализ"

    3. При наличии ошибок:

    - они появятся в таблице
    - можно нажать на ошибку
    - курсор перейдёт к месту ошибки

    Поддерживаемая конструкция:

    type Color =
    | Red
    | Green
    | Blue;

    Горячие клавиши:

    Ctrl+N — новый файл
    Ctrl+O — открыть
    Ctrl+S — сохранить
    """

        QMessageBox.information(
            self,
            "Справка",
            help_text
        )
    
    def show_about(self):

        about_text = """
    <h3>Синтаксический анализатор F#</h3>

    <p><b>Лабораторная работа №3</b></p>

    <p>Тема:</p>

    <p>Разработка синтаксического анализатора
    для объявления перечислений F#</p>

    <p><b>Метод анализа:</b></p>

    <p>Рекурсивный спуск</p>

    <p><b>Обработка ошибок:</b></p>

    <p>Метод Айронса</p>
    """

        QMessageBox.about(
            self,
            "О программе",
            about_text
        )


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = TextEditor()
    window.show()
    sys.exit(app.exec())