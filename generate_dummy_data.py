#!/usr/bin/env python3
"""
HR Management Dummy Data Generator
Author: AI Generator
Version: 1.0
Description: Generate comprehensive dummy data for HR management system
"""

import json
import random
import string
import os
import sys
from datetime import datetime, timedelta, date
from typing import List, Dict, Any
import uuid
import base64
from PIL import Image, ImageDraw, ImageFont
import io
import zipfile
from fpdf import FPDF
import pymongo
from pymongo import MongoClient
import threading
import time

class HRDataGenerator:
    def __init__(self, config_file="accounts.json"):
        self.config_file = config_file
        self.config = self.load_config()
        self.companies = []
        self.employees = []
        self.attendance_records = []
        self.leave_records = []
        self.payroll_records = []
        self.documents = []
        
        # Data templates
        self.company_names = [
            "TechCorp Solutions", "Global Innovations Inc", "Digital Dynamics", "Future Systems",
            "Smart Technologies", "Innovation Hub", "Digital Solutions Pro", "Tech Pioneers",
            "Advanced Systems", "Modern Solutions", "Digital Enterprises", "Tech Leaders",
            "Innovation Partners", "Digital Experts", "Technology Masters", "Smart Solutions",
            "Future Technologies", "Digital Innovations", "Tech Solutions", "Modern Systems"
        ]
        
        self.departments = [
            "Engineering", "Sales", "Marketing", "Human Resources", "Finance", "Operations",
            "Customer Support", "Research & Development", "Quality Assurance", "Product Management",
            "Business Development", "Legal", "IT Support", "Design", "Analytics"
        ]
        
        self.job_titles = {
            "Engineering": ["Software Engineer", "Senior Engineer", "Lead Engineer", "Architect", "DevOps Engineer"],
            "Sales": ["Sales Representative", "Account Manager", "Sales Director", "Business Development"],
            "Marketing": ["Marketing Specialist", "Marketing Manager", "Brand Manager", "Content Creator"],
            "Human Resources": ["HR Specialist", "HR Manager", "Recruiter", "HR Director"],
            "Finance": ["Accountant", "Financial Analyst", "Finance Manager", "Controller"],
            "Operations": ["Operations Manager", "Project Manager", "Process Analyst", "Operations Director"]
        }
        
        self.first_names = [
            "James", "Mary", "John", "Patricia", "Robert", "Jennifer", "Michael", "Linda",
            "William", "Elizabeth", "David", "Barbara", "Richard", "Susan", "Joseph", "Jessica",
            "Thomas", "Sarah", "Christopher", "Karen", "Charles", "Nancy", "Daniel", "Lisa",
            "Matthew", "Betty", "Anthony", "Helen", "Mark", "Sandra", "Donald", "Donna",
            "Steven", "Carol", "Paul", "Ruth", "Andrew", "Sharon", "Joshua", "Michelle"
        ]
        
        self.last_names = [
            "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis",
            "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson",
            "Thomas", "Taylor", "Moore", "Jackson", "Martin", "Lee", "Perez", "Thompson",
            "White", "Harris", "Sanchez", "Clark", "Ramirez", "Lewis", "Robinson", "Walker",
            "Young", "Allen", "King", "Wright", "Scott", "Torres", "Nguyen", "Hill", "Flores"
        ]
        
        self.cities = [
            "New York", "Los Angeles", "Chicago", "Houston", "Phoenix", "Philadelphia", "San Antonio",
            "San Diego", "Dallas", "San Jose", "Austin", "Jacksonville", "Fort Worth", "Columbus",
            "Charlotte", "San Francisco", "Indianapolis", "Seattle", "Denver", "Washington"
        ]
        
        self.streets = [
            "Main Street", "Oak Avenue", "Pine Road", "Elm Street", "Cedar Lane", "Maple Drive",
            "Washington Street", "Park Avenue", "Broadway", "Fifth Avenue", "Madison Avenue",
            "Lexington Avenue", "Park Place", "Central Park West", "Riverside Drive"
        ]
        
        self.leave_types = ["Annual", "Sick", "Personal", "Maternity", "Paternity", "Bereavement", "Unpaid"]
        
    def load_config(self) -> Dict[str, Any]:
        """Load configuration from JSON file"""
        try:
            with open(self.config_file, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"Error: Configuration file {self.config_file} not found")
            sys.exit(1)
        except json.JSONDecodeError:
            print(f"Error: Invalid JSON in configuration file {self.config_file}")
            sys.exit(1)
    
    def generate_random_string(self, length: int = 10) -> str:
        """Generate random string"""
        return ''.join(random.choices(string.ascii_letters + string.digits, k=length))
    
    def generate_random_email(self, first_name: str, last_name: str) -> str:
        """Generate random email address"""
        domains = ["gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "company.com"]
        domain = random.choice(domains)
        return f"{first_name.lower()}.{last_name.lower()}@{domain}"
    
    def generate_random_phone(self) -> str:
        """Generate random phone number"""
        return f"+1-{random.randint(200, 999)}-{random.randint(200, 999)}-{random.randint(1000, 9999)}"
    
    def generate_random_address(self) -> Dict[str, str]:
        """Generate random address"""
        return {
            "street": f"{random.randint(1, 9999)} {random.choice(self.streets)}",
            "city": random.choice(self.cities),
            "state": random.choice(["NY", "CA", "TX", "FL", "IL", "PA", "OH", "GA", "NC", "MI"]),
            "zip_code": f"{random.randint(10000, 99999)}",
            "country": "USA"
        }
    
    def generate_company(self, company_id: int) -> Dict[str, Any]:
        """Generate a single company"""
        company_name = random.choice(self.company_names) + f" {random.randint(1, 999)}"
        
        return {
            "_id": f"company_{company_id}",
            "company_id": company_id,
            "name": company_name,
            "industry": random.choice(["Technology", "Healthcare", "Finance", "Retail", "Manufacturing", "Education"]),
            "size": random.choice(["Small", "Medium", "Large"]),
            "founded_year": random.randint(1990, 2020),
            "address": self.generate_random_address(),
            "phone": self.generate_random_phone(),
            "email": f"contact@{company_name.lower().replace(' ', '')}.com",
            "website": f"www.{company_name.lower().replace(' ', '')}.com",
            "tax_id": f"TAX-{random.randint(100000000, 999999999)}",
            "created_at": datetime.now(),
            "updated_at": datetime.now()
        }
    
    def generate_employee(self, employee_id: int, company_id: int) -> Dict[str, Any]:
        """Generate a single employee"""
        first_name = random.choice(self.first_names)
        last_name = random.choice(self.last_names)
        department = random.choice(self.departments)
        job_title = random.choice(self.job_titles.get(department, ["Specialist", "Manager", "Director"]))
        
        # Generate hire date (within last 5 years)
        hire_date = datetime.now() - timedelta(days=random.randint(1, 1825))
        
        # Generate salary based on job title and experience
        base_salary = random.randint(30000, 150000)
        if "Senior" in job_title or "Lead" in job_title:
            base_salary = random.randint(80000, 200000)
        elif "Manager" in job_title or "Director" in job_title:
            base_salary = random.randint(100000, 250000)
        
        return {
            "_id": f"employee_{employee_id}",
            "employee_id": employee_id,
            "company_id": f"company_{company_id}",
            "first_name": first_name,
            "last_name": last_name,
            "email": self.generate_random_email(first_name, last_name),
            "phone": self.generate_random_phone(),
            "address": self.generate_random_address(),
            "department": department,
            "job_title": job_title,
            "hire_date": hire_date,
            "salary": base_salary,
            "status": random.choice(["Active", "Active", "Active", "Terminated", "On Leave"]),
            "manager_id": None,  # Will be set later
            "created_at": datetime.now(),
            "updated_at": datetime.now()
        }
    
    def generate_attendance_record(self, employee_id: str, date: date) -> Dict[str, Any]:
        """Generate attendance record for an employee on a specific date"""
        # Generate work hours (8-10 hours)
        work_hours = random.uniform(7.5, 10.0)
        
        # Generate check-in time (between 7 AM and 10 AM)
        check_in_hour = random.randint(7, 10)
        check_in_minute = random.randint(0, 59)
        check_in_time = datetime.combine(date, datetime.min.time().replace(hour=check_in_hour, minute=check_in_minute))
        
        # Generate check-out time
        check_out_time = check_in_time + timedelta(hours=work_hours)
        
        # Generate break time (30-60 minutes)
        break_minutes = random.randint(30, 60)
        
        return {
            "_id": f"attendance_{employee_id}_{date.strftime('%Y%m%d')}",
            "employee_id": employee_id,
            "date": date,
            "check_in": check_in_time,
            "check_out": check_out_time,
            "work_hours": round(work_hours, 2),
            "break_minutes": break_minutes,
            "overtime_hours": max(0, work_hours - 8),
            "status": random.choice(["Present", "Present", "Present", "Late", "Absent"]),
            "notes": random.choice(["", "Work from home", "Business trip", "Training"]),
            "created_at": datetime.now()
        }
    
    def generate_leave_record(self, employee_id: str) -> Dict[str, Any]:
        """Generate leave record for an employee"""
        leave_type = random.choice(self.leave_types)
        start_date = datetime.now() - timedelta(days=random.randint(1, 365))
        duration_days = random.randint(1, 14) if leave_type in ["Annual", "Sick"] else random.randint(1, 30)
        end_date = start_date + timedelta(days=duration_days)
        
        return {
            "_id": f"leave_{employee_id}_{start_date.strftime('%Y%m%d')}",
            "employee_id": employee_id,
            "leave_type": leave_type,
            "start_date": start_date,
            "end_date": end_date,
            "duration_days": duration_days,
            "reason": random.choice([
                "Personal vacation", "Family emergency", "Medical appointment", "Mental health day",
                "Wedding", "Funeral", "Maternity leave", "Paternity leave", "Training", "Conference"
            ]),
            "status": random.choice(["Approved", "Pending", "Rejected"]),
            "approved_by": None,  # Will be set later
            "created_at": datetime.now()
        }
    
    def generate_payroll_record(self, employee_id: str, month: int, year: int) -> Dict[str, Any]:
        """Generate payroll record for an employee"""
        # Get employee data
        employee = next((e for e in self.employees if e["_id"] == employee_id), None)
        if not employee:
            return None
        
        base_salary = employee["salary"]
        working_days = random.randint(20, 23)  # Assuming 22 working days per month
        
        # Calculate deductions and bonuses
        tax_rate = random.uniform(0.15, 0.35)
        insurance = random.uniform(100, 500)
        bonus = random.uniform(0, base_salary * 0.2) if random.random() < 0.3 else 0
        
        gross_salary = base_salary + bonus
        tax_amount = gross_salary * tax_rate
        net_salary = gross_salary - tax_amount - insurance
        
        return {
            "_id": f"payroll_{employee_id}_{year}{month:02d}",
            "employee_id": employee_id,
            "month": month,
            "year": year,
            "base_salary": base_salary,
            "bonus": round(bonus, 2),
            "gross_salary": round(gross_salary, 2),
            "tax_amount": round(tax_amount, 2),
            "insurance": round(insurance, 2),
            "net_salary": round(net_salary, 2),
            "working_days": working_days,
            "overtime_hours": random.uniform(0, 20),
            "overtime_pay": round(random.uniform(0, 1000), 2),
            "status": "Paid",
            "payment_date": datetime(year, month, random.randint(25, 28)),
            "created_at": datetime.now()
        }
    
    def generate_dummy_image(self, width: int = 800, height: int = 600) -> bytes:
        """Generate a dummy image"""
        # Create a simple image with random colors
        image = Image.new('RGB', (width, height), color=(
            random.randint(0, 255),
            random.randint(0, 255),
            random.randint(0, 255)
        ))
        
        # Add some text
        draw = ImageDraw.Draw(image)
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 40)
        except:
            font = ImageFont.load_default()
        
        text = f"Dummy Image {random.randint(1000, 9999)}"
        text_bbox = draw.textbbox((0, 0), text, font=font)
        text_width = text_bbox[2] - text_bbox[0]
        text_height = text_bbox[3] - text_bbox[1]
        
        x = (width - text_width) // 2
        y = (height - text_height) // 2
        
        draw.text((x, y), text, fill=(255, 255, 255), font=font)
        
        # Convert to bytes
        img_byte_arr = io.BytesIO()
        image.save(img_byte_arr, format='PNG')
        return img_byte_arr.getvalue()
    
    def generate_dummy_pdf(self, title: str, content: str) -> bytes:
        """Generate a dummy PDF document"""
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=16)
        pdf.cell(200, 10, txt=title, ln=True, align='C')
        pdf.set_font("Arial", size=12)
        
        # Split content into lines
        lines = content.split('\n')
        for line in lines:
            pdf.cell(200, 10, txt=line, ln=True, align='L')
        
        return pdf.output(dest='S').encode('latin-1')
    
    def generate_document(self, employee_id: str, doc_type: str) -> Dict[str, Any]:
        """Generate a document for an employee"""
        doc_id = str(uuid.uuid4())
        
        if doc_type == "image":
            content = self.generate_dummy_image()
            filename = f"document_{doc_id}.png"
            mime_type = "image/png"
        elif doc_type == "pdf":
            title = f"Employee Document - {employee_id}"
            content = f"""
            This is a dummy document for employee {employee_id}.
            
            Document Type: {doc_type.upper()}
            Generated Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
            Document ID: {doc_id}
            
            This document contains dummy information for testing purposes.
            It includes various fields and formatting to simulate real HR documents.
            
            Employee Information:
            - Employee ID: {employee_id}
            - Document Type: {doc_type}
            - Generated: {datetime.now().isoformat()}
            """
            content = self.generate_dummy_pdf(title, content)
            filename = f"document_{doc_id}.pdf"
            mime_type = "application/pdf"
        else:
            content = f"Dummy content for {doc_type} document".encode('utf-8')
            filename = f"document_{doc_id}.txt"
            mime_type = "text/plain"
        
        return {
            "_id": doc_id,
            "employee_id": employee_id,
            "filename": filename,
            "doc_type": doc_type,
            "mime_type": mime_type,
            "content": base64.b64encode(content).decode('utf-8'),
            "size_bytes": len(content),
            "upload_date": datetime.now(),
            "created_at": datetime.now()
        }
    
    def generate_all_data(self, num_companies: int = 100, employees_per_company: int = 50):
        """Generate all dummy data"""
        print(f"Generating data for {num_companies} companies with {employees_per_company} employees each...")
        
        employee_counter = 1
        
        for company_id in range(1, num_companies + 1):
            print(f"Generating company {company_id}/{num_companies}")
            
            # Generate company
            company = self.generate_company(company_id)
            self.companies.append(company)
            
            # Generate employees for this company
            company_employees = []
            for i in range(employees_per_company):
                employee = self.generate_employee(employee_counter, company_id)
                company_employees.append(employee)
                self.employees.append(employee)
                employee_counter += 1
            
            # Set manager relationships
            for i, employee in enumerate(company_employees):
                if i > 0 and i % 10 == 0:  # Every 10th employee is a manager
                    manager_id = company_employees[i-10]["_id"]
                    for j in range(i-9, min(i+1, len(company_employees))):
                        if j < len(company_employees):
                            company_employees[j]["manager_id"] = manager_id
            
            # Generate attendance records (last 30 days)
            print(f"  Generating attendance records...")
            for employee in company_employees:
                for days_ago in range(30):
                    date = datetime.now().date() - timedelta(days=days_ago)
                    if date.weekday() < 5:  # Monday to Friday
                        attendance = self.generate_attendance_record(employee["_id"], date)
                        self.attendance_records.append(attendance)
            
            # Generate leave records
            print(f"  Generating leave records...")
            for employee in company_employees:
                if random.random() < 0.3:  # 30% chance of having leave records
                    num_leaves = random.randint(1, 3)
                    for _ in range(num_leaves):
                        leave = self.generate_leave_record(employee["_id"])
                        self.leave_records.append(leave)
            
            # Generate payroll records (last 12 months)
            print(f"  Generating payroll records...")
            for employee in company_employees:
                for month in range(1, 13):
                    year = datetime.now().year - 1 if month > datetime.now().month else datetime.now().year
                    payroll = self.generate_payroll_record(employee["_id"], month, year)
                    if payroll:
                        self.payroll_records.append(payroll)
            
            # Generate documents
            print(f"  Generating documents...")
            for employee in company_employees:
                if random.random() < 0.5:  # 50% chance of having documents
                    num_docs = random.randint(1, 5)
                    for _ in range(num_docs):
                        doc_type = random.choice(["image", "pdf", "text"])
                        document = self.generate_document(employee["_id"], doc_type)
                        self.documents.append(document)
        
        print(f"Data generation completed!")
        print(f"  Companies: {len(self.companies)}")
        print(f"  Employees: {len(self.employees)}")
        print(f"  Attendance Records: {len(self.attendance_records)}")
        print(f"  Leave Records: {len(self.leave_records)}")
        print(f"  Payroll Records: {len(self.payroll_records)}")
        print(f"  Documents: {len(self.documents)}")
    
    def save_to_json(self, filename: str):
        """Save data to JSON file"""
        print(f"Saving data to {filename}...")
        
        data = {
            "companies": self.companies,
            "employees": self.employees,
            "attendance_records": self.attendance_records,
            "leave_records": self.leave_records,
            "payroll_records": self.payroll_records,
            "documents": self.documents
        }
        
        with open(filename, 'w') as f:
            json.dump(data, f, default=str, indent=2)
        
        print(f"Data saved to {filename}")
    
    def save_to_mongodb(self):
        """Save data to MongoDB"""
        print("Connecting to MongoDB...")
        
        # Get primary node from config
        primary_node = next((node for node in self.config["nodes"] if node["role"] == "primary"), None)
        if not primary_node:
            print("Error: No primary node found in configuration")
            return
        
        # Connect to MongoDB
        connection_string = f"mongodb://{primary_node['ip']}:{primary_node['port']}"
        client = MongoClient(connection_string)
        
        # Use admin database for authentication
        admin_db = client.admin
        admin_db.authenticate(self.config["admin_user"], self.config["admin_password"])
        
        # Get HR database
        db = client[self.config["database_name"]]
        
        print("Saving data to MongoDB...")
        
        # Create collections and insert data
        if self.companies:
            db.companies.insert_many(self.companies)
            print(f"  Inserted {len(self.companies)} companies")
        
        if self.employees:
            db.employees.insert_many(self.employees)
            print(f"  Inserted {len(self.employees)} employees")
        
        if self.attendance_records:
            db.attendance.insert_many(self.attendance_records)
            print(f"  Inserted {len(self.attendance_records)} attendance records")
        
        if self.leave_records:
            db.leaves.insert_many(self.leave_records)
            print(f"  Inserted {len(self.leave_records)} leave records")
        
        if self.payroll_records:
            db.payroll.insert_many(self.payroll_records)
            print(f"  Inserted {len(self.payroll_records)} payroll records")
        
        if self.documents:
            db.documents.insert_many(self.documents)
            print(f"  Inserted {len(self.documents)} documents")
        
        # Create indexes for better performance
        print("Creating indexes...")
        db.employees.create_index("company_id")
        db.employees.create_index("department")
        db.attendance.create_index([("employee_id", 1), ("date", 1)])
        db.leaves.create_index("employee_id")
        db.payroll.create_index([("employee_id", 1), ("year", 1), ("month", 1)])
        db.documents.create_index("employee_id")
        
        print("Data successfully saved to MongoDB!")
        client.close()

def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Generate HR Management Dummy Data")
    parser.add_argument("--companies", type=int, default=100, help="Number of companies to generate")
    parser.add_argument("--employees", type=int, default=50, help="Employees per company")
    parser.add_argument("--output", type=str, default="hr_dummy_data.json", help="Output JSON file")
    parser.add_argument("--mongodb", action="store_true", help="Save to MongoDB")
    parser.add_argument("--config", type=str, default="accounts.json", help="Configuration file")
    
    args = parser.parse_args()
    
    # Initialize generator
    generator = HRDataGenerator(args.config)
    
    # Generate data
    generator.generate_all_data(args.companies, args.employees)
    
    # Save data
    if args.mongodb:
        generator.save_to_mongodb()
    else:
        generator.save_to_json(args.output)

if __name__ == "__main__":
    main()