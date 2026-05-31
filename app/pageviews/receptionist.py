"""
pages/receptionist.py — FIXED
Fix: "Invalid format" error on patient registration
Fix: Appointment time validation now enforces 2-hour buffer for today
Root causes:
  1. insert was passing wrong number of params to procedure
  2. insurance insert was failing and causing cascade error
  3. email validation was rejecting empty string (optional field)
  4. validate_appointment_time was not receiving appt_date for today check
"""
import streamlit as st
from datetime import date, timedelta
from db import run_query, run_query_one, call_procedure
from validators import (validate_name, validate_email, validate_phone,
                        validate_dob, validate_appointment_date,
                        validate_appointment_time,
                        sanitize_string, sanitize_phone, sanitize_email)
from auth import require_role

def show_dashboard(user):
    st.markdown('<p class="page-title">📊 Receptionist Dashboard</p>', unsafe_allow_html=True)
    col1, col2, col3 = st.columns(3)
    t = run_query_one("SELECT COUNT(*) as c FROM patients")
    a = run_query_one("SELECT COUNT(*) as c FROM appointments WHERE appt_date=CURRENT_DATE")
    p = run_query_one("SELECT COUNT(*) as c FROM appointments WHERE appt_date=CURRENT_DATE AND status='Pending'")
    col1.metric("Total Patients",        t['c'] if t else 0)
    col2.metric("Today's Appointments",  a['c'] if a else 0)
    col3.metric("Pending Today",         p['c'] if p else 0)
    st.markdown("---")
    show_queue(user)


