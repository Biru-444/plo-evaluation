"""
ทำอะไร : แกนคำนวณ "% บรรลุ PLO" ของนักศึกษา — ย้ายออกมาจาก app/routes/plo_calculation.py เดิม (ตรรกะ
         เดียวเป๊ะ ไม่มีการแก้สูตร) เพื่อให้มี service กลางที่ทั้ง endpoint เดิมและ export รายงาน PLO
         (plo_report_export_service.py) เรียกใช้ร่วมกัน ไม่มีสูตรคำนวณซ้ำสองชุดที่อาจ drift

สูตรคำนวณ (ค่าเฉลี่ยถ่วงน้ำหนักต่อเนื่อง - Workstream 3) :
  1. ระดับความเชี่ยวชาญ (mastery) ของแต่ละ CLO = ค่าเฉลี่ยถ่วงน้ำหนักของ % คะแนนที่นักศึกษาได้ในทุก
     assessment item ที่วัด CLO นั้น ถ่วงน้ำหนักด้วย item_clo.weight_percent (สูตรเดียวกับใน
     clo_calculation.py) — CLO ที่นักศึกษาไม่มีคะแนนบันทึกไว้เลยจะไม่มีค่า mastery
  2. CLO จะ "ผ่าน" (ใช้แสดงผลแยกต่างหากเท่านั้น เช่น course-breakdown - ไม่เข้าสูตร PLO ด้านล่าง) ก็
     ต่อเมื่อ mastery >= pass_threshold_percent ของ CLO นั้นเอง ไม่มีค่า mastery = ไม่ผ่าน
  3. PLO_x (ต่อนักศึกษา 1 คน) = Σ(mastery_i × weight_i) / Σ(weight_i) โดย i วิ่งผ่านทุก CLO ที่ผูกกับ
     PLO_x โดยตรงผ่าน clo_plo_mapping (ข้าม CLO ที่นักศึกษาคนนั้นไม่มี mastery เลย - ไม่นับเป็น 0)
     weight_i คือ clo_plo_mapping.weight_percent ของคู่ CLO-PLO นั้นๆ โดยเฉพาะ ไม่จัดกลุ่มตามวิชา
     ผลรวมน้ำหนักของ CLO ทุกตัวที่ผูกกับ PLO ข้อหนึ่งๆ ไม่บังคับต้องเท่า 100 PLO ที่ไม่มี CLO ผูกอยู่
     เลย หรือมี CLO ผูกอยู่แต่นักศึกษาไม่มี mastery ของ CLO เหล่านั้นเลยสักตัว ได้ PLO_x = 0.0
  4. is_achieved = PLO_x >= PLO_ACHIEVEMENT_THRESHOLD_PERCENT (ค่าคงที่เดียวทั้งระบบ ไม่มี threshold
     แยกต่อ PLO) achieved_percent คือค่า PLO_x ตรงๆ (ต่อเนื่อง 0-100 จริง) - สูตร/เกณฑ์รายบุคคลนี้ไม่
     เปลี่ยนจาก TASK-plo-denominator เลย

ตัวหารสถิติระดับรุ่น/หลักสูตร (TASK-plo-denominator, 2026-09) :
  ระบบประเมินรายชั้นปี นักศึกษาที่ยังไม่ได้เรียนวิชาที่วัด PLO ข้อหนึ่งเป็นกรณี "ยังไม่มีข้อมูล" ไม่ใช่
  "ไม่ผ่าน" - สถิติระดับรุ่น (average_achieved_percent, achieved_rate_percent, all_plo_achieved_percent)
  จึงหารด้วย**นักศึกษาที่มีข้อมูลของ PLO นั้น** (has_data=True) ไม่ใช่นักศึกษาทั้งหมด ให้ตรงกับหลักการ
  เดียวกับ clo_achievement_service.py ที่หารด้วย passed+failed อยู่แล้ว ไม่หารด้วยทุกคนที่ลงทะเบียน
  has_data ของนักศึกษา 1 คนต่อ PLO 1 ข้อ = True เมื่อมี CLO ที่ผูกกับ PLO นั้นอย่างน้อย 1 ตัวที่คนนั้นมี
  mastery จริง (Σweight ของ CLO ที่นับได้ > 0 ใน _student_plo_score) - นักศึกษาที่มีคะแนนจริงแต่ได้ 0%
  ยังนับว่า has_data=True (มีหลักฐาน แค่คะแนนต่ำ) ต่างจากคนที่ยังไม่มีคะแนน CLO นั้นเลยสักตัว
  (has_data=False) ตัวเลข coverage_percent (สัดส่วนคนมีข้อมูลจากทั้งหมด) ต้องคู่กับ average/rate เสมอ
  ให้ผู้อ่านรู้ว่าตัวเลขมาจากกี่คน - ถ้า count_with_data=0 average/rate เป็น None (หารไม่ได้ ไม่ใช่ 0)
  สูตรรายบุคคล (PLO_x) และเกณฑ์บรรลุ 60% ไม่เปลี่ยนเลย มีแค่ตัวหารตอนสรุปเป็นระดับรุ่นเท่านั้นที่เปลี่ยน

เชื่อมกับ : - อ่าน/เขียนผ่านตาราง clo_plo_mapping, course, clo, item_clo, assessment_item,
              student_score (course_plo ไม่ได้ใช้คำนวณตรงนี้ — ใช้แสดง Curriculum Mapping เท่านั้น)
            - app/routes/plo_calculation.py import ฟังก์ชันในนี้ทั้งหมดมาใช้ในทุก endpoint (คงพฤติกรรม
              เดิมทุกประการ - ดู compute_cohort_plo_achievement ที่ endpoint /achievement/cohort
              เรียกตรงๆ) app/routes/courses.py (enrolled-students ?plo_id=) และ
              app/routes/ylo_calculation.py (_clo_passed) ยัง import ฟังก์ชันพวกนี้ผ่าน
              app.routes.plo_calculation เหมือนเดิม (ไฟล์นั้นยังคง import จากที่นี่แล้ว re-export ต่อ
              ไม่ต้องแก้ import 2 ไฟล์นั้น)
            - app/services/plo_report_export_service.py เรียก compute_cohort_plo_achievement ตัวเดียว
              กับ endpoint /achievement/cohort เพื่อให้ตัวเลขในรายงาน Excel ตรงกับหน้าเว็บเป๊ะ

ถ้าแก้ : แก้สูตรในไฟล์นี้ (โดยเฉพาะที่มาของ CLO ที่นับเป็นหลักฐานของ PLO, น้ำหนัก, หรือเกณฑ์ผ่าน CLO) จะ
         กระทบ % บรรลุ PLO ทั้งระบบทันที (หน้าภาพรวม PLO, ผลบรรลุรายบุคคล, export รายงาน PLO) รวมถึง
         ทำให้ผลของ tests/test_plo_achievement_cohort.py เปลี่ยนไปด้วย

         PLO_ACHIEVEMENT_THRESHOLD_PERCENT (60.0) ตั้งให้ตรงกับ CLO.pass_threshold_percent's
         server_default (60.00) และ threshold ที่ frontend ใช้อยู่แล้วหลายจุด - เป็นค่าคงที่เดียวทั้ง
         ระบบ (ไม่ใช่ตั้งแยกได้ต่อ PLO เหมือน CLO.pass_threshold_percent) แก้ค่านี้กระทบ is_achieved/
         achieved_rate_percent/all_plo_achieved_count ทั้งระบบทันที
"""
from __future__ import annotations

