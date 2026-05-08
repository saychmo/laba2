# automaton_searcher.py
# Модуль для поиска комментариев C++ с использованием конечного автомата

from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from enum import Enum


class AutomatonState(Enum):
    """Состояния автомата для поиска комментариев C++"""
    START = 0               # Начальное состояние
    SLASH = 1               # Найден символ '/'
    SINGLE_LINE = 2         # Внутри однострочного комментария //
    MULTI_LINE = 3          # Внутри многострочного комментария /*
    MULTI_LINE_STAR = 4     # Найден '*' внутри многострочного комментария
    END_COMMENT = 5         # Конец комментария (сохранение)


@dataclass
class AutomatonMatch:
    """Класс для хранения информации о найденном комментарии"""
    text: str
    start_line: int
    start_pos: int
    end_line: int
    end_pos: int
    absolute_start: int
    absolute_end: int
    length: int
    comment_type: str      # "single_line" или "multi_line"
    
    def __repr__(self):
        return f"AutomatonMatch(text='{self.text}', type={self.comment_type}, line={self.start_line}, pos={self.start_pos})"


class AutomatonSearcher:
    """
    Конечный автомат для поиска комментариев C++.
    Поддерживает:
    - Однострочные комментарии: // текст до конца строки
    - Многострочные комментарии: /* текст */ (включая переносы строк)
    """
    
    def __init__(self):
        """Инициализация автомата"""
        self.reset()
    
    def reset(self):
        """Сброс автомата в начальное состояние"""
        self.current_state = AutomatonState.START
        self.comment_start_pos = -1
        self.comment_start_line = -1
        self.comment_start_col = -1
        self.comment_chars = []
        self.comment_type = ""
    
    def _update_line_info(self, text: str, position: int) -> Tuple[int, int, int]:
        """
        Определяет номер строки и позицию в строке по абсолютной позиции
        
        Returns:
            tuple: (номер_строки, позиция_в_строке, абсолютная_позиция_начала_строки)
        """
        lines = text[:position + 1].split('\n')
        line_num = len(lines) - 1
        line_start = position - len(lines[-1]) if line_num > 0 else 0
        col_num = position - line_start
        return line_num, col_num, line_start
    
    def find_matches(self, text: str) -> List[AutomatonMatch]:
        """
        Поиск всех комментариев в тексте с использованием конечного автомата
        """
        matches = []
        self.reset()
        
        i = 0
        length = len(text)
        
        while i < length:
            char = text[i]
            next_state = self._transition(char)
            
            # Обработка действий при переходе
            action_result = self._action(char, i, text)
            if action_result is not None:
                matches.append(action_result)
            
            self.current_state = next_state
            i += 1
        
        # КОРРЕКЦИЯ: Сохраняем последний комментарий, если текст не заканчивается на \n
        if self.current_state == AutomatonState.SINGLE_LINE and self.comment_chars:
            # Убираем последний символ, если это не \n
            comment_text = ''.join(self.comment_chars)
            
            # Если последний символ не \n, то это конец файла
            if comment_text and comment_text[-1] != '\n':
                end_pos = len(text) - 1
                end_line, end_col, _ = self._update_line_info(text, end_pos)
                
                start_pos_adjusted = self.comment_start_col + 1
                
                match = AutomatonMatch(
                    text=comment_text,
                    start_line=self.comment_start_line + 1,
                    start_pos=start_pos_adjusted,
                    end_line=end_line + 1,
                    end_pos=end_col + 1,
                    absolute_start=self.comment_start_pos,
                    absolute_end=end_pos,
                    length=len(comment_text),
                    comment_type=self.comment_type
                )
                matches.append(match)
        
        return matches
    
    def _transition(self, char: str) -> AutomatonState:
        """
        Функция переходов автомата
        """
        if self.current_state == AutomatonState.START:
            if char == '/':
                return AutomatonState.SLASH
            return AutomatonState.START
            
        elif self.current_state == AutomatonState.SLASH:
            if char == '/':
                return AutomatonState.SINGLE_LINE
            elif char == '*':
                return AutomatonState.MULTI_LINE
            return AutomatonState.START
            
        elif self.current_state == AutomatonState.SINGLE_LINE:
            if char == '\n':
                return AutomatonState.END_COMMENT
            return AutomatonState.SINGLE_LINE
            
        elif self.current_state == AutomatonState.MULTI_LINE:
            if char == '*':
                return AutomatonState.MULTI_LINE_STAR
            return AutomatonState.MULTI_LINE
            
        elif self.current_state == AutomatonState.MULTI_LINE_STAR:
            if char == '/':
                return AutomatonState.END_COMMENT
            elif char == '*':
                return AutomatonState.MULTI_LINE_STAR
            return AutomatonState.MULTI_LINE
            
        elif self.current_state == AutomatonState.END_COMMENT:
            return AutomatonState.START
        
        return AutomatonState.START
    
    def _action(self, char: str, position: int, text: str) -> Optional[AutomatonMatch]:
        """
        Действия при переходах между состояниями
        """
        
        # START -> SLASH: запоминаем позицию
        if self.current_state == AutomatonState.START and char == '/':
            self.comment_start_pos = position
            line, col, _ = self._update_line_info(text, position)
            self.comment_start_line = line
            self.comment_start_col = col
            self.comment_chars = [char]
            self.comment_type = ""
            
        # SLASH -> SINGLE_LINE: начало однострочного комментария
        elif self.current_state == AutomatonState.SLASH and char == '/':
            self.comment_chars.append(char)
            self.comment_type = "single_line"
            
        # SLASH -> MULTI_LINE: начало многострочного комментария
        elif self.current_state == AutomatonState.SLASH and char == '*':
            self.comment_chars.append(char)
            self.comment_type = "multi_line"
            
        # SLASH -> START: не комментарий, сброс
        elif self.current_state == AutomatonState.SLASH and char not in ['/', '*']:
            self.comment_chars = []
            self.comment_start_pos = -1
            
        # Внутри однострочного комментария: добавляем символы
        elif self.current_state == AutomatonState.SINGLE_LINE:
            if char != '\n':
                self.comment_chars.append(char)
            else:
                self.comment_chars.append(char)
                
        # Внутри многострочного комментария: добавляем символы
        elif self.current_state == AutomatonState.MULTI_LINE:
            self.comment_chars.append(char)
            
        # Внутри MULTI_LINE_STAR: добавляем символы
        elif self.current_state == AutomatonState.MULTI_LINE_STAR:
            self.comment_chars.append(char)
            
        # Конец комментария - сохраняем
        elif self.current_state == AutomatonState.END_COMMENT:
            if self.comment_chars:
                comment_text = ''.join(self.comment_chars)
                
                end_line, end_col, _ = self._update_line_info(text, position)
                
                absolute_start = self.comment_start_pos
                absolute_end = position
                
                start_pos_adjusted = self.comment_start_col + 1
                
                match = AutomatonMatch(
                    text=comment_text,
                    start_line=self.comment_start_line + 1,
                    start_pos=start_pos_adjusted,
                    end_line=end_line + 1,
                    end_pos=end_col + 1,
                    absolute_start=absolute_start,
                    absolute_end=absolute_end,
                    length=len(comment_text),
                    comment_type=self.comment_type
                )
                
                # Сброс для следующего комментария
                self.comment_chars = []
                self.comment_type = ""
                return match
        
        return None


