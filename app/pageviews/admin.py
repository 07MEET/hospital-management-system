"""
pages/admin.py — FIXED + Feature 4: Medicine management for Admin
Fix: HTML metric cards rendering as raw text (use st.metric instead)
Fix: Added show_medicines() function for admin to add medicines
"""
import streamlit as st
import pandas as pd
from datetime import date
from db import run_query, run_query_one
from validators import (validate_name, validate_email, validate_phone,
                        validate_password, validate_username,
                        validate_medicine_name, validate_stock_quantity,
                        validate_amount, sanitize_string)
from auth import require_role


def show_dashboard(user):
    require_role(["Admin"])
    st.markdown('<p class="page-title">📊 Admin Dashboard</p>', unsafe_allow_html=True)

    # ── Metrics using native st.metric (no HTML rendering issue) ──
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    patients  = run_query_one("SELECT COUNT(*) as c FROM patients")
    doctors   = run_query_one("SELECT COUNT(*) as c FROM doctors WHERE status='Active'")
    appts     = run_query_one("SELECT COUNT(*) as c FROM appointments WHERE appt_date=CURRENT_DATE")
    fraud     = run_query_one("SELECT COUNT(*) as c FROM fraud_alerts WHERE status='Open'")
    revenue   = run_query_one("SELECT COALESCE(SUM(amount_paid),0) as s FROM payments WHERE DATE(payment_date)=CURRENT_DATE")
    unpaid    = run_query_one("SELECT COUNT(*) as c FROM bills WHERE status='Unpaid'")

    c1.metric("Patients",          patients['c']  if patients  else 0)
    c2.metric("Active Doctors",    doctors['c']   if doctors   else 0)
    c3.metric("Today's Appts",     appts['c']     if appts     else 0)
    c4.metric("Fraud Alerts",      fraud['c']     if fraud     else 0)
    c5.metric("Today Revenue",     f"₹{revenue['s']:,.0f}" if revenue else "₹0")
    c6.metric("Unpaid Bills",      unpaid['c']    if unpaid    else 0)

    st.markdown("---")
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**📅 Today's Appointments**")
        queue = run_query("""
            SELECT p.full_name AS patient, d.full_name AS doctor,
                   a.appt_time, a.appt_type, a.status
            FROM appointments a
            JOIN patients p ON a.patient_id=p.patient_id
            JOIN doctors d  ON a.doctor_id=d.doctor_id
            WHERE a.appt_date=CURRENT_DATE ORDER BY a.appt_time LIMIT 8
        """)
        if queue:
            st.dataframe(pd.DataFrame(queue), use_container_width=True)
        else:
            st.info("No appointments today.")

    with col2:
        st.markdown("**🚨 Recent Fraud Alerts**")
        alerts = run_query("""
            SELECT fa.rule_triggered, fa.severity, p.full_name AS patient, fa.status
            FROM fraud_alerts fa
            JOIN patients p ON fa.patient_id=p.patient_id
            WHERE fa.status='Open'
            ORDER BY fa.detected_at DESC LIMIT 5
        """)
        if alerts:
            st.dataframe(pd.DataFrame(alerts), use_container_width=True)
        else:
            st.success("✅ No open fraud alerts.")