from decimal import Decimal

from sqlalchemy.orm import Session

from app.models import (
    CLO,
    CLOPLOMapping,
    Course,
    CourseOffering,
    Curriculum,
    Enrollment,
    AssessmentItem,
    ItemCLO,
    PLO,
    Student,
    StudentScore,
)
from app.schemas.plo_calculation import (
    CurriculumPLOAchievement,
    PLOAchievementItem,
    PLOCohortSummaryItem,
    StudentPLOAchievement,
)

# เกณฑ์ตัดสิน is_achieved จาก PLO_x ที่เป็นค่าต่อเนื่องแล้ว - ค่าคงที่เดียวทั้งระบบ (ไม่แยกต่อ PLO) ดู
# module docstring ด้านบนสำหรับเหตุผลที่เลือก 60.0
PLO_ACHIEVEMENT_THRESHOLD_PERCENT = Decimal("60.0")


def _build_plo_requirements(
    db: Session, curriculum_id: int
) -> tuple[dict[int, dict[int, Decimal]], dict[int, dict[int, set[int]]], dict[int, Decimal]]:
    """
    ทำอะไร : อ่านตาราง clo_plo_mapping รอบเดียว แล้วจัดเป็น 3 โครงสร้างที่ต่างกัน ให้แต่ละ caller ใช้ตาม
             ต้องการ (คำนวณต่อหลักสูตรเพียงครั้งเดียว ไม่ใช่ต่อนักศึกษา แล้วนำผลไปใช้ซ้ำกับนักศึกษาทุกคน
             ในรุ่น เพื่อลดจำนวน query) คืนค่าเป็น 3 ตัว :
               1. plo_clo_weights[plo_id][clo_id] = weight_percent ของคู่ CLO-PLO นั้น - ใช้เข้าสูตร
                  PLO_x = Σ(mastery×weight)/Σ(weight) โดยตรง **ไม่จัดกลุ่มตามวิชา**
               2. plo_course_clo_ids[plo_id][course_id] = เซตของ CLO id ที่ผูกกับ PLO นั้นและสังกัดวิชา
                  นั้น (โครงเดิม - ยังต้องมีไว้ให้ courses.py::get_course_enrolled_students(?plo_id=)
                  และ get_student_plo_course_breakdown ที่ยังเป็น all-or-nothing ต่อวิชาเหมือนเดิม)
               3. clo_pass_thresholds[clo_id] = เกณฑ์ผ่านของ CLO นั้น (ไม่เปลี่ยน)

    เชื่อมกับ : - อ่านจากตาราง clo_plo_mapping, clo, course — กรองเฉพาะ CLO ของวิชาที่อยู่ในหลักสูตรนี้
                  เท่านั้น (course_plo ไม่ได้ใช้ตรงนี้แล้ว — ดูโมดูล docstring ด้านบน)
                - ถูกเรียกจากทุก endpoint ในไฟล์นี้ที่ต้องคำนวณผลบรรลุ PLO รวมถึง
                  courses.py::get_course_enrolled_students (?plo_id=)

    ถ้าแก้ : เปลี่ยนที่มาของ CLO ที่นับเป็นหลักฐานตรงนี้ จะทำให้ % บรรลุ PLO เปลี่ยนทั้งระบบทันที
    """
    rows = (
        db.query(
            CLOPLOMapping.plo_id,
            CLO.course_id,
            CLO.id,
            CLO.pass_threshold_percent,
            CLOPLOMapping.weight_percent,
        )
        .join(CLO, CLO.id == CLOPLOMapping.clo_id)
        .join(Course, Course.id == CLO.course_id)
        .filter(Course.curriculum_id == curriculum_id)
        .all()
    )
    plo_clo_weights: dict[int, dict[int, Decimal]] = {}
    plo_course_clo_ids: dict[int, dict[int, set[int]]] = {}
    clo_pass_thresholds: dict[int, Decimal] = {}
    for plo_id, course_id, clo_id, threshold, weight in rows:
        plo_clo_weights.setdefault(plo_id, {})[clo_id] = weight
        plo_course_clo_ids.setdefault(plo_id, {}).setdefault(course_id, set()).add(clo_id)
        clo_pass_thresholds[clo_id] = threshold
    return plo_clo_weights, plo_course_clo_ids, clo_pass_thresholds


