"""
pages/billing.py — Fixed
Fix: HTML metric cards rendering as raw text
"""
import streamlit as st
import pandas as pd
from db import run_query, run_query_one, call_procedure
from validators import validate_amount, validate_transaction_ref
from auth import require_role

def show_dashboard(user):
    require_role(["Billing_Staff"])
    st.markdown('<p class="page-title">💰 Billing Dashboard</p>', unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4)
    total  = run_query_one("SELECT COUNT(*) as c FROM bills")
    unpaid = run_query_one("SELECT COUNT(*) as c FROM bills WHERE status='Unpaid'")
    fraud  = run_query_one("SELECT COUNT(*) as c FROM fraud_alerts WHERE status='Open'")
    rev    = run_query_one("SELECT COALESCE(SUM(amount_paid),0) as s FROM payments WHERE DATE(payment_date)=CURRENT_DATE")
    c1.metric("Total Bills",       total['c']  if total  else 0)
    c2.metric("Unpaid Bills",      unpaid['c'] if unpaid else 0)
    c3.metric("Open Fraud Alerts", fraud['c']  if fraud  else 0)
    c4.metric("Today's Revenue",   f"₹{rev['s']:,.0f}" if rev else "₹0")
    st.markdown("---")
    show_generate(user)


def show_generate(user):
    require_role(["Billing_Staff"])
    st.markdown('<p class="page-title">🧾 Generate Bill</p>', unsafe_allow_html=True)

    completed = run_query("""
        SELECT a.appt_id, p.full_name, p.phone, a.appt_date,
               d.full_name AS doctor, d.opd_fee
        FROM appointments a
        JOIN patients p ON a.patient_id=p.patient_id
        JOIN doctors d  ON a.doctor_id=d.doctor_id
        WHERE a.status='Completed'
        AND a.appt_id NOT IN (SELECT appt_id FROM bills WHERE appt_id IS NOT NULL)
        ORDER BY a.appt_date DESC
    """)

    if not completed:
        st.info("No completed appointments pending billing.")
        return

    appt_sel = st.selectbox("Select Appointment",
        [""]+[f"{a['appt_id']} — {a['full_name']} ({a['phone']}) — {a['appt_date']} — Dr.{a['doctor']}" for a in completed])

    if appt_sel:
        appt_id = int(appt_sel.split("—")[0].strip())
        appt    = next((a for a in completed if a['appt_id']==appt_id), None)
        if appt:
            lab_r  = run_query_one("SELECT COALESCE(SUM(lt.price),0) AS t FROM lab_orders lo JOIN lab_tests lt ON lo.test_id=lt.test_id WHERE lo.appt_id=%s", [appt_id])
            pha_r  = run_query_one("SELECT COALESCE(SUM(m.unit_price*pr.duration_days),0) AS t FROM diagnoses d JOIN prescriptions pr ON d.diag_id=pr.diag_id JOIN medicines m ON pr.medicine_id=m.medicine_id WHERE d.appt_id=%s", [appt_id])
            consult  = float(appt['opd_fee'] or 0)
            lab      = float(lab_r['t'] if lab_r else 0)
            pharmacy = float(pha_r['t'] if pha_r else 0)
            total    = consult + lab + pharmacy

            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Consultation", f"₹{consult:,.2f}")
            col2.metric("Lab Tests",    f"₹{lab:,.2f}")
            col3.metric("Pharmacy",     f"₹{pharmacy:,.2f}")
            col4.metric("Total",        f"₹{total:,.2f}")

    if st.button("🧾 Generate Bill", type="primary",
                 use_container_width=True, disabled=not appt_sel):
        try:
            call_procedure("generate_bill", [appt_id, user["user_id"]])
            st.success("✅ Bill generated! Fraud scan completed automatically.")
            st.rerun()
        except Exception as e:
            st.error(f"❌ {e}")


