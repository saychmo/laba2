# parser.py
# Синтаксический анализатор объявления перечислений F#

from typing import List, Optional, Tuple
from scanner import Token, TokenType


# =========================================================
# КЛАСС ОШИБКИ
# =========================================================

class ParserError:
    def __init__(self,
                 fragment: str,
                 line: int,
                 position: int,
                 message: str):

        self.fragment = fragment
        self.line = line
        self.position = position
        self.message = message

    def __str__(self):
        return f"{self.line}:{self.position} -> {self.message}"


# =========================================================
# AST
# =========================================================

class ASTNode:
    def __init__(self, node_type: str):
        self.node_type = node_type
        self.children: List['ASTNode'] = []


class EnumDeclarationNode(ASTNode):

    def __init__(self, type_name: str, cases: List[str]):
        super().__init__("EnumDeclaration")

        self.type_name = type_name
        self.cases = cases


# =========================================================
# ПАРСЕР
# =========================================================

class Parser:

    """
    Грамматика:

    EnumDeclaration ::= "type" IDENTIFIER "=" CaseList ";"

    CaseList ::= Case { Case }

    Case ::= "|" IDENTIFIER
    """

    def __init__(self, tokens: List[Token]):

        self.tokens = [
            t for t in tokens
            if t.type != TokenType.WHITESPACE
        ]

        self.position = 0

        self.errors: List[ParserError] = []

    # =====================================================
    # СЛУЖЕБНЫЕ МЕТОДЫ
    # =====================================================

    def current_token(self) -> Optional[Token]:
        """
        Возвращает текущий токен без побочных эффектов.
        ERROR-токены не пропускаются здесь: их обрабатывает
        consume() как "джокер" (лексер уже сообщил об ошибке,
        парсер не должен дублировать диагностику).
        """

        if self.position < len(self.tokens):
            return self.tokens[self.position]

        return None

    def next_token(self):

        self.position += 1

    # =====================================================
    # МЕТОД АЙРОНСА
    # =====================================================

    def synchronize(self):

        """
        Синхронизация после ошибки.
        Пропускаем токены до ближайшего
        безопасного символа.
        """

        sync_tokens = {
            TokenType.PIPE,
            TokenType.SEPARATOR
        }

        while self.current_token():

            token = self.current_token()

            if token.type in sync_tokens:
                return

            self.position += 1

    # =====================================================
    # CONSUME
    # =====================================================

    # позиции, где ERROR логично считать "сломанным словом"
    # (идентификатор / ключевое слово). В структурных позициях
    # (|, =, ;) ERROR просто проскакиваем — лексер о нём
    # уже отчитался и плодить вторую ошибку не нужно.
    _WORD_LIKE_TYPES = {TokenType.KEYWORD, TokenType.IDENTIFIER}

    def consume(self, expected_type, expected_value=None):

        # ==========================================
        # Пропуск ERROR-токенов в структурных позициях.
        # Для PIPE / OPERATOR / SEPARATOR посторонний
        # ошибочный токен не должен сдвигать разбор.
        # ==========================================

        if expected_type not in self._WORD_LIKE_TYPES:
            while (self.position < len(self.tokens)
                   and self.tokens[self.position].type == TokenType.ERROR):
                self.position += 1

        token = self.current_token()

        # ==========================================
        # ERROR в "словесной" позиции: трактуем как
        # заглушку для ожидаемого KEYWORD/IDENTIFIER.
        # Это предотвращает каскадную диагностику
        # после уже сообщённой лексической ошибки.
        # ==========================================

        if token is not None and token.type == TokenType.ERROR:
            self.position += 1
            return token

        # ==========================================
        # EOF
        # ==========================================

        if token is None:

            last_token = self.tokens[-1] if len(self.tokens) > 0 else None

            if last_token is not None:

                self.errors.append(
                    ParserError(
                        "EOF",
                        last_token.line,
                        last_token.end_pos + 1,
                        f"Ожидался {expected_type.name}"
                    )
                )

            return None

        # ==========================================
        # Неверный тип токена
        # ==========================================

        if token.type != expected_type:

            self.errors.append(
                ParserError(
                    token.value,
                    token.line,
                    token.start_pos,
                    f"Ожидался {expected_type.name}"
                )
            )

            # ======================================
            # ВАЖНО:
            # продвигаем позицию
            # чтобы не было каскада ошибок
            # ======================================

            self.position += 1

            return None

        # ==========================================
        # Неверное значение
        # ==========================================

        if expected_value is not None and token.value != expected_value:

            self.errors.append(
                ParserError(
                    token.value,
                    token.line,
                    token.start_pos,
                    f"Ожидался '{expected_value}'"
                )
            )

            self.position += 1

            return None

        # ==========================================
        # OK
        # ==========================================

        self.position += 1

        return token
    # =====================================================
    # PARSE
    # =====================================================

    def parse(self):
        """
        Главный метод синтаксического анализа
        """
        ast = self.parse_enum_declaration()

        # Если AST не построен — прекращаем дальнейший анализ
        # чтобы не было каскадных ошибок
        if ast is None:
            return None, self.errors

        # Проверка лишних токенов
        current = self.current_token()

        if current is not None:
            self.errors.append(
                ParserError(
                    fragment=current.value,
                    line=current.line,
                    position=current.start_pos,
                    message="Лишний текст после завершения конструкции"
                )
            )

        return ast, self.errors


    def parse_enum_declaration(self):

        # =====================================================
        # type
        # =====================================================

        keyword = self.consume(TokenType.KEYWORD, "type")

        # =====================================================
        # Ошибка в type — догоняем до ближайшего IDENTIFIER,
        # чтобы продолжить разбор имени типа без каскада.
        # =====================================================

        if keyword is None:

            while self.current_token() is not None:

                token = self.current_token()

                if token is None:
                    break

                if token.type == TokenType.IDENTIFIER:
                    break

                self.position += 1

        # =====================================================
        # TypeName
        # =====================================================

        type_name = self.parse_type_name()

        if type_name is None:
            type_name = "UNKNOWN"

        # =====================================================
        # =
        # =====================================================

        eq = self.consume(TokenType.OPERATOR, "=")

        # =====================================================
        # Ошибка =
        # =====================================================

        if eq is None:

            while self.current_token() is not None:

                token = self.current_token()

                if token is None:
                    break

                # нашли начало cases
                if token.type == TokenType.PIPE:
                    break

                # нашли ;
                if (
                    token.type == TokenType.SEPARATOR
                    and token.value == ";"
                ):
                    break

                self.position += 1

        # =====================================================
        # CaseList
        # =====================================================
        # Разбираем case-list всегда: если выше уже были ошибки,
        # recovery подвёл нас либо к ближайшему '|', либо к ';'.
        # В любом случае дальнейший разбор не должен плодить
        # дополнительные сообщения сверх уже выданных.

        cases = []

        parsed_cases = self.parse_case_list()

        if parsed_cases is not None:
            cases = parsed_cases

        # =====================================================
        # ;
        # =====================================================

        self.consume(TokenType.SEPARATOR, ";")

        # =====================================================
        # AST
        # =====================================================

        return EnumDeclarationNode(
            type_name,
            cases
        )

    def parse_type_name(self) -> Optional[str]:
        """
        TypeName ::= IDENTIFIER
        """

        token = self.consume(TokenType.IDENTIFIER)

        if token is None:
            return None

        return token.value
    # =====================================================
    # CaseList
    # =====================================================

    def parse_case_list(self):

        cases = []

        while self.current_token():

            token = self.current_token()

            if token is None:
                break
            # Конец списка
            if token.type == TokenType.SEPARATOR:
                break

            # Случайный ERROR-токен между кейсами (или
            # на месте первого '|', если выше уже была
            # ошибка). Лексер уже сообщил о нём — просто
            # пропускаем, не плодя синтаксических диагностик.
            if token.type == TokenType.ERROR:
                self.position += 1
                continue

            case = self.parse_case()

            if case:
                cases.append(case)

        return cases

    # =====================================================
    # Case
    # =====================================================

    def parse_case(self):

        # |
        if self.consume(TokenType.PIPE, "|") is None:

            self.synchronize()

            current = self.current_token()

            if current is not None:
                if current.type == TokenType.PIPE:
                    return self.parse_case()

            return None

        # IDENTIFIER
        token = self.consume(TokenType.IDENTIFIER)

        if token is None:

            self.synchronize()

            return None

        return token.value