def _qualifying_plo_ids(plo_clo_weights: dict[int, dict[int, Decimal]]) -> set[int]:
    """
    ทำอะไร : หา PLO ที่มี CLO ผูกอยู่อย่างน้อย 1 ตัวผ่านเกณฑ์การคำนวณ (คือมี key อยู่ใน
             plo_clo_weights เลย — _build_plo_requirements ใส่ key เฉพาะ plo_id ที่เจอ clo_plo_mapping
             จริงเท่านั้น)

    เชื่อมกับ : ใช้ตัดสินว่า PLO ข้อไหนควรถูกนับเป็นส่วนหนึ่งของ "บรรลุ PLO ครบทุกข้อ" (สถิติวงแหวนหน้า
                "ภาพรวม PLO" ดู all_plo_achieved_count/_count_all_qualifying_plo_achieved) — dynamic
                ตามข้อมูล clo_plo_mapping จริงเสมอ ไม่ hardcode รายชื่อ PLO ที่ตัดออก

    ถ้าแก้ : ถ้าข้อมูล clo_plo_mapping เปลี่ยน (เช่นมีคนเติม mapping ให้ PLO ที่เคยไม่มี CLO ผูกเลย)
             ผลลัพธ์จะเปลี่ยนตามอัตโนมัติโดยไม่ต้องแก้โค้ดจุดนี้ — ถ้าลบฟังก์ชันนี้ไป วงแหวน "บรรลุครบทุก
             ข้อ" จะค้างที่ 0% เสมอ เพราะ PLO ที่ไม่มี CLO ผูกเลยเป็นไปไม่ได้อยู่แล้วโดยดีไซน์
    """
    return {plo_id for plo_id, clo_weights in plo_clo_weights.items() if clo_weights}


def _clo_passed(
    clo_id: int, clo_mastery: dict[int, Decimal], clo_pass_thresholds: dict[int, Decimal]
) -> bool:
    """
    ทำอะไร : ตัดสินว่านักศึกษา "ผ่าน" CLO ข้อนี้หรือไม่ — ผ่านก็ต่อเมื่อ mastery >=
             pass_threshold_percent ของ CLO นั้นเอง ไม่มีข้อมูลคะแนนเลย (mastery หา key ไม่เจอ) = ไม่ผ่าน

    เชื่อมกับ : ใช้กฎเดียวกับที่ clo_calculation.py ใช้แยก "students_without_data" — ถูกเรียกโดย
                _student_passed_course_for_plo และ app/routes/ylo_calculation.py (import ผ่าน
                app.routes.plo_calculation ที่ re-export ชื่อนี้จากที่นี่)

    ถ้าแก้ : เปลี่ยนเกณฑ์ตรงนี้กระทบทั้งผลบรรลุ PLO และ YLO พร้อมกัน เพราะสองไฟล์ใช้ฟังก์ชันเดียวกัน
    """
    mastery = clo_mastery.get(clo_id)
    if mastery is None:
        return False
    threshold = clo_pass_thresholds.get(clo_id)
    if threshold is None:
        return False
    return mastery >= threshold


def _student_passed_course_for_plo(
    course_clo_ids: set[int], clo_mastery: dict[int, Decimal], clo_pass_thresholds: dict[int, Decimal]
) -> bool:
    """
    ทำอะไร : ตัดสินว่านักศึกษา "ผ่านวิชานี้สำหรับ PLO นี้" หรือไม่ — ผ่านก็ต่อเมื่อผ่านทุก CLO ในกลุ่มนี้
             (course_clo_ids คือ CLO ของวิชาที่ถูกผูกกับ PLO นี้โดยตรงผ่าน clo_plo_mapping เท่านั้น
             อาจเป็นแค่บางส่วนของ CLO ทั้งหมดในวิชา — ดู docstring ของ _build_plo_requirements)

    เชื่อมกับ : เรียก _clo_passed ทีละ CLO — ถูกเรียกโดย courses.py::get_course_enrolled_students และ
                get_student_plo_course_breakdown (ยังเป็น all-or-nothing ต่อวิชาเหมือนเดิม)

    ถ้าแก้ : ถ้าเปลี่ยนจาก all() เป็น any() จะทำให้ผ่านวิชาง่ายขึ้นมาก (แค่ CLO เดียวผ่านก็พอ) ซึ่ง
             ขัดกับ spec ที่ยืนยันแล้วว่าต้องผ่านทุก CLO
    """
    return all(_clo_passed(clo_id, clo_mastery, clo_pass_thresholds) for clo_id in course_clo_ids)