def show_doctors(user):
    require_role(["Admin"])
    st.markdown('<p class="page-title">👨‍⚕️ Doctor Management</p>', unsafe_allow_html=True)
    tab1, tab2 = st.tabs(["All Doctors", "Add New Doctor"])

    with tab1:
        doctors = run_query("""
            SELECT d.doctor_id, d.full_name, dept.dept_name AS dept,
                   d.specialization, d.phone, d.opd_fee, d.status
            FROM doctors d JOIN departments dept ON d.dept_id=dept.dept_id
            ORDER BY d.full_name
        """)
        if doctors:
            st.dataframe(pd.DataFrame(doctors), use_container_width=True)
        else:
            st.info("No doctors registered.")

    with tab2:
        depts  = run_query("SELECT dept_id, dept_name FROM departments ORDER BY dept_name")
        col1, col2 = st.columns(2)
        with col1:
            name  = st.text_input("Full Name *",       placeholder="Dr. First Last")
            dept  = st.selectbox("Department *",        [""]+[f"{d['dept_id']} — {d['dept_name']}" for d in depts])
            spec  = st.text_input("Specialization *",   placeholder="e.g. Cardiologist")
            qual  = st.text_input("Qualification *",    placeholder="e.g. MBBS, MD")
        with col2:
            phone  = st.text_input("Phone *",            placeholder="10-digit number")
            email  = st.text_input("Email",              placeholder="doctor@hospital.com")
            fee    = st.number_input("OPD Fee (₹) *",   min_value=100.0, value=500.0)
            join_d = st.date_input("Joining Date *")

        if st.button("Add Doctor", type="primary"):
            errors = []
            ok, msg = validate_name(name, "Name")
            if not ok: errors.append(msg)
            if not dept: errors.append("Department required.")
            if not spec.strip(): errors.append("Specialization required.")
            if not qual.strip(): errors.append("Qualification required.")
            ok, msg = validate_phone(phone)
            if not ok: errors.append(msg)
            if email.strip():
                ok, msg = validate_email(email)
                if not ok: errors.append(msg)
            if errors:
                for e in errors: st.error(f"❌ {e}")
            else:
                try:
                    dept_id = int(dept.split("—")[0].strip())
                    run_query("""
                        INSERT INTO doctors(full_name,dept_id,specialization,qualification,phone,email,joining_date,opd_fee)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                    """, [sanitize_string(name), dept_id, sanitize_string(spec),
                          sanitize_string(qual), phone.strip(),
                          email.strip() or None, join_d, fee], fetch=False)
                    st.success(f"✅ Dr. {name} added!")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ {e}")


