#!/usr/bin/env python3
import argparse
import io
import os
import random
import time
from datetime import datetime, timedelta
from typing import List

from faker import Faker
from PIL import Image, ImageDraw
from fpdf import FPDF
from tqdm import tqdm
from pymongo import MongoClient, ASCENDING, InsertOne
from pymongo.errors import BulkWriteError
import gridfs

from tools.common import load_config, build_replset_uri


def ensure_indexes(db):
    db.companies.create_index([("name", ASCENDING)], unique=True)
    db.employees.create_index([("company_id", ASCENDING), ("name", ASCENDING)])
    db.employees.create_index([("email", ASCENDING)], unique=True)
    db.attendance.create_index([("employee_id", ASCENDING), ("date", ASCENDING)])
    db.leaves.create_index([("employee_id", ASCENDING), ("start", ASCENDING)])
    db.payroll.create_index([("employee_id", ASCENDING), ("period", ASCENDING)])


def generate_png_bytes(text: str, width: int = 600, height: int = 400) -> bytes:
    image = Image.new("RGB", (width, height), color=(random.randint(0, 255), random.randint(0, 255), random.randint(0, 255)))
    draw = ImageDraw.Draw(image)
    draw.text((10, 10), text, fill=(255, 255, 255))
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


def generate_jpg_bytes(text: str, width: int = 600, height: int = 400) -> bytes:
    image = Image.new("RGB", (width, height), color=(random.randint(0, 255), random.randint(0, 255), random.randint(0, 255)))
    draw = ImageDraw.Draw(image)
    draw.text((10, 10), text, fill=(255, 255, 255))
    buf = io.BytesIO()
    image.save(buf, format="JPEG", quality=85)
    return buf.getvalue()


def generate_pdf_bytes(title: str, lines: List[str]) -> bytes:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(40, 10, title)
    pdf.ln(12)
    pdf.set_font("Arial", size=12)
    for line in lines:
        pdf.multi_cell(0, 8, line)
    out = pdf.output(dest="S").encode("latin-1")
    return out