def _student_plo_score(
    clo_weights: dict[int, Decimal], clo_mastery: dict[int, Decimal]
) -> tuple[Decimal, bool]:
    """
    ทำอะไร : PLO_x ของนักศึกษา 1 คน = Σ(mastery_i × weight_i) / Σ(weight_i) - สูตรหลัก (ดู module
             docstring) clo_weights คือ {clo_id: weight_percent} ของ PLO ข้อเดียว (จาก
             plo_clo_weights[plo_id] ที่ _build_plo_requirements สร้างไว้) - CLO ที่นักศึกษาไม่มี
             mastery เลย (ไม่เคยมีคะแนนบันทึกไว้สักชิ้นงาน) ถูกข้ามไปทั้งตัวตั้งและตัวหาร ไม่นับเป็น 0
             คืนค่าเป็นคู่ (score, has_data) - has_data = weight_total > 0 (TASK-plo-denominator) บอกว่า
             ตัวเลข score นี้มีหลักฐานจริงหรือเป็นแค่ 0.0 เพราะยังไม่มีข้อมูลให้คำนวณเลย

    เชื่อมกับ : ถูกเรียกโดย _calculate_plo_achievement_from_mastery ทีละ PLO - ผลลัพธ์นี้คือค่า
                achieved_percent/has_data ที่แสดงบนหน้าภาพรวม PLO / ผลบรรลุรายบุคคล / export รายงาน PLO
                ทุกจุด

    ถ้าแก้ : เป็นจุดตัดสินใจหลักของทั้งระบบ แก้ตรงนี้กระทบ achieved_percent/is_achieved/has_data ทุกที่ -
             ผลรวมน้ำหนัก (weight_total) เป็น 0 ได้ 2 กรณี: (1) PLO นี้ไม่มี CLO ผูกอยู่เลย (clo_weights
             ว่าง) (2) มี CLO ผูกอยู่แต่นักศึกษาไม่มี mastery ของ CLO เหล่านั้นเลยสักตัว - ทั้งสองกรณีคืน
             (0.0, False) เหมือนกัน (ไม่มีหลักฐานให้คำนวณ ไม่ใช่บรรลุอัตโนมัติ) นักศึกษาที่มี mastery
             จริงแต่ได้คะแนนต่ำ (เช่น 0%) ยังคืน has_data=True เสมอ (weight_total > 0) - อย่าสับสนกับ
             achieved_percent == 0.0 ซึ่งเกิดได้ทั้งสองกรณี ต้องเช็ค has_data แยกต่างหากเท่านั้น
    """
    weighted_sum = Decimal(0)
    weight_total = Decimal(0)
    for clo_id, weight in clo_weights.items():
        mastery = clo_mastery.get(clo_id)
        if mastery is None:
            continue
        weighted_sum += mastery * weight
        weight_total += weight
    if weight_total == 0:
        return Decimal("0.0"), False
    return (weighted_sum / weight_total).quantize(Decimal("0.1")), True


def _clo_mastery_for_student(
    db: Session, student_id: str, course_id_filter: set[int] | None = None
) -> dict[int, Decimal]:
    """
    ทำอะไร : คำนวณระดับความเชี่ยวชาญ (mastery) ของนักศึกษา 1 คน แยกเป็นราย CLO ที่เคยถูกประเมิน
             สูตรคือค่าเฉลี่ยถ่วงน้ำหนัก (weighted average) ของ % คะแนนแต่ละชิ้นงาน โดยถ่วงน้ำหนักด้วย
             item_clo.weight_percent (สูตรเดียวกับใน clo_calculation.py) — CLO ที่ไม่มี key อยู่ใน
             dict ที่คืนกลับมา แปลว่าไม่มีข้อมูลคะแนนเลยสักชิ้นงาน (ดู _clo_passed)

    เชื่อมกับ : - อ่านจากตาราง enrollment, assessment_item, student_score, item_clo
                - course_id_filter (ถ้าใส่มา) จำกัดเฉพาะวิชาที่นักศึกษาลงทะเบียนในกลุ่มนั้น ใช้โดย
                  endpoint by-year เพื่อคิดคะแนนเฉพาะวิชาของปีนั้น ๆ ไม่ใส่ = นับทุกวิชาที่ลงทะเบียน

    ถ้าแก้ : เป็นสูตรคำนวณ mastery หลักของทั้งระบบ (ใช้ตัดสิน CLO ผ่าน/ไม่ผ่าน) แก้สูตรตรงนี้กระทบ
             % บรรลุ PLO ทุกจุดที่พึ่งพา mastery
    """
    offering_query = db.query(Enrollment.offering_id).filter(Enrollment.student_id == student_id)
    if course_id_filter is not None:
        offering_query = offering_query.join(
            CourseOffering, CourseOffering.id == Enrollment.offering_id
        ).filter(CourseOffering.course_id.in_(course_id_filter))
    offering_ids = [row[0] for row in offering_query.all()]

    item_by_id: dict[int, AssessmentItem] = {}
    score_by_item: dict[int, Decimal] = {}
    item_clos: list[ItemCLO] = []

    if offering_ids:
        items = (
            db.query(AssessmentItem)
            .filter(AssessmentItem.offering_id.in_(offering_ids))
            .all()
        )
        item_by_id = {item.id: item for item in items}

        if item_by_id:
            scores = (
                db.query(StudentScore)
                .filter(
                    StudentScore.student_id == student_id,
                    StudentScore.item_id.in_(item_by_id.keys()),
                )
                .all()
            )
            score_by_item = {s.item_id: s.score_obtained for s in scores}

            item_clos = (
                db.query(ItemCLO).filter(ItemCLO.item_id.in_(item_by_id.keys())).all()
            )

    clo_weighted_sum: dict[int, Decimal] = {}
    clo_weight_total: dict[int, Decimal] = {}
    for ic in item_clos:
        score = score_by_item.get(ic.item_id)
        item = item_by_id.get(ic.item_id)
        # ข้ามชิ้นงานที่ยังไม่มีคะแนน หรือคะแนนเต็มเป็น 0 (หารไม่ได้) — ไม่นับรวมเข้าสูตรเลย ไม่ใช่นับเป็น 0
        if score is None or item is None or item.total_score <= 0:
            continue
        # แปลงคะแนนดิบเป็น % ก่อน (เช่น 18/20 -> 90%) แล้วค่อยถ่วงน้ำหนักด้วย weight_percent ของ
        # item_clo แต่ละอัน สะสมทั้งตัวตั้ง (weighted_sum) และตัวหาร (weight_total) แยกตาม CLO
        item_percent = (score / item.total_score) * Decimal(100)
        clo_weighted_sum[ic.clo_id] = clo_weighted_sum.get(ic.clo_id, Decimal(0)) + item_percent * ic.weight_percent
        clo_weight_total[ic.clo_id] = clo_weight_total.get(ic.clo_id, Decimal(0)) + ic.weight_percent

    # mastery ของแต่ละ CLO = weighted_sum / weight_total (ถ่วงน้ำหนักเฉลี่ย) — CLO ที่ weight_total
    # เป็น 0 (ไม่มีชิ้นงานที่มีคะแนนเลย) จะไม่มี key อยู่ใน dict ที่คืนกลับ ไม่ใช่คืนค่า 0
    return {
        clo_id: clo_weighted_sum[clo_id] / clo_weight_total[clo_id]
        for clo_id in clo_weighted_sum
        if clo_weight_total[clo_id] > 0
    }


