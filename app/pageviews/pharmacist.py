"""
pages/pharmacist.py — Fixed + Feature 4 (pharmacist side)
Pharmacist can manage existing medicines (restock, update expiry)
Admin adds new medicines
"""
import streamlit as st
import pandas as pd
from db import run_query, run_query_one
from validators import validate_amount, validate_stock_quantity
from auth import require_role

def show_dashboard(user):
    require_role(["Pharmacist"])
    st.markdown('<p class="page-title">💊 Pharmacist Dashboard</p>', unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    total  = run_query_one("SELECT COUNT(*) as c FROM medicines")
    low    = run_query_one("SELECT COUNT(*) as c FROM medicines WHERE stock_quantity<=reorder_level")
    out    = run_query_one("SELECT COUNT(*) as c FROM medicines WHERE stock_quantity=0")
    c1.metric("Total Medicines",  total['c'] if total else 0)
    c2.metric("Low Stock",        low['c']   if low   else 0)
    c3.metric("Out of Stock",     out['c']   if out   else 0)
    st.markdown("---")
    show_low_stock(user)


def show_dispense(user):
    require_role(["Pharmacist"])
    st.markdown('<p class="page-title">💊 Dispense Medicine</p>', unsafe_allow_html=True)

    col1, col2 = st.columns([3, 2])

    with col1:
        prescriptions = run_query("""
            SELECT pr.rx_id, pat.full_name AS patient,
                   m.brand_name, m.generic_name, m.unit_price,
                   pr.dosage, pr.frequency, pr.duration_days,
                   pr.instructions, m.stock_quantity, m.medicine_id
            FROM prescriptions pr
            JOIN diagnoses d    ON pr.diag_id      = d.diag_id
            JOIN appointments a ON d.appt_id        = a.appt_id
            JOIN patients pat   ON a.patient_id     = pat.patient_id
            JOIN medicines m    ON pr.medicine_id   = m.medicine_id
            ORDER BY pr.prescribed_at DESC LIMIT 30
        """)

        if not prescriptions:
            st.info("No prescriptions found.")
        else:
            rx_sel = st.selectbox("Select Prescription",
                [""]+[f"{p['rx_id']} — {p['patient']} — {p['brand_name']} ({p['dosage']})" for p in prescriptions])

            if rx_sel:
                rx_id  = int(rx_sel.split("—")[0].strip())
                rx     = next((p for p in prescriptions if p['rx_id']==rx_id), None)
                if rx:
                    st.markdown(f"""
                    **Patient:** {rx['patient']}  
                    **Medicine:** {rx['brand_name']} ({rx['generic_name']})  
                    **Dosage:** {rx['dosage']} | **Frequency:** {rx['frequency']}  
                    **Duration:** {rx['duration_days']} days  
                    **Current Stock:** {rx['stock_quantity']} units  
                    {"**Instructions:** " + rx['instructions'] if rx['instructions'] else ""}
                    """)

                    max_qty = max(1, rx['stock_quantity'])
                    qty     = st.number_input("Quantity to Dispense *",
                                              min_value=1, max_value=max_qty,
                                              value=min(rx['duration_days'], max_qty))

                    if rx['stock_quantity'] == 0:
                        st.error("⚠️ OUT OF STOCK — cannot dispense.")
                    elif rx['stock_quantity'] < rx['duration_days']:
                        st.warning(f"⚠️ Only {rx['stock_quantity']} units available. Full course needs {rx['duration_days']}.")

                    if st.button("✅ Dispense", type="primary",
                                 disabled=(rx['stock_quantity']==0)):
                        if qty > rx['stock_quantity']:
                            st.error(f"Cannot dispense {qty} units. Only {rx['stock_quantity']} in stock.")
                        else:
                            try:
                                run_query("""
                                    UPDATE medicines SET stock_quantity=stock_quantity-%s
                                    WHERE medicine_id=%s AND stock_quantity>=%s
                                """, [qty, rx['medicine_id'], qty], fetch=False)
                                updated = run_query_one("SELECT stock_quantity, reorder_level FROM medicines WHERE medicine_id=%s", [rx['medicine_id']])
                                st.success(f"✅ Dispensed {qty} units of {rx['brand_name']}!")
                                if updated and updated['stock_quantity'] <= updated['reorder_level']:
                                    st.warning(f"⚠️ LOW STOCK: {rx['brand_name']} now has only {updated['stock_quantity']} units!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"❌ {e}")

    with col2:
        st.markdown("**⚠️ Low Stock**")
        low = run_query("""
            SELECT brand_name, stock_quantity, reorder_level
            FROM medicines WHERE stock_quantity<=reorder_level
            ORDER BY stock_quantity ASC LIMIT 10
        """)
        if low:
            for m in low:
                color = "#fee2e2" if m['stock_quantity']==0 else "#fef3c7"
                st.markdown(f'<div style="background:{color};border-radius:8px;padding:0.5rem 0.75rem;margin-bottom:0.4rem;font-size:0.85rem;"><b>{m["brand_name"]}</b><br>Stock: {m["stock_quantity"]} | Reorder: {m["reorder_level"]}</div>', unsafe_allow_html=True)
        else:
            st.success("All stock levels OK")


def show_inventory(user):
    require_role(["Pharmacist"])
    st.markdown('<p class="page-title">📦 Medicine Inventory</p>', unsafe_allow_html=True)
    st.caption("View and manage existing medicine stock. Contact admin to add new medicines.")

    col1, col2, col3 = st.columns(3)
    with col1: search = st.text_input("Search", placeholder="Brand or generic name")
    with col2:
        cats = run_query("SELECT DISTINCT category FROM medicines WHERE category IS NOT NULL ORDER BY category")
        cat  = st.selectbox("Category", ["All"]+[c['category'] for c in cats])
    with col3: stock_f = st.selectbox("Stock", ["All","In Stock","Low Stock","Out of Stock"])

    q = "SELECT medicine_id, brand_name, generic_name, category, stock_quantity, reorder_level, unit_price, expiry_date FROM medicines WHERE 1=1"
    p = []
    if search.strip(): q += " AND (LOWER(brand_name) LIKE LOWER(%s) OR LOWER(generic_name) LIKE LOWER(%s))"; p+=[f"%{search}%",f"%{search}%"]
    if cat!="All":     q += " AND category=%s"; p.append(cat)
    if stock_f=="In Stock":    q += " AND stock_quantity>reorder_level"
    elif stock_f=="Low Stock": q += " AND stock_quantity>0 AND stock_quantity<=reorder_level"
    elif stock_f=="Out of Stock": q += " AND stock_quantity=0"
    q += " ORDER BY brand_name"

    meds = run_query(q, p if p else None)
    if meds:
        st.dataframe(pd.DataFrame(meds), use_container_width=True)
    else:
        st.info("No medicines found.")

    # Pharmacist can RESTOCK (not add new)
    st.markdown("---")
    st.markdown("**📦 Restock Medicine**")
    st.caption("To add a completely new medicine, contact the Admin.")
    all_meds = run_query("SELECT medicine_id, brand_name, stock_quantity FROM medicines ORDER BY brand_name")
    m_sel    = st.selectbox("Medicine to Restock",
        [""]+[f"{m['medicine_id']} — {m['brand_name']} (Current: {m['stock_quantity']})" for m in all_meds])
    qty      = st.number_input("Quantity to Add", min_value=1, max_value=100000, value=100)

    if st.button("📦 Update Stock", type="primary"):
        if not m_sel:
            st.error("Select a medicine.")
        else:
            try:
                m_id = int(m_sel.split("—")[0].strip())
                run_query("UPDATE medicines SET stock_quantity=stock_quantity+%s WHERE medicine_id=%s",
                          [int(qty), m_id], fetch=False)
                updated = run_query_one("SELECT brand_name, stock_quantity FROM medicines WHERE medicine_id=%s", [m_id])
                st.success(f"✅ {updated['brand_name']} restocked to {updated['stock_quantity']} units!")
                st.rerun()
            except Exception as e:
                st.error(f"❌ {e}")


def show_low_stock(user):
    require_role(["Pharmacist"])
    st.markdown('<p class="page-title">⚠️ Low Stock Alerts</p>', unsafe_allow_html=True)
    low = run_query("""
        SELECT brand_name, generic_name, category,
               stock_quantity, reorder_level,
               (reorder_level-stock_quantity) AS units_short,
               expiry_date
        FROM medicines WHERE stock_quantity<=reorder_level
        ORDER BY units_short DESC
    """)
    if low:
        st.dataframe(pd.DataFrame(low), use_container_width=True)
        st.warning(f"⚠️ {len(low)} medicine(s) need restocking.")
    else:
        st.success("✅ All medicines are adequately stocked!")