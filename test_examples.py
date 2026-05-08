"""
Тесты на примеры из каталога examples/.

Под каждый файл — отдельный TestCase: оригинал + 5–6 «играющих»
вариаций (что-то добавили, что-то убрали, что-то заменили).
Запуск:

    python -m unittest test_examples.py -v
"""

import os
import unittest

from scanner import analyze_text
from parser import Parser


EXAMPLES_DIR = os.path.join(os.path.dirname(__file__), "examples")


def read_example(filename: str) -> str:
    with open(os.path.join(EXAMPLES_DIR, filename), encoding="utf-8") as f:
        return f.read()


def analyze(code: str):
    """Полный цикл лексер + парсер."""
    tokens, lex = analyze_text(code)
    ast, syn = Parser(tokens).parse()
    return lex, syn, ast


def total_errors(code: str) -> int:
    lex, syn, _ = analyze(code)
    return len(lex) + len(syn)


# =========================================================
# examples/14.txt — заведомо невалидный F# enum
# (опечатка в "type" + "&" вместо "|")
# =========================================================

class Examples_14_Tests(unittest.TestCase):

    ORIG = "teeeeeeeeype Day = \n\t| Monday \n\t& Thuesday;"

    def test_01_original_has_two_lex_one_syn(self):
        # 'teeeeeeeeype' и '&' — две лексические ошибки;
        # вместо | стоит &, поэтому ещё одна синтаксическая.
        lex, syn, ast = analyze(read_example("14.txt"))
        self.assertEqual(len(lex), 2)
        self.assertEqual(len(syn), 1)
        self.assertEqual(ast.cases, ["Monday"])

    def test_02_added_percents_break_word_more(self):
        # 'teeeee%%%eeeype' слипается в один ERROR-токен
        # (буквы + недопустимые '%' до пробела), плюс '&' — 2 lex.
        code = "teeeee%%%eeeype Day = \n\t| Monday \n\t& Thuesday;"
        lex, syn, _ = analyze(code)
        self.assertEqual(len(lex), 2)
        self.assertEqual(len(syn), 1)

    def test_03_fix_typo_only(self):
        # Чиним "teeeeeeeeype" -> "type", но '&' остаётся
        code = "type Day = \n\t| Monday \n\t& Thuesday;"
        lex, syn, _ = analyze(code)
        self.assertEqual(len(lex), 1)
        self.assertEqual(len(syn), 1)

    def test_04_fix_both_problems(self):
        # И опечатку правим, и & -> | — должно стать валидным
        code = "type Day = \n\t| Monday \n\t| Thuesday;"
        self.assertEqual(total_errors(code), 0)
        _, _, ast = analyze(code)
        self.assertEqual(ast.cases, ["Monday", "Thuesday"])

    def test_05_drop_second_case(self):
        # Оставляем только первый кейс — остаётся одна лекс. ошибка
        code = "teeeeeeeeype Day = \n\t| Monday;"
        lex, syn, _ = analyze(code)
        self.assertEqual(len(lex), 1)
        self.assertEqual(len(syn), 0)

    def test_06_remove_semicolon(self):
        # Убираем ; — добавляется синтаксическая ошибка про SEPARATOR
        code = "teeeeeeeeype Day = \n\t| Monday \n\t& Thuesday"
        lex, syn, _ = analyze(code)
        self.assertEqual(len(lex), 2)
        self.assertEqual(len(syn), 2)

    def test_07_replace_all_pipes_with_amp(self):
        # Все | заменены на & — два лексических ERROR + структурный
        code = "type Day = \n\t& Monday \n\t& Tuesday;"
        lex, syn, _ = analyze(code)
        self.assertEqual(len(lex), 2)
        self.assertEqual(len(syn), 1)


# =========================================================
# examples/true_code.txt — валидный enum (7 дней недели, табы)
# =========================================================