def main():
    parser = argparse.ArgumentParser(description="Generate HR dummy data with attachments")
    parser.add_argument("--accounts", default="./accounts.json")
    parser.add_argument("--companies", type=int, default=200)
    parser.add_argument("--employees-per-company", type=int, default=3000)
    parser.add_argument("--attendance-days", type=int, default=30)
    parser.add_argument("--payroll-months", type=int, default=6)
    parser.add_argument("--attachments-per-employee", type=int, default=2)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    random.seed(args.seed)
    fake = Faker()

    cfg = load_config(args.accounts)
    uri = build_replset_uri(cfg, auth=True)
    client = MongoClient(uri, retryWrites=True)
    db = client.hr
    fs = gridfs.GridFS(db)

    ensure_indexes(db)

    companies_bulk = []
    for i in range(args.companies):
        name = f"{fake.company()} {i:03d}"
        companies_bulk.append(InsertOne({
            "name": name,
            "domain": fake.domain_name(),
            "address": fake.address(),
            "created_at": datetime.utcnow(),
        }))
    if companies_bulk:
        try:
            db.companies.bulk_write(companies_bulk, ordered=False)
        except BulkWriteError:
            pass

    company_ids = list(db.companies.find({}, {"_id": 1}))
    company_ids = [c["_id"] for c in company_ids]

    for company_id in tqdm(company_ids, desc="Companies"):
        employees_bulk = []
        for _ in range(args.employees_per_company):
            first = fake.first_name()
            last = fake.last_name()
            email = f"{first}.{last}.{random.randint(1000,9999)}@{fake.free_email_domain()}".lower()
            employees_bulk.append(InsertOne({
                "company_id": company_id,
                "name": f"{first} {last}",
                "email": email,
                "dob": fake.date_of_birth(minimum_age=20, maximum_age=60),
                "hire_date": fake.date_between(start_date="-10y", end_date="-30d"),
                "title": fake.job(),
                "salary": random.randint(4_000_000, 60_000_000),
                "created_at": datetime.utcnow(),
            }))
        if employees_bulk:
            try:
                db.employees.bulk_write(employees_bulk, ordered=False)
            except BulkWriteError:
                pass

        employee_ids = [e["_id"] for e in db.employees.find({"company_id": company_id}, {"_id": 1})]

        # Attachments, Attendance, Leaves, Payroll
        today = datetime.utcnow().date()
        start_att = today - timedelta(days=args.attendance_days)

        attendance_ops = []
        leaves_ops = []
        payroll_ops = []

        for emp_id in employee_ids:
            # Attachments
            for a in range(args.attachments_per_employee):
                label = f"emp_{emp_id}_doc_{a}"
                png_id = fs.put(generate_png_bytes(label), filename=f"{label}.png", contentType="image/png", metadata={"employee_id": emp_id})
                jpg_id = fs.put(generate_jpg_bytes(label), filename=f"{label}.jpg", contentType="image/jpeg", metadata={"employee_id": emp_id})
                pdf_lines = [f"Employee: {emp_id}", f"Generated: {datetime.utcnow().isoformat()} "]
                pdf_id = fs.put(generate_pdf_bytes("Document", pdf_lines), filename=f"{label}.pdf", contentType="application/pdf", metadata={"employee_id": emp_id})
                db.files_meta.insert_one({
                    "employee_id": emp_id,
                    "files": [png_id, jpg_id, pdf_id],
                    "created_at": datetime.utcnow(),
                })

            # Attendance
            d = start_att
            while d <= today:
                status = random.choices(["present", "late", "absent"], weights=[85, 10, 5], k=1)[0]
                check_in = None
                check_out = None
                if status != "absent":
                    check_in = datetime.combine(d, datetime.min.time()) + timedelta(hours=8, minutes=random.randint(0, 90))
                    check_out = datetime.combine(d, datetime.min.time()) + timedelta(hours=17, minutes=random.randint(0, 60))
                attendance_ops.append(InsertOne({
                    "employee_id": emp_id,
                    "date": d,
                    "status": status,
                    "check_in": check_in,
                    "check_out": check_out,
                }))
                if len(attendance_ops) >= 50_000:
                    db.attendance.bulk_write(attendance_ops, ordered=False)
                    attendance_ops.clear()
                d += timedelta(days=1)

            # Leaves
            for _ in range(random.randint(0, 3)):
                start = today - timedelta(days=random.randint(1, 365))
                end = start + timedelta(days=random.randint(1, 5))
                leaves_ops.append(InsertOne({
                    "employee_id": emp_id,
                    "start": start,
                    "end": end,
                    "type": random.choice(["annual", "sick", "unpaid"]),
                    "approved": random.choice([True, False]),
                }))
                if len(leaves_ops) >= 20_000:
                    db.leaves.bulk_write(leaves_ops, ordered=False)
                    leaves_ops.clear()

            # Payroll
            for m in range(args.payroll_months):
                first = (today.replace(day=1) - timedelta(days=30 * m)).replace(day=1)
                payroll_ops.append(InsertOne({
                    "employee_id": emp_id,
                    "period": first,
                    "gross": random.randint(4_000_000, 60_000_000),
                    "tax": random.randint(100_000, 2_000_000),
                    "net": random.randint(3_000_000, 50_000_000),
                    "generated_at": datetime.utcnow(),
                }))
                if len(payroll_ops) >= 20_000:
                    db.payroll.bulk_write(payroll_ops, ordered=False)
                    payroll_ops.clear()

        if attendance_ops:
            db.attendance.bulk_write(attendance_ops, ordered=False)
        if leaves_ops:
            db.leaves.bulk_write(leaves_ops, ordered=False)
        if payroll_ops:
            db.payroll.bulk_write(payroll_ops, ordered=False)

    print("Dummy data generation completed.")


if __name__ == "__main__":
    main()

