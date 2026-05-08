"""
Тесты для синтаксического анализатора объявлений enum на F#.

Тестируется связка scanner.analyze_text + parser.Parser, как она
используется в main.py: общее количество ошибок, показываемых
пользователю, складывается из лексических (ERROR-токены) и
синтаксических (ParserError).

Запуск:
    python -m unittest test_parser.py -v
"""

import unittest

from scanner import analyze_text, TokenType
from parser import Parser


def analyze(code: str):
    """
    Прогон полного цикла анализа.
    Возвращает (lex_errors, parser_errors, ast).
    """
    tokens, lex_errors = analyze_text(code)
    parser = Parser(tokens)
    ast, parser_errors = parser.parse()
    return lex_errors, parser_errors, ast


def total_errors(code: str) -> int:
    """Сколько ошибок увидит пользователь в UI."""
    lex, syn, _ = analyze(code)
    return len(lex) + len(syn)


class ValidEnumTests(unittest.TestCase):
    """Корректные объявления enum — ошибок быть не должно."""

    def test_01_simple_singleline(self):
        code = "type Status = | Active | Inactive | Pending;"
        self.assertEqual(total_errors(code), 0)
        _, _, ast = analyze(code)
        self.assertEqual(ast.type_name, "Status")
        self.assertEqual(ast.cases, ["Active", "Inactive", "Pending"])

    def test_02_multiline_with_tabs(self):
        code = (
            "type Day =\n"
            "\t| Monday\n"
            "\t| Tuesday\n"
            "\t| Wednesday\n"
            "\t| Thursday\n"
            "\t| Friday\n"
            "\t| Saturday\n"
            "\t| Sunday;"
        )
        self.assertEqual(total_errors(code), 0)
        _, _, ast = analyze(code)
        self.assertEqual(len(ast.cases), 7)

    def test_03_single_case(self):
        code = "type Single = | Only;"
        self.assertEqual(total_errors(code), 0)
        _, _, ast = analyze(code)
        self.assertEqual(ast.cases, ["Only"])

    def test_04_underscores_and_digits_inside_identifier(self):
        code = "type T = | Case_One | Case_2 | RGB_Red_42;"
        self.assertEqual(total_errors(code), 0)
        _, _, ast = analyze(code)
        self.assertEqual(ast.cases, ["Case_One", "Case_2", "RGB_Red_42"])

    def test_05_lowercase_identifiers(self):
        code = "type myType = | optionA | optionB;"
        self.assertEqual(total_errors(code), 0)


class InvalidEnumTests(unittest.TestCase):
    """Некорректные объявления — должно быть ровно 1 сообщение об ошибке."""

    def test_06_identifier_starts_with_digits(self):
        # Главный кейс из задачи пользователя.
        code = (
            "type Day =\n"
            "\t| Monday\n"
            "\t| Tuesday\n"
            "\t| Wednesday\n"
            "\t| Thursday\n"
            "\t| 423423Friday\n"
            "\t| Saturday\n"
            "\t| Sunday;"
        )
        lex, syn, ast = analyze(code)
        self.assertEqual(len(lex), 1, "ожидалась одна лексическая ошибка")
        self.assertEqual(len(syn), 0, "парсер не должен плодить каскад")
        # Saturday не должен теряться из-за ошибочного токена выше
        self.assertIn("Saturday", ast.cases)
        self.assertIn("Sunday", ast.cases)

    def test_07_missing_type_keyword(self):
        code = "Day = | Monday | Tuesday;"
        self.assertGreaterEqual(total_errors(code), 1)

    def test_08_missing_equals_sign(self):
        code = "type Day | Monday | Tuesday;"
        self.assertGreaterEqual(total_errors(code), 1)

    def test_09_missing_semicolon(self):
        code = "type Day = | Monday | Tuesday"
        self.assertGreaterEqual(total_errors(code), 1)

    def test_10_missing_pipe_before_first_case(self):
        code = "type Day = Monday | Tuesday;"
        self.assertGreaterEqual(total_errors(code), 1)

    def test_11_double_pipe_no_identifier(self):
        code = "type Day = | | Tuesday;"
        lex, syn, _ = analyze(code)
        self.assertEqual(len(lex), 0)
        self.assertEqual(len(syn), 1, "ожидалась ровно одна синтаксическая ошибка")

    def test_12_invalid_symbol_after_identifier(self):
        code = "type Day = | Monday @ | Tuesday;"
        lex, syn, ast = analyze(code)
        self.assertEqual(len(lex), 1, "лексер должен поймать '@' одной ошибкой")
        self.assertEqual(len(syn), 0, "парсер не должен дублировать диагностику")
        self.assertIn("Monday", ast.cases)
        self.assertIn("Tuesday", ast.cases)

    def test_13_misspelled_keyword_type(self):
        code = "tipe Day = | Monday;"
        lex, _, _ = analyze(code)
        self.assertEqual(len(lex), 1)
        self.assertEqual(total_errors(code), 1)

    def test_14_empty_input_treated_as_blank(self):
        # main.py не вызывает парсер на пустой строке, но напрямую
        # анализатор обязан корректно отчитаться об ошибке.
        code = ""
        _, syn, _ = analyze(code)
        self.assertEqual(len(syn), 0, "пустой ввод — нет токенов, парсер молчит")

    def test_15a_typo_in_keyword_and_missing_eq(self):
        # Регрессия: 'jdjtype Day | … | Sunday;' — нет ни 'type',
        # ни '='. Должно быть ровно 2 синтаксические ошибки
        # (Ожидался KEYWORD + Ожидался OPERATOR), без каскада.
        code = (
            "jdjtype Day \n"
            " | Monday\n"
            " | Tuesday\n"
            " | Wednesday\n"
            " | Thursday\n"
            " | Friday\n"
            " | Saturday\n"
            " | Sunday;"
        )
        lex, syn, ast = analyze(code)
        self.assertEqual(len(lex), 0)
        self.assertEqual(len(syn), 2)
        # Сами кейсы парсер должен распознать (Monday будет
        # пропущен как часть recovery после '=').
        self.assertIn("Sunday", ast.cases)

    def test_15_garbage_glued_to_identifier_is_one_error(self):
        # Регрессия: 'S%%%%unday' — это «обломанный» идентификатор,
        # сканер должен слепить его в один ERROR, парсер не должен
        # каскадить «Ожидался PIPE/SEPARATOR».
        code = (
            "type Day =\n"
            "\t| Monday\n"
            "\t| Tuesday\n"
            "\t| Wednesday\n"
            "\t| Thursday\n"
            "\t| Friday\n"
            "\t| Saturday\n"
            "\t| S%%%%unday;"
        )
        lex, syn, ast = analyze(code)
        self.assertEqual(len(lex), 1)
        self.assertEqual(len(syn), 0)
        self.assertEqual(ast.cases[-1], "S%%%%unday")

    def test_16_two_independent_lex_errors(self):
        # Два разных недопустимых токена -> две лексические ошибки
        # и никакого каскада от парсера.
        code = "type Day = | $bad | Monday | #other | Tuesday;"
        lex, syn, ast = analyze(code)
        self.assertEqual(len(lex), 2)
        self.assertEqual(len(syn), 0)
        # Все четыре варианта дошли до AST (ошибочные как заглушки)
        self.assertEqual(len(ast.cases), 4)
        self.assertIn("Monday", ast.cases)
        self.assertIn("Tuesday", ast.cases)


if __name__ == "__main__":
    unittest.main(verbosity=2)
