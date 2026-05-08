# scanner.py
from enum import Enum
from typing import List, Tuple


class TokenType(Enum):
    KEYWORD = 1
    IDENTIFIER = 2
    OPERATOR = 3
    PIPE = 4
    SEPARATOR = 5
    WHITESPACE = 6
    ERROR = -1


class Token:
    def __init__(self, token_type: TokenType, value: str, line: int, start_pos: int, end_pos: int):
        self.type = token_type
        self.code = token_type.value
        self.value = value
        self.line = line
        self.start_pos = start_pos
        self.end_pos = end_pos


class Scanner:
    def __init__(self):
        self.tokens = []
        self.current_line = 1
        self.current_pos = 0
        self.line_start = 0
    
    def reset(self):
        self.tokens = []
        self.current_line = 1
        self.current_pos = 0
        self.line_start = 0
    
    def is_letter(self, c):
        return 'a' <= c <= 'z' or 'A' <= c <= 'Z'
    
    def is_digit(self, c):
        return '0' <= c <= '9'
    
    def is_whitespace(self, c):
        return c in ' \t\r'

    # Символы, которые "закрывают" текущую лексему: пробелы и
    # любой структурный токен языка. Всё, что не в этом списке,
    # считается частью текущей последовательности.
    _STOP_CHARS = ' \t\r\n=|;'

    def add_token(self, token_type, value, line, start, end):
        if token_type != TokenType.WHITESPACE:
            self.tokens.append(Token(token_type, value, line, start, end))
    
    def scan(self, text: str) -> List[Token]:
        self.reset()
        i = 0
        n = len(text)
        
        while i < n:
            c = text[i]
            
            # Обновляем номер строки
            if c == '\n':
                self.current_line += 1
                self.line_start = i + 1
            
            # Пропускаем пробелы
            if self.is_whitespace(c) or c == '\n':
                i += 1
                continue
            
            # Определяем начало лексемы
            start_pos = i - self.line_start
            start_line = self.current_line
            
            # Ключевое слово "type"
            if c == 't':

                j = i

                while j < n and (
                    self.is_letter(text[j]) or
                    self.is_digit(text[j]) or
                    text[j] == '_'
                ):
                    j += 1

                # Если сразу после слова идёт недопустимый символ
                # (не пробел и не структурный разделитель),
                # вся "слипшаяся" последовательность считается
                # одной лексической ошибкой.
                if j < n and text[j] not in self._STOP_CHARS:
                    while j < n and text[j] not in self._STOP_CHARS:
                        j += 1
                    value = text[i:j]
                    self.add_token(
                        TokenType.ERROR,
                        value,
                        start_line,
                        start_pos,
                        start_pos + len(value) - 1
                    )
                    i = j
                    continue

                value = text[i:j]

                # корректный type
                if value == "type":

                    self.add_token(
                        TokenType.KEYWORD,
                        value,
                        start_line,
                        start_pos,
                        start_pos + len(value) - 1
                    )

                else:
                    # неправильное написание type
                    self.add_token(
                        TokenType.ERROR,
                        value,
                        start_line,
                        start_pos,
                        start_pos + len(value) - 1
                    )

                i = j
                continue
            
            # Идентификатор (буква + буквы/цифры)
            if self.is_letter(c):
                j = i
                while j < n and (self.is_letter(text[j]) or self.is_digit(text[j]) or text[j] == '_'):
                    j += 1

                # Идентификатор, "слипшийся" с недопустимым символом,
                # — целиком одна лексическая ошибка.
                if j < n and text[j] not in self._STOP_CHARS:
                    while j < n and text[j] not in self._STOP_CHARS:
                        j += 1
                    value = text[i:j]
                    self.add_token(
                        TokenType.ERROR,
                        value,
                        start_line,
                        start_pos,
                        start_pos + len(value) - 1
                    )
                    i = j
                    continue

                value = text[i:j]
                self.add_token(TokenType.IDENTIFIER, value, start_line, start_pos, start_pos + len(value) - 1)
                i = j
                continue
            
            # Оператор =
            if c == '=':
                self.add_token(TokenType.OPERATOR, "=", start_line, start_pos, start_pos)
                i += 1
                continue
            
            # Разделитель |
            if c == '|':
                self.add_token(TokenType.PIPE, "|", start_line, start_pos, start_pos)
                i += 1
                continue
            
            # Разделитель ;
            if c == ';':
                self.add_token(TokenType.SEPARATOR, ";", start_line, start_pos, start_pos)
                i += 1
                continue
            
            # Ошибка: собираем все недопустимые символы подряд
            j = i

            while j < n:

                ch = text[j]

                # продолжаем собирать
                # всё подряд до разделителя
                if ch in ' \t\r\n=|;':
                    break

                j += 1

            value = text[i:j]

            self.add_token(
                TokenType.ERROR,
                value,
                start_line,
                start_pos,
                start_pos + len(value) - 1
            )

            i = j
        
        return self.tokens


def analyze_text(text: str) -> Tuple[List[Token], List[str]]:
    scanner = Scanner()
    tokens = scanner.scan(text)
    errors = [f"Недопустимый символ '{t.value}' в строке {t.line}, позиция {t.start_pos}" 
              for t in tokens if t.type == TokenType.ERROR]
    return tokens, errors