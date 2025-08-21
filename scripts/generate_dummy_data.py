#!/usr/bin/env python3
"""Generate massive HR demo data for the replica-set.

The script will create:
* Hundreds of companies
* Thousands of employees per company
* Collections: companies, employees, attendance, leaves, payrolls
* Dummy binary assets (profile JPG, payslip PDF) stored inside GridFS

Usage
-----
```bash
python scripts/generate_dummy_data.py --mongo-uri "mongodb://admin:pass@host1,host2,host3/?replicaSet=rs0" \
       --companies 300 --employees 1000
```

The script is resume-safe: it will skip companies that are already present.
"""
from __future__ import annotations

import argparse
import io
import os
import random
import string
import sys
from datetime import datetime, timedelta
from pathlib import Path

from faker import Faker
from PIL import Image, ImageDraw, ImageFont
from pymongo import MongoClient
import gridfs
from reportlab.pdfgen import canvas

fake = Faker()

def random_logo(text: str) -> bytes:
    """Generate a PNG logo with text."""
    img = Image.new("RGB", (256, 256), color=(random.randint(0, 255), random.randint(0, 255), random.randint(0, 255)))
    d = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", 64)
    except IOError:
        font = ImageFont.load_default()
    w, h = d.textsize(text, font=font)
    d.text(((256 - w) / 2, (256 - h) / 2), text, fill=(255, 255, 255), font=font)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

def pdf_payslip(name: str, amount: float, date: datetime) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(595, 842))  # A4
    c.setFont("Helvetica", 14)
    c.drawString(100, 800, f"Payslip for {name}")
    c.drawString(100, 770, f"Date: {date.strftime('%Y-%m-%d')}")
    c.drawString(100, 740, f"Amount: ${amount:,.2f}")
    c.showPage()
    c.save()
    return buf.getvalue()

def generate_data(client: MongoClient, companies_count: int, employees_per_company: int):
    db = client.hr
    fs = gridfs.GridFS(db)

    existing = db.companies.count_documents({})
    start_index = existing
    for idx in range(start_index, companies_count):
        company_name = fake.company()
        code = "".join(filter(str.isalpha, company_name.upper()))[:3]
        logo_data = random_logo(code)
        logo_id = fs.put(logo_data, filename=f"{code}_logo.png", contentType="image/png")

        company_doc = {
            "name": company_name,
            "code": code,
            "created_at": datetime.utcnow(),
            "logo_id": logo_id,
        }
        company_id = db.companies.insert_one(company_doc).inserted_id
        print(f"[+] Company {idx+1}/{companies_count}: {company_name}")

        employee_bulk = []
        attendance_bulk = []
        leaves_bulk = []
        payroll_bulk = []

        for _ in range(employees_per_company):
            emp_name = fake.name()
            emp_email = fake.email()
            emp_salary = random.randint(3_000, 15_000)

            # Profile picture
            avatar = random_logo(emp_name.split()[0][0])
            avatar_id = fs.put(avatar, filename=f"{emp_email}_avatar.png", contentType="image/png")

            employee_doc = {
                "company_id": company_id,
                "name": emp_name,
                "email": emp_email,
                "salary": emp_salary,
                "join_date": fake.date_between(start_date="-5y", end_date="today"),
                "avatar_id": avatar_id,
            }
            employee_bulk.append(employee_doc)

        # insert employees in one go
        employee_ids = db.employees.insert_many(employee_bulk).inserted_ids

        for eid in employee_ids:
            join_date = db.employees.find_one({"_id": eid})["join_date"]
            # Attendance for last 30 days
            for day_offset in range(30):
                day = datetime.utcnow().date() - timedelta(days=day_offset)
                attendance_bulk.append({
                    "employee_id": eid,
                    "company_id": company_id,
                    "date": day,
                    "clock_in": datetime.combine(day, datetime.strptime("09:00", "%H:%M").time()),
                    "clock_out": datetime.combine(day, datetime.strptime("17:00", "%H:%M").time()),
                })
            # One random leave
            leave_start = join_date + timedelta(days=random.randint(0, 365))
            leaves_bulk.append({
                "employee_id": eid,
                "company_id": company_id,
                "start_date": leave_start,
                "end_date": leave_start + timedelta(days=random.randint(1, 14)),
                "type": random.choice(["ANNUAL", "SICK", "PARENTAL"]),
            })
            # Payroll last 6 months
            for m in range(6):
                date_month = datetime.utcnow() - timedelta(days=30 * m)
                payslip_pdf = pdf_payslip(emp_name, emp_salary, date_month)
                pdf_id = fs.put(payslip_pdf, filename=f"payslip_{eid}_{m}.pdf", contentType="application/pdf")
                payroll_bulk.append({
                    "employee_id": eid,
                    "company_id": company_id,
                    "amount": emp_salary,
                    "payslip_id": pdf_id,
                    "date": date_month,
                })

        # bulk insert other collections
        if attendance_bulk:
            db.attendance.insert_many(attendance_bulk)
        if leaves_bulk:
            db.leaves.insert_many(leaves_bulk)
        if payroll_bulk:
            db.payroll.insert_many(payroll_bulk)

        print(f"    Employees: {len(employee_ids)} | Attendance: {len(attendance_bulk)} | Payroll: {len(payroll_bulk)}")


def main():
    parser = argparse.ArgumentParser(description="Generate dummy HR data into MongoDB")
    parser.add_argument("--mongo-uri", required=True, help="MongoDB connection URI")
    parser.add_argument("--companies", type=int, default=300, help="Number of companies")
    parser.add_argument("--employees", type=int, default=1000, help="Employees per company")
    args = parser.parse_args()

    client = MongoClient(args.mongo_uri)
    generate_data(client, args.companies, args.employees)
    print("\nData generation complete. ✨")

if __name__ == "__main__":
    main()