def _clo_mastery_for_students_batch(
    db: Session, student_ids: list[str], course_id_filter: set[int] | None = None
) -> dict[str, dict[int, Decimal]]:
    """
    ทำอะไร : เหมือน _clo_mastery_for_student ทุกประการ (สูตร weighted average เดียวกัน) แต่คำนวณให้
             หลายคนพร้อมกันด้วย query ชุดเดียว คืนค่า {student_id: {clo_id: mastery}} ครบทุก
             student_id ที่ส่งมาเสมอ (dict ว่างถ้าคนนั้นไม่มีข้อมูลเลย ไม่ใช่ key หายไป)

    เชื่อมกับ : ใช้ตอนต้องได้ CLO mastery ของนักศึกษาทั้ง roster พร้อมกัน — เรียกโดย
                compute_cohort_plo_achievement และ get_plo_achievement_by_year

    ถ้าแก้ : ห้ามเปลี่ยนกลับไปวนเรียก _clo_mastery_for_student ทีละคนในลูป เพราะจะกลายเป็น N+1
             query — รุ่นที่มีนักศึกษาเยอะ (~200 คน) เคยทำให้ backend ตอบช้าจนเกิน timeout ของ
             frontend แม้จะคำนวณเสร็จถูกต้องในที่สุดก็ตาม
    """
    result: dict[str, dict[int, Decimal]] = {sid: {} for sid in student_ids}
    if not student_ids:
        return result

    offering_query = db.query(Enrollment.student_id, Enrollment.offering_id).filter(
        Enrollment.student_id.in_(student_ids)
    )
    if course_id_filter is not None:
        offering_query = offering_query.join(
            CourseOffering, CourseOffering.id == Enrollment.offering_id
        ).filter(CourseOffering.course_id.in_(course_id_filter))
    enrollment_rows = offering_query.all()

    offering_ids_by_student: dict[str, set[int]] = {}
    all_offering_ids: set[int] = set()
    for student_id, offering_id in enrollment_rows:
        offering_ids_by_student.setdefault(student_id, set()).add(offering_id)
        all_offering_ids.add(offering_id)

    if not all_offering_ids:
        return result

    items = db.query(AssessmentItem).filter(AssessmentItem.offering_id.in_(all_offering_ids)).all()
    item_by_id: dict[int, AssessmentItem] = {item.id: item for item in items}
    if not item_by_id:
        return result

    item_clos = db.query(ItemCLO).filter(ItemCLO.item_id.in_(item_by_id.keys())).all()
    scores = (
        db.query(StudentScore)
        .filter(
            StudentScore.student_id.in_(student_ids),
            StudentScore.item_id.in_(item_by_id.keys()),
        )
        .all()
    )
    score_by_student_item: dict[tuple[str, int], Decimal] = {
        (s.student_id, s.item_id): s.score_obtained for s in scores
    }

    for student_id in student_ids:
        enrolled_offering_ids = offering_ids_by_student.get(student_id)
        if not enrolled_offering_ids:
            continue
        clo_weighted_sum: dict[int, Decimal] = {}
        clo_weight_total: dict[int, Decimal] = {}
        for ic in item_clos:
            item = item_by_id.get(ic.item_id)
            if item is None or item.offering_id not in enrolled_offering_ids:
                continue
            score = score_by_student_item.get((student_id, ic.item_id))
            if score is None or item.total_score <= 0:
                continue
            item_percent = (score / item.total_score) * Decimal(100)
            clo_weighted_sum[ic.clo_id] = clo_weighted_sum.get(ic.clo_id, Decimal(0)) + item_percent * ic.weight_percent
            clo_weight_total[ic.clo_id] = clo_weight_total.get(ic.clo_id, Decimal(0)) + ic.weight_percent
        result[student_id] = {
            clo_id: clo_weighted_sum[clo_id] / clo_weight_total[clo_id]
            for clo_id in clo_weighted_sum
            if clo_weight_total[clo_id] > 0
        }
    return result


def _calculate_plo_achievement_from_mastery(
    student: Student,
    plos: list[PLO],
    clo_mastery: dict[int, Decimal],
    plo_clo_weights: dict[int, dict[int, Decimal]],
) -> StudentPLOAchievement:
    """
    ทำอะไร : รวม CLO mastery ของนักศึกษา 1 คนขึ้นเป็นผลบรรลุ PLO ทุกข้อ (คำนวณล้วน ๆ ไม่แตะฐานข้อมูล)
             ใช้ plo_clo_weights ที่คำนวณไว้แล้วระดับหลักสูตร (เหมือนกันทุกนักศึกษา) ร่วมกับ clo_mastery
             ของนักศึกษาคนนั้นที่ดึงมาก่อนหน้าแล้ว

    เชื่อมกับ : เรียก _student_plo_score ทีละ PLO — ถูกเรียกโดย get_plo_achievement (รายบุคคล),
                compute_cohort_plo_achievement และ get_plo_achievement_by_year เพื่อให้ดึงรายชื่อ PLO
                และคำนวณ mastery ของทั้ง roster ได้ครั้งเดียว แทนที่จะ query ซ้ำทุกครั้งต่อนักศึกษา 1 คน

    ถ้าแก้ : ถ้าเปลี่ยนให้ query ข้อมูลเพิ่มในฟังก์ชันนี้ จะเสียจุดประสงค์ของการ batch ไป
    """
    achievements = []
    for plo in plos:
        score, has_data = _student_plo_score(plo_clo_weights.get(plo.id, {}), clo_mastery)
        achievements.append(
            PLOAchievementItem(
                plo_id=plo.id,
                plo_code=plo.code,
                description=plo.description_th,
                achieved_percent=float(score),
                is_achieved=score >= PLO_ACHIEVEMENT_THRESHOLD_PERCENT,
                has_data=has_data,
            )
        )

    return StudentPLOAchievement(
        student_id=student.id,
        student_name=f"{student.first_name} {student.last_name}",
        curriculum_id=student.curriculum_id,
        plo_achievements=achievements,
    )


