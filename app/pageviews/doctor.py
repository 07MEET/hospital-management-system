"""
pages/doctor.py — FIXED
Fix: column "user_id_ref" does not exist
"""
import streamlit as st
from datetime import date
from db import run_query, run_query_one
from validators import (validate_icd_code, validate_text,
                        validate_dosage, sanitize_string)
from auth import require_role

def get_doctor_id(user: dict):
    require_role(["Doctor"])
    if user.get('staff_ref_id'):
        exists = run_query_one("SELECT doctor_id FROM doctors WHERE doctor_id=%s", [user['staff_ref_id']])
        if exists:
            return user['staff_ref_id']
    uname     = user.get('username', '').lower()
    name_part = uname.replace('dr_','').replace('dr.','').replace('_',' ').strip()
    if name_part:
        doc = run_query_one("SELECT doctor_id FROM doctors WHERE LOWER(full_name) LIKE LOWER(%s) LIMIT 1", [f"%{name_part}%"])
        if doc:
            return doc['doctor_id']
    return None


def show_dashboard(user):
    require_role(["Doctor"])
    st.markdown("## 👨‍⚕️ Doctor Dashboard")
    doc_id = get_doctor_id(user)
    if not doc_id:
        st.info("ℹ️ Doctor profile not linked. Ask admin to set your Staff Reference ID.")
        return
    col1, col2, col3 = st.columns(3)
    t = run_query_one("SELECT COUNT(*) as c FROM appointments WHERE doctor_id=%s AND appt_date=CURRENT_DATE", [doc_id])
    c = run_query_one("SELECT COUNT(*) as c FROM appointments WHERE doctor_id=%s AND appt_date=CURRENT_DATE AND status='Completed'", [doc_id])
    p = run_query_one("SELECT COUNT(*) as c FROM appointments WHERE doctor_id=%s AND appt_date=CURRENT_DATE AND status IN ('Pending','Confirmed')", [doc_id])
    col1.metric("Today's Total",  t['c'] if t else 0)
    col2.metric("Completed",      c['c'] if c else 0)
    col3.metric("Pending",        p['c'] if p else 0)
    st.markdown("---")
    show_appointments(user)


def show_appointments(user):
    require_role(["Doctor"])
    st.markdown("## 📅 My Appointments")
    doc_id = get_doctor_id(user)
    if not doc_id:
        st.error("Doctor profile not linked.")
        return
    col1, col2 = st.columns(2)
    with col1:
        filter_date = st.date_input("Date", value=date.today())
    with col2:
        filter_status = st.selectbox("Status", ["All","Pending","Confirmed","Completed","Cancelled"])

    query  = "SELECT a.appt_id, p.full_name AS patient, p.phone, p.blood_group, a.appt_time, a.appt_type, a.status FROM appointments a JOIN patients p ON a.patient_id=p.patient_id WHERE a.doctor_id=%s AND a.appt_date=%s"
    params = [doc_id, filter_date]
    if filter_status != "All":
        query += " AND a.status=%s"; params.append(filter_status)
    query += " ORDER BY a.appt_time"

    appts = run_query(query, params)
    if appts:
        import pandas as pd
        st.dataframe(pd.DataFrame(appts), use_container_width=True)
        completable = [str(a['appt_id']) for a in appts if a['status'] in ('Confirmed','Pending')]
        if completable:
            sel = st.selectbox("Mark as Completed", [""]+completable)
            if st.button("✅ Mark Completed", type="primary") and sel:
                try:
                    run_query("UPDATE appointments SET status='Completed' WHERE appt_id=%s AND doctor_id=%s", [int(sel), doc_id], fetch=False)
                    st.success(f"Appointment #{sel} marked completed!")
                    st.rerun()
                except Exception as e:
                    st.error(str(e))
    else:
        st.info("No appointments found.")


