"""
Unit tests สำหรับ app/services/year_level.py - เรียกฟังก์ชันตรงๆ พร้อม today= ที่กำหนดเอง ไม่ต้องพึ่ง
monkeypatch หรือนาฬิกาเครื่องจริงเลย (ต่างจาก test_ylo_achievement_by_year.py ที่ทดสอบผ่าน endpoint
จริง ซึ่งอ่าน "วันนี้" ผ่าน _today() ภายใน เลยต้อง monkeypatch แทน)

cohort 66 เข้าปีการศึกษา 2566 (พ.ศ.) = มิถุนายน ค.ศ. 2023 - cutoff เดือนมิถุนายนของทุกปีเลื่อนชั้นปีขึ้น 1
"""
from __future__ import annotations

from datetime import date

from app.services.year_level import current_year_level, min_cohort_year_for_level


class TestCurrentYearLevel:
    def test_year_1_right_after_entry_cutoff(self):
        result = current_year_level(66, today=date(2023, 6, 1))
        assert result.level == 1
        assert result.beyond_curriculum is False

    def test_still_year_1_just_before_next_cutoff(self):
        result = current_year_level(66, today=date(2024, 5, 31))
        assert result.level == 1

    def test_year_2_right_after_next_cutoff(self):
        result = current_year_level(66, today=date(2024, 6, 1))
        assert result.level == 2

    def test_year_3(self):
        result = current_year_level(66, today=date(2025, 7, 1))
        assert result.level == 3
        assert result.beyond_curriculum is False

    def test_year_4_still_within_curriculum(self):
        result = current_year_level(66, today=date(2026, 7, 1))
        assert result.level == 4
        assert result.beyond_curriculum is False

    def test_year_5_is_beyond_curriculum_not_clamped(self):
        result = current_year_level(66, today=date(2027, 7, 1))
        assert result.level == 5
        assert result.beyond_curriculum is True

    def test_beyond_curriculum_level_keeps_growing(self):
        result = current_year_level(66, today=date(2030, 7, 1))
        assert result.level == 8
        assert result.beyond_curriculum is True

    def test_future_cohort_clamped_to_minimum_year_1(self):
        # cohort_year ในอนาคต (ยังไม่ถึงปีที่เข้าจริง) - level ดิบติดลบ/ศูนย์ ต้อง clamp ที่ 1 เสมอ
        result = current_year_level(70, today=date(2023, 6, 1))
        assert result.level == 1
        assert result.beyond_curriculum is False

    def test_defaults_to_real_today_when_not_given(self):
        # แค่เช็คว่าไม่ raise และคืนค่าที่สมเหตุสมผล (level >= 1) - ไม่ assert ค่าตายตัว เพราะขึ้นกับ
        # วันที่รันจริง
        result = current_year_level(66)
        assert result.level >= 1


class TestMinCohortYearForLevel:
    def test_is_inverse_of_current_year_level(self):
        today = date(2026, 9, 1)
        for level in range(1, 6):
            threshold = min_cohort_year_for_level(level, today=today)
            assert current_year_level(threshold, today=today).level == level

    def test_newer_cohort_than_threshold_falls_below_level(self):
        # ระดับ >= 2 เท่านั้น (level=1 ถูก clamp ขั้นต่ำไว้ที่ 1 เสมอ ไม่มีทางต่ำกว่านี้ให้เทียบ)
        today = date(2026, 9, 1)
        for level in range(2, 6):
            threshold = min_cohort_year_for_level(level, today=today)
            # รุ่นใหม่กว่า threshold 1 ปี (ตัวเลขมากกว่า) ต้องมีชั้นปีต่ำกว่า level นี้เสมอ
            assert current_year_level(threshold + 1, today=today).level == level - 1

    def test_older_cohort_than_threshold_still_satisfies_level(self):
        today = date(2026, 9, 1)
        threshold = min_cohort_year_for_level(2, today=today)
        # รุ่นเก่ากว่า threshold (ตัวเลขน้อยกว่า) ต้องมีชั้นปี >= 2 เสมอ (เรียนมานานกว่า)
        assert current_year_level(threshold - 1, today=today).level >= 2
