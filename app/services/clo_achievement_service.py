"""
ทำอะไร : คำนวณผล CLO ทุกข้อของ course_offering เดียว (ทั้งห้อง) — สูตรเดียวกับ
         plo_calculation.py._clo_mastery_for_student ("ขั้นตอนที่ 1" ของสูตร PLO) ทุกประการ: ค่าเฉลี่ย
         ถ่วงน้ำหนัก sum(score/total_score*100 * item_clo.weight_percent) / sum(item_clo.weight_percent)
         นับเฉพาะ assessment item ที่นักศึกษามีคะแนนบันทึกไว้จริง

         refactor ออกมาจาก app/routes/clo_calculation.py::get_offering_clo_achievement เดิม (ตรรกะเดียว
         เป๊ะ ย้ายมาไว้ที่นี่เฉยๆ) เพราะตอนนี้มี 2 ผู้เรียก: endpoint เดิม (GET /clo-achievement) กับ
         export มคอ.5 (GET /clo-achievement/export/mco5) - ทั้งคู่ต้องได้ตัวเลขตรงกันเป๊ะเสมอ ห้ามมีสูตร
         คำนวณแยกสองชุดที่อาจ drift

เชื่อมกับ : compute_offering_clo_achievement_raw() คือรุ่นละเอียด (Decimal/None แยกแยะ "ไม่มีข้อมูล"
            ออกจาก "ได้ 0% จริง" ได้ตรงๆ) ใช้โดย mco5_export_service.py ที่ต้องการค่าเฉลี่ยเฉพาะคนที่มี
            ข้อมูลจริง (ไม่ปนคนที่ไม่มีคะแนนเข้าไปเป็น 0) - compute_offering_clo_achievement() ห่อรุ่น
            ละเอียดนั้นให้เป็น response shape เดิมของ GET /clo-achievement เป๊ะ (clo_percent/passed ของคน
            ไม่มีข้อมูลกลายเป็น 0.0/False เหมือนพฤติกรรมเดิมก่อน refactor ทุกประการ)

ถ้าแก้ : เปลี่ยนสูตรตรงนี้กระทบทั้ง GET /clo-achievement และไฟล์ export มคอ.5 พร้อมกันทันที ต้องตรงกับ
         สูตรใน plo_calculation.py เสมอ (คนละ scope แต่สูตรเดียวกัน)
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models import (
    CLO,
    AssessmentItem,
    CourseOffering,
    Enrollment,
    ItemCLO,
    Student,
    StudentScore,
)
from app.schemas.clo_calculation import CLOAchievementItem, OfferingCLOAchievement, StudentCLOScore


# ผล CLO ข้อเดียวของนักศึกษา 1 คน แบบละเอียด — clo_percent/passed เป็น None พร้อมกันเสมอเมื่อไม่มี
# ข้อมูล (ต่างจาก response shape เดิมของ GET /clo-achievement ที่ใช้ 0.0/False แทน "ไม่มีข้อมูล" ซึ่งทำให้
# แยกไม่ออกจาก "ได้ 0% จริง" - รุ่นนี้แยกออกได้ตรงๆ ด้วย None)
@dataclass
class StudentCLOResult:
    student: Student
    clo_percent: Decimal | None
    passed: bool | None


# ผล CLO ข้อเดียวของทั้งห้อง แบบละเอียด (รายการ StudentCLOResult + property คำนวณสรุปให้)
@dataclass
class CLOAchievementResult:
    clo: CLO
    student_results: list[StudentCLOResult]
    # ชื่อชิ้นงาน+น้ำหนักที่ผูกกับ CLO นี้ - เก็บไว้ที่นี่เพราะ export มคอ.5 ชีต 2 ต้องใช้ (คอลัมน์
    # "วิธีการประเมิน") ไม่ต้อง query ซ้ำ
    item_clo_mappings: list[ItemCLO]

    @property
    def passed_count(self) -> int:
        return sum(1 for r in self.student_results if r.passed is True)

    @property
    def failed_count(self) -> int:
        return sum(1 for r in self.student_results if r.passed is False)

    @property
    def students_without_data(self) -> int:
        return sum(1 for r in self.student_results if r.clo_percent is None)

    @property
    def achieved_rate_percent(self) -> float:
        """ร้อยละที่ผ่าน คิดจากคนที่ "มีข้อมูลให้ตัดสิน" เท่านั้น (passed+failed) ไม่รวม
        students_without_data เข้าตัวหาร - สูตรเดียวกับ endpoint เดิมทุกประการ"""
        denom = self.passed_count + self.failed_count
        if denom == 0:
            return 0.0
        return round(float(Decimal(self.passed_count) / Decimal(denom) * Decimal(100)), 1)

    @property
    def average_percent_with_data(self) -> Decimal | None:
        """ค่าเฉลี่ย clo_percent เฉพาะคนที่มีข้อมูลจริง (ไม่ปนคนที่ไม่มีคะแนนเป็น 0) - ใช้ในชีต 2 ของ
        export มคอ.5 เท่านั้น ("คะแนนเฉลี่ย (%)") None ถ้าไม่มีใครมีข้อมูลเลย"""
        with_data = [r.clo_percent for r in self.student_results if r.clo_percent is not None]
        if not with_data:
            return None
        return (sum(with_data, Decimal(0)) / Decimal(len(with_data))).quantize(Decimal("0.1"))


def compute_offering_clo_achievement_raw(
    db: Session, offering: CourseOffering
) -> list[CLOAchievementResult]:
    """ทำอะไร : คำนวณผล CLO ทุกข้อของ offering นี้ แบบละเอียด (ดู CLOAchievementResult) - นี่คือ single
    source of truth ของสูตรคำนวณจริง เรียงตาม clo.code"""
    clos = db.query(CLO).filter(CLO.course_id == offering.course_id).order_by(CLO.code).all()

    items = db.query(AssessmentItem).filter(AssessmentItem.offering_id == offering.id).all()
    item_by_id: dict[int, AssessmentItem] = {item.id: item for item in items}

    item_clos: list[ItemCLO] = []
    if item_by_id:
        item_clos = db.query(ItemCLO).filter(ItemCLO.item_id.in_(item_by_id.keys())).all()

    roster: list[Student] = (
        db.query(Student)
        .join(Enrollment, Enrollment.student_id == Student.id)
        .filter(Enrollment.offering_id == offering.id)
        .order_by(Student.id)
        .all()
    )

    scores_by_student_item: dict[tuple[str, int], Decimal] = {}
    if item_by_id and roster:
        student_ids = [s.id for s in roster]
        scores = (
            db.query(StudentScore)
            .filter(
                StudentScore.item_id.in_(item_by_id.keys()),
                StudentScore.student_id.in_(student_ids),
            )
            .all()
        )
        scores_by_student_item = {(s.student_id, s.item_id): s.score_obtained for s in scores}

    item_clos_by_clo: dict[int, list[ItemCLO]] = {}
    for ic in item_clos:
        item_clos_by_clo.setdefault(ic.clo_id, []).append(ic)

    results: list[CLOAchievementResult] = []
    for clo in clos:
        mappings = item_clos_by_clo.get(clo.id, [])
        student_results: list[StudentCLOResult] = []

        for student in roster:
            weighted_sum = Decimal(0)
            weight_total = Decimal(0)
            for ic in mappings:
                item = item_by_id.get(ic.item_id)
                score = scores_by_student_item.get((student.id, ic.item_id))
                if item is None or score is None or item.total_score <= 0:
                    continue
                item_percent = (score / item.total_score) * Decimal(100)
                weighted_sum += item_percent * ic.weight_percent
                weight_total += ic.weight_percent

            if weight_total > 0:
                clo_percent = (weighted_sum / weight_total).quantize(Decimal("0.1"))
                passed = clo_percent >= clo.pass_threshold_percent
                student_results.append(
                    StudentCLOResult(student=student, clo_percent=clo_percent, passed=passed)
                )
            else:
                student_results.append(
                    StudentCLOResult(student=student, clo_percent=None, passed=None)
                )

        results.append(
            CLOAchievementResult(clo=clo, student_results=student_results, item_clo_mappings=mappings)
        )

    return results


def compute_offering_clo_achievement(db: Session, offering: CourseOffering) -> OfferingCLOAchievement:
    """ทำอะไร : ห่อ compute_offering_clo_achievement_raw() ให้เป็น response shape เดิมของ
    GET /clo-achievement เป๊ะ - คนที่ไม่มีข้อมูล (clo_percent/passed เป็น None) กลายเป็น 0.0/False
    เหมือนพฤติกรรมเดิมก่อน refactor ทุกประการ (endpoint เดิมไม่เคยแยก "ไม่มีข้อมูล" ออกจาก "ได้ 0% จริง"
    ในค่าที่คืน - แยกแค่ผ่าน students_without_data count เท่านั้น)"""
    raw_results = compute_offering_clo_achievement_raw(db, offering)

    clo_achievements = [
        CLOAchievementItem(
            clo_id=result.clo.id,
            clo_code=result.clo.code,
            description=result.clo.description,
            pass_threshold_percent=float(result.clo.pass_threshold_percent),
            passed_count=result.passed_count,
            failed_count=result.failed_count,
            students_without_data=result.students_without_data,
            achieved_rate_percent=result.achieved_rate_percent,
            student_scores=[
                StudentCLOScore(
                    student_id=sr.student.id,
                    student_name=f"{sr.student.first_name} {sr.student.last_name}",
                    clo_percent=float(sr.clo_percent) if sr.clo_percent is not None else 0.0,
                    passed=bool(sr.passed),
                )
                for sr in result.student_results
            ],
        )
        for result in raw_results
    ]

    return OfferingCLOAchievement(
        offering_id=offering.id,
        course_name=offering.course.name_th,
        clo_achievements=clo_achievements,
    )