class Examples_TrueCode_Tests(unittest.TestCase):

    def test_01_original_is_valid(self):
        lex, syn, ast = analyze(read_example("true_code.txt"))
        self.assertEqual(len(lex), 0)
        self.assertEqual(len(syn), 0)
        self.assertEqual(len(ast.cases), 7)

    def test_02_remove_trailing_semicolon(self):
        code = read_example("true_code.txt").rstrip().rstrip(";")
        lex, syn, _ = analyze(code)
        self.assertEqual(len(lex), 0)
        self.assertEqual(len(syn), 1)

    def test_03_replace_eq_with_arrow(self):
        # '->' даёт лексический мусор и синтаксическую ошибку про '='
        code = "type Day ->\n\t| Monday\n\t| Tuesday;"
        lex, syn, _ = analyze(code)
        self.assertEqual(len(lex), 1)
        self.assertEqual(len(syn), 1)

    def test_04_replace_one_pipe_with_amp(self):
        code = "type Day =\n\t| Monday\n\t& Tuesday;"
        lex, syn, _ = analyze(code)
        self.assertEqual(len(lex), 1)
        self.assertEqual(len(syn), 1)

    def test_05_identifier_starts_with_digit(self):
        code = "type Day =\n\t| Monday\n\t| 1Tuesday;"
        lex, syn, ast = analyze(code)
        self.assertEqual(len(lex), 1)
        self.assertEqual(len(syn), 0)
        self.assertEqual(ast.cases, ["Monday", "1Tuesday"])

    def test_06_drop_type_keyword(self):
        code = "Day =\n\t| Monday\n\t| Tuesday;"
        lex, syn, _ = analyze(code)
        self.assertEqual(len(lex), 0)
        self.assertEqual(len(syn), 2)

    def test_07_garbage_after_semicolon(self):
        code = "type Day =\n\t| Monday\n\t| Tuesday; @ extra"
        lex, syn, _ = analyze(code)
        # @ — лексический ERROR, "extra" после ; — синтаксическая
        self.assertEqual(len(lex), 1)
        self.assertEqual(len(syn), 1)


# =========================================================
# examples/correct.txt — валидный enum, отступы пробелами
# =========================================================

class Examples_Correct_Tests(unittest.TestCase):

    def test_01_original_is_valid(self):
        self.assertEqual(total_errors(read_example("correct.txt")), 0)

    def test_02_double_pipe_in_middle(self):
        code = read_example("correct.txt").replace("| Tuesday", "| | Tuesday", 1)
        lex, syn, _ = analyze(code)
        self.assertEqual(len(lex), 0)
        self.assertEqual(len(syn), 1)

    def test_03_underscores_in_identifiers(self):
        # _ допустим внутри идентификатора
        code = "type Day =\n    | Mid_Week\n    | Other_One;"
        self.assertEqual(total_errors(code), 0)

    def test_04_uppercase_keyword(self):
        # 'Type' -> идентификатор; парсер сообщает один раз
        # ("Ожидался KEYWORD"), затем спокойно разбирает имя
        # типа, '=', case-list и ';'.
        code = "Type Day =\n    | Monday;"
        lex, syn, ast = analyze(code)
        self.assertEqual(len(lex), 0)
        self.assertEqual(len(syn), 1)
        self.assertEqual(ast.cases, ["Monday"])

    def test_05_drop_equals(self):
        code = "type Day\n    | Monday\n    | Tuesday;"
        lex, syn, _ = analyze(code)
        self.assertEqual(len(lex), 0)
        self.assertEqual(len(syn), 1)

    def test_06_dangling_pipe_before_semicolon(self):
        # 'Sunday |;' — оператор | без идентификатора в конце
        code = read_example("correct.txt").replace("Sunday;", "Sunday |;")
        lex, syn, _ = analyze(code)
        self.assertEqual(len(lex), 0)
        self.assertEqual(len(syn), 2)

    def test_07_minimal_one_case(self):
        code = "type Day =\n    | Monday;"
        self.assertEqual(total_errors(code), 0)


# =========================================================
# examples/1.txt — мусорная пара слов "Primer koda"
# =========================================================

class Examples_1_Tests(unittest.TestCase):

    def test_01_original_misses_everything(self):
        # Нет 'type', нет '=', нет '|', нет ';'.
        lex, syn, _ = analyze(read_example("1.txt"))
        self.assertEqual(len(lex), 0)
        self.assertEqual(len(syn), 3)

    def test_02_wrap_into_valid_enum(self):
        code = "type Primer = | koda;"
        lex, syn, ast = analyze(code)
        self.assertEqual(len(lex), 0)
        self.assertEqual(len(syn), 0)
        self.assertEqual(ast.cases, ["koda"])

    def test_03_prepend_type_only(self):
        # 'type Primer koda' — нет '=' и '|'
        code = "type Primer koda"
        lex, syn, _ = analyze(code)
        self.assertEqual(len(lex), 0)
        self.assertEqual(len(syn), 2)

    def test_04_inject_hash_into_identifier(self):
        # 'Primer#' слипается в один ERROR-токен; затем 'koda'
        # парсится как имя типа, но нет '=' и ';'.
        code = "Primer# koda"
        lex, syn, _ = analyze(code)
        self.assertEqual(len(lex), 1)
        self.assertEqual(len(syn), 2)

    def test_05_replace_space_with_pipe(self):
        # 'Primer | koda' — двe идентификатора через PIPE, но без 'type'
        code = "Primer | koda"
        lex, syn, _ = analyze(code)
        self.assertEqual(len(lex), 0)
        self.assertEqual(len(syn), 3)

    def test_06_single_word(self):
        lex, syn, _ = analyze("Primer")
        self.assertEqual(len(lex), 0)
        self.assertEqual(len(syn), 4)

    def test_07_keyword_only(self):
        # Только 'type' — нет ни имени типа, ни '='
        lex, syn, _ = analyze("type")
        self.assertEqual(len(lex), 0)
        self.assertEqual(len(syn), 3)