def show_diagnose(user):
    require_role(["Doctor"])
    st.markdown("## 🩺 Diagnose & Prescribe")
    doc_id = get_doctor_id(user)
    if not doc_id:
        st.error("Doctor profile not linked.")
        return

    tab1, tab2 = st.tabs(["🩺 Record Diagnosis", "💊 Write Prescription"])

    with tab1:
        appts = run_query("""
            SELECT a.appt_id, p.full_name, a.appt_date FROM appointments a
            JOIN patients p ON a.patient_id=p.patient_id
            WHERE a.doctor_id=%s AND a.status='Completed'
            AND a.appt_id NOT IN (SELECT appt_id FROM diagnoses WHERE appt_id IS NOT NULL)
            ORDER BY a.appt_date DESC LIMIT 20
        """, [doc_id])
        if not appts:
            st.info("No completed appointments pending diagnosis.")
        else:
            appt     = st.selectbox("Appointment", [""]+[f"{a['appt_id']} — {a['full_name']} ({a['appt_date']})" for a in appts])
            icd_code = st.text_input("ICD-10 Code *", placeholder="e.g. J18.9")
            desc     = st.text_area("Description *", height=100)
            severity = st.selectbox("Severity *", ["","Mild","Moderate","Severe"])
            if st.button("💾 Save Diagnosis", type="primary"):
                errors = []
                if not appt: errors.append("Select an appointment.")
                ok, msg = validate_icd_code(icd_code)
                if not ok: errors.append(msg)
                ok, msg = validate_text(desc, "Description")
                if not ok: errors.append(msg)
                if not severity: errors.append("Severity required.")
                if errors:
                    for e in errors: st.error(e)
                else:
                    try:
                        run_query("INSERT INTO diagnoses(appt_id,icd_code,description,severity) VALUES(%s,%s,%s,%s)",
                                  [int(appt.split("—")[0].strip()), icd_code.strip().upper(), sanitize_string(desc), severity], fetch=False)
                        st.success("✅ Diagnosis saved!")
                    except Exception as e:
                        st.error(str(e))

    with tab2:
        diags = run_query("""
            SELECT d.diag_id, p.full_name, d.icd_code FROM diagnoses d
            JOIN appointments a ON d.appt_id=a.appt_id
            JOIN patients p ON a.patient_id=p.patient_id
            WHERE a.doctor_id=%s ORDER BY d.diag_id DESC LIMIT 20
        """, [doc_id])
        meds  = run_query("SELECT medicine_id, brand_name, generic_name, unit_price, stock_quantity FROM medicines WHERE stock_quantity>0 ORDER BY brand_name")

        if not diags:
            st.info("No diagnoses found.")
            return

        diag     = st.selectbox("Diagnosis",  [""]+[f"{d['diag_id']} — {d['full_name']} — {d['icd_code']}" for d in diags])
        med      = st.selectbox("Medicine",   [""]+[f"{m['medicine_id']} — {m['brand_name']} ({m['generic_name']}) ₹{m['unit_price']}" for m in meds])
        col1, col2, col3 = st.columns(3)
        with col1: dosage    = st.text_input("Dosage *", placeholder="500mg")
        with col2: frequency = st.selectbox("Frequency *", ["","Once daily","Twice daily","Three times daily","Every 8 hours","As needed (SOS)"])
        with col3: duration  = st.number_input("Days *", min_value=1, max_value=365, value=5)
        instructions = st.text_input("Instructions", placeholder="e.g. Take after food")

        if st.button("💊 Save Prescription", type="primary"):
            errors = []
            if not diag: errors.append("Select a diagnosis.")
            if not med:  errors.append("Select a medicine.")
            ok, msg = validate_dosage(dosage)
            if not ok: errors.append(msg)
            if not frequency: errors.append("Frequency required.")
            if errors:
                for e in errors: st.error(e)
            else:
                try:
                    run_query("INSERT INTO prescriptions(diag_id,medicine_id,dosage,frequency,duration_days,instructions) VALUES(%s,%s,%s,%s,%s,%s)",
                              [int(diag.split("—")[0].strip()), int(med.split("—")[0].strip()),
                               dosage.strip(), frequency, int(duration),
                               instructions.strip() or None], fetch=False)
                    st.success("✅ Prescription saved!")
                except Exception as e:
                    st.error(str(e))


def show_lab(user):
    require_role(["Doctor"])
    st.markdown("## 🔬 Order Lab Tests")
    doc_id = get_doctor_id(user)
    if not doc_id:
        st.error("Doctor profile not linked.")
        return

    col1, col2 = st.columns(2)
    with col1:
        appts = run_query("""
            SELECT a.appt_id, p.full_name, a.appt_date FROM appointments a
            JOIN patients p ON a.patient_id=p.patient_id
            WHERE a.doctor_id=%s AND a.status IN ('Confirmed','Completed')
            ORDER BY a.appt_date DESC LIMIT 20
        """, [doc_id])
        tests = run_query("SELECT test_id, test_name, category, price, normal_range, turnaround_hours FROM lab_tests ORDER BY test_name")

        appt = st.selectbox("Appointment", [""]+[f"{a['appt_id']} — {a['full_name']} ({a['appt_date']})" for a in appts])
        test = st.selectbox("Test",        [""]+[f"{t['test_id']} — {t['test_name']} ({t['category']}) ₹{t['price']}" for t in tests])
        if test:
            t_id   = int(test.split("—")[0].strip())
            t_info = next((t for t in tests if t['test_id']==t_id), None)
            if t_info:
                st.info(f"Normal range: {t_info['normal_range']} | Results in {t_info['turnaround_hours']} hrs")

        if st.button("🔬 Order Test", type="primary"):
            if not appt or not test:
                st.error("Select both appointment and test.")
            else:
                try:
                    appt_id = int(appt.split("—")[0].strip())
                    test_id = int(test.split("—")[0].strip())
                    dup = run_query_one("SELECT order_id FROM lab_orders WHERE appt_id=%s AND test_id=%s AND status!='Done'", [appt_id, test_id])
                    if dup:
                        st.warning("Already ordered for this appointment.")
                    else:
                        run_query("INSERT INTO lab_orders(appt_id,test_id) VALUES(%s,%s)", [appt_id, test_id], fetch=False)
                        st.success("✅ Lab test ordered!")
                except Exception as e:
                    st.error(str(e))

    with col2:
        st.markdown("**Recent Results**")
        results = run_query("""
            SELECT p.full_name AS patient, lt.test_name, lo.result_value, lo.is_abnormal
            FROM lab_orders lo
            JOIN appointments a ON lo.appt_id=a.appt_id
            JOIN patients p ON a.patient_id=p.patient_id
            JOIN lab_tests lt ON lo.test_id=lt.test_id
            WHERE a.doctor_id=%s ORDER BY lo.ordered_at DESC LIMIT 8
        """, [doc_id])
        if results:
            for r in results:
                color = "#fee2e2" if r['is_abnormal'] else "#f0fdf4"
                flag  = "🔴 ABNORMAL" if r['is_abnormal'] else "🟢 Normal"
                st.markdown(f'<div style="background:{color};padding:0.5rem 0.75rem;border-radius:8px;margin-bottom:0.4rem;font-size:0.85rem;"><b>{r["patient"]}</b> — {r["test_name"]}<br>{r["result_value"] or "Pending"} | {flag}</div>', unsafe_allow_html=True)
        else:
            st.info("No results yet.")