class AutomatonVisualizer:
    """Класс для визуализации работы автомата"""
    
    @staticmethod
    def trace_search(text: str, searcher: AutomatonSearcher) -> List[Dict]:
        """Трассировка работы автомата"""
        trace = []
        searcher.reset()
        
        i = 0
        length = len(text)
        
        while i < length:
            char = text[i]
            old_state = searcher.current_state
            new_state = searcher._transition(char)
            
            # Определяем тип события
            is_comment_start = False
            is_comment_end = False
            event_type = ""
            
            if old_state == AutomatonState.SLASH and char == '/':
                is_comment_start = True
                event_type = "🔵 НАЧАЛО // комментария"
            elif old_state == AutomatonState.SLASH and char == '*':
                is_comment_start = True
                event_type = "🔵 НАЧАЛО /* комментария"
            elif old_state == AutomatonState.SINGLE_LINE and char == '\n':
                is_comment_end = True
                event_type = "🟢 КОНЕЦ // комментария"
            elif old_state == AutomatonState.MULTI_LINE_STAR and char == '/':
                is_comment_end = True
                event_type = "🟢 КОНЕЦ */ комментария"
            
            trace.append({
                'position': i,
                'char': char,
                'old_state': old_state.name,
                'new_state': new_state.name,
                'is_comment_start': is_comment_start,
                'is_comment_end': is_comment_end,
                'event_type': event_type
            })
            
            # Выполняем действие
            searcher._action(char, i, text)
            searcher.current_state = new_state
            i += 1
        
        return trace
    
    @staticmethod
    def print_trace(trace: List[Dict]):
        """Вывод трассировки в консоль"""
        print("\n" + "="*80)
        print("Трассировка работы автомата (поиск комментариев C++):")
        print("="*80)
        print(f"{'Поз.':<6} {'Символ':<10} {'Состояние→':<20} {'Событие':<35}")
        print("-"*80)
        
        for step in trace:
            pos = step['position']
            char = repr(step['char'])[1:-1] if step['char'] != '\n' else '\\n'
            if step['char'] == ' ':
                char = '␣'
            trans = f"{step['old_state']} → {step['new_state']}"
            event = step['event_type'] if step['event_type'] else ""
            
            print(f"{pos:<6} {char:<10} {trans:<20} {event:<35}")
        
        print("="*80 + "\n")