def _calculate_plo_achievement_for_student(
    db: Session,
    student: Student,
    plo_clo_weights: dict[int, dict[int, Decimal]],
    course_id_filter: set[int] | None = None,
) -> StudentPLOAchievement:
    """
    ทำอะไร : เวอร์ชันรายบุคคล — ดึงรายชื่อ PLO และ CLO mastery ของนักศึกษาคนนี้เอง แล้วคำนวณผลบรรลุ

    เชื่อมกับ : เรียกโดย GET /plo/achievement (endpoint รายบุคคลเท่านั้น) — endpoint ระดับ cohort/
                by-year ใช้ _calculate_plo_achievement_from_mastery แบบ batch แทน เพื่อไม่ต้อง query
                รายชื่อ PLO และ mastery ซ้ำทุกคนในรุ่น

    ถ้าแก้ : ปลอดภัยที่จะ query ต่อครั้งที่นี่ เพราะมีผู้เรียกเดียวคือ endpoint รายบุคคล (1 คนต่อ 1
             request) ไม่ใช่จุดที่ทำให้เกิด N+1 query เหมือน endpoint ระดับ cohort
    """
    plos = (
        db.query(PLO)
        .filter(PLO.curriculum_id == student.curriculum_id)
        .order_by(PLO.code)
        .all()
    )
    clo_mastery = _clo_mastery_for_student(db, student.id, course_id_filter)
    return _calculate_plo_achievement_from_mastery(student, plos, clo_mastery, plo_clo_weights)


def _aggregate_plo_percent_stats(
    student_achievements: list[StudentPLOAchievement],
) -> tuple[dict[int, Decimal], dict[int, int], dict[int, int]]:
    """
    ทำอะไร : รวมยอด achieved_percent (เฉพาะคนที่ has_data=True) และนับจำนวนนักศึกษาที่มีข้อมูล / ที่บรรลุ
             แยกตาม PLO แต่ละข้อ (ใช้คิดค่าเฉลี่ยและอัตราการบรรลุของทั้งรุ่น - ดู _compute_plo_rate_stats
             ที่ใช้ผลลัพธ์นี้หารด้วย count_with_data แทนจำนวนนักศึกษาทั้งหมด)

    เชื่อมกับ : ใช้ร่วมกันโดย compute_cohort_plo_achievement และ GET /achievement/by-year เพื่อให้
                ตรรกะหาค่าเฉลี่ยระดับรุ่น (cohort-level averaging) อยู่ที่เดียวไม่ซ้ำโค้ด

    ถ้าแก้ : ถ้าแก้เงื่อนไขการนับตรงนี้ จะกระทบทั้ง average_achieved_percent, achieved_rate_percent
             และ coverage_percent ที่แสดงในหน้าภาพรวม PLO และ YLO ตามชั้นปีพร้อมกัน
    """
    percent_sum_by_plo: dict[int, Decimal] = {}
    # count_with_data_by_plo นับจาก has_data ตรงๆ (TASK-plo-denominator - เดิมนับจาก achieved_percent
    # > 0 ซึ่งผิด: นักศึกษาที่มีคะแนนจริงแต่ได้ 0% เคยถูกนับว่า "ไม่มีข้อมูล" ทั้งที่มีหลักฐานจริง) -
    # percent_sum ก็รวมเฉพาะคนที่ has_data=True เท่านั้นด้วยเหตุผลเดียวกัน (แม้ผลรวมจะเท่าเดิมในทางคณิต-
    # ศาสตร์เพราะคนไม่มีข้อมูลได้ achieved_percent=0.0 เสมออยู่แล้ว แต่กรองไว้ตรงๆ ให้อ่านโค้ดเข้าใจง่าย
    # กว่าไม่ต้องพึ่ง invariant นั้น) - ใช้จริงจากหลายจุดแล้ว: average/rate ระดับรุ่น, export รายงาน PLO
    count_with_data_by_plo: dict[int, int] = {}
    achieved_count_by_plo: dict[int, int] = {}

    for achievement in student_achievements:
        for item in achievement.plo_achievements:
            if item.has_data:
                percent_sum_by_plo[item.plo_id] = (
                    percent_sum_by_plo.get(item.plo_id, Decimal(0)) + Decimal(str(item.achieved_percent))
                )
                count_with_data_by_plo[item.plo_id] = count_with_data_by_plo.get(item.plo_id, 0) + 1
            if item.is_achieved:
                achieved_count_by_plo[item.plo_id] = achieved_count_by_plo.get(item.plo_id, 0) + 1

    return percent_sum_by_plo, count_with_data_by_plo, achieved_count_by_plo


