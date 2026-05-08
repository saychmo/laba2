# searcher.py
# Модуль для поиска подстрок в тексте с поддержкой различных типов поиска

import re
from typing import List, Tuple, Optional, Callable
from enum import Enum
from automaton_searcher import AutomatonSearcher, AutomatonMatch, AutomatonVisualizer
from typing import Dict

class SearchType(Enum):
    """Типы поиска"""
    SINGLE_QUOTES = "Цитаты в одинарных кавычках ('...')"
    DOUBLE_QUOTES = "Цитаты в двойных кавычках (\"...\")"
    ANY_QUOTES = "Любые кавычки ('...' или \"...\")"
    CAPITALIZED_WORDS = "Слова с заглавной буквы"
    NUMBERS = "Числа (целые и десятичные)"
    CPP_SINGLE_LINE_COMMENTS = "Однострочные комментарии C++ (//...)"
    CPP_MULTI_LINE_COMMENTS = "Многострочные комментарии C++ (/*...*/)"
    CPP_ALL_COMMENTS = "Все комментарии C++ (// и /*...*/)"
    MAC_ADDRESS = "MAC-адреса (XX:XX:XX:XX:XX:XX)"
    MAC_ADDRESS_COMPACT = "MAC-адреса без разделителей (XXXXXXXXXXXX)"
    MAC_ADDRESS_ALL = "MAC-адреса (с разделителями и без)"
    CUSTOM = "Пользовательский шаблон"
    AUTOMATON_QUOTES = "Автоматный поиск цитат (конечный автомат)"


class QuoteMatch:
    """Класс для хранения информации о найденной подстроке"""
    def __init__(self, text: str, line: int, start_pos: int, end_pos: int, absolute_pos: int):
        self.text = text  # найденная подстрока
        self.line = line  # номер строки (1-based)
        self.start_pos = start_pos  # позиция начала в строке (1-based)
        self.end_pos = end_pos  # позиция конца в строке (1-based)
        self.absolute_pos = absolute_pos  # абсолютная позиция в тексте (0-based)
        self.length = len(text)  # длина подстроки
    
    def __repr__(self):
        return f"QuoteMatch(text='{self.text}', line={self.line}, pos={self.start_pos}-{self.end_pos})"


