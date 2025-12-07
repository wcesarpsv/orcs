import streamlit as st
from tinydb import TinyDB, Query
from datetime import datetime
import pandas as pd

# ============================
# DATABASE SETUP
# ============================

db = TinyDB("manual_db.json")
troubleshooting_table = db.table("troubleshooting")
brands_table = db.table("brands")
Q = Query()

st.set_page_config(page_title="Troubleshooting Guide – Technical Diagnostics", layout="wide")
st.title("🛠 Troubleshooting Guide – Technical Diagnostics")


# ============================
# PAGE: REGISTER BRAND
# ============================

def page_register_brand():
    st.header("🏷 Register Brand / Equipment Type")

    brand_name = st.text_input("Brand name*", placeholder="Ex: Admart, Carmanah, WJS Sign")

    if st.button("Save brand", type="primary"):
        if not brand_name:
            st.error("Brand name is required.")
        else:
            brands_table.insert({
                "brand": brand_name,
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M")
            })
            st.success("Brand saved successfully!")

    st.markdown("---")
    st.subheader("Registered brands")

    brands = brands_table.all()
    if brands:
        df = pd.DataFrame(brands)
        st.dataframe(df, use_container_width=True)
    else:
        st.info("No brands registered yet.")


# ============================
# PAGE: REGISTER ISSUE
# ============================

def page_register_issue():
    st.header("⚠ Register Issue / Symptom")

    brands = brands_table.all()
    if not brands:
        st.warning("No brands found. Register one in 'Register Brand' first.")
        return

    brand_names = [b["brand"] for b in brands]
    selected_brand = st.selectbox("Select brand:", brand_names)

    issue_title = st.text_input("Issue title*", placeholder="Ex: Sign Not Receiving Power")

    if st.button("Create issue", type="primary"):
        if not issue_title:
            st.error("Issue title is required.")
        else:
            troubleshooting_table.insert({
                "brand": selected_brand,
                "issue": issue_title,
                "failure_indicators": [],
                "corrective_actions": [],
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M")
            })
            st.success(f"Issue created for brand '{selected_brand}'!")


# ============================
# PAGE: FAILURE INDICATORS
# ============================

def page_failure_indicators():
    st.header("🔍 Add Failure Indicators")

    issues = troubleshooting_table.all()
    if not issues:
        st.warning("No issues found. Create one in 'Register Issue' first.")
        return

    issue_map = {f"{i['brand']} – {i['issue']}": i.doc_id for i in issues}
    option = st.selectbox("Select issue:", list(issue_map.keys()))
    issue_id = issue_map[option]

    indicator = st.text_input("Failure indicator*", placeholder="Ex: Display is blank, spontaneous restarts")

    if st.button("Add indicator", type="primary"):
        if not indicator:
            st.error("Indicator text is required.")
        else:
            row = troubleshooting_table.get(doc_id=issue_id)
            updated_list = row["failure_indicators"] + [indicator]
            troubleshooting_table.update({"failure_indicators": updated_list}, doc_ids=[issue_id])
            st.success("Indicator added!")

    st.markdown("---")
    st.subheader("Current indicators for this issue")

    row = troubleshooting_table.get(doc_id=issue_id)
    for i, item in enumerate(row["failure_indicators"], 1):
        st.write(f"{i}. {item}")


# ============================
# PAGE: CORRECTIVE ACTIONS
# ============================

def page_corrective_actions():
    st.header("🛠 Add Corrective Actions")

    issues = troubleshooting_table.all()
    if not issues:
        st.warning("No issues found. Create one first.")
        return

    issue_map = {f"{i['brand']} – {i['issue']}": i.doc_id for i in issues}
    option = st.selectbox("Select issue:", list(issue_map.keys()))
    issue_id = issue_map[option]

    action = st.text_area("Corrective action*", placeholder="Ex: Inspect cables, replace transceiver, reboot router")

    if st.button("Add corrective action", type="primary"):
        if not action:
            st.error("Corrective action text is required.")
        else:
            row = troubleshooting_table.get(doc_id=issue_id)
            updated_list = row["corrective_actions"] + [action]
            troubleshooting_table.update({"corrective_actions": updated_list}, doc_ids=[issue_id])
            st.success("Corrective action added!")

    st.markdown("---")
    st.subheader("Current actions for this issue")

    row = troubleshooting_table.get(doc_id=issue_id)
    for i, item in enumerate(row["corrective_actions"], 1):
        st.write(f"{i}. {item}")


# ============================
# PAGE: VIEW TROUBLESHOOTING GUIDE
# ============================

def page_view_guide():
    st.header("📘 Troubleshooting Guide – Full View")

    issues = troubleshooting_table.all()
    if not issues:
        st.info("No issues registered yet.")
        return

    # Group by brand
    grouped = {}
    for row in issues:
        grouped.setdefault(row["brand"], []).append(row)

    for brand, rows in grouped.items():
        st.markdown(f"## 🏷 {brand}")

        for item in rows:
            st.markdown(f"### **{item['issue']}**")

            st.markdown("#### 🔴 Failure Indicators")
            for f in item["failure_indicators"]:
                st.write(f"- {f}")

            st.markdown("#### 🟢 Corrective Actions")
            for c in item["corrective_actions"]:
                st.write(f"- {c}")

            st.markdown("---")


# ============================
# NAVIGATION MENU
# ============================

menu = st.sidebar.radio(
    "Troubleshooting Navigation",
    [
        "View Guide",
        "Register Brand",
        "Register Issue",
        "Add Failure Indicators",
        "Add Corrective Actions",
    ]
)

if menu == "View Guide":
    page_view_guide()
elif menu == "Register Brand":
    page_register_brand()
elif menu == "Register Issue":
    page_register_issue()
elif menu == "Add Failure Indicators":
    page_failure_indicators()
elif menu == "Add Corrective Actions":
    page_corrective_actions()