def _compute_plo_rate_stats(
    percent_sum: Decimal, achieved_count: int, count_with_data: int, total_students: int
) -> tuple[float | None, float | None, float]:
    """
    ทำอะไร : คำนวณ (average_achieved_percent, achieved_rate_percent, coverage_percent) ของ PLO ข้อ
             เดียวระดับรุ่น - average/rate หารด้วย count_with_data (นักศึกษาที่มีข้อมูล) ไม่ใช่
             total_students (TASK-plo-denominator) coverage_percent หารด้วย total_students เสมอ (บอก
             สัดส่วนคนมีข้อมูลจากทั้งหมด ไม่ใช่ตัวหารของ average/rate)

    เชื่อมกับ : ใช้ helper ตัวเดียวนี้ทุกจุดที่ต้องสรุประดับรุ่น (compute_cohort_plo_achievement,
                GET /achievement/by-year) เพื่อไม่ให้สูตร/พฤติกรรม edge case (หารด้วยศูนย์) เพี้ยนไปคนละ
                ทางระหว่างสองจุด

    ถ้าแก้ : count_with_data = 0 -> (None, None, coverage) เสมอ (หารไม่ได้ ไม่ใช่ 0 - ผู้เรียกต้องแสดง
             "ยังไม่มีข้อมูล" ไม่ใช่ 0%) total_students = 0 -> coverage = 0.0 (กันหารศูนย์ แม้ในทาง
             ปฏิบัติ caller จะเช็ค total_students == 0 แยกไว้ก่อนแล้วในกรณีไม่มีนักศึกษาเลย)
    """
    coverage_percent = (
        float((Decimal(count_with_data) / Decimal(total_students) * Decimal(100)).quantize(Decimal("0.1")))
        if total_students > 0
        else 0.0
    )
    if count_with_data == 0:
        return None, None, coverage_percent

    average = float((percent_sum / Decimal(count_with_data)).quantize(Decimal("0.1")))
    rate = float(
        (Decimal(achieved_count) / Decimal(count_with_data) * Decimal(100)).quantize(Decimal("0.1"))
    )
    return average, rate, coverage_percent


def _count_all_qualifying_plo_achieved(
    student_achievements: list[StudentPLOAchievement], qualifying_plo_ids: set[int]
) -> int:
    """
    ทำอะไร : นับจำนวนนักศึกษาที่บรรลุ PLO ครบทุกข้อใน qualifying_plo_ids (ไม่ใช่ครบทุก PLO ในหลักสูตร
             เสมอไป — ดู _qualifying_plo_ids) PLO ที่ไม่มีวิชา "หลัก" ผ่านเกณฑ์เลยไม่ถูกนับ เพราะเป็น
             ไปไม่ได้อยู่แล้วโดยดีไซน์ ไม่ควรทำให้ไม่มีใครนับว่า "บรรลุครบ" เลยสักคน

    เชื่อมกับ : ใช้คำนวณ all_plo_achieved_count ใน compute_cohort_plo_achievement (สถิติวงแหวนหน้า
                "ภาพรวม PLO")

    ถ้าแก้ : 0 qualifying PLO = ไม่มีใครบรรลุครบได้ (edge case ที่ไม่ควรเกิดในทางปฏิบัติ แต่คืน 0
             อย่างปลอดภัยแทนการหารด้วยศูนย์/พังตอนไม่มี PLO เข้าเกณฑ์เลย)
    """
    if not qualifying_plo_ids:
        return 0
    count = 0
    for achievement in student_achievements:
        if all(
            item.is_achieved
            for item in achievement.plo_achievements
            if item.plo_id in qualifying_plo_ids
        ):
            count += 1
    return count


def _count_students_with_complete_data(
    student_achievements: list[StudentPLOAchievement], qualifying_plo_ids: set[int]
) -> int:
    """
    ทำอะไร : นับจำนวนนักศึกษาที่มีข้อมูล (has_data=True) ครบทุก qualifying PLO - คือตัวหานใหม่ของ
             all_plo_achieved_percent (TASK-plo-denominator - เดิมหารด้วยนักศึกษาทั้งหมด) คนที่ยังไม่มี
             ข้อมูลของ PLO ข้อใดข้อหนึ่งเลย ไม่ควรถูกนับเป็นตัวหารของ "บรรลุครบทุกข้อ" เพราะยังตัดสินไม่ได้
             ว่าครบจริงหรือแค่ยังไม่ถึงเวลาวัด

    เชื่อมกับ : ใช้คำนวณ all_plo_data_complete_count คู่กับ all_plo_achieved_count ใน
                compute_cohort_plo_achievement (สถิติวงแหวนหน้า "ภาพรวม PLO")

    ถ้าแก้ : 0 qualifying PLO = ไม่มีใครนับเป็น "มีข้อมูลครบ" ได้ (เหมือน _count_all_qualifying_plo_achieved
             ด้านบน) - all_plo_achieved_percent ต้องเป็น None ถ้าค่าที่ฟังก์ชันนี้คืนเป็น 0
    """
    if not qualifying_plo_ids:
        return 0
    count = 0
    for achievement in student_achievements:
        has_data_by_plo = {item.plo_id: item.has_data for item in achievement.plo_achievements}
        if all(has_data_by_plo.get(plo_id, False) for plo_id in qualifying_plo_ids):
            count += 1
    return count


