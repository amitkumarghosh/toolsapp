import sqlite3
from datetime import datetime, timedelta
import streamlit as st
import pytz
import pandas as pd
import time


# Connect to SQLite database
conn = sqlite3.connect("Tools_And_Tools.sqlite", check_same_thread=False)
cursor = conn.cursor()


def get_kolkata_time():
    kolkata_tz = pytz.timezone("Asia/Kolkata")
    return datetime.now(kolkata_tz).strftime('%Y-%m-%d %H:%M:%S')


def styled_input_box(label, default_value, submitted):
    """
    Creates a styled input box with:
    - Font color dynamically changing (green for submitted, yellow for not submitted).
    - No counter or other additional visual clutter.
    """
    # Determine font color
    font_color = "green" if submitted else "yellow"

    # Generate unique key for each input
    unique_key = label.replace(" ", "_").lower()

    # Display styled input box
    st.markdown(
        f"""
        <style>
        .{unique_key} {{
            font-size: 16px;
            color: {font_color};
            border: 1px solid #ddd;
            padding: 5px;
            width: 80px;
            height: 30px;
            text-align: center;
            border-radius: 5px;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )
    user_input = st.text_input(
        label=f"{label}",
        value=str(default_value),
        key=unique_key,
    )
    if not user_input.isdigit() or not (0 <= int(user_input) <= 9999):
        st.error(f"{label} must be an integer between 0 and 9999.")
        return default_value
    return int(user_input)

def daily_workstation_data_entry(workstation_name, supervisor_name):
    # st.title("Daily Workstation Data Entry")
    st.write(f"Logged in as: {workstation_name}")

    # Get the current date, timestamp, and start of the current month
    kolkata_time = get_kolkata_time()
    current_date = datetime.now(pytz.timezone("Asia/Kolkata"))
    start_of_month = current_date.replace(day=1)

    with sqlite3.connect("Tools_And_Tools.sqlite") as conn:
        cursor = conn.cursor()
        # Fetch target value from User_Credentials
        cursor.execute('SELECT Target FROM User_Credentials WHERE Name = ?', (workstation_name,))
        target_value = cursor.fetchone()
        target_display = target_value[0] if target_value else "No Target Assigned"
        st.write(f"**Target:** {target_display}")

        # Fetch cumulative data for the current month
        cursor.execute('''
            SELECT SUM(running_repair), SUM(free_service), SUM(paid_service), SUM(body_shop), 
                SUM(total), SUM(align), SUM(balance), SUM(align_and_balance)
            FROM Workstation_Data
            WHERE date >= ? AND workstation_name = ?
        ''', (start_of_month, workstation_name))
        monthly_totals = cursor.fetchone()

        # Display Monthly Summary Table
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

    # Current date
    current_date = datetime.now(pytz.timezone("Asia/Kolkata")).strftime("%Y-%m-%d")
    
    # Define fields
    fields = ["Running Repair", "Free Service", "Paid Service", "Body Shop", "Align", "Balance"]
    default_values = [0] * len(fields)
    input_values = {}
    summary_data = None

    # Connect to database and fetch existing data
    with sqlite3.connect("Tools_And_Tools.sqlite") as conn:
        cursor = conn.cursor()

        # Check if data exists for the current date
        cursor.execute('SELECT * FROM Workstation_Data WHERE date = ? AND workstation_name = ?', (current_date, workstation_name))
        existing_data = cursor.fetchone()

        # Fetch summary data for the current month
        cursor.execute('''
            SELECT 
                SUM(running_repair), SUM(free_service), SUM(paid_service), SUM(body_shop), 
                SUM(total), SUM(align), SUM(balance), SUM(align_and_balance) 
            FROM Workstation_Data
            WHERE strftime('%Y-%m', date) = strftime('%Y-%m', DATE('now', 'localtime'))
              AND workstation_name = ?
        ''', (workstation_name,))
        summary_data = cursor.fetchone()

        # Check if data already exists for the current date
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
    # Retain existing data as defaults if available
    default_values = existing_data if existing_data else (0, 0, 0, 0, 0, 0, 0, 0)

    running_repair = st.text_input("Running Repair", value=str(default_values[0]), key="rr")
    free_service = st.text_input("Free Service", value=str(default_values[1]), key="fs")
    paid_service = st.text_input("Paid Service", value=str(default_values[2]), key="ps")
    body_shop = st.text_input("Body Shop", value=str(default_values[3]), key="bs")

    try:
        total = int(running_repair) + int(free_service) + int(paid_service) + int(body_shop)
    except ValueError:
        total = default_values[4]
    st.markdown(f"**Total:** {total}")

    align = st.text_input("Align", value=str(default_values[5]), key="align")
    balance = st.text_input("Balance", value=str(default_values[6]), key="balance")

    try:
        align_and_balance = int(align) + int(balance)
    except ValueError:
        align_and_balance = default_values[7]
    st.markdown(f"**Align and Balance:** {align_and_balance}")

    # Submit Button
    if st.button("Submit Data"):
        try:
            if existing_data:
                # Update existing data (retain values if not edited)
                cursor.execute('''
                    UPDATE Workstation_Data
                    SET running_repair = ?, free_service = ?, paid_service = ?, body_shop = ?, total = ?, align = ?, balance = ?, align_and_balance = ?, timestamp = ?
                    WHERE date = ? AND workstation_name = ?
                ''', (
                    int(running_repair) if running_repair else default_values[0],
                    int(free_service) if free_service else default_values[1],
                    int(paid_service) if paid_service else default_values[2],
                    int(body_shop) if body_shop else default_values[3],
                    total,
                    int(align) if align else default_values[5],
                    int(balance) if balance else default_values[6],
                    align_and_balance, kolkata_time,
                    current_date, workstation_name
                ))
                with st.spinner('Wait for it...'):
                    time.sleep(1)
                    st.success("Workstation data submitted successfully!")
                    time.sleep(1)
            else:
                # Insert new data
                cursor.execute('''
                    INSERT INTO Workstation_Data (date, timestamp, workstation_name, supervisor_name, running_repair, free_service, paid_service, body_shop, total, align, balance, align_and_balance)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    current_date, kolkata_time, workstation_name, supervisor_name,
                    int(running_repair), int(free_service), int(paid_service), int(body_shop), total,
                    int(align), int(balance), align_and_balance
                ))
                with st.spinner('Wait for it...'):
                    time.sleep(1)
                    st.success("Workstation data submitted successfully!")
                    time.sleep(1)
            conn.commit()
            st.rerun()
        except ValueError:
            st.error("Please enter valid integer values between 0 and 9999.")


#Main Page
def workstation_interface(user_workstation_id):
    st.title("Workstation Dashboard")

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

    # After collecting the rows_data, add the `timestamp` and `supervisor_code` to each entry and submit data
   
    if st.button("Submit Data"):
        for row in rows_data:
            # Check if a record exists for the current advisor and date
            cursor.execute("""
                SELECT COUNT(*)
                FROM Advisor_Data
                WHERE date = ? AND advisor_name = ?
            """, (row["date"], row["advisor_name"]))
            record_exists = cursor.fetchone()[0] > 0

            if record_exists:
                # Update existing record without changing the timestamp
                cursor.execute('''
                    UPDATE Advisor_Data
                    SET running_repair = ?, free_service = ?, paid_service = ?, body_shop = ?, total = ?, align = ?, balance = ?, align_and_balance = ?
                    WHERE date = ? AND advisor_name = ?
                ''', (
                    row["running_repair"], row["free_service"], row["paid_service"], row["body_shop"],
                    row["total"], row["align"], row["balance"], row["align_and_balance"],
                    row["date"], row["advisor_name"]
                ))
            else:
                # Insert new record with timestamp
                # timestamp = get_kolkata_time()
                timestamp = datetime.now(pytz.timezone("Asia/Kolkata")).strftime("%Y-%m-%d")
                cursor.execute('''
                    INSERT INTO Advisor_Data (date, workstation_name, supervisor_name, advisor_name, running_repair, free_service, paid_service, body_shop, total, align, balance, align_and_balance, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    row["date"], user_workstation_id, supervisor_name, row["advisor_name"],
                    row["running_repair"], row["free_service"], row["paid_service"], row["body_shop"],
                    row["total"], row["align"], row["balance"], row["align_and_balance"], timestamp
                ))

        conn.commit()
        st.success("Data submitted successfully.")
