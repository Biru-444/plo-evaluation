"""
เพิ่มคอลัมน์ clo_plo_mapping.weight_percent (น้ำหนักของคู่ CLO-PLO นี้โดยเฉพาะ - ใช้เข้าสูตร
PLO_x = Σ(mastery_i × weight_i) / Σ(weight_i) ใน plo_calculation.py แทนสูตร all-or-nothing เดิม)

เหตุผล : Workstream 3 (แผนการแก้ไขครั้งใหญ่-PLO-CLO.md) - น้ำหนักผูกกับคู่ CLO-PLO แยกกัน ไม่ใช่ผูกกับ
         CLO เดียวใช้ซ้ำทุก PLO ที่ผูกอยู่ คอลัมน์นี้ NOT NULL เสมอ (ห้าม null - auto-fill เกลี่ยเท่ากัน
         เสมอฝั่ง backend/frontend ตอนสร้างแถวใหม่ ดู app/routes/clo_plo_mapping.py)

Backfill : แถวเก่าที่มีอยู่แล้วก่อน migration นี้ไม่เคยมีแนวคิดเรื่องน้ำหนักเลย - เกลี่ยเท่ากันตาม CLO
           (ต่อ CLO หนึ่งๆ น้ำหนักของทุกคู่ CLO-PLO ที่ CLO นั้นมีอยู่ = 100/จำนวนคู่ทั้งหมดของ CLO นั้น)
           ให้ตรงกับตรรกะ auto-fill ที่ใช้จริงตอนสร้างคู่ใหม่ทุกประการ ไม่ใช่ default ตายตัวค่าเดียว

Idempotent : เช็คว่าคอลัมน์มีอยู่แล้วหรือยังก่อน ADD - ถ้ามีแล้วข้าม (รวมถึงข้าม backfill/SET NOT NULL
             ด้วย เพราะแปลว่า migration นี้เคยรันสำเร็จมาก่อนแล้ว)
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text

from app.database import engine


def column_exists(conn, table, column):
    result = conn.execute(
        text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name = :table AND column_name = :column"
        ),
        {"table": table, "column": column},
    )
    return result.first() is not None


def main():
    with engine.begin() as conn:
        if column_exists(conn, "clo_plo_mapping", "weight_percent"):
            print("clo_plo_mapping.weight_percent มีอยู่แล้ว - ข้าม")
            return

        conn.execute(text("ALTER TABLE clo_plo_mapping ADD COLUMN weight_percent NUMERIC(5, 2)"))

        # Backfill: เกลี่ยเท่ากันต่อ CLO (100 / จำนวนคู่ CLO-PLO ทั้งหมดของ CLO นั้น) - ตรงกับตรรกะ
        # auto-fill ที่ใช้จริงตอนผูกคู่ใหม่ (ดู _rebalance_clo_weights_evenly)
        conn.execute(
            text(
                """
                UPDATE clo_plo_mapping AS m
                SET weight_percent = ROUND(100.0 / counts.pair_count, 2)
                FROM (
                    SELECT clo_id, COUNT(*) AS pair_count
                    FROM clo_plo_mapping
                    GROUP BY clo_id
                ) AS counts
                WHERE m.clo_id = counts.clo_id
                """
            )
        )

        conn.execute(text("ALTER TABLE clo_plo_mapping ALTER COLUMN weight_percent SET NOT NULL"))
        conn.execute(
            text(
                "COMMENT ON COLUMN clo_plo_mapping.weight_percent IS "
                "'น้ำหนักของคู่ CLO-PLO นี้โดยเฉพาะ เข้าสูตร PLO_x = Σ(mastery×weight)/Σ(weight) "
                "- ไม่บังคับผลรวมต่อ PLO ต้องเท่า 100'"
            )
        )
        print("เพิ่มคอลัมน์ clo_plo_mapping.weight_percent แล้ว (NOT NULL, backfill เกลี่ยเท่ากันต่อ CLO)")


if __name__ == "__main__":
    main()
