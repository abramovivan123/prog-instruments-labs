"""Boundary checks and CSV integration tests for variant 1."""

import csv
import json
import tempfile
import unittest
from pathlib import Path

from checksum import calculate_checksum
from main import BASE_DIR, save_result, validate_csv
from patterns import PATTERNS


VALID_ROW = {
    "email": "operators.1947@sub.domain.ru",
    "http_status_message": "226 IM Used",
    "snils": "00534478510",
    "passport": "27 17 117724",
    "ip_v4": "19.121.223.58",
    "longitude": "-63.65076",
    "hex_color": "#d8346b",
    "isbn": "018-1-50114-053-6",
    "locale_code": "es-uy",
    "time": "18:24:12.734883",
}

BOUNDARY_CASES = {
    "email": (
        ["a@b.ru", "relate1878@sub.domain.ru"],
        ["a..b@x.ru", ".a@x.ru", "a@x,ru", "a@x", "a@x ru"],
    ),
    "http_status_message": (
        ["100 Continue", "200 OK", "207 Multi-Status"],
        ["200OK", "200_OK", "7202 Accepted", "600 Invalid", "200 "],
    ),
    "snils": (
        ["00000000000"],
        ["1234567890", "123456789012", "_00534478510_", "١" * 11],
    ),
    "passport": (
        ["00 00 000000"],
        ["27-17-117724", "2717117724", "27 17 11772", "27  17 117724"],
    ),
    "ip_v4": (
        ["0.0.0.0", "255.255.255.255", "249.250.254.255"],
        ["256.1.1.1", "1.1.1.256", "01.2.3.4", "1.2.3", "1.2.3.4:32"],
    ),
    "longitude": (
        ["-180", "180.000", "-180.0", "179.999999", "0", "-0.5"],
        ["180.000001", "-180.1", "181", "1,25", "1.25°", "1.", "_1.2"],
    ),
    "hex_color": (
        ["#000000", "#FFFFFF", "#aBc123"],
        ["123456", "###123456", "#12345g", "#12345", "#1234567"],
    ),
    "isbn": (
        ["1-74254-734-5", "1-74254-734-X", "527-1-62998-937-8"],
        ["1742547345", "1 74254 734 5", "1_74254_734_5",
         "527-1-62998-937-X"],
    ),
    "locale_code": (
        ["xh", "en-us", "zh-cn"],
        ["en_us", "_ru_", "ru_1", "ru-", "en-us-extra", "e", "123"],
    ),
    "time": (
        ["00:00:00.000000", "23:59:59.999999"],
        ["24:00:00.000000", "12:60:00.000000", "12:00:60.000000",
         "1:00:00.000000", "12:00:00.00000", "12-00-00_000000"],
    ),
}


class PatternTests(unittest.TestCase):
    """Check acceptance and rejection at meaningful format boundaries."""

    def test_patterns(self):
        for field, (valid, invalid) in BOUNDARY_CASES.items():
            for value in valid + [VALID_ROW[field]]:
                with self.subTest(field=field, value=value, valid=True):
                    self.assertIsNotNone(PATTERNS[field].fullmatch(value))
            for value in invalid:
                with self.subTest(field=field, value=value, valid=False):
                    self.assertIsNone(PATTERNS[field].fullmatch(value))

    def test_extra_characters_are_rejected(self):
        for field, value in VALID_ROW.items():
            for corrupted in (" " + value, value + " ", value + "\n", ""):
                with self.subTest(field=field, value=corrupted):
                    self.assertIsNone(PATTERNS[field].fullmatch(corrupted))


class CsvTests(unittest.TestCase):
    """Verify row numbering, duplicate errors and malformed CSV handling."""

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "sample.csv"

    def write_rows(self, rows, headers=None):
        if headers is None:
            headers = list(PATTERNS)
        with self.path.open("w", encoding="utf-16", newline="") as output:
            writer = csv.writer(output, delimiter=";")
            writer.writerow(headers)
            writer.writerows(rows)

    def test_zero_based_rows_and_multiple_invalid_cells(self):
        invalid = dict(VALID_ROW, email="bad", snils="123")
        self.write_rows(
            [invalid.values(), VALID_ROW.values(), invalid.values()]
        )
        result = validate_csv(self.path)
        self.assertEqual(result.row_count, 3)
        self.assertEqual(result.invalid_rows, [0, 2])
        self.assertEqual(result.errors_by_field["email"], 2)
        self.assertEqual(sum(result.errors_by_field.values()), 4)

    def test_header_only(self):
        self.write_rows([])
        result = validate_csv(self.path)
        self.assertEqual(result.row_count, 0)
        self.assertEqual(result.invalid_rows, [])

    def test_invalid_headers(self):
        for headers in ([], ["email"], ["email"] * 10):
            with self.subTest(headers=headers):
                self.write_rows([], headers)
                with self.assertRaises(ValueError):
                    validate_csv(self.path)

    def test_wrong_number_of_cells(self):
        values = list(VALID_ROW.values())
        for row in (values[:-1], values + ["extra"]):
            with self.subTest(row=row):
                self.write_rows([row])
                with self.assertRaises(ValueError):
                    validate_csv(self.path)

    def test_result_format(self):
        output = Path(self.directory.name) / "result.json"
        checksum = calculate_checksum([2, 0])
        save_result(output, checksum)
        self.assertEqual(
            json.loads(output.read_text(encoding="utf-8")),
            {"variant": "1", "checksum": checksum},
        )

    def test_original_dataset(self):
        result = validate_csv(BASE_DIR / "1.csv")
        self.assertEqual(result.row_count, 10000)
        self.assertEqual(len(result.invalid_rows), 1000)
        self.assertTrue(
            all(count == 100 for count in result.errors_by_field.values())
        )
        expected = json.loads(
            (BASE_DIR / "result.json").read_text(encoding="utf-8")
        )
        self.assertEqual(
            calculate_checksum(result.invalid_rows), expected["checksum"]
        )


if __name__ == "__main__":
    unittest.main()
