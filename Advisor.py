import sqlite3
from datetime import datetime, timedelta
import streamlit as st
import pytz
import pandas as pd
import uuid

# Helper to get Kolkata time
def get_kolkata_time():
    kolkata_tz = pytz.timezone("Asia/Kolkata")
    return datetime.now(kolkata_tz).strftime('%Y-%m-%d %H:%M:%S')

# Helper function for database connection management
def get_db_connection():
    return sqlite3.connect("Tools_And_Tools.sqlite", check_same_thread=False)

# Ensure a unique session ID is initialized
def initialize_session():
    if 'session_id' not in st.session_state:
        st.session_state['session_id'] = str(uuid.uuid4())

# Fix empty label warnings by collapsing labels
def styled_number_input(label, value, key):
    return st.number_input(
        label,
        min_value=0,
        max_value=9999,
        value=value,
        step=1,
        key=key,
        label_visibility="collapsed"
    )

def daily_workstation_data_entry(workstation_name, supervisor_name):
    st.title("Daily Workstation Data Entry")

    initialize_session()

    kolkata_time = get_kolkata_time()
    current_date = datetime.now(pytz.timezone("Asia/Kolkata")).strftime("%Y-%m-%d")

    with get_db_connection() as conn:
        cursor = conn.cursor()

        # Fetch target value from User_Credentials
        cursor.execute('SELECT Target FROM User_Credentials WHERE Name = ?', (workstation_name,))
        target_value = cursor.fetchone()
        target_display = target_value[0] if target_value else "No Target Assigned"
        st.write(f"**Target:** {target_display}")

        # Fetch cumulative data for the current month
        start_of_month = datetime.now(pytz.timezone("Asia/Kolkata")).replace(day=1).strftime("%Y-%m-%d")
        cursor.execute('''
            SELECT SUM(running_repair), SUM(free_service), SUM(paid_service), SUM(body_shop), 
                   SUM(total), SUM(align), SUM(balance), SUM(align_and_balance)
            FROM Workstation_Data
            WHERE date >= ? AND workstation_name = ?
        ''', (start_of_month, workstation_name))
        monthly_totals = cursor.fetchone()

        st.subheader("Monthly Summary (From Start of Month to Today)")
        if any(monthly_totals):
            summary_df = pd.DataFrame(
                [monthly_totals],
                columns=[
                    "Running Repair", "Free Service", "Paid Service", "Body Shop",
                    "Total", "Align", "Balance", "Align and Balance"
                ]
            )
            st.table(summary_df)
        else:
            st.write("No data submitted for this month.")

        # Fetch existing data for the current date
        cursor.execute('''
            SELECT running_repair, free_service, paid_service, body_shop, total, align, balance, align_and_balance
            FROM Workstation_Data
            WHERE date = ? AND workstation_name = ?
        ''', (current_date, workstation_name))
        existing_data = cursor.fetchone()

    # Display Existing Data at the Top
    st.subheader("Existing Data for Today")
    if existing_data:
        existing_df = pd.DataFrame(
            [existing_data],
            columns=[
                "Running Repair", "Free Service", "Paid Service", "Body Shop",
                "Total", "Align", "Balance", "Align and Balance"
            ]
        )
        st.table(existing_df)
    else:
        st.write("No data submitted for today. (Empty)")

    # Input fields for new data
    st.subheader("Enter Data for Today")
    default_values = existing_data if existing_data else (0, 0, 0, 0, 0, 0, 0, 0)
    st.write("Running Repair")
    running_repair = styled_number_input("Running Repair", default_values[0], key="rr")
    st.write("Free Service")
    free_service = styled_number_input("Free Service", default_values[1], key="fs")
    st.write("Paid Service")
    paid_service = styled_number_input("Paid Service", default_values[2], key="ps")
    st.write("Body Shop")
    body_shop = styled_number_input("Body Shop", default_values[3], key="bs")
    total = running_repair + free_service + paid_service + body_shop
    st.markdown(f"**Total:** {total}")
    st.write("Align")
    align = styled_number_input("Align", default_values[5], key="align")
    st.write("Balance")
    balance = styled_number_input("Balance", default_values[6], key="balance")

    

    align_and_balance = align + balance
    st.markdown(f"**Align and Balance:** {align_and_balance}")


    # Submit Button
    if st.button("Submit Data"):
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                if existing_data:
                    cursor.execute('''
                        UPDATE Workstation_Data
                        SET running_repair = ?, free_service = ?, paid_service = ?, body_shop = ?, 
                            total = ?, align = ?, balance = ?, align_and_balance = ?, timestamp = ?
                        WHERE date = ? AND workstation_name = ?
                    ''', (
                        running_repair, free_service, paid_service, body_shop, total,
                        align, balance, align_and_balance, kolkata_time,
                        current_date, workstation_name
                    ))
                else:
                    cursor.execute('''
                        INSERT INTO Workstation_Data (date, timestamp, workstation_name, supervisor_name, 
                                                      running_repair, free_service, paid_service, body_shop, total, 
                                                      align, balance, align_and_balance)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        current_date, kolkata_time, workstation_name, supervisor_name,
                        running_repair, free_service, paid_service, body_shop, total,
                        align, balance, align_and_balance
                    ))
                conn.commit()
            st.success("Workstation data submitted successfully!")
        except ValueError:
            st.error("Please enter valid integer values between 0 and 9999.")

    #==================================================
    #Main Page
def workstation_interface(user_workstation_id):
    st.title("Workstation Dashboard")
    with get_db_connection() as conn:
        cursor = conn.cursor()
    # st.sidebar.title("Options")
    # option = st.sidebar.radio("Choose an Action", ["Daily Workstation Data Entry", "Daily Advisor Data Entry"])
    option = st.sidebar.selectbox("Choose an Action", ["Daily Workstation Data Entry", "Daily Advisor Data Entry"])
    # Retrieve Advisor names under the current Workstation
    cursor.execute("SELECT name FROM User_Credentials WHERE Supervisor_Code = ? AND User_Role = 'Advisor'", (user_workstation_id,))
    advisors = cursor.fetchall()



    # Fetch supervisor name for the current workstation
    cursor.execute("SELECT Supervisor_Code FROM User_Credentials WHERE code = ?", (user_workstation_id,))
    supervisor_data = cursor.fetchone()
    supervisor_name = supervisor_data[0] if supervisor_data else "N/A"

    # Get the logged-in workstation name
    cursor.execute("SELECT name FROM User_Credentials WHERE code = ?", (user_workstation_id,))
    workstation_data = cursor.fetchone()
    workstation_name = workstation_data[0] if workstation_data else "N/A"

    if option == "Daily Workstation Data Entry":
        daily_workstation_data_entry(workstation_name, supervisor_name)
    elif option == "Daily Advisor Data Entry":
        if not advisors:
            st.write("No advisors found for this workstation.")
            return  # Stop if no advisors are found
        daily_advisor_data_entry(user_workstation_id,supervisor_name) 


def daily_advisor_data_entry(user_workstation_id,supervisor_name):
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
    # Retrieve Advisor names under the current Workstation
    cursor.execute("SELECT name FROM User_Credentials WHERE Supervisor_Code = ? AND User_Role = 'Advisor'", (user_workstation_id,))
    advisors = cursor.fetchall()

    # Get the date from the date picker
    start_date = datetime.now() - timedelta(days=180)
    selected_date = st.date_input("Select Date", value=datetime.now().date(), min_value=start_date.date(), max_value=datetime.now().date())
  
    # Display headers as a fixed row
    st.markdown(
        "<style>div.row-header {display: flex; justify-content: space-between; font-weight: bold;}</style>",
        unsafe_allow_html=True
    )
    st.markdown('<div class="row-header">', unsafe_allow_html=True)
    col1, col2, col3, col4, col5, col6, col7, col8, col9, col10 = st.columns([1.5, 1.5, 2, 2, 2, 2, 2, 2, 2, 2])
    with col1:
        st.write("Advisor Name")
    with col2:
        st.write("Edit")
    with col3:
        st.write("Running Repair")
    with col4:
        st.write("Free Service")
    with col5:
        st.write("Paid Service")
    with col6:
        st.write("Body Shop")
    with col7:
        st.write("Total")
    with col8:
        st.write("Align")
    with col9:
        st.write("Balance")
    with col10:
        st.write("Align and Balance")
    st.markdown('</div>', unsafe_allow_html=True)

    # Display rows for each advisor
    rows_data = []
    for advisor in advisors:
        advisor_name = advisor[0]

        # Check if data exists for the selected date and advisor
        cursor.execute("""
            SELECT running_repair, free_service, paid_service, body_shop, align, balance
            FROM Advisor_Data
            WHERE date = ? AND advisor_name = ?
        """, (selected_date, advisor_name))
        result = cursor.fetchone()

        # Set initial values based on existing data if found, or default values if not
        if result:
            initial_running_repair, initial_free_service, initial_paid_service, initial_body_shop, initial_align, initial_balance = result
        else:
            initial_running_repair = initial_free_service = initial_paid_service = initial_body_shop = initial_align = initial_balance = 0

        # Arrange input fields in columns
        col1, col2, col3, col4, col5, col6, col7, col8, col9, col10 = st.columns([1.5, 1.5, 2, 2, 2, 2, 2, 2, 2, 2])
        with col1:
            st.write(advisor_name)
        with col2:
            edit_row = st.checkbox("", key=f"edit_{advisor_name}")  # Checkbox in its own column
        with col3:
            running_repair = st.number_input(f"Running Repair {advisor_name}", min_value=0, value=initial_running_repair, step=1, key=f"rr_{advisor_name}", disabled=not edit_row, max_value=9999, label_visibility="collapsed")
        with col4:
            free_service = st.number_input(f"Free Service {advisor_name}", min_value=0, value=initial_free_service, step=1, key=f"fs_{advisor_name}", disabled=not edit_row, max_value=9999, label_visibility="collapsed")
        with col5:
            paid_service = st.number_input(f"Paid Service {advisor_name}", min_value=0, value=initial_paid_service, step=1, key=f"ps_{advisor_name}", disabled=not edit_row, max_value=9999, label_visibility="collapsed")
        with col6:
            body_shop = st.number_input(f"Body Shop {advisor_name}", min_value=0, value=initial_body_shop, step=1, key=f"bs_{advisor_name}", disabled=not edit_row, max_value=9999, label_visibility="collapsed")

        # Total Calculation
        total = running_repair + free_service + paid_service + body_shop
        with col7:
            st.write(total)  # Display total for reference

        with col8:
            align = st.number_input(f"Align {advisor_name}", min_value=0, value=initial_align, step=1, key=f"al_{advisor_name}", disabled=not edit_row, max_value=9999, label_visibility="collapsed")
        with col9:
            balance = st.number_input(f"Balance {advisor_name}", min_value=0, value=initial_balance, step=1, key=f"bal_{advisor_name}", disabled=not edit_row, max_value=9999, label_visibility="collapsed")

        # Align and Balance Calculation
        align_and_balance = align + balance
        with col10:
            st.write(align_and_balance)  # Display align_and_balance for reference

        # Only add data to rows_data if the row is editable
        if edit_row:
            rows_data.append({
                "date": selected_date,
                "advisor_name": advisor_name,
                "running_repair": running_repair,
                "free_service": free_service,
                "paid_service": paid_service,
                "body_shop": body_shop,
                "total": total,
                "align": align,
                "balance": balance,
                "align_and_balance": align_and_balance
            })

        # Add a horizontal line after each advisor row
        st.markdown("---")
#================================================


# Main function to run the dashboard
def main():
    st.set_page_config(page_title="Workstation Dashboard", layout="wide")
    st.sidebar.title("Options")
    option = st.sidebar.radio("Choose an Action", ["Daily Workstation Data Entry"])

    if option == "Daily Workstation Data Entry":
        # Replace with actual data for logged-in workstation and supervisor
        workstation_name = "Workstation A"
        supervisor_name = "Supervisor B"
        daily_workstation_data_entry(workstation_name, supervisor_name)


if __name__ == "__main__":
    main()
