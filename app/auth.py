"""
auth.py — Authentication, session management, and security for HMS
"""
import streamlit as st
import datetime
from db import get_connection, run_query, run_query_one


# ── Login ─────────────────────────────────────────────────────────────────
def login(username: str, password: str) -> tuple[dict | None, str | None]:
    """
    Authenticate user. Returns (user_dict, None) on success
    or (None, error_message) on failure.
    """
    if not username or not password:
        return None, "Username and password are required."

    # Sanitize
    username = username.strip().lower()

    conn = None
    try:
        conn = get_connection()
        cur  = conn.cursor()

        # Fetch user with password check
        cur.execute("""
            SELECT u.user_id, u.username, r.role_name, u.is_active,
                   u.locked_until, u.failed_attempts,
                   u.staff_ref_id,
                   (u.password_hash = crypt(%s, u.password_hash)) AS pwd_ok
            FROM users u
            JOIN roles r ON u.role_id = r.role_id
            WHERE LOWER(u.username) = %s
        """, (password, username))

        row = cur.fetchone()

        if row is None:
            conn.close()
            return None, "Invalid username or password."

        (user_id, uname, role, is_active,
         locked_until, failed_attempts, staff_ref_id, pwd_ok) = row

        # Check if account is locked
        if locked_until and locked_until > datetime.datetime.now():
            mins_left = int((locked_until - datetime.datetime.now()).seconds / 60) + 1
            conn.close()
            return None, f"🔒 Account locked for {mins_left} more minute(s) due to too many failed attempts."

        # Check password
        if not pwd_ok:
            # Increment failed attempts
            new_attempts = failed_attempts + 1
            lock_time = None
            if new_attempts >= 5:
                lock_time = datetime.datetime.now() + datetime.timedelta(minutes=30)
                msg = f"❌ Invalid password. Account locked for 30 minutes after {new_attempts} failed attempts."
            else:
                remaining = 5 - new_attempts
                msg = f"❌ Invalid password. {remaining} attempt(s) remaining before lockout."

            cur.execute("""
                UPDATE users
                SET failed_attempts = %s,
                    locked_until = %s
                WHERE user_id = %s
            """, (new_attempts, lock_time, user_id))
            conn.commit()
            conn.close()
            return None, msg

        # Check active
        if not is_active:
            conn.close()
            return None, "🚫 Your account has been disabled. Please contact the administrator."

        # Success — reset failed attempts, update last login
        cur.execute("""
            UPDATE users
            SET failed_attempts = 0,
                locked_until    = NULL,
                last_login      = NOW()
            WHERE user_id = %s
        """, (user_id,))
        conn.commit()
        conn.close()

        return {
            "user_id":      user_id,
            "username":     uname,
            "role":         role,
            "staff_ref_id": staff_ref_id
        }, None

    except Exception as e:
        if conn:
            conn.close()
        return None, f"Login error: Please ensure the database is running."


# ── Session helpers ───────────────────────────────────────────────────────
def set_session(user: dict):
    """Store user in Streamlit session state."""
    now = datetime.datetime.now()
    
    st.session_state["user"] = user
    st.session_state["login_time"] = now
    st.session_state["last_activity"] = now


def get_session() -> dict | None:
    """Return current user dict or None."""
    return st.session_state.get("user")


def is_logged_in() -> bool:
    return "user" in st.session_state


def require_login():
    """Redirect to login if not authenticated."""
    
    check_session_timeout()

    if not is_logged_in():
        st.warning("⚠️ Please login to access this page.")
        st.stop()

    st.session_state["last_activity"] = datetime.datetime.now()

    return st.session_state["user"]


def require_role(allowed_roles: list):
    """Ensure user has one of the allowed roles."""
    user = require_login()
    if user["role"] not in allowed_roles:
        st.error(f"🚫 Access denied. This page requires: {', '.join(allowed_roles)}")
        st.stop()
    return user


def logout():
    """Clear session and rerun."""
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()


# ── Session Timeout ───────────────────────────────────────────────────────
SESSION_TIMEOUT_MINUTES = 60

def check_session_timeout():
    """Auto-logout after inactivity."""
    
    if not is_logged_in():
        return

    last_activity = st.session_state.get("last_activity")

    if last_activity:
        elapsed = (
            datetime.datetime.now() - last_activity
        ).total_seconds() / 60

        if elapsed >= SESSION_TIMEOUT_MINUTES:
            logout()
