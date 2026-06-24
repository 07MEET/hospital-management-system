# 🏥 MediCare HMS – Hospital Management System

A comprehensive **Hospital Management System (HMS)** built using **Python, Streamlit, and PostgreSQL**. The platform streamlines hospital operations through role-based workflows for patient registration, appointment scheduling, diagnosis, laboratory management, pharmacy inventory, billing, payments, and administrative monitoring.

Designed with a modular architecture and a normalized relational database, the project demonstrates practical software engineering concepts including **Role-Based Access Control (RBAC)**, **stored procedures**, **database triggers**, **audit logging**, and **transaction-safe workflows**.

---

# ✨ Key Features

## 👥 Role-Based Access Control

The system provides dedicated dashboards and permissions for six user roles:

- 👨‍💼 Admin
- 👨‍⚕️ Doctor
- 🧑‍💼 Receptionist
- 🔬 Lab Technician
- 💊 Pharmacist
- 💳 Billing Staff

Each role has access only to the modules required for its responsibilities.

---

## 🧑‍⚕️ Patient Management

- Register and manage patient records
- Store demographic and contact information
- Maintain emergency contact details
- Support insurance information
- Search patients by name, phone number, or ID

---

## 📅 Appointment Management

- Book appointments with doctors
- Prevent duplicate appointment slots
- Manage appointment lifecycle
- Track appointment status
- View daily schedules

---

## 🩺 Doctor Module

- View assigned appointments
- Record diagnoses
- Prescribe medicines
- Order laboratory tests
- Maintain patient consultation history

---

## 🔬 Laboratory Module

- View pending laboratory orders
- Enter test results
- Flag abnormal findings
- Automatically update test status

---

## 💊 Pharmacy Module

- Dispense prescribed medicines
- Manage medicine inventory
- Monitor low-stock medicines
- Restock existing inventory
- Track stock quantities

---

## 💳 Billing & Payments

- Generate bills for completed consultations
- Include consultation, laboratory, and pharmacy charges
- Record payments using multiple payment modes
- Maintain billing history
- Track payment status
- Export bills as PDF invoices

---

## 📋 Audit Logging

Automatically records critical database operations:

- INSERT
- UPDATE
- DELETE

The audit trail stores previous and updated row snapshots using PostgreSQL `JSONB` for improved traceability and accountability.

---

# 🛠️ Tech Stack

| Layer | Technology |
|---------|------------|
| Frontend | Streamlit |
| Backend | Python |
| Database | PostgreSQL |
| Visualization | Plotly |
| Data Processing | Pandas |
| Database Driver | psycopg2 |
| Styling | Custom CSS |

---

## 🗄️ Key Database Features

- PL/pgSQL Stored Procedures
- Trigger-Based Business Rule Enforcement
- Analytical Database Views
- JSONB-Based Audit Logging
- Role-Based Access Control (RBAC)
- Appointment Conflict Prevention
- Transaction-Safe Billing Workflow
- Indexed Query Optimization

---

## 📁 Project Structure

```text
Hospital_Management_System/
├── app/
│   ├── main.py                    # Application entry point and routing
│   ├── auth.py                    # Authentication and session management
│   ├── db.py                      # PostgreSQL connection and query utilities
│   ├── validators.py              # Input validation helpers
│   ├── styles.py                  # Global UI styling
│   │
│   ├── components/
│   │   └── (shared reusable UI components)
│   │
│   └── pageviews/
│       ├── admin.py               # Admin module
│       ├── doctor.py              # Doctor module
│       ├── receptionist.py        # Receptionist module
│       ├── billing.py             # Billing & payment module
│       ├── pharmacist.py          # Pharmacy & inventory module
│       ├── lab_tech.py            # Laboratory module
│       │
│       └── components/
│           ├── charts.py          # Dashboard visualizations
│           ├── patient_card.py    # Reusable patient information cards
│           └── sidebar.py         # Role-based sidebar navigation
│
├── database/
│   ├── tables.sql                 # Database schema and constraints
│   ├── functions.sql              # User-defined SQL functions
│   ├── procedures.sql             # PL/pgSQL stored procedures
│   ├── triggers.sql               # Trigger functions and trigger definitions
│   ├── views.sql                  # Database views for reporting
│   ├── rbac.sql                   # Role-based access configuration
│   └── sample_data.sql            # Sample data for testing
│
├── assets/
│   └── logo.svg                   # Application assets
│
├── requirements.txt               # Python dependencies
└── README.md                      # Project documentation
```

---

# 🚀 Getting Started

## Clone the repository

```bash
git clone https://github.com/07MEET/Hospital_Management_System.git
cd Hospital_Management_System
```

## Install dependencies

```bash
pip install -r requirements.txt
```

## Configure PostgreSQL

Update the database credentials in `app/db.py` according to your local PostgreSQL setup.

## Initialize the database

Execute the SQL scripts from the `database/` directory in the appropriate order.

## Run the application

```bash
cd app
streamlit run main.py
```

The application will be available at:

```
http://localhost:8501
```

---

# 🔐 Security & Validation

- Role-Based Access Control (RBAC)
- Session-based authentication
- Server-side input validation
- Database constraints and checks
- Audit logging for critical operations
- Duplicate appointment prevention
- Payment validation and overpayment checks

---

# 📊 Core Workflows

### Patient Journey

```
Patient Registration
        │
        ▼
Appointment Booking
        │
        ▼
Doctor Consultation
        │
 ┌──────┴─────────┐
 │                │
 ▼                ▼
Prescription   Lab Order
 │                │
 └──────┬─────────┘
        ▼
Bill Generation
        │
        ▼
Payment Recording
```

---

# 🎯 Learning Outcomes

This project demonstrates practical experience in:

- Full-stack application development
- PostgreSQL database design
- Role-Based Access Control (RBAC)
- Stored procedures and database triggers
- Transaction-safe business workflows
- Healthcare information systems
- Dashboard development and visualization
- Modular software architecture
- Input validation and data integrity

---

# 👨‍💻 Author

**Meet Patel**  
B.Tech – Artificial Intelligence & Machine Learning

**Areas of Interest**
- Machine Learning
- Deep Learning
- Generative AI
- Data Science
- Backend Development

---

# 📄 License

This project is intended for educational, portfolio, and learning purposes.