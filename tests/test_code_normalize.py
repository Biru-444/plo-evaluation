"""Unit tests สำหรับ app/services/code_normalize.py - กฎ normalize รหัส PLO/CLO เดียวที่ใช้ทั้งตอนเขียน
(มคอ.2/มคอ.3 import, สร้าง/แก้ PLO-CLO ด้วยมือ) และตอนเทียบ (มคอ.3 import matching,
domain_category_check, clo-plo-mapping save) ทั่วระบบ"""
from __future__ import annotations

import pytest

from app.services.code_normalize import normalize_code


@pytest.mark.parametrize(
    "raw_code",
    ["PLO4", "PLO 4", "plo4", "plo 4", "PLO ๔", "  PLO4  ", " plo   4 "],
)
def test_all_variants_normalize_to_same_canonical_form(raw_code):
    assert normalize_code(raw_code) == "PLO4"


def test_thai_digits_convert_to_arabic():
    assert normalize_code("CLO๓") == "CLO3"
    assert normalize_code("CLO ๑๐") == "CLO10"


def test_none_and_empty_return_empty_string():
    assert normalize_code(None) == ""
    assert normalize_code("") == ""
    assert normalize_code("   ") == ""


def test_different_codes_stay_different():
    assert normalize_code("PLO1") != normalize_code("PLO4")
    assert normalize_code("CLO1") != normalize_code("PLO1")