def show_register(user):
    require_role(["Receptionist"])
    st.markdown('<p class="page-title">🧑‍⚕️ Register New Patient</p>', unsafe_allow_html=True)
    st.caption("Fields marked * are required")

    col1, col2 = st.columns(2)
    with col1:
        name   = st.text_input("Full Name *",      placeholder="e.g. Rajesh Kumar")
        dob    = st.date_input("Date of Birth *",
                               min_value=date(1900,1,1),
                               max_value=date.today() - timedelta(days=1),
                               value=date(1990,6,15))
        gender = st.selectbox("Gender *", ["","Male","Female","Other"])
        blood  = st.selectbox("Blood Group *", ["","A+","A-","B+","B-","AB+","AB-","O+","O-"])
    with col2:
        phone  = st.text_input("Mobile Number *", placeholder="10-digit number e.g. 9876543210")
        email  = st.text_input("Email (Optional)", placeholder="patient@example.com")
        addr   = st.text_area("Address",          placeholder="Residential address", height=80)
        emerg  = st.text_input("Emergency Contact", placeholder="Name & number")

    st.markdown("**🛡️ Insurance (Optional)**")
    col3, col4 = st.columns(2)
    with col3:
        ins_provider = st.text_input("Insurance Provider", placeholder="e.g. Star Health")
        ins_policy   = st.text_input("Policy Number",      placeholder="e.g. STAR-001")
    with col4:
        ins_coverage = st.number_input("Coverage Amount (₹)", min_value=0.0, step=10000.0, value=0.0)
        ins_expiry   = st.date_input("Policy Expiry",
                                     min_value=date.today(),
                                     value=date.today() + timedelta(days=365))

    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("✅ Register Patient", type="primary", use_container_width=True):
        # ── Collect errors ────────────────────────────────────
        errors = []

        ok, msg = validate_name(name, "Full Name")
        if not ok: errors.append(msg)

        ok, msg = validate_dob(dob)
        if not ok: errors.append(msg)

        if not gender: errors.append("Gender is required.")
        if not blood:  errors.append("Blood Group is required.")

        ok, msg = validate_phone(phone)
        if not ok: errors.append(msg)

        # Email is optional — only validate if filled
        if email.strip():
            ok, msg = validate_email(email)
            if not ok: errors.append(msg)

        has_insurance = any([ins_provider.strip(), ins_policy.strip(), ins_coverage > 0])
        if has_insurance:
            if not ins_provider.strip(): errors.append("Insurance provider name required.")
            if not ins_policy.strip():   errors.append("Policy number required.")
            if ins_coverage <= 0:        errors.append("Coverage amount must be greater than 0.")

        if errors:
            for e in errors:
                st.error(f"❌ {e}")
            return

        # ── Insert ────────────────────────────────────────────
        try:
            insurance_id = None

            if has_insurance:
                # Check if policy already exists
                existing_ins = run_query_one(
                    "SELECT insurance_id FROM insurance WHERE policy_number=%s",
                    [ins_policy.strip()]
                )
                if existing_ins:
                    insurance_id = existing_ins['insurance_id']
                else:
                    result = run_query("""
                        INSERT INTO insurance(provider_name, policy_number, coverage_amount, expiry_date)
                        VALUES (%s,%s,%s,%s) RETURNING insurance_id
                    """, [ins_provider.strip(), ins_policy.strip(), ins_coverage, ins_expiry])
                    if result:
                        insurance_id = result[0]['insurance_id']

            # Check duplicate phone before inserting
            dup = run_query_one("SELECT patient_id FROM patients WHERE phone=%s",
                                [sanitize_phone(phone)])
            if dup:
                st.error(f"❌ A patient with phone {sanitize_phone(phone)} already exists.")
                return

            # Check duplicate email if provided
            if email.strip():
                dup_email = run_query_one("SELECT patient_id FROM patients WHERE email=LOWER(%s)",
                                          [email.strip()])
                if dup_email:
                    st.error("❌ A patient with this email is already registered.")
                    return

            # Direct INSERT (more reliable than procedure for this case)
            run_query("""
                INSERT INTO patients
                  (full_name, date_of_birth, gender, blood_group,
                   phone, email, address, emergency_contact, insurance_id)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, [
                sanitize_string(name),
                dob,
                gender,
                blood,
                sanitize_phone(phone),
                sanitize_email(email) if email.strip() else None,
                sanitize_string(addr) if addr.strip() else None,
                sanitize_string(emerg) if emerg.strip() else None,
                insurance_id
            ], fetch=False)

            st.success(f"✅ Patient '{sanitize_string(name)}' registered successfully!")
            st.balloons()

        except Exception as e:
            st.error(f"❌ {e}")


def show_book(user):
    require_role(["Receptionist"])
    st.markdown('<p class="page-title">📅 Book Appointment</p>', unsafe_allow_html=True)

    col1, col2 = st.columns([3, 2])

    with col1:
        # ── Patient search ────────────────────────────────
        st.markdown("**Search Patient**")
        search = st.text_input("Name or Phone", placeholder="Type at least 2 characters...")
        selected_patient = None

        if search and len(search.strip()) >= 2:
            results = run_query("""
                SELECT patient_id, full_name, phone, blood_group, status
                FROM patients
                WHERE LOWER(full_name) LIKE LOWER(%s) OR phone LIKE %s
                ORDER BY full_name LIMIT 10
            """, [f"%{search}%", f"%{search}%"])

            if results:
                opts = {f"#{p['patient_id']} — {p['full_name']} ({p['phone']})": p for p in results}
                ch   = st.selectbox("Select Patient", [""]+list(opts.keys()))
                if ch:
                    selected_patient = opts[ch]
                    p = selected_patient
                    st.info(f"👤 {p['full_name']} | 🩸 {p['blood_group']} | Status: {p['status']}")
            else:
                st.warning("No patients found. Register the patient first.")

        st.markdown("**Appointment Details**")
        depts = run_query("SELECT dept_id, dept_name FROM departments ORDER BY dept_name")
        dept  = st.selectbox("Department", [""]+[f"{d['dept_id']} — {d['dept_name']}" for d in depts])

        doctors = []
        if dept:
            dept_id = int(dept.split("—")[0].strip())
            doctors = run_query("""
                SELECT doctor_id, full_name, specialization, opd_fee
                FROM doctors WHERE dept_id=%s AND status='Active' ORDER BY full_name
            """, [dept_id])

        doc      = st.selectbox("Doctor", [""]+[f"{d['doctor_id']} — Dr. {d['full_name']} ({d['specialization']}) — ₹{d['opd_fee']}" for d in doctors])
        col_a, col_b = st.columns(2)
        with col_a:
            appt_date = st.date_input("Date", min_value=date.today(), value=date.today())
        with col_b:
            from datetime import time as dtime
            appt_time = st.time_input("Time", value=dtime(9, 0))
        appt_type = st.selectbox("Type", ["OPD","IPD","Emergency"])
        notes     = st.text_area("Notes", placeholder="Optional notes", height=60)

    with col2:
        if doc and appt_date:
            doc_id = int(doc.split("—")[0].strip())
            booked = run_query("""
                SELECT appt_time FROM appointments
                WHERE doctor_id=%s AND appt_date=%s AND status!='Cancelled'
                ORDER BY appt_time
            """, [doc_id, appt_date])
            st.markdown("**Booked Slots**")
            if booked:
                for s in booked:
                    st.markdown(f"🔴 {s['appt_time']}")
            else:
                st.success("All slots available")

    if st.button("📅 Book Appointment", type="primary", use_container_width=True):
        errors = []
        if not selected_patient: errors.append("Search and select a patient.")
        if not doc:              errors.append("Select a doctor.")

        ok, msg = validate_appointment_date(appt_date)
        if not ok: errors.append(msg)

        # ── Pass appt_date so validator can enforce 2-hour buffer ──
        ok, msg = validate_appointment_time(appt_time, appt_date=appt_date)
        if not ok: errors.append(msg)

        if errors:
            for e in errors: st.error(f"❌ {e}")
        else:
            try:
                doc_id = int(doc.split("—")[0].strip())
                # Check conflict manually
                conflict = run_query_one("""
                    SELECT appt_id FROM appointments
                    WHERE doctor_id=%s AND appt_date=%s AND appt_time=%s
                    AND status NOT IN ('Cancelled')
                """, [doc_id, appt_date, appt_time])

                if conflict:
                    st.error("❌ This slot is already booked. Please choose a different time.")
                else:
                    run_query("""
                        INSERT INTO appointments
                          (patient_id, doctor_id, appt_date, appt_time, appt_type, status, notes)
                        VALUES (%s,%s,%s,%s,%s,'Confirmed',%s)
                    """, [selected_patient['patient_id'], doc_id, appt_date,
                          appt_time, appt_type,
                          notes.strip() if notes.strip() else None], fetch=False)
                    st.success(f"✅ Appointment booked for {selected_patient['full_name']} on {appt_date} at {appt_time}!")
            except Exception as e:
                st.error(f"❌ {e}")


def show_queue(user):
    require_role(["Receptionist"])
    st.markdown('<p class="page-title">📋 Today\'s Queue</p>', unsafe_allow_html=True)
    st.caption(f"All appointments for {date.today().strftime('%d %B %Y')}")

    col1, col2 = st.columns(2)
    with col1: filter_status = st.selectbox("Filter Status", ["All","Pending","Confirmed","Completed","Cancelled"])
    with col2: filter_dept = st.selectbox("Department", ["All"]+[d['dept_name'] for d in run_query("SELECT dept_name FROM departments ORDER BY dept_name")])

    query  = """
        SELECT a.appt_id, p.full_name AS patient, p.phone,
               d.full_name AS doctor, dept.dept_name AS dept,
               a.appt_time, a.appt_type, a.status
        FROM appointments a
        JOIN patients p ON a.patient_id=p.patient_id
        JOIN doctors d ON a.doctor_id=d.doctor_id
        JOIN departments dept ON d.dept_id=dept.dept_id
        WHERE a.appt_date=CURRENT_DATE
    """
    params = []
    if filter_status != "All": query += " AND a.status=%s"; params.append(filter_status)
    if filter_dept != "All":   query += " AND dept.dept_name=%s"; params.append(filter_dept)
    query += " ORDER BY a.appt_time"

    queue = run_query(query, params if params else None)
    if queue:
        import pandas as pd
        st.dataframe(pd.DataFrame(queue), use_container_width=True)

        st.markdown("---")
        st.markdown("**Cancel an Appointment**")
        cancellable = [str(a['appt_id']) for a in queue if a['status'] not in ('Completed','Cancelled')]
        if cancellable:
            sel    = st.selectbox("Appointment ID", [""]+cancellable)
            reason = st.text_input("Reason for cancellation *")
            if st.button("❌ Cancel"):
                if not sel:               st.error("Select an appointment.")
                elif not reason.strip():  st.error("Cancellation reason required.")
                elif len(reason.strip()) < 5: st.error("Please give a more detailed reason.")
                else:
                    try:
                        run_query("UPDATE appointments SET status='Cancelled',notes=%s WHERE appt_id=%s AND status NOT IN ('Completed','Cancelled')",
                                  [reason.strip(), int(sel)], fetch=False)
                        st.success(f"✅ Appointment #{sel} cancelled.")
                        st.rerun()
                    except Exception as e:
                        st.error(str(e))
    else:
        st.info("No appointments scheduled for today.")


def show(user, tab="queue"):
    require_role(["Receptionist"])
    if tab == "patients":       show_register(user)
    elif tab == "appointments": show_book(user)
    else:                       show_queue(user)