# ── Feature 4: Admin Medicine Management ─────────────────────
def show_medicines(user):
    require_role(["Admin"])
    st.markdown('<p class="page-title">💊 Medicine Management</p>', unsafe_allow_html=True)
    tab1, tab2, tab3 = st.tabs(["All Medicines", "Add New Medicine", "Restock"])

    with tab1:
        col1, col2 = st.columns(2)
        with col1: search = st.text_input("Search", placeholder="Brand or generic name")
        with col2:
            cats = run_query("SELECT DISTINCT category FROM medicines WHERE category IS NOT NULL ORDER BY category")
            cat  = st.selectbox("Category", ["All"]+[c['category'] for c in cats])

        q  = "SELECT medicine_id, brand_name, generic_name, category, stock_quantity, reorder_level, unit_price, expiry_date, manufacturer FROM medicines WHERE 1=1"
        p  = []
        if search.strip():
            q += " AND (LOWER(brand_name) LIKE LOWER(%s) OR LOWER(generic_name) LIKE LOWER(%s))"
            p += [f"%{search}%", f"%{search}%"]
        if cat != "All":
            q += " AND category=%s"; p.append(cat)
        q  += " ORDER BY brand_name"
        meds = run_query(q, p if p else None)
        if meds:
            df = pd.DataFrame(meds)
            # Highlight low stock
            st.dataframe(df, use_container_width=True)
            low_count = len([m for m in meds if m['stock_quantity'] <= m['reorder_level']])
            if low_count:
                st.warning(f"⚠️ {low_count} medicine(s) at or below reorder level.")
        else:
            st.info("No medicines found.")

    with tab2:
        st.markdown("**Add New Medicine to Inventory**")
        col1, col2 = st.columns(2)
        with col1:
            brand    = st.text_input("Brand Name *",    placeholder="e.g. Crocin")
            generic  = st.text_input("Generic Name *",  placeholder="e.g. Paracetamol")
            category = st.selectbox("Category *", [
                "", "Painkiller", "Antibiotic", "Antacid", "Antidiabetic",
                "Cholesterol", "Antihypertensive", "Antihistamine",
                "Antidepressant", "Anticoagulant", "NSAID",
                "Vitamin", "Supplement", "Other"
            ])
            manufacturer = st.text_input("Manufacturer", placeholder="e.g. GSK")
        with col2:
            stock    = st.number_input("Initial Stock (units) *", min_value=0, value=100)
            reorder  = st.number_input("Reorder Level *",         min_value=1, value=50)
            price    = st.number_input("Unit Price (₹) *",        min_value=0.01, value=10.0, step=0.5)
            expiry   = st.date_input("Expiry Date *",
                                     min_value=date.today(),
                                     value=date(date.today().year+2, 12, 31))

        if st.button("➕ Add Medicine", type="primary"):
            errors = []
            ok, msg = validate_medicine_name(brand)
            if not ok: errors.append(msg)
            ok, msg = validate_medicine_name(generic)
            if not ok: errors.append("Generic name: " + msg)
            if not category: errors.append("Category is required.")
            ok, msg = validate_stock_quantity(stock)
            if not ok: errors.append(msg)
            ok, msg = validate_amount(price, "Unit Price", min_val=0.01)
            if not ok: errors.append(msg)
            if reorder < 1: errors.append("Reorder level must be at least 1.")

            if errors:
                for e in errors: st.error(f"❌ {e}")
            else:
                # Check duplicate
                dup = run_query_one("SELECT medicine_id FROM medicines WHERE LOWER(brand_name)=LOWER(%s) AND LOWER(generic_name)=LOWER(%s)", [brand.strip(), generic.strip()])
                if dup:
                    st.error(f"❌ Medicine '{brand}' ({generic}) already exists in inventory.")
                else:
                    try:
                        run_query("""
                            INSERT INTO medicines
                              (brand_name, generic_name, category, stock_quantity,
                               reorder_level, unit_price, expiry_date, manufacturer)
                            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                        """, [brand.strip(), generic.strip(), category,
                              int(stock), int(reorder), float(price),
                              expiry, manufacturer.strip() or None], fetch=False)
                        st.success(f"✅ Medicine '{brand}' added to inventory!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ {e}")

    with tab3:
        st.markdown("**Restock Existing Medicine**")
        all_meds = run_query("SELECT medicine_id, brand_name, stock_quantity, reorder_level FROM medicines ORDER BY brand_name")
        med_sel  = st.selectbox("Select Medicine",
            [""]+[f"{m['medicine_id']} — {m['brand_name']} (Stock: {m['stock_quantity']}, Reorder: {m['reorder_level']})" for m in all_meds])
        qty_add  = st.number_input("Quantity to Add *", min_value=1, max_value=100000, value=100)

        if st.button("📦 Update Stock", type="primary"):
            if not med_sel:
                st.error("Select a medicine.")
            else:
                try:
                    med_id = int(med_sel.split("—")[0].strip())
                    run_query("UPDATE medicines SET stock_quantity=stock_quantity+%s WHERE medicine_id=%s",
                              [int(qty_add), med_id], fetch=False)
                    updated = run_query_one("SELECT brand_name, stock_quantity FROM medicines WHERE medicine_id=%s", [med_id])
                    st.success(f"✅ {updated['brand_name']} stock updated to {updated['stock_quantity']} units!")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ {e}")


