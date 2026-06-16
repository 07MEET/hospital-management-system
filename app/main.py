"""
main.py — FIXED & REDESIGNED
Fixes: HTML metric cards rendering as raw HTML
       Login page layout issues
       Sidebar navigation using native Streamlit
       Sidebar arrow hidden on login page only, visible after login
       pages folder renamed to pageviews to avoid Streamlit default nav
"""
import streamlit as st
from styles import load_css
from auth import login, set_session, is_logged_in, logout, check_session_timeout

# Check login state BEFORE set_page_config so we can set sidebar state correctly
_logged_in = "user" in st.session_state

st.set_page_config(
    page_title="MediCare HMS",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="collapsed" if not _logged_in else "expanded"
)
st.markdown(load_css(), unsafe_allow_html=True)

# ── NAV CONFIG ────────────────────────────────────────────────
NAV = {
    "Admin":         ["📊 Dashboard","👥 Patients","📅 Appointments","👨‍⚕️ Doctors","💊 Medicines","🚨 Fraud Alerts","📋 Audit Log","⚙️ Settings"],
    "Doctor":        ["📊 Dashboard","📅 My Appointments","🩺 Diagnose & Prescribe","🔬 Lab Orders"],
    "Receptionist": ["📊 Dashboard", "👥 Patients", "📅 Appointments"],
    "Lab_Tech":      ["📊 Dashboard","⏳ Pending Orders","✅ Enter Results"],
    "Pharmacist":    ["📊 Dashboard","💊 Dispense Medicine","📦 Inventory","⚠️ Low Stock"],
    "Billing_Staff": ["📊 Dashboard","🧾 Generate Bill","💳 Record Payment","📜 Bill History","🚨 Fraud Alerts"],
}


# ── Login ─────────────────────────────────────────────────────
def show_login():
    # Hide the floating sidebar arrow ONLY on the login page
    st.markdown("""
        <style>
            [data-testid="stSidebarCollapsedControl"] {
                display: none !important;
                visibility: hidden !important;
                pointer-events: none !important;
                width: 0 !important;
                height: 0 !important;
            }
        </style>
    """, unsafe_allow_html=True)

    col_l, col_m, col_r = st.columns([1.2, 1, 1.2])
    with col_m:
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.markdown("## 🏥 MediCare HMS")
        st.caption("Hospital Management System — Secure Digital Healthcare")
        st.markdown("<br>", unsafe_allow_html=True)

        with st.form("login_form"):
            username = st.text_input("Username", placeholder="Enter username")
            password = st.text_input("Password", type="password", placeholder="Enter password")
            submitted = st.form_submit_button("Sign In →", use_container_width=True, type="primary")

        if submitted:
            if not username.strip():
                st.error("Username is required.")
            elif not password:
                st.error("Password is required.")
            else:
                with st.spinner("Authenticating..."):
                    user, error = login(username.strip(), password)
                if user:
                    set_session(user)
                    st.rerun()
                else:
                    st.error(error)

        with st.expander("Demo Accounts  (Password: Pass@1234)"):
            st.markdown("""
| Username | Role |
|---|---|
| `admin` | Admin |
| `dr_sharma` | Doctor |
| `reception1` | Receptionist |
| `labtech1` | Lab Tech |
| `pharma1` | Pharmacist |
| `billing1` | Billing |
            """)


