#!/usr/bin/env python3
"""
HR Management Dummy Data Generator
Generates hundreds of companies with thousands of employees each
Includes attendance, leave, payroll data and dummy documents
"""

import os
import sys
import json
import random
import logging
from datetime import datetime, timedelta, date
from pathlib import Path
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

import pymongo
from faker import Faker
from PIL import Image, ImageDraw, ImageFont
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.colors import HexColor
import numpy as np
import pandas as pd
from tqdm import tqdm
import click
import colorama
from colorama import Fore, Back, Style

# Initialize colorama for colored output
colorama.init()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/log/hr_data_generator.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class HRDataGenerator:
    def __init__(self, config_file='../config/accounts.json'):
        self.fake = Faker(['id_ID', 'en_US'])  # Indonesian and English locales
        self.config_file = config_file
        self.config = self.load_config()
        self.db = None
        self.companies = []
        self.departments = [
            'Human Resources', 'Finance', 'IT', 'Marketing', 'Sales', 
            'Operations', 'Legal', 'Customer Service', 'Research & Development',
            'Quality Assurance', 'Procurement', 'Administration'
        ]
        self.positions = {
            'Human Resources': ['HR Manager', 'HR Specialist', 'Recruiter', 'Training Coordinator'],
            'Finance': ['Finance Manager', 'Accountant', 'Financial Analyst', 'Bookkeeper'],
            'IT': ['IT Manager', 'Software Developer', 'System Administrator', 'Database Administrator', 'DevOps Engineer'],
            'Marketing': ['Marketing Manager', 'Digital Marketing Specialist', 'Content Creator', 'Brand Manager'],
            'Sales': ['Sales Manager', 'Sales Representative', 'Account Executive', 'Business Development'],
            'Operations': ['Operations Manager', 'Operations Coordinator', 'Process Analyst', 'Supply Chain Manager'],
            'Legal': ['Legal Manager', 'Legal Counsel', 'Compliance Officer', 'Contract Specialist'],
            'Customer Service': ['Customer Service Manager', 'Customer Support Representative', 'Call Center Agent'],
            'Research & Development': ['R&D Manager', 'Research Scientist', 'Product Developer', 'Innovation Specialist'],
            'Quality Assurance': ['QA Manager', 'QA Engineer', 'Quality Inspector', 'Test Coordinator'],
            'Procurement': ['Procurement Manager', 'Buyer', 'Vendor Manager', 'Contract Administrator'],
            'Administration': ['Admin Manager', 'Executive Assistant', 'Office Manager', 'Receptionist']
        }
        self.leave_types = [
            'Annual Leave', 'Sick Leave', 'Maternity Leave', 'Paternity Leave',
            'Emergency Leave', 'Study Leave', 'Unpaid Leave', 'Compassionate Leave'
        ]
        
        # Create directories for dummy files
        self.files_dir = Path('dummy_files')
        self.files_dir.mkdir(exist_ok=True)
        (self.files_dir / 'documents').mkdir(exist_ok=True)
        (self.files_dir / 'photos').mkdir(exist_ok=True)
        (self.files_dir / 'reports').mkdir(exist_ok=True)

    def load_config(self):
        """Load configuration from accounts.json"""
        try:
            with open(self.config_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            sys.exit(1)

    def connect_to_mongodb(self):
        """Connect to MongoDB replica set"""
        try:
            # Get primary node connection details
            primary_node = next(node for node in self.config['mongodb_cluster']['nodes'] 
                               if node['role'] == 'primary')
            
            connection_string = f"mongodb://{primary_node['user']}:{primary_node['password']}@"
            
            # Add all nodes to connection string
            hosts = []
            for node in self.config['mongodb_cluster']['nodes']:
                hosts.append(f"{node['ip']}:{node['port']}")
            
            connection_string += ",".join(hosts)
            connection_string += f"/{self.config['hr_database']['name']}?replicaSet={self.config['mongodb_cluster']['replica_set_name']}"
            
            logger.info(f"Connecting to MongoDB: {connection_string.split('@')[0]}@***")
            
            client = pymongo.MongoClient(connection_string)
            self.db = client[self.config['hr_database']['name']]
            
            # Test connection
            self.db.admin.command('ping')
            logger.info("Successfully connected to MongoDB replica set")
            
        except Exception as e:
            logger.error(f"Failed to connect to MongoDB: {e}")
            sys.exit(1)

    def create_indexes(self):
        """Create database indexes for better performance"""
        logger.info("Creating database indexes...")
        
        try:
            # Company indexes
            self.db.companies.create_index("company_id", unique=True)
            self.db.companies.create_index("name")
            
            # Employee indexes
            self.db.employees.create_index("employee_id", unique=True)
            self.db.employees.create_index("company_id")
            self.db.employees.create_index("email", unique=True)
            self.db.employees.create_index([("company_id", 1), ("department", 1)])
            
            # Attendance indexes
            self.db.attendance.create_index([("employee_id", 1), ("date", 1)], unique=True)
            self.db.attendance.create_index("company_id")
            self.db.attendance.create_index("date")
            
            # Leave indexes
            self.db.leaves.create_index("employee_id")
            self.db.leaves.create_index("company_id")
            self.db.leaves.create_index([("start_date", 1), ("end_date", 1)])
            
            # Payroll indexes
            self.db.payroll.create_index([("employee_id", 1), ("period", 1)], unique=True)
            self.db.payroll.create_index("company_id")
            self.db.payroll.create_index("period")
            
            # Document indexes
            self.db.documents.create_index("employee_id")
            self.db.documents.create_index("company_id")
            self.db.documents.create_index("document_type")
            
            logger.info("Database indexes created successfully")
            
        except Exception as e:
            logger.error(f"Failed to create indexes: {e}")

    def generate_dummy_image(self, width=800, height=600, filename=None):
        """Generate dummy image file"""
        if not filename:
            filename = f"dummy_image_{random.randint(1000, 9999)}.png"
        
        # Create image with random background color
        bg_color = (random.randint(50, 200), random.randint(50, 200), random.randint(50, 200))
        image = Image.new('RGB', (width, height), bg_color)
        draw = ImageDraw.Draw(image)
        
        # Add some random shapes
        for _ in range(random.randint(3, 8)):
            shape_type = random.choice(['rectangle', 'ellipse', 'line'])
            color = (random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))
            
            if shape_type == 'rectangle':
                x1, y1 = random.randint(0, width//2), random.randint(0, height//2)
                x2, y2 = random.randint(width//2, width), random.randint(height//2, height)
                draw.rectangle([x1, y1, x2, y2], fill=color)
            elif shape_type == 'ellipse':
                x1, y1 = random.randint(0, width//2), random.randint(0, height//2)
                x2, y2 = random.randint(width//2, width), random.randint(height//2, height)
                draw.ellipse([x1, y1, x2, y2], fill=color)
            else:  # line
                x1, y1 = random.randint(0, width), random.randint(0, height)
                x2, y2 = random.randint(0, width), random.randint(0, height)
                draw.line([x1, y1, x2, y2], fill=color, width=random.randint(1, 5))
        
        # Add text
        try:
            font = ImageFont.load_default()
            text = f"Generated Image {random.randint(1000, 9999)}"
            text_bbox = draw.textbbox((0, 0), text, font=font)
            text_width = text_bbox[2] - text_bbox[0]
            text_height = text_bbox[3] - text_bbox[1]
            x = (width - text_width) // 2
            y = (height - text_height) // 2
            draw.text((x, y), text, fill=(255, 255, 255), font=font)
        except:
            pass  # Skip if font loading fails
        
        filepath = self.files_dir / 'photos' / filename
        image.save(filepath)
        return str(filepath)

    def generate_dummy_pdf(self, title="Dummy Document", content=None, filename=None):
        """Generate dummy PDF document"""
        if not filename:
            filename = f"dummy_document_{random.randint(1000, 9999)}.pdf"
        
        filepath = self.files_dir / 'documents' / filename
        
        # Create PDF
        c = canvas.Canvas(str(filepath), pagesize=A4)
        width, height = A4
        
        # Add title
        c.setFont("Helvetica-Bold", 16)
        c.drawString(50, height - 50, title)
        
        # Add content
        c.setFont("Helvetica", 12)
        y_position = height - 100
        
        if not content:
            content = [
                f"Document ID: {random.randint(100000, 999999)}",
                f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                "",
                "This is a dummy document generated for testing purposes.",
                "It contains sample data and should not be used for actual business operations.",
                "",
                f"Random data: {self.fake.text(max_nb_chars=200)}",
                "",
                f"Contact: {self.fake.email()}",
                f"Phone: {self.fake.phone_number()}",
                f"Address: {self.fake.address()}",
            ]
        
        for line in content:
            if y_position < 50:  # Start new page if needed
                c.showPage()
                y_position = height - 50
                c.setFont("Helvetica", 12)
            
            c.drawString(50, y_position, str(line))
            y_position -= 20
        
        c.save()
        return str(filepath)

    def generate_companies(self, count=100):
        """Generate dummy companies"""
        logger.info(f"Generating {count} companies...")
        
        companies = []
        for i in tqdm(range(count), desc="Generating companies"):
            company = {
                'company_id': f"COMP_{i+1:04d}",
                'name': self.fake.company(),
                'industry': random.choice([
                    'Technology', 'Finance', 'Healthcare', 'Manufacturing', 
                    'Retail', 'Education', 'Construction', 'Transportation',
                    'Energy', 'Telecommunications', 'Food & Beverage', 'Real Estate'
                ]),
                'address': self.fake.address(),
                'city': self.fake.city(),
                'country': 'Indonesia',
                'postal_code': self.fake.postcode(),
                'phone': self.fake.phone_number(),
                'email': self.fake.company_email(),
                'website': self.fake.url(),
                'founded_year': random.randint(1980, 2020),
                'employee_count': random.randint(100, 5000),
                'annual_revenue': random.randint(1000000, 100000000),
                'tax_id': self.fake.ssn(),
                'business_license': f"BL{random.randint(100000, 999999)}",
                'created_at': datetime.now(),
                'updated_at': datetime.now(),
                'is_active': True
            }
            companies.append(company)
        
        # Insert companies into database
        try:
            result = self.db.companies.insert_many(companies)
            logger.info(f"Successfully inserted {len(result.inserted_ids)} companies")
            self.companies = companies
        except Exception as e:
            logger.error(f"Failed to insert companies: {e}")

    def generate_employees(self, employees_per_company=1000):
        """Generate dummy employees for each company"""
        logger.info(f"Generating {employees_per_company} employees per company...")
        
        total_employees = len(self.companies) * employees_per_company
        
        with tqdm(total=total_employees, desc="Generating employees") as pbar:
            for company in self.companies:
                employees = []
                
                for i in range(employees_per_company):
                    department = random.choice(self.departments)
                    position = random.choice(self.positions[department])
                    
                    # Generate employee data
                    first_name = self.fake.first_name()
                    last_name = self.fake.last_name()
                    email = f"{first_name.lower()}.{last_name.lower()}@{company['name'].lower().replace(' ', '').replace(',', '').replace('.', '')}.com"
                    
                    hire_date = self.fake.date_between(start_date='-5y', end_date='today')
                    birth_date = self.fake.date_between(start_date='-65y', end_date='-18y')
                    
                    # Generate salary based on position and experience
                    base_salary = random.randint(5000000, 25000000)  # IDR
                    if 'Manager' in position:
                        base_salary *= random.uniform(1.5, 3.0)
                    
                    # Generate dummy photo
                    photo_path = self.generate_dummy_image(200, 250, f"employee_{company['company_id']}_{i+1:04d}.jpg")
                    
                    employee = {
                        'employee_id': f"{company['company_id']}_EMP_{i+1:04d}",
                        'company_id': company['company_id'],
                        'employee_number': f"E{random.randint(100000, 999999)}",
                        'first_name': first_name,
                        'last_name': last_name,
                        'full_name': f"{first_name} {last_name}",
                        'email': email,
                        'phone': self.fake.phone_number(),
                        'birth_date': birth_date,
                        'gender': random.choice(['Male', 'Female']),
                        'marital_status': random.choice(['Single', 'Married', 'Divorced', 'Widowed']),
                        'address': self.fake.address(),
                        'city': self.fake.city(),
                        'postal_code': self.fake.postcode(),
                        'national_id': self.fake.ssn(),
                        'tax_id': f"NPWP{random.randint(100000000000000, 999999999999999)}",
                        'department': department,
                        'position': position,
                        'hire_date': hire_date,
                        'employment_status': random.choice(['Active', 'Inactive', 'Terminated']),
                        'employment_type': random.choice(['Full-time', 'Part-time', 'Contract', 'Intern']),
                        'manager_id': None,  # Will be set later
                        'salary': int(base_salary),
                        'currency': 'IDR',
                        'bank_account': {
                            'bank_name': random.choice(['BCA', 'Mandiri', 'BRI', 'BNI', 'CIMB']),
                            'account_number': str(random.randint(1000000000, 9999999999)),
                            'account_holder': f"{first_name} {last_name}"
                        },
                        'emergency_contact': {
                            'name': self.fake.name(),
                            'relationship': random.choice(['Spouse', 'Parent', 'Sibling', 'Friend']),
                            'phone': self.fake.phone_number()
                        },
                        'photo_path': photo_path,
                        'created_at': datetime.now(),
                        'updated_at': datetime.now(),
                        'is_active': True
                    }
                    employees.append(employee)
                    pbar.update(1)
                
                # Insert employees for this company
                try:
                    result = self.db.employees.insert_many(employees)
                    logger.info(f"Inserted {len(result.inserted_ids)} employees for {company['name']}")
                except Exception as e:
                    logger.error(f"Failed to insert employees for {company['name']}: {e}")

    def generate_attendance_data(self, months=12):
        """Generate attendance data for all employees"""
        logger.info(f"Generating attendance data for last {months} months...")
        
        # Get all active employees
        employees = list(self.db.employees.find({'employment_status': 'Active'}))
        total_records = len(employees) * months * 22  # Approximate working days per month
        
        with tqdm(total=total_records, desc="Generating attendance") as pbar:
            for employee in employees:
                attendance_records = []
                
                # Generate attendance for each month
                start_date = datetime.now() - timedelta(days=months * 30)
                current_date = start_date
                
                while current_date <= datetime.now():
                    # Skip weekends (assuming Monday=0, Sunday=6)
                    if current_date.weekday() < 5:  # Monday to Friday
                        # 90% attendance rate
                        if random.random() < 0.9:
                            check_in_time = current_date.replace(
                                hour=random.randint(7, 9),
                                minute=random.randint(0, 59),
                                second=random.randint(0, 59)
                            )
                            
                            # Work duration 7-10 hours
                            work_hours = random.uniform(7, 10)
                            check_out_time = check_in_time + timedelta(hours=work_hours)
                            
                            # Break time
                            break_minutes = random.randint(30, 90)
                            
                            attendance = {
                                'employee_id': employee['employee_id'],
                                'company_id': employee['company_id'],
                                'date': current_date.date(),
                                'check_in': check_in_time,
                                'check_out': check_out_time,
                                'break_minutes': break_minutes,
                                'work_hours': work_hours,
                                'overtime_hours': max(0, work_hours - 8),
                                'status': random.choice(['Present', 'Late', 'Early Leave']) if random.random() < 0.1 else 'Present',
                                'location': random.choice(['Office', 'Remote', 'Client Site']),
                                'notes': self.fake.sentence() if random.random() < 0.1 else None,
                                'created_at': datetime.now()
                            }
                            attendance_records.append(attendance)
                    
                    current_date += timedelta(days=1)
                    pbar.update(1)
                
                # Insert attendance records for this employee
                if attendance_records:
                    try:
                        self.db.attendance.insert_many(attendance_records)
                    except Exception as e:
                        logger.error(f"Failed to insert attendance for {employee['employee_id']}: {e}")

    def generate_leave_data(self):
        """Generate leave requests and approvals"""
        logger.info("Generating leave data...")
        
        employees = list(self.db.employees.find({'employment_status': 'Active'}))
        
        with tqdm(total=len(employees), desc="Generating leaves") as pbar:
            for employee in employees:
                leave_records = []
                
                # Generate 2-5 leave requests per employee per year
                num_leaves = random.randint(2, 5)
                
                for _ in range(num_leaves):
                    leave_type = random.choice(self.leave_types)
                    
                    # Generate leave dates
                    start_date = self.fake.date_between(start_date='-1y', end_date='+3m')
                    
                    # Leave duration based on type
                    if leave_type == 'Sick Leave':
                        duration = random.randint(1, 5)
                    elif leave_type in ['Maternity Leave', 'Paternity Leave']:
                        duration = random.randint(30, 90)
                    elif leave_type == 'Annual Leave':
                        duration = random.randint(2, 14)
                    else:
                        duration = random.randint(1, 7)
                    
                    end_date = start_date + timedelta(days=duration)
                    
                    leave = {
                        'leave_id': f"LEAVE_{employee['employee_id']}_{random.randint(1000, 9999)}",
                        'employee_id': employee['employee_id'],
                        'company_id': employee['company_id'],
                        'leave_type': leave_type,
                        'start_date': start_date,
                        'end_date': end_date,
                        'duration_days': duration,
                        'reason': self.fake.sentence(),
                        'status': random.choice(['Pending', 'Approved', 'Rejected', 'Cancelled']),
                        'applied_date': start_date - timedelta(days=random.randint(1, 30)),
                        'approved_by': None,  # Will be set to manager
                        'approved_date': None,
                        'comments': self.fake.sentence() if random.random() < 0.3 else None,
                        'created_at': datetime.now(),
                        'updated_at': datetime.now()
                    }
                    leave_records.append(leave)
                
                # Insert leave records
                if leave_records:
                    try:
                        self.db.leaves.insert_many(leave_records)
                    except Exception as e:
                        logger.error(f"Failed to insert leaves for {employee['employee_id']}: {e}")
                
                pbar.update(1)

    def generate_payroll_data(self, months=12):
        """Generate payroll data"""
        logger.info(f"Generating payroll data for last {months} months...")
        
        employees = list(self.db.employees.find({'employment_status': 'Active'}))
        
        with tqdm(total=len(employees) * months, desc="Generating payroll") as pbar:
            for employee in employees:
                payroll_records = []
                
                for month_offset in range(months):
                    period_date = datetime.now() - timedelta(days=month_offset * 30)
                    period = period_date.strftime('%Y-%m')
                    
                    base_salary = employee['salary']
                    
                    # Calculate allowances and deductions
                    transport_allowance = random.randint(500000, 1500000)
                    meal_allowance = random.randint(300000, 800000)
                    health_insurance = int(base_salary * 0.02)  # 2% of salary
                    tax_deduction = int(base_salary * random.uniform(0.05, 0.15))
                    
                    # Get overtime hours from attendance
                    overtime_hours = random.uniform(0, 20)  # Simplified
                    overtime_pay = int(overtime_hours * (base_salary / 160))  # Assuming 160 work hours per month
                    
                    gross_salary = base_salary + transport_allowance + meal_allowance + overtime_pay
                    total_deductions = health_insurance + tax_deduction
                    net_salary = gross_salary - total_deductions
                    
                    payroll = {
                        'payroll_id': f"PAY_{employee['employee_id']}_{period.replace('-', '')}",
                        'employee_id': employee['employee_id'],
                        'company_id': employee['company_id'],
                        'period': period,
                        'pay_date': period_date.replace(day=25),
                        'base_salary': base_salary,
                        'allowances': {
                            'transport': transport_allowance,
                            'meal': meal_allowance,
                            'overtime': overtime_pay
                        },
                        'deductions': {
                            'health_insurance': health_insurance,
                            'tax': tax_deduction
                        },
                        'gross_salary': gross_salary,
                        'total_deductions': total_deductions,
                        'net_salary': net_salary,
                        'currency': 'IDR',
                        'payment_method': random.choice(['Bank Transfer', 'Cash', 'Check']),
                        'payment_status': random.choice(['Paid', 'Pending', 'Processing']),
                        'overtime_hours': overtime_hours,
                        'created_at': datetime.now(),
                        'updated_at': datetime.now()
                    }
                    payroll_records.append(payroll)
                
                # Insert payroll records
                if payroll_records:
                    try:
                        self.db.payroll.insert_many(payroll_records)
                    except Exception as e:
                        logger.error(f"Failed to insert payroll for {employee['employee_id']}: {e}")
                
                pbar.update(months)

    def generate_documents(self):
        """Generate document records with dummy files"""
        logger.info("Generating employee documents...")
        
        employees = list(self.db.employees.find({'employment_status': 'Active'}))
        document_types = [
            'Contract', 'ID Card', 'Resume', 'Certificate', 'Performance Review',
            'Training Record', 'Medical Certificate', 'Tax Document', 'Insurance Form'
        ]
        
        with tqdm(total=len(employees), desc="Generating documents") as pbar:
            for employee in employees:
                document_records = []
                
                # Generate 3-7 documents per employee
                num_docs = random.randint(3, 7)
                
                for _ in range(num_docs):
                    doc_type = random.choice(document_types)
                    
                    # Generate appropriate file
                    if doc_type in ['ID Card', 'Certificate']:
                        file_path = self.generate_dummy_image(600, 400, f"{doc_type}_{employee['employee_id']}.jpg")
                        file_type = 'image'
                        file_size = os.path.getsize(file_path)
                    else:
                        file_path = self.generate_dummy_pdf(
                            title=f"{doc_type} - {employee['full_name']}",
                            filename=f"{doc_type}_{employee['employee_id']}.pdf"
                        )
                        file_type = 'pdf'
                        file_size = os.path.getsize(file_path)
                    
                    document = {
                        'document_id': f"DOC_{employee['employee_id']}_{random.randint(1000, 9999)}",
                        'employee_id': employee['employee_id'],
                        'company_id': employee['company_id'],
                        'document_type': doc_type,
                        'title': f"{doc_type} - {employee['full_name']}",
                        'description': self.fake.sentence(),
                        'file_path': file_path,
                        'file_name': os.path.basename(file_path),
                        'file_type': file_type,
                        'file_size': file_size,
                        'uploaded_by': 'system',
                        'upload_date': self.fake.date_between(start_date='-2y', end_date='today'),
                        'is_confidential': random.choice([True, False]),
                        'expiry_date': self.fake.date_between(start_date='today', end_date='+2y') if random.random() < 0.3 else None,
                        'version': 1,
                        'status': 'Active',
                        'created_at': datetime.now(),
                        'updated_at': datetime.now()
                    }
                    document_records.append(document)
                
                # Insert document records
                if document_records:
                    try:
                        self.db.documents.insert_many(document_records)
                    except Exception as e:
                        logger.error(f"Failed to insert documents for {employee['employee_id']}: {e}")
                
                pbar.update(1)

    def generate_summary_statistics(self):
        """Generate and display summary statistics"""
        logger.info("Generating summary statistics...")
        
        stats = {
            'companies': self.db.companies.count_documents({}),
            'employees': self.db.employees.count_documents({}),
            'attendance_records': self.db.attendance.count_documents({}),
            'leave_records': self.db.leaves.count_documents({}),
            'payroll_records': self.db.payroll.count_documents({}),
            'documents': self.db.documents.count_documents({})
        }
        
        print(f"\n{Fore.GREEN}=== DATA GENERATION SUMMARY ==={Style.RESET_ALL}")
        print(f"{Fore.CYAN}Companies:{Style.RESET_ALL} {stats['companies']:,}")
        print(f"{Fore.CYAN}Employees:{Style.RESET_ALL} {stats['employees']:,}")
        print(f"{Fore.CYAN}Attendance Records:{Style.RESET_ALL} {stats['attendance_records']:,}")
        print(f"{Fore.CYAN}Leave Records:{Style.RESET_ALL} {stats['leave_records']:,}")
        print(f"{Fore.CYAN}Payroll Records:{Style.RESET_ALL} {stats['payroll_records']:,}")
        print(f"{Fore.CYAN}Documents:{Style.RESET_ALL} {stats['documents']:,}")
        
        # Calculate total file sizes
        total_size = 0
        for root, dirs, files in os.walk(self.files_dir):
            total_size += sum(os.path.getsize(os.path.join(root, file)) for file in files)
        
        print(f"{Fore.CYAN}Total File Size:{Style.RESET_ALL} {total_size / (1024*1024):.2f} MB")
        
        return stats

@click.command()
@click.option('--companies', default=100, help='Number of companies to generate')
@click.option('--employees-per-company', default=1000, help='Number of employees per company')
@click.option('--months', default=12, help='Number of months of historical data')
@click.option('--config', default='../config/accounts.json', help='Configuration file path')
@click.option('--skip-files', is_flag=True, help='Skip generating dummy files')
def main(companies, employees_per_company, months, config, skip_files):
    """Generate HR management dummy data for MongoDB cluster"""
    
    print(f"{Fore.GREEN}=== HR DATA GENERATOR ==={Style.RESET_ALL}")
    print(f"Companies: {companies}")
    print(f"Employees per company: {employees_per_company}")
    print(f"Historical data: {months} months")
    print(f"Skip files: {skip_files}")
    print()
    
    try:
        # Initialize generator
        generator = HRDataGenerator(config)
        
        # Connect to MongoDB
        generator.connect_to_mongodb()
        
        # Create indexes
        generator.create_indexes()
        
        # Generate data
        generator.generate_companies(companies)
        generator.generate_employees(employees_per_company)
        generator.generate_attendance_data(months)
        generator.generate_leave_data()
        generator.generate_payroll_data(months)
        
        if not skip_files:
            generator.generate_documents()
        
        # Generate summary
        stats = generator.generate_summary_statistics()
        
        print(f"\n{Fore.GREEN}Data generation completed successfully!{Style.RESET_ALL}")
        
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}Data generation interrupted by user{Style.RESET_ALL}")
    except Exception as e:
        logger.error(f"Data generation failed: {e}")
        print(f"\n{Fore.RED}Data generation failed: {e}{Style.RESET_ALL}")
        sys.exit(1)

if __name__ == '__main__':
    main()