def compute_cohort_plo_achievement(
    db: Session, curriculum_id: int, cohort_year: int | None = None
) -> CurriculumPLOAchievement | None:
    """
    ทำอะไร : คำนวณสรุปผลบรรลุ PLO ทุกข้อของทั้งหลักสูตร (ค่าเฉลี่ย, อัตราบรรลุ - หารด้วยนักศึกษาที่มี
             ข้อมูลของ PLO นั้น ไม่ใช่นักศึกษาทั้งหมด ดู module docstring เรื่องตัวหารใหม่) พร้อมรายชื่อ
             นักศึกษาทุกคนและผลบรรลุ PLO รายข้อของแต่ละคน กรองตามรุ่น (cohort_year) ได้ ถ้าไม่ใส่จะรวม
             ทุกรุ่น - ย้ายมาจาก app/routes/plo_calculation.py::get_cohort_plo_achievement เดิม (สูตร
             รายบุคคลเหมือนเดิมทุกประการ ตัวหารสรุประดับรุ่นเปลี่ยนตาม TASK-plo-denominator) เพื่อให้
             endpoint เดิมและ export รายงาน PLO (plo_report_export_service.py) เรียกตัวเดียวกัน คืน
             None ถ้าไม่พบ curriculum_id (ผู้เรียกเป็นคนตัดสินใจว่าจะแปลงเป็น HTTPException 404 หรือ
             พฤติกรรมอื่น)

    เชื่อมกับ : ใช้ _build_plo_requirements + _qualifying_plo_ids (คำนวณครั้งเดียวต่อ request) แล้ว
                ดึง CLO mastery ของนักศึกษาทั้ง roster แบบ batch ผ่าน _clo_mastery_for_students_batch
                ก่อนวนคำนวณผลบรรลุทีละคนด้วย _calculate_plo_achievement_from_mastery แล้วสรุปด้วย
                _compute_plo_rate_stats (average/rate/coverage ต่อ PLO) และ
                _count_students_with_complete_data (ตัวหารของ all_plo_achieved_percent) — เรียกโดย
                GET /plo/achievement/cohort (หน้า "ภาพรวม PLO") และ GET /plo/achievement/export

    ถ้าแก้ : ห้ามเปลี่ยนกลับไปคำนวณ mastery ทีละคนในลูป (ดู docstring ของ _clo_mastery_for_students_batch
             เรื่อง N+1 query)
    """
    curriculum = db.get(Curriculum, curriculum_id)
    if curriculum is None:
        return None

    plos = (
        db.query(PLO)
        .filter(PLO.curriculum_id == curriculum_id)
        .order_by(PLO.code)
        .all()
    )

    plo_clo_weights, _plo_course_clo_ids, _clo_pass_thresholds = _build_plo_requirements(
        db, curriculum_id
    )
    qualifying_plo_ids = _qualifying_plo_ids(plo_clo_weights)

    available_cohort_years = sorted(
        {
            row[0]
            for row in db.query(Student.cohort_year)
            .filter(Student.curriculum_id == curriculum_id, Student.cohort_year.isnot(None))
            .distinct()
            .all()
        }
    )

    students_query = db.query(Student).filter(Student.curriculum_id == curriculum_id)
    if cohort_year is not None:
        students_query = students_query.filter(Student.cohort_year == cohort_year)
    students = students_query.all()

    if not students:
        return CurriculumPLOAchievement(
            curriculum_id=curriculum.id,
            curriculum_name=curriculum.name,
            total_students=0,
            plo_summary=[
                PLOCohortSummaryItem(
                    plo_id=plo.id,
                    plo_code=plo.code,
                    description=plo.description_th,
                    student_count_with_data=0,
                    average_achieved_percent=None,
                    achieved_student_count=0,
                    achieved_rate_percent=None,
                    coverage_percent=0.0,
                    has_clo_mapping=plo.id in qualifying_plo_ids,
                )
                for plo in plos
            ],
            students=[],
            available_cohort_years=available_cohort_years,
            all_plo_achieved_percent=None,
            qualifying_plo_count=len(qualifying_plo_ids),
            total_plo_count=len(plos),
        )

    # Batched: one round of queries for every student's CLO mastery instead
    # of one round PER student - a ~200-student roster otherwise means
    # thousands of individual DB round-trips (fine on a local Postgres, slow
    # enough over the network to a hosted DB that the frontend's request
    # timeout fires before the response comes back, even though it eventually
    # would have finished correctly).
    student_ids = [student.id for student in students]
    clo_mastery_by_student = _clo_mastery_for_students_batch(db, student_ids)
    student_achievements = [
        _calculate_plo_achievement_from_mastery(
            student, plos, clo_mastery_by_student.get(student.id, {}), plo_clo_weights
        )
        for student in students
    ]
    # เรียงตามรหัสนักศึกษาจากน้อยไปมาก ไม่ใช่ตามชื่อ (string sort ตรงๆ ไม่ int() - รหัสทดสอบในระบบนี้ไม่ใช่
    # ตัวเลขล้วนเสมอไป)
    students_sorted = sorted(student_achievements, key=lambda sa: sa.student_id)

    total_students = len(students)
    percent_sum_by_plo, count_with_data_by_plo, achieved_count_by_plo = _aggregate_plo_percent_stats(
        student_achievements
    )

    plo_summary = []
    for plo in plos:
        percent_sum = percent_sum_by_plo.get(plo.id, Decimal(0))
        achieved_count = achieved_count_by_plo.get(plo.id, 0)
        count_with_data = count_with_data_by_plo.get(plo.id, 0)

        average_achieved_percent, achieved_rate_percent, coverage_percent = _compute_plo_rate_stats(
            percent_sum, achieved_count, count_with_data, total_students
        )

        plo_summary.append(
            PLOCohortSummaryItem(
                plo_id=plo.id,
                plo_code=plo.code,
                description=plo.description_th,
                student_count_with_data=count_with_data,
                average_achieved_percent=average_achieved_percent,
                achieved_student_count=achieved_count,
                achieved_rate_percent=achieved_rate_percent,
                coverage_percent=coverage_percent,
                has_clo_mapping=plo.id in qualifying_plo_ids,
            )
        )

    all_plo_achieved_count = _count_all_qualifying_plo_achieved(student_achievements, qualifying_plo_ids)
    all_plo_data_complete_count = _count_students_with_complete_data(
        student_achievements, qualifying_plo_ids
    )
    all_plo_achieved_percent = (
        float(
            (Decimal(all_plo_achieved_count) / Decimal(all_plo_data_complete_count) * Decimal(100))
            .quantize(Decimal("0.1"))
        )
        if all_plo_data_complete_count > 0
        else None
    )

    return CurriculumPLOAchievement(
        curriculum_id=curriculum.id,
        curriculum_name=curriculum.name,
        total_students=total_students,
        plo_summary=plo_summary,
        students=students_sorted,
        available_cohort_years=available_cohort_years,
        all_plo_achieved_count=all_plo_achieved_count,
        all_plo_achieved_percent=all_plo_achieved_percent,
        all_plo_data_complete_count=all_plo_data_complete_count,
        qualifying_plo_count=len(qualifying_plo_ids),
        total_plo_count=len(plos),
    )