# ── Sidebar ───────────────────────────────────────────────────
def show_sidebar(user: dict) -> str:
    role = user["role"]
    items = NAV.get(role, [])

    with st.sidebar:
        st.markdown(f"""
        <div style="padding:1.25rem 1rem 0.75rem;
                    border-bottom:1px solid rgba(255,255,255,0.08);">
            <div style="font-size:1.3rem;font-weight:700;color:#f1f5f9;
                        letter-spacing:-0.5px;">🏥 MediCare</div>
            <div style="font-size:0.7rem;color:#475569;
                        text-transform:uppercase;letter-spacing:1.5px;margin-top:2px;">
                Hospital Management
            </div>
        </div>
        <div style="padding:0.75rem 1rem;border-bottom:1px solid rgba(255,255,255,0.08);
                    margin-bottom:0.5rem;">
            <div style="font-size:0.875rem;font-weight:600;color:#e2e8f0;">
                {user['username']}
            </div>
            <div style="font-size:0.72rem;color:#3b82f6;margin-top:1px;">
                {role.replace('_',' ')}
            </div>
        </div>
        """, unsafe_allow_html=True)

        if "nav_page" not in st.session_state:
            st.session_state["nav_page"] = items[0] if items else ""

        for item in items:
            is_active = (st.session_state.get("nav_page") == item)
            label     = f"**{item}**" if is_active else item
            if st.button(label, key=f"nav_{item}", use_container_width=True):
                st.session_state["nav_page"] = item
                st.rerun()

        st.markdown("<br>", unsafe_allow_html=True)

        # DB connection status
        from db import test_connection
        ok, _ = test_connection()
        st.markdown(
            f'<div style="padding:0 1rem;font-size:0.72rem;color:#475569;">DB: '
            f'<span style="color:{"#22c55e" if ok else "#ef4444"}">{"● Connected" if ok else "● Disconnected"}</span></div>',
            unsafe_allow_html=True
        )
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Logout", use_container_width=True):
            logout()

    return st.session_state.get("nav_page", items[0] if items else "")


# ── Router ────────────────────────────────────────────────────
def route(user: dict, page: str):
    role = user["role"]

    if role == "Admin":
        if "Dashboard"     in page: from pageviews.admin import show_dashboard;  show_dashboard(user)
        elif "Patients"    in page: from pageviews.receptionist import show_register; show_register(user)
        elif "Appointment" in page: from pageviews.receptionist import show_book; show_book(user)
        elif "Doctors"     in page: from pageviews.admin import show_doctors;    show_doctors(user)
        elif "Medicines"   in page: from pageviews.admin import show_medicines;  show_medicines(user)
        elif "Fraud"       in page: from pageviews.billing import show_fraud;    show_fraud(user)
        elif "Audit"       in page: from pageviews.admin import show_audit;      show_audit(user)
        elif "Settings"    in page: from pageviews.admin import show_settings;   show_settings(user)

    elif role == "Doctor":
        if "Dashboard"     in page: from pageviews.doctor import show_dashboard;    show_dashboard(user)
        elif "Appointment" in page: from pageviews.doctor import show_appointments; show_appointments(user)
        elif "Diagnose"    in page: from pageviews.doctor import show_diagnose;     show_diagnose(user)
        elif "Lab"         in page: from pageviews.doctor import show_lab;          show_lab(user)

    elif role == "Receptionist":
        if "Dashboard"     in page: from pageviews.receptionist import show_dashboard; show_dashboard(user)
        elif "Patients" in page: from pageviews.receptionist import show_patients; show_patients(user)
        elif "Appointments" in page: from pageviews.receptionist import show_appointment_management; show_appointment_management(user)

    elif role == "Lab_Tech":
        if "Dashboard"     in page: from pageviews.lab_tech import show_dashboard; show_dashboard(user)
        elif "Pending"     in page: from pageviews.lab_tech import show_pending;   show_pending(user)
        elif "Results"     in page: from pageviews.lab_tech import show_results;   show_results(user)

    elif role == "Pharmacist":
        if "Dashboard"     in page: from pageviews.pharmacist import show_dashboard;  show_dashboard(user)
        elif "Dispense"    in page: from pageviews.pharmacist import show_dispense;   show_dispense(user)
        elif "Inventory"   in page: from pageviews.pharmacist import show_inventory;  show_inventory(user)
        elif "Low"         in page: from pageviews.pharmacist import show_low_stock;  show_low_stock(user)

    elif role == "Billing_Staff":
        if "Dashboard"     in page: from pageviews.billing import show_dashboard; show_dashboard(user)
        elif "Generate"    in page: from pageviews.billing import show_generate;  show_generate(user)
        elif "Payment"     in page: from pageviews.billing import show_payment;   show_payment(user)
        elif "History" in page: from pageviews.billing import show_bill_history; show_bill_history(user)
        elif "Fraud"       in page: from pageviews.billing import show_fraud;     show_fraud(user)
        


# ── Entry ─────────────────────────────────────────────────────
def main():
    check_session_timeout()
    if not is_logged_in():
        show_login()
    else:
        user = st.session_state["user"]
        page = show_sidebar(user)
        route(user, page)

if __name__ == "__main__":
    main()