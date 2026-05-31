"""
pages/lab_tech.py — Fixed, clean light theme
"""
import streamlit as st
import pandas as pd
from db import run_query, run_query_one
from validators import validate_text
from auth import require_role

def show_dashboard(user):
    require_role(["Lab_Tech"])  
    st.markdown('<p class="page-title">🔬 Lab Dashboard</p>', unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    pending  = run_query_one("SELECT COUNT(*) as c FROM lab_orders WHERE status='Pending'")
    done     = run_query_one("SELECT COUNT(*) as c FROM lab_orders WHERE status='Done' AND DATE(result_date)=CURRENT_DATE")
    abnormal = run_query_one("SELECT COUNT(*) as c FROM lab_orders WHERE is_abnormal=TRUE AND DATE(result_date)=CURRENT_DATE")
    c1.metric("Pending Tests",    pending['c']  if pending  else 0)
    c2.metric("Completed Today",  done['c']     if done     else 0)
    c3.metric("Abnormal Today",   abnormal['c'] if abnormal else 0)
    st.markdown("---")
    show_pending(user)


def show_pending(user):
    require_role(["Lab_Tech"])
    st.markdown('<p class="page-title">⏳ Pending Lab Orders</p>', unsafe_allow_html=True)
    orders = run_query("""
        SELECT lo.order_id, p.full_name AS patient, p.phone,
               lt.test_name, lt.category, lt.normal_range, lt.unit,
               lo.ordered_at
        FROM lab_orders lo
        JOIN appointments a ON lo.appt_id=a.appt_id
        JOIN patients p     ON a.patient_id=p.patient_id
        JOIN lab_tests lt   ON lo.test_id=lt.test_id
        WHERE lo.status='Pending' ORDER BY lo.ordered_at ASC
    """)
    if orders:
        st.dataframe(pd.DataFrame(orders), use_container_width=True)
    else:
        st.success("✅ No pending lab orders!")


def show_results(user):
    require_role(["Lab_Tech"])
    st.markdown('<p class="page-title">✅ Enter Lab Results</p>', unsafe_allow_html=True)

    col1, col2 = st.columns([3, 2])

    with col1:
        orders = run_query("""
            SELECT lo.order_id, p.full_name, lt.test_name, lt.normal_range, lt.unit
            FROM lab_orders lo
            JOIN appointments a ON lo.appt_id=a.appt_id
            JOIN patients p     ON a.patient_id=p.patient_id
            JOIN lab_tests lt   ON lo.test_id=lt.test_id
            WHERE lo.status='Pending' ORDER BY lo.ordered_at ASC
        """)

        if not orders:
            st.success("✅ No pending orders to enter results for.")
            return

        order = st.selectbox("Select Order",
            [""]+[f"{o['order_id']} — {o['full_name']} — {o['test_name']}" for o in orders])

        if order:
            o_id   = int(order.split("—")[0].strip())
            o_info = next((o for o in orders if o['order_id']==o_id), None)
            if o_info:
                st.info(f"Normal Range: **{o_info['normal_range']}** {o_info['unit']}")

        result_val  = st.text_input("Result Value *", placeholder="e.g. 12.5 g/dL or Negative")
        is_abnormal = st.checkbox("⚠️ Mark as Abnormal",
                                  help="Check if result is outside the normal range")

        if st.button("✅ Save Result", type="primary"):
            errors = []
            if not order: errors.append("Select a lab order.")
            ok, msg = validate_text(result_val, "Result Value", required=True, max_len=200)
            if not ok: errors.append(msg)
            if errors:
                for e in errors: st.error(f"❌ {e}")
            else:
                try:
                    o_id = int(order.split("—")[0].strip())
                    run_query("""
                        UPDATE lab_orders SET result_value=%s, is_abnormal=%s,
                               status='Done', result_date=NOW()
                        WHERE order_id=%s AND status='Pending'
                    """, [result_val.strip(), is_abnormal, o_id], fetch=False)
                    if is_abnormal:
                        st.warning("⚠️ Result marked ABNORMAL — Doctor can see this in their dashboard.")
                    st.success(f"✅ Result saved for Order #{o_id}!")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ {e}")

    with col2:
        st.markdown("**Today's Results**")
        today = run_query("""
            SELECT lt.test_name, lo.result_value, lo.is_abnormal, p.full_name
            FROM lab_orders lo
            JOIN appointments a ON lo.appt_id=a.appt_id
            JOIN patients p     ON a.patient_id=p.patient_id
            JOIN lab_tests lt   ON lo.test_id=lt.test_id
            WHERE lo.status='Done' AND DATE(lo.result_date)=CURRENT_DATE
            ORDER BY lo.result_date DESC LIMIT 10
        """)
        if today:
            for r in today:
                color = "#fee2e2" if r['is_abnormal'] else "#f0fdf4"
                icon  = "🔴" if r['is_abnormal'] else "🟢"
                st.markdown(f'<div style="background:{color};border-radius:8px;padding:0.5rem 0.75rem;margin-bottom:0.4rem;font-size:0.85rem;">{icon} <b>{r["full_name"]}</b><br>{r["test_name"]}: {r["result_value"]}</div>', unsafe_allow_html=True)
        else:
            st.info("No results entered today.")