def show_audit(user):
    require_role(["Admin"])
    st.markdown('<p class="page-title">📋 Audit Log</p>', unsafe_allow_html=True)
    col1, col2, col3 = st.columns(3)
    with col1: table_f = st.selectbox("Table", ["All","patients","appointments","bills","medicines"])
    with col2: op_f    = st.selectbox("Operation", ["All","INSERT","UPDATE","DELETE"])
    with col3: date_f  = st.date_input("Date", value=date.today())

    q  = "SELECT al.log_id, al.table_name, al.operation, al.record_id, u.username AS changed_by, al.changed_at FROM audit_log al LEFT JOIN users u ON al.changed_by=u.user_id WHERE DATE(al.changed_at)=%s"
    p  = [date_f]
    if table_f != "All": q += " AND al.table_name=%s"; p.append(table_f)
    if op_f != "All":    q += " AND al.operation=%s";  p.append(op_f)
    q  += " ORDER BY al.changed_at DESC LIMIT 100"

    logs = run_query(q, p)
    if logs:
        st.dataframe(pd.DataFrame(logs), use_container_width=True)
        st.caption(f"Showing {len(logs)} records (max 100)")
    else:
        st.info("No audit records found.")


def show_settings(user):
    require_role(["Admin"])
    st.markdown('<p class="page-title">⚙️ Settings</p>', unsafe_allow_html=True)
    tab1, tab2 = st.tabs(["User Management", "Create New User"])

    with tab1:
        users = run_query("""
            SELECT u.user_id, u.username, r.role_name, u.is_active,
                   u.last_login, u.failed_attempts
            FROM users u JOIN roles r ON u.role_id=r.role_id ORDER BY u.username
        """)
        if users:
            st.dataframe(pd.DataFrame(users), use_container_width=True)

        st.markdown("---")
        st.markdown("**Enable / Disable Account**")
        all_u  = run_query("SELECT user_id, username, is_active FROM users ORDER BY username")
        u_sel  = st.selectbox("Select User",
            [""]+[f"{u['user_id']} — {u['username']} ({'Active' if u['is_active'] else 'Disabled'})" for u in all_u])
        action = st.selectbox("Action", ["Enable","Disable"])
        if st.button("Apply") and u_sel:
            u_id = int(u_sel.split("—")[0].strip())
            if u_id == user['user_id']:
                st.error("You cannot disable your own account.")
            else:
                try:
                    run_query("UPDATE users SET is_active=%s, failed_attempts=0, locked_until=NULL WHERE user_id=%s",
                              [action=="Enable", u_id], fetch=False)
                    st.success(f"✅ Account {action.lower()}d.")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ {e}")

    with tab2:
        roles   = run_query("SELECT role_id, role_name FROM roles ORDER BY role_name")
        col1, col2 = st.columns(2)
        with col1:
            new_u = st.text_input("Username *", placeholder="e.g. dr_kumar")
            new_p = st.text_input("Password *", type="password", help="Min 8 chars, upper+lower+digit+special")
            conf  = st.text_input("Confirm Password *", type="password")
        with col2:
            new_r = st.selectbox("Role *", [""]+[f"{r['role_id']} — {r['role_name']}" for r in roles])

        if new_p:
            ok, msg = validate_password(new_p)
            st.success("✅ Strong password") if ok else st.warning(f"⚠️ {msg}")

        if st.button("Create User", type="primary"):
            errors = []
            ok, msg = validate_username(new_u);  
            if not ok: errors.append(msg)
            ok, msg = validate_password(new_p);  
            if not ok: errors.append(msg)
            if new_p != conf: errors.append("Passwords do not match.")
            if not new_r: errors.append("Role required.")
            if errors:
                for e in errors: st.error(f"❌ {e}")
            else:
                try:
                    r_id = int(new_r.split("—")[0].strip())
                    # Check username exists
                    dup = run_query_one("SELECT user_id FROM users WHERE LOWER(username)=LOWER(%s)", [new_u.strip()])
                    if dup:
                        st.error(f"❌ Username '{new_u}' already taken.")
                    else:
                        run_query("INSERT INTO users(username,password_hash,role_id) VALUES(%s,crypt(%s,gen_salt('bf',12)),%s)",
                                  [new_u.strip().lower(), new_p, r_id], fetch=False)
                        st.success(f"✅ User '{new_u}' created!")
                except Exception as e:
                    st.error(f"❌ {e}")