class QuoteSearcher:
    """Класс для поиска подстрок в тексте с поддержкой различных типов поиска"""
    
    def __init__(self):
        # Предопределенные шаблоны для различных типов поиска
        self.patterns = {
            SearchType.SINGLE_QUOTES: r"'([^'\\]|\\.)*'",
            SearchType.DOUBLE_QUOTES: r'"([^"\\]|\\.)*"',
            SearchType.ANY_QUOTES: r"(['\"])([^\1\\]|\\.)*\1",
            SearchType.CAPITALIZED_WORDS: r"\b[A-Z][a-z]*\b",
            SearchType.NUMBERS: r"\b\d+(?:\.\d+)?\b",
            # Комментарии C++
            SearchType.CPP_SINGLE_LINE_COMMENTS: r"//[^\n]*",
            SearchType.CPP_MULTI_LINE_COMMENTS: r"/\*[\s\S]*?\*/",
            SearchType.CPP_ALL_COMMENTS: r"//[^\n]*|/\*[\s\S]*?\*/",
            # MAC-адреса
            SearchType.MAC_ADDRESS: self._get_mac_pattern_with_delimiters(),
            SearchType.MAC_ADDRESS_COMPACT: self._get_mac_pattern_compact(),
            SearchType.MAC_ADDRESS_ALL: self._get_mac_pattern_all(),
            SearchType.CUSTOM: ""
        }
        
        self.current_search_type = SearchType.SINGLE_QUOTES
        self.custom_pattern = ""
        self.last_pattern = None
        self.last_compiled_pattern = None
        self.automaton_searcher = AutomatonSearcher()
    
    def _get_mac_pattern_with_delimiters(self) -> str:
        """
        MAC-адрес с разделителями (: или -)
        Формат: XX:XX:XX:XX:XX:XX или XX-XX-XX-XX-XX-XX
        где X - шестнадцатеричная цифра (0-9, A-F, a-f)
        """
        # Шестнадцатеричная цифра
        hex_byte = r"[0-9A-Fa-f]{2}"
        # Разделитель (: или -)
        delimiter = r"[:\-]"
        # Полный паттерн: 6 групп, разделенных разделителями
        return rf"{hex_byte}{delimiter}{hex_byte}{delimiter}{hex_byte}{delimiter}{hex_byte}{delimiter}{hex_byte}{delimiter}{hex_byte}"
    
    def _get_mac_pattern_compact(self) -> str:
        """
        MAC-адрес без разделителей
        Формат: XXXXXXXXXXXX (12 шестнадцатеричных цифр)
        """
        return r"[0-9A-Fa-f]{12}"
    
    def _get_mac_pattern_all(self) -> str:
        """
        Все форматы MAC-адресов:
        1. С разделителями (: или -)
        2. Без разделителей (12 цифр)
        3. С точками (XXXX.XXXX.XXXX)
        """
        # Формат с разделителями
        with_delim = self._get_mac_pattern_with_delimiters()
        # Компактный формат
        compact = self._get_mac_pattern_compact()
        # Формат с точками (например: 0123.4567.89AB)
        with_dots = r"[0-9A-Fa-f]{4}\.[0-9A-Fa-f]{4}\.[0-9A-Fa-f]{4}"
        
        return rf"{with_delim}|{compact}|{with_dots}"
    
    def set_search_type(self, search_type: SearchType):
        """Устанавливает тип поиска"""
        self.current_search_type = search_type
        self.last_pattern = None  # Сбрасываем кэш
        self.last_compiled_pattern = None
    
    def set_custom_pattern(self, pattern: str):
        """Устанавливает пользовательский шаблон"""
        self.custom_pattern = pattern
        if self.current_search_type == SearchType.CUSTOM:
            self.last_pattern = None
            self.last_compiled_pattern = None
    
    def get_pattern(self) -> str:
        """Возвращает регулярное выражение для текущего типа поиска"""
        if self.current_search_type == SearchType.CUSTOM:
            return self.custom_pattern
        return self.patterns.get(self.current_search_type, self.patterns[SearchType.SINGLE_QUOTES])
    
    def get_compiled_pattern(self) -> Optional[re.Pattern]:
        """Возвращает скомпилированное регулярное выражение"""
        pattern = self.get_pattern()
        
        if not pattern:
            return None
        
        # Используем кэш для оптимизации
        if pattern == self.last_pattern and self.last_compiled_pattern is not None:
            return self.last_compiled_pattern
        
        try:
            # Для многострочных комментариев используем DOTALL флаг
            if self.current_search_type in [SearchType.CPP_MULTI_LINE_COMMENTS, 
                                           SearchType.CPP_ALL_COMMENTS]:
                self.last_compiled_pattern = re.compile(pattern, re.DOTALL)
            else:
                # Для MAC-адресов используем флаг IGNORECASE для поддержки a-f
                if self.current_search_type in [SearchType.MAC_ADDRESS, 
                                               SearchType.MAC_ADDRESS_COMPACT,
                                               SearchType.MAC_ADDRESS_ALL]:
                    self.last_compiled_pattern = re.compile(pattern, re.IGNORECASE)
                else:
                    self.last_compiled_pattern = re.compile(pattern)
            self.last_pattern = pattern
            return self.last_compiled_pattern
        except re.error as e:
            raise ValueError(f"Ошибка в регулярном выражении: {str(e)}")
    
    def find_matches(self, text: str) -> List[QuoteMatch]:
        """
        Находит все подстроки в тексте согласно текущему типу поиска
        
        Args:
            text: исходный текст
        
        Returns:
            Список объектов QuoteMatch с информацией о найденных подстроках
        """
        if not text:
            return []
        
        compiled_pattern = self.get_compiled_pattern()
        
        # Если шаблон пустой или некорректный, возвращаем пустой список
        if compiled_pattern is None:
            return []
        
        matches = []
        
        # Проходим по всему тексту с поиском совпадений
        for match in compiled_pattern.finditer(text):
            matched_text = match.group(0)
            start_abs = match.start()
            end_abs = match.end()
            
            # Определяем номер строки и позицию в строке
            line_num, line_start, line_end = self._get_line_info(text, start_abs)
            
            # Позиция в строке (1-based)
            pos_in_line = start_abs - line_start + 1
            
            matches.append(QuoteMatch(
                text=matched_text,
                line=line_num + 1,  # переводим в 1-based для пользователя
                start_pos=pos_in_line,
                end_pos=pos_in_line + len(matched_text) - 1,
                absolute_pos=start_abs
            ))
        
        return matches
    
    def _get_line_info(self, text: str, position: int) -> Tuple[int, int, int]:
        """
        Определяет номер строки и границы строки по абсолютной позиции
        
        Returns:
            tuple: (номер_строки, начало_строки, конец_строки)
        """
        lines = text.split('\n')
        current_pos = 0
        
        for i, line in enumerate(lines):
            line_start = current_pos
            line_end = current_pos + len(line)
            
            if line_start <= position <= line_end:
                return i, line_start, line_end
            
            # +1 для символа новой строки
            current_pos += len(line) + 1
        
        # Если позиция вне диапазона (например, конец файла)
        return len(lines) - 1, current_pos - len(lines[-1]) - 1, current_pos
    
    def get_match_count(self, text: str) -> int:
        """Возвращает количество найденных подстрок"""
        return len(self.find_matches(text))
    
    def get_search_types_list(self) -> List[Tuple[SearchType, str]]:
        """Возвращает список доступных типов поиска для UI"""
        return [(st, st.value) for st in SearchType]
    
    def validate_pattern(self, pattern: str) -> bool:
        """Проверяет корректность регулярного выражения"""
        try:
            re.compile(pattern)
            return True
        except re.error:
            return False
    
    def highlight_match_in_text(self, text: str, match: QuoteMatch, 
                                highlight_start: str = '\x01', 
                                highlight_end: str = '\x02') -> str:
        """
        Добавляет маркеры выделения вокруг найденной подстроки
        
        Args:
            text: исходный текст
            match: объект найденной подстроки
            highlight_start: маркер начала выделения
            highlight_end: маркер конца выделения
        
        Returns:
            Текст с маркерами выделения
        """
        if match.absolute_pos < 0 or match.absolute_pos + match.length > len(text):
            return text
        
        return (text[:match.absolute_pos] + 
                highlight_start + 
                text[match.absolute_pos:match.absolute_pos + match.length] + 
                highlight_end + 
                text[match.absolute_pos + match.length:])
    
        
    def find_matches_automaton(self, text: str) -> List[QuoteMatch]:
        """
        Поиск цитат с использованием конечного автомата
        """
        if not text:
            return []
        
        automaton_matches = self.automaton_searcher.find_matches(text)
        
        # Конвертируем AutomatonMatch в QuoteMatch для совместимости
        quotes = []
        for match in automaton_matches:
            quotes.append(QuoteMatch(
                text=match.text,
                line=match.start_line,
                start_pos=match.start_pos,
                end_pos=match.start_pos + match.length - 1,
                absolute_pos=match.absolute_start
            ))
        
        return quotes
    
    def trace_automaton_search(self, text: str) -> List[Dict]:
        """Возвращает трассировку работы автомата"""
        return AutomatonVisualizer.trace_search(text, self.automaton_searcher)
    
    def print_automaton_trace(self, text: str):
        """Выводит трассировку в консоль"""
        trace = self.trace_automaton_search(text)
        AutomatonVisualizer.print_trace(trace)

    # Добавить в класс QuoteSearcher:

    def find_matches_comments_automaton(self, text: str) -> List[QuoteMatch]:
        """Поиск комментариев C++ с использованием конечного автомата"""
        from automaton_searcher import AutomatonSearcher
    
        if not text:
            return []
    
        automaton = AutomatonSearcher()
        automaton_matches = automaton.find_matches(text)
    
        # Конвертируем AutomatonMatch в QuoteMatch для совместимости
        comments = []
        for match in automaton_matches:
            comments.append(QuoteMatch(
                text=match.text,
                line=match.start_line,
                start_pos=match.start_pos,
                end_pos=match.start_pos + match.length - 1,
                absolute_pos=match.absolute_start
            ))
    
        return comments