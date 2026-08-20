"""
Seed the real PLO/YLO text from the CS curriculum's มคอ.2 (revised 2566)
into curriculum_id=1. Separate from seed_data.py so it survives re-running
that script.

seed_data.py already creates placeholder PLO1-9 / YLO year 1-4 rows for
curriculum_id=1 with the same codes/year_levels this script uses, and
plo.code / ylo.year_level are unique per curriculum - so this script
UPSERTs: existing rows (matched by curriculum_id + code / year_level) get
their text updated in place instead of being skipped, so the real มคอ.2
wording always ends up in the database. YLO-PLO mappings have no text to
update, so those are matched by (ylo_id, plo_id) and simply skipped if
already present.

Run: python scripts/seed_real_plo_ylo.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import SessionLocal
from app.models import PLO, YLO, YLOPLOMapping

CURRICULUM_ID = 1

PLO_DATA = [
    ("PLO1", "ประยุกต์ใช้องค์ความรู้พื้นฐานทางวิทยาศาสตร์และเทคโนโลยีดิจิทัลในชีวิตประจำวันได้อย่างถูกต้อง"),
    ("PLO2", "สามารถสื่อสารภาษาไทยและภาษาต่างประเทศเพื่อการเรียนรู้และการใช้งานในชีวิตประจำวันได้"),
    ("PLO3", "เห็นคุณค่าและแสดงพฤติกรรมความเป็นพลเมืองดี มีคุณธรรม จริยธรรม มีจิตสาธารณะ มีภาวะผู้นำ ทำงานร่วมกับผู้อื่นในสังคมและชุมชนได้"),
    ("PLO4", "อธิบาย แนวคิด ทฤษฎี และหลักพื้นฐานด้านวิทยาการคอมพิวเตอร์ ได้อย่างถูกต้อง"),
    ("PLO5", "อธิบายหลักการ ขั้นตอนและองค์ประกอบที่เกี่ยวกับการเขียนโปรแกรมคอมพิวเตอร์ขั้นสูง โดยใช้วิธีการทางซอฟต์แวร์ในการแก้ปัญหาได้อย่างเหมาะสม"),
    ("PLO6", "สามารถประยุกต์ใช้ความรู้ด้านการออกแบบและพัฒนาซอฟต์แวร์ รวมถึงเทคโนโลยีที่เกี่ยวข้อง เพื่อแก้ปัญหาและตอบสนองความต้องการขององค์กร ท้องถิ่นได้อย่างมีประสิทธิภาพ"),
    ("PLO7", "สามารถวิเคราะห์ ออกแบบ และพัฒนาซอฟต์แวร์โดยบูรณาการองค์ความรู้ด้านวิทยาการคอมพิวเตอร์เข้ากับศาสตร์อื่นๆ ได้อย่างมีประสิทธิภาพ"),
    ("PLO8", "แสดงออกถึงการมีความคิดเชิงตรรกะ ทักษะด้านดิจิทัล และสามารถปฏิบัติงานได้เป็นอย่างดี"),
    ("PLO9", "แสดงออกถึงการมีวินัย ความรับผิดชอบต่อตนเองและสังคม และมีจรรยาบรรณทางวิชาชีพด้านวิทยาการคอมพิวเตอร์"),
]

YLO_DATA = [
    (1, "อธิบาย แนวคิด ทฤษฎี และหลักความรู้ที่เกี่ยวกับหลักการเขียนโปรแกรมคอมพิวเตอร์ โครงสร้างพื้นฐานของระบบคอมพิวเตอร์ วิทยาศาสตร์ข้อมูล การคิดเชิงคำนวณ มีความสามารถในการติดต่อสื่อสาร และทำงานร่วมกับผู้อื่นได้เป็นอย่างดี มีพฤติกรรมเหมาะสม รวมทั้งมีความรับผิดชอบต่อตนเองและสังคม"),
    (2, "อธิบาย แนวคิด ทฤษฎี และหลักความรู้การเขียนโปรแกรมคอมพิวเตอร์ขั้นสูง โดยเลือกใช้โครงสร้างข้อมูล ออกแบบส่วนติดต่อผู้ใช้งาน ออกแบบฐานข้อมูล วิเคราะห์และออกแบบระบบ การเขียนโปรแกรมประยุกต์บนอินเทอร์เน็ต เพื่อแก้ปัญหาในสถานการณ์ต่าง ๆ ได้อย่างเหมาะสม มีความสามารถในการติดต่อสื่อสารและทำงานร่วมกับผู้อื่นได้เป็นอย่างดี"),
    (3, "สามารถวิเคราะห์ ประยุกต์ทฤษฎีทางด้านวิทยาการคอมพิวเตอร์ขั้นสูง ได้แก่ เครือข่ายคอมพิวเตอร์ สถาปัตยกรรมและองค์ประกอบคอมพิวเตอร์ ระบบปฏิบัติการ การออกแบบและการวิเคราะห์ขั้นตอนวิธี ระบบสารสนเทศเพื่อการจัดการ และใช้ทักษะทางด้านการสื่อสาร ความคิดสร้างสรรค์ไปประยุกต์ใช้ในการออกแบบโครงงานวิทยาการคอมพิวเตอร์ อย่างมีจรรยาบรรณทางวิชาชีพ รวมทั้งมีความรับผิดชอบต่อตนเองและสังคม"),
    (4, "สามารถบูรณาการความรู้ด้านวิทยาการคอมพิวเตอร์ เพื่อวิเคราะห์ ออกแบบและพัฒนาซอฟต์แวร์ให้เกิดประโยชน์ได้อย่างมีประสิทธิภาพ รวมถึงแสวงหาความรู้เพื่อพัฒนาตนเองอย่างต่อเนื่อง มีวินัย มีความซื่อสัตย์ และสามารถทำงานร่วมกับผู้อื่นได้เป็นอย่างดี"),
]

# year_level -> [plo_code, ...]
YLO_PLO_MAP = {
    1: ["PLO1", "PLO2", "PLO3", "PLO4", "PLO8", "PLO9"],
    2: ["PLO1", "PLO2", "PLO3", "PLO5", "PLO8", "PLO9"],
    3: ["PLO6", "PLO8", "PLO9"],
    4: ["PLO7", "PLO8", "PLO9"],
}


def upsert_plos(db) -> dict[str, PLO]:
    inserted = updated = unchanged = 0
    plo_by_code: dict[str, PLO] = {}

    for code, description_th in PLO_DATA:
        plo = (
            db.query(PLO)
            .filter(PLO.curriculum_id == CURRICULUM_ID, PLO.code == code)
            .first()
        )
        if plo is None:
            plo = PLO(curriculum_id=CURRICULUM_ID, code=code, description_th=description_th)
            db.add(plo)
            db.flush()
            inserted += 1
        elif plo.description_th != description_th:
            plo.description_th = description_th
            updated += 1
        else:
            unchanged += 1
        plo_by_code[code] = plo

    db.commit()
    print(f"PLO: inserted {inserted}, updated {updated}, unchanged {unchanged}")
    return plo_by_code


def upsert_ylos(db) -> dict[int, YLO]:
    inserted = updated = unchanged = 0
    ylo_by_year: dict[int, YLO] = {}

    for year_level, description in YLO_DATA:
        ylo = (
            db.query(YLO)
            .filter(YLO.curriculum_id == CURRICULUM_ID, YLO.year_level == year_level)
            .first()
        )
        if ylo is None:
            ylo = YLO(curriculum_id=CURRICULUM_ID, year_level=year_level, description=description)
            db.add(ylo)
            db.flush()
            inserted += 1
        elif ylo.description != description:
            ylo.description = description
            updated += 1
        else:
            unchanged += 1
        ylo_by_year[year_level] = ylo

    db.commit()
    print(f"YLO: inserted {inserted}, updated {updated}, unchanged {unchanged}")
    return ylo_by_year


def insert_ylo_plo_mappings(db, plo_by_code: dict[str, PLO], ylo_by_year: dict[int, YLO]) -> None:
    inserted = skipped = 0

    for year_level, plo_codes in YLO_PLO_MAP.items():
        ylo = ylo_by_year[year_level]
        for code in plo_codes:
            plo = plo_by_code[code]
            existing = (
                db.query(YLOPLOMapping)
                .filter(YLOPLOMapping.ylo_id == ylo.id, YLOPLOMapping.plo_id == plo.id)
                .first()
            )
            if existing is not None:
                skipped += 1
                continue
            db.add(YLOPLOMapping(ylo_id=ylo.id, plo_id=plo.id))
            inserted += 1

    db.commit()
    print(f"YLO-PLO mapping: inserted {inserted}, skipped (already existed) {skipped}")


def main() -> None:
    db = SessionLocal()
    try:
        plo_by_code = upsert_plos(db)
        ylo_by_year = upsert_ylos(db)
        insert_ylo_plo_mappings(db, plo_by_code, ylo_by_year)
        print("\nDone.")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