def show_payment(user):
    require_role(["Billing_Staff"])
    st.markdown('<p class="page-title">💳 Record Payment</p>', unsafe_allow_html=True)

    bills = run_query("""
        SELECT b.bill_id, p.full_name AS patient, p.phone,
               b.total_amount, b.insurance_covered, b.net_payable,
               b.status, b.due_date,
               COALESCE(SUM(pay.amount_paid),0) AS paid_so_far,
               b.net_payable - COALESCE(SUM(pay.amount_paid),0) AS outstanding
        FROM bills b
        JOIN patients p ON b.patient_id=p.patient_id
        LEFT JOIN payments pay ON b.bill_id=pay.bill_id
        WHERE b.status!='Paid'
        GROUP BY b.bill_id, p.full_name, p.phone, b.total_amount,
                 b.insurance_covered, b.net_payable, b.status, b.due_date
        ORDER BY b.due_date ASC
    """)

    if not bills:
        st.info("No outstanding bills.")
        return

    col1, col2 = st.columns([3, 2])
    with col1:
        st.dataframe(pd.DataFrame(bills), use_container_width=True)
        bill_sel = st.selectbox("Select Bill",
            [""]+[f"{b['bill_id']} — {b['patient']} — ₹{b['outstanding']:,.2f} outstanding" for b in bills])

        if bill_sel:
            b_id  = int(bill_sel.split("—")[0].strip())
            b_inf = next((b for b in bills if b['bill_id']==b_id), None)
            if b_inf:
                outstanding = float(b_inf['outstanding'])
                st.info(f"Total: ₹{b_inf['total_amount']:,.2f} | Insurance: ₹{b_inf['insurance_covered']:,.2f} | Net: ₹{b_inf['net_payable']:,.2f} | Outstanding: ₹{outstanding:,.2f}")

                amount = st.number_input("Amount (₹) *", min_value=1.0, max_value=outstanding, value=outstanding, step=100.0)
                mode   = st.selectbox("Payment Mode *", ["Cash","Card","UPI","Insurance"])
                ref    = st.text_input("Transaction Reference", placeholder="Required for Card/UPI")

                if st.button("💳 Record Payment", type="primary"):
                    errors = []
                    ok, msg = validate_amount(amount, "Payment Amount", min_val=1, max_val=outstanding)
                    if not ok: errors.append(msg)
                    ok, msg = validate_transaction_ref(ref, mode)
                    if not ok: errors.append(msg)
                    if errors:
                        for e in errors: st.error(f"❌ {e}")
                    else:
                        try:
                            call_procedure("record_payment", [b_id, amount, mode, ref.strip() or None, user["user_id"]])
                            st.success(f"✅ Payment of ₹{amount:,.2f} recorded!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ {e}")

    with col2:
        st.markdown("**Recent Payments**")
        recent = run_query("""
            SELECT p.full_name AS patient, pay.amount_paid, pay.payment_mode, pay.payment_date
            FROM payments pay JOIN bills b ON pay.bill_id=b.bill_id JOIN patients p ON b.patient_id=p.patient_id
            ORDER BY pay.payment_date DESC LIMIT 8
        """)
        if recent:
            for r in recent:
                st.markdown(f'<div style="background:#f0fdf4;border-radius:8px;padding:0.5rem 0.75rem;margin-bottom:0.4rem;font-size:0.85rem;">💳 <b>₹{r["amount_paid"]:,.2f}</b> — {r["patient"]}<br>{r["payment_mode"]} | {str(r["payment_date"])[:16]}</div>', unsafe_allow_html=True)
        else:
            st.info("No payment history yet.")


def show_fraud(user):
    require_role(["Billing_Staff"])
    st.markdown('<p class="page-title">🚨 Fraud Alerts</p>', unsafe_allow_html=True)
    alerts = run_query("SELECT * FROM vw_fraud_dashboard")

    if not alerts:
        st.success("✅ No open fraud alerts. All billing looks clean!")
        return

    high   = [a for a in alerts if a['severity']=='High']
    medium = [a for a in alerts if a['severity']=='Medium']
    low    = [a for a in alerts if a['severity']=='Low']
    c1, c2, c3 = st.columns(3)
    c1.metric("🔴 High",   len(high))
    c2.metric("🟡 Medium", len(medium))
    c3.metric("🟢 Low",    len(low))
    st.markdown("---")

    for a in alerts:
        sev_colors = {"High":"#fee2e2","Medium":"#fef3c7","Low":"#dcfce7"}
        color      = sev_colors.get(a['severity'], "#f8fafc")
        icon       = {"High":"🔴","Medium":"🟡","Low":"🟢"}.get(a['severity'],"⚪")
        st.markdown(f"""
        <div style="background:{color};border-radius:10px;padding:1rem 1.25rem;
                    margin-bottom:0.75rem;border:1px solid #e2e8f0;">
            <div style="font-weight:700;">{icon} {a['rule_triggered']}</div>
            <div style="font-size:0.85rem;margin-top:4px;color:#475569;">
                Patient: {a['patient']} | Bill: ₹{a['total_amount']:,.2f} |
                Detected: {str(a['detected_at'])[:16]}
            </div>
            <div style="font-size:0.82rem;margin-top:4px;color:#64748b;">{a.get('details','')}</div>
        </div>
        """, unsafe_allow_html=True)

    if user['role'] == 'Admin':
        st.markdown("---")
        st.markdown("**Update Alert Status**")
        open_ids = [str(a['alert_id']) for a in alerts if a['status']=='Open']
        if open_ids:
            sel_a  = st.selectbox("Alert ID", [""]+open_ids)
            new_st = st.selectbox("Status", ["Reviewed","Closed"])
            if st.button("Update") and sel_a:
                try:
                    run_query("UPDATE fraud_alerts SET status=%s, reviewed_by=%s WHERE alert_id=%s",
                              [new_st, user['user_id'], int(sel_a)], fetch=False)
                    st.success(f"✅ Alert #{sel_a} marked as {new_st}.")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ {e}")


def show(user, tab="dashboard"):
    require_role(["Billing_Staff"])
    if tab=="fraud":    show_fraud(user)
    elif tab=="generate": show_generate(user)
    elif tab=="payment":  show_payment(user)
    else:               show_dashboard(user)