# =========================================================
# examples/grammer_text.txt — русский текст-вывод другой лабы
# =========================================================

class Examples_GrammerText_Tests(unittest.TestCase):

    def test_01_original_full_file(self):
        # Файл из другой лабы — кириллица и пунктуация => куча ERROR
        lex, syn, _ = analyze(read_example("grammer_text.txt"))
        self.assertEqual(len(lex), 66)
        self.assertEqual(len(syn), 2)

    def test_02_only_first_line(self):
        first_line = read_example("grammer_text.txt").splitlines()[0]
        lex, syn, _ = analyze(first_line)
        self.assertEqual(len(lex), 4)
        self.assertEqual(len(syn), 2)

    def test_03_one_ascii_word(self):
        lex, syn, _ = analyze("TEXT")
        self.assertEqual(len(lex), 0)
        self.assertEqual(len(syn), 4)

    def test_04_cyrillic_inside_identifier(self):
        # 'Сабака' — ERROR на каждой буквы кириллицы (одной группой)
        code = "type Russian = | Сабака;"
        lex, syn, _ = analyze(code)
        self.assertEqual(len(lex), 1)
        self.assertEqual(len(syn), 0)

    def test_05_only_punctuation(self):
        lex, syn, _ = analyze("...")
        self.assertEqual(len(lex), 1)
        self.assertEqual(len(syn), 3)

    def test_06_translit_makes_it_valid(self):
        code = "type Doc = | Sabaka | Beget | Pa | Lait | Zales;"
        self.assertEqual(total_errors(code), 0)

    def test_07_empty_string(self):
        # Парсер на пустом вводе молча отчитывается, что не нашёл type
        lex, syn, _ = analyze("")
        self.assertEqual(len(lex), 0)
        self.assertEqual(len(syn), 0)


# =========================================================
# examples/calc.txt — текст про вычисление выражения
# =========================================================

class Examples_Calc_Tests(unittest.TestCase):

    def test_01_original_huge_lex_noise(self):
        # Кириллица + операторы + числа = много ERROR
        lex, syn, _ = analyze(read_example("calc.txt"))
        self.assertEqual(len(lex), 55)
        self.assertEqual(len(syn), 2)

    def test_02_simple_assign(self):
        # 'a = 15' -> '15' стартует с цифры (ERROR)
        code = "a = 15"
        lex, syn, _ = analyze(code)
        self.assertEqual(len(lex), 1)
        self.assertEqual(len(syn), 4)

    def test_03_just_eq(self):
        lex, syn, _ = analyze("=")
        self.assertEqual(len(lex), 0)
        self.assertEqual(len(syn), 4)

    def test_04_wrap_as_enum(self):
        # Имена a, b, c — допустимые идентификаторы
        code = "type Calc = | a | b | c;"
        self.assertEqual(total_errors(code), 0)

    def test_05_only_operators(self):
        # '+ - * /' — четыре отдельных ERROR
        lex, syn, _ = analyze("+ - * /")
        self.assertEqual(len(lex), 4)
        self.assertEqual(len(syn), 2)

    def test_06_empty_case_list(self):
        # 'type X = ;' — пустой список case-ов; парсер не возражает
        code = "type X = ;"
        lex, syn, ast = analyze(code)
        self.assertEqual(len(lex), 0)
        self.assertEqual(len(syn), 0)
        self.assertEqual(ast.cases, [])

    def test_07_math_expression(self):
        # 'a + b - c' — два ERROR на + и -
        lex, syn, _ = analyze("a + b - c")
        self.assertEqual(len(lex), 2)
        self.assertEqual(len(syn), 3)


# =========================================================
# examples/primer.txt — кириллический мусор "попоао"
# =========================================================

