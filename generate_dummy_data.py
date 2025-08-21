#!/usr/bin/env python3
"""
HR Management Dummy Data Generator
Generates comprehensive HR data including companies, employees, attendance, leave, payroll, and documents
"""

import json
import random
import string
import os
import base64
from datetime import datetime, timedelta
from pymongo import MongoClient
from faker import Faker
import uuid
import hashlib
from PIL import Image, ImageDraw, ImageFont
import io
import pdfkit
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
import tempfile

class HRDataGenerator:
    def __init__(self, config_file="accounts.json"):
        self.fake = Faker(['en_US', 'id_ID'])
        self.config = self.load_config(config_file)
        self.client = None
        self.db = None
        self.setup_database()
        
    def load_config(self, config_file):
        """Load configuration from JSON file"""
        with open(config_file, 'r') as f:
            return json.load(f)
    
    def setup_database(self):
        """Setup MongoDB connection"""
        primary_node = next(node for node in self.config['nodes'] if node['role'] == 'primary')
        
        connection_string = f"mongodb://{primary_node['user']}:{primary_node['password']}@{primary_node['ip']}:{primary_node['port']}/admin?replicaSet={self.config['replica_set_name']}"
        
        self.client = MongoClient(connection_string)
        self.db = self.client[self.config['database_name']]
        
        # Create collections
        self.companies = self.db.companies
        self.employees = self.db.employees
        self.attendance = self.db.attendance
        self.leave_requests = self.db.leave_requests
        self.payroll = self.db.payroll
        self.documents = self.db.documents
        self.departments = self.db.departments
        self.positions = self.db.positions
    
    def generate_company_data(self, num_companies=200):
        """Generate company data"""
        print(f"Generating {num_companies} companies...")
        
        company_types = ['Technology', 'Manufacturing', 'Finance', 'Healthcare', 'Education', 'Retail', 'Consulting', 'Real Estate']
        industries = ['Software', 'Automotive', 'Banking', 'Hospital', 'University', 'E-commerce', 'Management', 'Property']
        
        companies = []
        for i in range(num_companies):
            company_type = random.choice(company_types)
            industry = random.choice(industries)
            
            company = {
                '_id': str(uuid.uuid4()),
                'name': f"{self.fake.company()} {company_type}",
                'industry': industry,
                'type': company_type,
                'address': {
                    'street': self.fake.street_address(),
                    'city': self.fake.city(),
                    'state': self.fake.state(),
                    'zip_code': self.fake.zipcode(),
                    'country': self.fake.country()
                },
                'contact': {
                    'phone': self.fake.phone_number(),
                    'email': self.fake.company_email(),
                    'website': self.fake.url()
                },
                'founded_date': self.fake.date_between(start_date='-20y', end_date='-1y'),
                'employee_count': random.randint(50, 5000),
                'revenue': random.randint(1000000, 1000000000),
                'status': random.choice(['Active', 'Active', 'Active', 'Inactive']),
                'created_at': datetime.now(),
                'updated_at': datetime.now()
            }
            companies.append(company)
        
        self.companies.insert_many(companies)
        print(f"Generated {len(companies)} companies")
        return companies
    
    def generate_department_data(self, companies):
        """Generate department data for each company"""
        print("Generating departments...")
        
        department_templates = [
            'Human Resources', 'Finance', 'IT', 'Marketing', 'Sales', 'Operations', 
            'Engineering', 'Customer Service', 'Legal', 'Research & Development',
            'Quality Assurance', 'Supply Chain', 'Business Development', 'Product Management'
        ]
        
        departments = []
        for company in companies:
            num_departments = random.randint(5, 12)
            selected_departments = random.sample(department_templates, num_departments)
            
            for dept_name in selected_departments:
                department = {
                    '_id': str(uuid.uuid4()),
                    'company_id': company['_id'],
                    'name': dept_name,
                    'code': ''.join(random.choices(string.ascii_uppercase, k=3)),
                    'manager_id': None,  # Will be set when employees are created
                    'budget': random.randint(100000, 5000000),
                    'location': random.choice(['Head Office', 'Branch Office', 'Remote']),
                    'created_at': datetime.now(),
                    'updated_at': datetime.now()
                }
                departments.append(department)
        
        self.departments.insert_many(departments)
        print(f"Generated {len(departments)} departments")
        return departments
    
    def generate_position_data(self, companies):
        """Generate position data"""
        print("Generating positions...")
        
        position_templates = {
            'Human Resources': ['HR Manager', 'HR Specialist', 'Recruiter', 'HR Assistant', 'Benefits Coordinator'],
            'Finance': ['Finance Manager', 'Accountant', 'Financial Analyst', 'Bookkeeper', 'Controller'],
            'IT': ['IT Manager', 'Software Engineer', 'System Administrator', 'Database Administrator', 'Network Engineer'],
            'Marketing': ['Marketing Manager', 'Marketing Specialist', 'Digital Marketing', 'Brand Manager', 'Content Creator'],
            'Sales': ['Sales Manager', 'Sales Representative', 'Account Executive', 'Sales Director', 'Business Development'],
            'Operations': ['Operations Manager', 'Operations Specialist', 'Process Analyst', 'Operations Director'],
            'Engineering': ['Engineering Manager', 'Senior Engineer', 'Junior Engineer', 'Lead Engineer', 'Architect'],
            'Customer Service': ['Customer Service Manager', 'Customer Service Representative', 'Support Specialist'],
            'Legal': ['Legal Counsel', 'Legal Assistant', 'Compliance Officer', 'Legal Manager'],
            'Research & Development': ['R&D Manager', 'Research Scientist', 'Product Researcher', 'Innovation Lead'],
            'Quality Assurance': ['QA Manager', 'QA Engineer', 'Test Lead', 'Quality Specialist'],
            'Supply Chain': ['Supply Chain Manager', 'Logistics Coordinator', 'Procurement Specialist'],
            'Business Development': ['Business Development Manager', 'Partnership Manager', 'Strategy Analyst'],
            'Product Management': ['Product Manager', 'Product Owner', 'Product Analyst', 'Product Director']
        }
        
        positions = []
        for company in companies:
            company_departments = list(self.departments.find({'company_id': company['_id']}))
            
            for dept in company_departments:
                dept_positions = position_templates.get(dept['name'], ['Specialist', 'Coordinator', 'Assistant'])
                
                for pos_name in dept_positions:
                    position = {
                        '_id': str(uuid.uuid4()),
                        'company_id': company['_id'],
                        'department_id': dept['_id'],
                        'title': pos_name,
                        'level': random.choice(['Entry', 'Mid', 'Senior', 'Lead', 'Manager', 'Director']),
                        'base_salary_min': random.randint(30000, 150000),
                        'base_salary_max': random.randint(50000, 200000),
                        'requirements': self.fake.text(max_nb_chars=200),
                        'responsibilities': self.fake.text(max_nb_chars=300),
                        'created_at': datetime.now(),
                        'updated_at': datetime.now()
                    }
                    positions.append(position)
        
        self.positions.insert_many(positions)
        print(f"Generated {len(positions)} positions")
        return positions
    
    def generate_employee_data(self, companies, departments, positions):
        """Generate employee data"""
        print("Generating employees...")
        
        employees = []
        employee_count = 0
        
        for company in companies:
            company_employee_count = min(company['employee_count'], random.randint(100, 2000))
            company_departments = [d for d in departments if d['company_id'] == company['_id']]
            company_positions = [p for p in positions if p['company_id'] == company['_id']]
            
            for i in range(company_employee_count):
                # Select random department and position
                department = random.choice(company_departments)
                dept_positions = [p for p in company_positions if p['department_id'] == department['_id']]
                position = random.choice(dept_positions) if dept_positions else random.choice(company_positions)
                
                # Generate employee data
                hire_date = self.fake.date_between(start_date='-5y', end_date='-1d')
                
                employee = {
                    '_id': str(uuid.uuid4()),
                    'company_id': company['_id'],
                    'department_id': department['_id'],
                    'position_id': position['_id'],
                    'employee_id': f"EMP{company['_id'][:8].upper()}{str(i+1).zfill(4)}",
                    'first_name': self.fake.first_name(),
                    'last_name': self.fake.last_name(),
                    'email': self.fake.email(),
                    'phone': self.fake.phone_number(),
                    'address': {
                        'street': self.fake.street_address(),
                        'city': self.fake.city(),
                        'state': self.fake.state(),
                        'zip_code': self.fake.zipcode(),
                        'country': self.fake.country()
                    },
                    'personal_info': {
                        'date_of_birth': self.fake.date_of_birth(minimum_age=18, maximum_age=65),
                        'gender': random.choice(['Male', 'Female', 'Other']),
                        'marital_status': random.choice(['Single', 'Married', 'Divorced', 'Widowed']),
                        'nationality': self.fake.country(),
                        'emergency_contact': {
                            'name': self.fake.name(),
                            'relationship': random.choice(['Spouse', 'Parent', 'Sibling', 'Friend']),
                            'phone': self.fake.phone_number()
                        }
                    },
                    'employment_info': {
                        'hire_date': hire_date,
                        'contract_type': random.choice(['Full-time', 'Part-time', 'Contract', 'Intern']),
                        'status': random.choice(['Active', 'Active', 'Active', 'Inactive', 'Terminated']),
                        'base_salary': random.randint(position['base_salary_min'], position['base_salary_max']),
                        'currency': 'USD'
                    },
                    'created_at': datetime.now(),
                    'updated_at': datetime.now()
                }
                
                employees.append(employee)
                employee_count += 1
                
                # Update department manager if this is the first employee in department
                if not department.get('manager_id'):
                    self.departments.update_one(
                        {'_id': department['_id']}, 
                        {'$set': {'manager_id': employee['_id']}}
                    )
        
        self.employees.insert_many(employees)
        print(f"Generated {len(employees)} employees")
        return employees
    
    def generate_attendance_data(self, employees, days_back=90):
        """Generate attendance data"""
        print("Generating attendance data...")
        
        attendance_records = []
        start_date = datetime.now() - timedelta(days=days_back)
        
        for employee in employees:
            if employee['employment_info']['status'] != 'Active':
                continue
                
            current_date = start_date
            while current_date <= datetime.now():
                # Skip weekends (Saturday=5, Sunday=6)
                if current_date.weekday() < 5:  # Monday to Friday
                    # Generate work hours
                    work_start = current_date.replace(hour=random.randint(7, 9), minute=random.randint(0, 59))
                    work_end = work_start + timedelta(hours=random.randint(7, 10))
                    
                    # Add some variation (late arrival, early departure, overtime)
                    if random.random() < 0.1:  # 10% chance of late arrival
                        work_start += timedelta(minutes=random.randint(15, 120))
                    
                    if random.random() < 0.05:  # 5% chance of early departure
                        work_end -= timedelta(minutes=random.randint(30, 180))
                    
                    if random.random() < 0.15:  # 15% chance of overtime
                        work_end += timedelta(hours=random.randint(1, 3))
                    
                    attendance = {
                        '_id': str(uuid.uuid4()),
                        'employee_id': employee['_id'],
                        'company_id': employee['company_id'],
                        'date': current_date.date(),
                        'check_in': work_start,
                        'check_out': work_end,
                        'total_hours': (work_end - work_start).total_seconds() / 3600,
                        'status': random.choice(['Present', 'Present', 'Present', 'Late', 'Absent']),
                        'location': random.choice(['Office', 'Remote', 'Client Site', 'Office']),
                        'notes': self.fake.text(max_nb_chars=100) if random.random() < 0.1 else None,
                        'created_at': datetime.now(),
                        'updated_at': datetime.now()
                    }
                    attendance_records.append(attendance)
                
                current_date += timedelta(days=1)
        
        # Insert in batches
        batch_size = 1000
        for i in range(0, len(attendance_records), batch_size):
            batch = attendance_records[i:i+batch_size]
            self.attendance.insert_many(batch)
        
        print(f"Generated {len(attendance_records)} attendance records")
        return attendance_records
    
    def generate_leave_data(self, employees, days_back=365):
        """Generate leave request data"""
        print("Generating leave data...")
        
        leave_types = ['Annual Leave', 'Sick Leave', 'Personal Leave', 'Maternity Leave', 'Paternity Leave', 'Bereavement Leave']
        leave_statuses = ['Approved', 'Pending', 'Rejected', 'Cancelled']
        
        leave_records = []
        start_date = datetime.now() - timedelta(days=days_back)
        
        for employee in employees:
            if employee['employment_info']['status'] != 'Active':
                continue
            
            # Generate 2-8 leave requests per employee
            num_leaves = random.randint(2, 8)
            
            for _ in range(num_leaves):
                leave_start = self.fake.date_between(start_date=start_date, end_date='+30d')
                leave_duration = random.randint(1, 14)
                leave_end = leave_start + timedelta(days=leave_duration)
                
                leave_type = random.choice(leave_types)
                status = random.choice(leave_statuses)
                
                leave_request = {
                    '_id': str(uuid.uuid4()),
                    'employee_id': employee['_id'],
                    'company_id': employee['company_id'],
                    'leave_type': leave_type,
                    'start_date': leave_start,
                    'end_date': leave_end,
                    'duration_days': leave_duration,
                    'reason': self.fake.text(max_nb_chars=200),
                    'status': status,
                    'approved_by': None,  # Will be set if approved
                    'approved_date': None,
                    'created_at': datetime.now(),
                    'updated_at': datetime.now()
                }
                
                # If approved, set approval details
                if status == 'Approved':
                    leave_request['approved_by'] = str(uuid.uuid4())  # Random manager ID
                    leave_request['approved_date'] = leave_start - timedelta(days=random.randint(1, 7))
                
                leave_records.append(leave_request)
        
        self.leave_requests.insert_many(leave_records)
        print(f"Generated {len(leave_records)} leave requests")
        return leave_records
    
    def generate_payroll_data(self, employees, months_back=12):
        """Generate payroll data"""
        print("Generating payroll data...")
        
        payroll_records = []
        start_date = datetime.now() - timedelta(days=months_back * 30)
        
        for employee in employees:
            if employee['employment_info']['status'] != 'Active':
                continue
            
            current_date = start_date
            while current_date <= datetime.now():
                # Generate monthly payroll
                base_salary = employee['employment_info']['base_salary']
                
                # Calculate deductions and bonuses
                tax_rate = random.uniform(0.1, 0.3)
                insurance = random.uniform(0.05, 0.15) * base_salary
                bonus = random.uniform(0, 0.2) * base_salary if random.random() < 0.3 else 0
                overtime_pay = random.uniform(0, 0.1) * base_salary if random.random() < 0.4 else 0
                
                gross_salary = base_salary + bonus + overtime_pay
                tax_amount = gross_salary * tax_rate
                net_salary = gross_salary - tax_amount - insurance
                
                payroll = {
                    '_id': str(uuid.uuid4()),
                    'employee_id': employee['_id'],
                    'company_id': employee['company_id'],
                    'pay_period': current_date.strftime('%Y-%m'),
                    'base_salary': base_salary,
                    'bonus': bonus,
                    'overtime_pay': overtime_pay,
                    'gross_salary': gross_salary,
                    'tax_amount': tax_amount,
                    'insurance': insurance,
                    'net_salary': net_salary,
                    'currency': employee['employment_info']['currency'],
                    'payment_date': current_date.replace(day=25),  # Pay on 25th of each month
                    'status': 'Paid',
                    'created_at': datetime.now(),
                    'updated_at': datetime.now()
                }
                
                payroll_records.append(payroll)
                current_date += timedelta(days=30)
        
        self.payroll.insert_many(payroll_records)
        print(f"Generated {len(payroll_records)} payroll records")
        return payroll_records
    
    def generate_dummy_documents(self, employees):
        """Generate dummy PDF, PNG, JPG documents"""
        print("Generating dummy documents...")
        
        documents = []
        
        for employee in employees:
            # Generate profile picture
            profile_pic = self.create_dummy_image(f"{employee['first_name']} {employee['last_name']}")
            
            # Generate contract PDF
            contract_pdf = self.create_dummy_pdf(f"Employment Contract - {employee['first_name']} {employee['last_name']}")
            
            # Generate ID card
            id_card = self.create_dummy_image(f"ID Card - {employee['employee_id']}", is_id_card=True)
            
            # Generate payslip PDF
            payslip_pdf = self.create_dummy_pdf(f"Payslip - {employee['first_name']} {employee['last_name']}", is_payslip=True)
            
            # Store documents
            doc_types = [
                ('profile_picture', profile_pic, 'image/png'),
                ('employment_contract', contract_pdf, 'application/pdf'),
                ('id_card', id_card, 'image/png'),
                ('payslip', payslip_pdf, 'application/pdf')
            ]
            
            for doc_type, content, mime_type in doc_types:
                document = {
                    '_id': str(uuid.uuid4()),
                    'employee_id': employee['_id'],
                    'company_id': employee['company_id'],
                    'document_type': doc_type,
                    'filename': f"{doc_type}_{employee['employee_id']}.{mime_type.split('/')[-1]}",
                    'mime_type': mime_type,
                    'size': len(content),
                    'content': base64.b64encode(content).decode('utf-8'),
                    'upload_date': datetime.now(),
                    'created_at': datetime.now(),
                    'updated_at': datetime.now()
                }
                documents.append(document)
        
        # Insert in batches
        batch_size = 100
        for i in range(0, len(documents), batch_size):
            batch = documents[i:i+batch_size]
            self.documents.insert_many(batch)
        
        print(f"Generated {len(documents)} documents")
        return documents
    
    def create_dummy_image(self, text, is_id_card=False):
        """Create a dummy image with text"""
        # Create a simple image
        width, height = 300, 200
        image = Image.new('RGB', (width, height), color='white')
        draw = ImageDraw.Draw(image)
        
        # Add text
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 20)
        except:
            font = ImageFont.load_default()
        
        # Center the text
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        x = (width - text_width) // 2
        y = (height - text_height) // 2
        
        draw.text((x, y), text, fill='black', font=font)
        
        # Add some random elements for ID card
        if is_id_card:
            draw.rectangle([10, 10, width-10, height-10], outline='blue', width=3)
            draw.text((20, 20), f"ID: {uuid.uuid4().hex[:8].upper()}", fill='blue', font=font)
        
        # Convert to bytes
        img_byte_arr = io.BytesIO()
        image.save(img_byte_arr, format='PNG')
        return img_byte_arr.getvalue()
    
    def create_dummy_pdf(self, title, is_payslip=False):
        """Create a dummy PDF document"""
        buffer = io.BytesIO()
        p = canvas.Canvas(buffer, pagesize=letter)
        width, height = letter
        
        # Add title
        p.setFont("Helvetica-Bold", 16)
        p.drawString(50, height - 50, title)
        
        # Add content
        p.setFont("Helvetica", 12)
        y_position = height - 100
        
        if is_payslip:
            # Payslip content
            content = [
                f"Employee: {title.split(' - ')[1]}",
                f"Period: {datetime.now().strftime('%B %Y')}",
                f"Base Salary: $5,000.00",
                f"Bonus: $500.00",
                f"Overtime: $200.00",
                f"Tax: $1,200.00",
                f"Insurance: $300.00",
                f"Net Pay: $4,200.00"
            ]
        else:
            # Contract content
            content = [
                "EMPLOYMENT CONTRACT",
                "",
                "This agreement is made between the Company and the Employee.",
                "",
                "Terms and Conditions:",
                "1. Employment period: 12 months",
                "2. Working hours: 40 hours per week",
                "3. Salary: As per company policy",
                "4. Benefits: Health insurance, paid leave",
                "",
                "Signed by:",
                "Company Representative: _________________",
                "Employee: _________________",
                f"Date: {datetime.now().strftime('%Y-%m-%d')}"
            ]
        
        for line in content:
            p.drawString(50, y_position, line)
            y_position -= 20
        
        p.save()
        return buffer.getvalue()
    
    def create_indexes(self):
        """Create database indexes for better performance"""
        print("Creating database indexes...")
        
        # Companies indexes
        self.companies.create_index("name")
        self.companies.create_index("industry")
        self.companies.create_index("status")
        
        # Employees indexes
        self.employees.create_index("company_id")
        self.employees.create_index("department_id")
        self.employees.create_index("employee_id")
        self.employees.create_index("email")
        self.employees.create_index([("first_name", 1), ("last_name", 1)])
        
        # Attendance indexes
        self.attendance.create_index("employee_id")
        self.attendance.create_index("company_id")
        self.attendance.create_index("date")
        self.attendance.create_index([("employee_id", 1), ("date", 1)])
        
        # Leave indexes
        self.leave_requests.create_index("employee_id")
        self.leave_requests.create_index("company_id")
        self.leave_requests.create_index("status")
        self.leave_requests.create_index("start_date")
        
        # Payroll indexes
        self.payroll.create_index("employee_id")
        self.payroll.create_index("company_id")
        self.payroll.create_index("pay_period")
        
        # Documents indexes
        self.documents.create_index("employee_id")
        self.documents.create_index("company_id")
        self.documents.create_index("document_type")
        
        print("Database indexes created successfully")
    
    def generate_all_data(self):
        """Generate all HR data"""
        print("Starting HR data generation...")
        
        # Generate companies
        companies = self.generate_company_data()
        
        # Generate departments
        departments = self.generate_department_data(companies)
        
        # Generate positions
        positions = self.generate_position_data(companies)
        
        # Generate employees
        employees = self.generate_employee_data(companies, departments, positions)
        
        # Generate attendance data
        attendance = self.generate_attendance_data(employees)
        
        # Generate leave data
        leave_data = self.generate_leave_data(employees)
        
        # Generate payroll data
        payroll_data = self.generate_payroll_data(employees)
        
        # Generate documents
        documents = self.generate_dummy_documents(employees)
        
        # Create indexes
        self.create_indexes()
        
        print("\n" + "="*50)
        print("HR DATA GENERATION COMPLETED!")
        print("="*50)
        print(f"Companies: {len(companies)}")
        print(f"Departments: {len(departments)}")
        print(f"Positions: {len(positions)}")
        print(f"Employees: {len(employees)}")
        print(f"Attendance Records: {len(attendance)}")
        print(f"Leave Requests: {len(leave_data)}")
        print(f"Payroll Records: {len(payroll_data)}")
        print(f"Documents: {len(documents)}")
        print("="*50)

if __name__ == "__main__":
    generator = HRDataGenerator()
    generator.generate_all_data()