class Examples_Primer_Tests(unittest.TestCase):

    def test_01_original_one_lex_error(self):
        lex, syn, _ = analyze(read_example("primer.txt"))
        self.assertEqual(len(lex), 1)
        self.assertEqual(len(syn), 3)

    def test_02_translit_no_lex_error(self):
        # 'popoao' — валидный идентификатор, но не enum
        lex, syn, _ = analyze("popoao")
        self.assertEqual(len(lex), 0)
        self.assertEqual(len(syn), 4)

    def test_03_wrap_translit_into_enum(self):
        code = "type Primer = | popoao;"
        self.assertEqual(total_errors(code), 0)

    def test_04_one_cyrillic_letter(self):
        lex, syn, _ = analyze("п")
        self.assertEqual(len(lex), 1)
        self.assertEqual(len(syn), 3)

    def test_05_mixed_languages_in_cases(self):
        code = "type Mixed = | Hello | Привет;"
        lex, syn, ast = analyze(code)
        self.assertEqual(len(lex), 1)
        self.assertEqual(len(syn), 0)
        self.assertIn("Hello", ast.cases)

    def test_06_two_cyrillic_words(self):
        # 'попоао попоао' — два ERROR подряд (разделены пробелом)
        lex, syn, _ = analyze("попоао попоао")
        self.assertEqual(len(lex), 2)
        self.assertEqual(len(syn), 2)

    def test_07_repeat_with_separator(self):
        # 'попоао|попоао' — между ERROR-ами прорывается PIPE
        lex, syn, _ = analyze("попоао|попоао")
        self.assertEqual(len(lex), 2)
        self.assertEqual(len(syn), 3)


# =========================================================
# examples/mac-adressa.txt — список MAC-адресов
# =========================================================

class Examples_MacAddress_Tests(unittest.TestCase):

    def test_01_original_many_errors(self):
        lex, syn, _ = analyze(read_example("mac-adressa.txt"))
        # Каждая строка с двоеточиями/дефисами даёт ERROR; ровно 7 строк
        # с разделителями + ничего синтаксически валидного.
        self.assertEqual(len(lex), 7)
        self.assertEqual(len(syn), 2)

    def test_02_first_address_with_colons(self):
        # ':' — недопустимый символ (тут он 5 раз -> 1 ERROR-блок,
        # т.к. он стоит между группами и сам по себе)
        lex, syn, _ = analyze("00:1A:2B:3C:4D:5E")
        self.assertEqual(len(lex), 1)
        self.assertEqual(len(syn), 3)

    def test_03_no_separator_address(self):
        # '001A2B3C4D5E' — стартует с цифры => один ERROR
        lex, syn, _ = analyze("001A2B3C4D5E")
        self.assertEqual(len(lex), 1)
        self.assertEqual(len(syn), 3)

    def test_04_alpha_only_mac(self):
        # Чистые буквы — IDENT, но не enum
        lex, syn, _ = analyze("FF")
        self.assertEqual(len(lex), 0)
        self.assertEqual(len(syn), 4)

    def test_05_wrap_letters_as_enum(self):
        code = "type Mac = | A | B | C | D | E | F;"
        self.assertEqual(total_errors(code), 0)

    def test_06_with_dash(self):
        # 'FF-FF-FF' слипается в одну ошибку: 'FF' буквы +
        # дефис не из стоп-списка => вся группа становится ERROR.
        lex, syn, _ = analyze("FF-FF-FF")
        self.assertEqual(len(lex), 1)
        self.assertEqual(len(syn), 3)

    def test_07_alphabetic_id_in_enum(self):
        # 'aabbccddeeff' — допустимый идентификатор
        code = "type Mac = | aabbccddeeff;"
        self.assertEqual(total_errors(code), 0)


# =========================================================
# examples/comments.txt — C++-комментарии
# =========================================================

class Examples_Comments_Tests(unittest.TestCase):

    def test_01_original_lex_errors_present(self):
        lex, syn, _ = analyze(read_example("comments.txt"))
        # Слэши и звёздочки — недопустимые символы; число подсчитано
        self.assertEqual(len(lex), 11)
        self.assertEqual(len(syn), 2)

    def test_02_single_line_comment(self):
        lex, syn, _ = analyze("// Comment")
        self.assertEqual(len(lex), 1)
        self.assertEqual(len(syn), 2)

    def test_03_int_assignment_with_number(self):
        # 'int z = 15' — '15' стартует с цифры (ERROR)
        lex, syn, _ = analyze("int z = 15")
        self.assertEqual(len(lex), 1)
        self.assertEqual(len(syn), 2)

    def test_04_wrap_keywords_as_enum(self):
        # int, float, bool — валидные идентификаторы для нашего сканера
        code = "type Words = | int | float | bool;"
        self.assertEqual(total_errors(code), 0)

    def test_05_block_comment_brackets(self):
        # '/* */' — два ERROR-блока (/* и */ через пробел)
        lex, syn, _ = analyze("/* */")
        self.assertEqual(len(lex), 2)
        self.assertEqual(len(syn), 2)

    def test_06_two_idents_no_structure(self):
        # 'Comment Comment' — два идентификатора без 'type'
        lex, syn, _ = analyze("Comment Comment")
        self.assertEqual(len(lex), 0)
        self.assertEqual(len(syn), 3)

    def test_07_line_and_block_starters(self):
        # '// /*' — два ERROR (через пробел)
        lex, syn, _ = analyze("// /*")
        self.assertEqual(len(lex), 2)
        self.assertEqual(len(syn), 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
