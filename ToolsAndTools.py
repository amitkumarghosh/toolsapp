import time
import streamlit as st
import sqlite3
import os
import shutil
from datetime import datetime, timedelta
import cv2
from PIL import Image
import io
import pandas as pd
import openpyxl
import zipfile
import pytz
import Advisor


def export_tables_to_csv(db_path, export_dir):
    """Export all tables from SQLite database to CSV files."""
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        
        if not os.path.exists(export_dir):
            os.makedirs(export_dir)
        
        for table in tables:
            table_name = table[0]
            df = pd.read_sql_query(f"SELECT * FROM {table_name}", conn)
            df.to_excel(os.path.join(export_dir, f"{table_name}.xlsx"), index=False)

def download_all_reports():
    """Generate a ZIP file containing all reports and the image folder, then delete the ZIP after download."""
    db_path = "Tools_And_Tools.sqlite"
    export_dir = "exported_reports"
    zip_file_name = datetime.now(pytz.timezone("Asia/Kolkata")).strftime("%d-%B-%Y") + ".zip"

    # Export tables to CSV
    export_tables_to_csv(db_path, export_dir)

    # Include the image folder
    if os.path.exists("images"):
        shutil.copytree("images", os.path.join(export_dir, "images"), dirs_exist_ok=True)
    
    # Create ZIP
    with zipfile.ZipFile(zip_file_name, "w") as zipf:
        for root, _, files in os.walk(export_dir):
            for file in files:
                file_path = os.path.join(root, file)
                zipf.write(file_path, os.path.relpath(file_path, export_dir))
    
    # Remove temporary files
    shutil.rmtree(export_dir)

    # Serve the file and delete after download
    try:
        with open(zip_file_name, "rb") as zip_file:
            zip_data = zip_file.read()
        os.remove(zip_file_name)  # Delete the ZIP file after reading it
        return zip_data  # Return binary data for downloading
    except Exception as e:
        st.error(f"Error occurred while processing the ZIP file: {e}")
        if os.path.exists(zip_file_name):
            os.remove(zip_file_name)  # Ensure the ZIP file is deleted in case of an error
        return None




def sales_admin_workshop_data(user_role, supervisor_code):
    """View and upload workstation data with Supervisor filtering."""
    st.subheader("Workshop Data")
    user_role = st.session_state.user_data['role']
    supervisor_code = st.session_state.user_data.get('code')

    conn = sqlite3.connect('Tools_And_Tools.sqlite')

    # Filter workstation data based on the user role
    if user_role == "Super Admin":
        df = pd.read_sql_query("SELECT * FROM Workstation_Data", conn)
        if df.empty:
            st.write("Empty")
        else:
            st.dataframe(df)

        # Option to upload new data
        st.write("Upload Data")
        uploaded_file = st.file_uploader("Choose an Excel file", type=["xlsx"])  # Accept only .xlsx files

        if uploaded_file is not None:
            try:
                # Read the Excel file
                new_data = pd.read_excel(uploaded_file, sheet_name=None)  # sheet_name=None reads all sheets into a dictionary
                # If you know the sheet name you want to load, use sheet_name="YourSheetName"
                
                # Assuming you know the sheet name, you can access it like this:
                sheet_name = "Sheet1"  # Replace with the actual sheet name
                if sheet_name in new_data:
                    df = new_data[sheet_name]  # Get the data from the specified sheet
                else:
                    raise ValueError(f"Sheet '{sheet_name}' not found in the uploaded file.")
                
                # Open the connection to the SQLite database
                conn = sqlite3.connect('Tools_And_Tools.sqlite')
                c = conn.cursor()

                # Delete all existing data from the Workstation_Data table
                c.execute("DELETE FROM Workstation_Data")
                conn.commit()  # Commit the delete operation
                
                # Now upload the new data
                df.to_sql("Workstation_Data", conn, if_exists="append", index=False)
                conn.close()
                
                st.success("Data uploaded successfully and previous data cleared.")
            except Exception as e:
                st.error(f"Error uploading data: {e}")

    elif user_role == "Supervisor":
        df = pd.read_sql_query(
            "SELECT * FROM Workstation_Data WHERE supervisor_name = ?", conn, params=(supervisor_code,)
        )

        if df.empty:
            st.write("Empty")
        else:
            st.dataframe(df)
            workstation_entry_by_supervisor(supervisor_code)
        
    else:
        st.error("Unauthorized access")
        return

    # if df.empty:
    #     st.write("Empty")
    # else:
    #     st.dataframe(df)

    # Option to upload new data
    # st.write("Upload Data")
    # uploaded_file = st.file_uploader("Choose a CSV file", type=["csv"])
    # if uploaded_file is not None:
    #     try:
    #         new_data = pd.read_csv(uploaded_file)
    #         new_data.to_sql("Workstation_Data", conn, if_exists="append", index=False)
    #         st.success("Data uploaded successfully")
    #     except Exception as e:
    #         st.error(f"Error uploading data: {e}")
    # conn.close()



def workstation_entry_by_supervisor(supervisor_code):
    conn = sqlite3.connect('Tools_And_Tools.sqlite')
    c = conn.cursor()
    
    # Fetch workstation names for the supervisor
    c.execute("SELECT name FROM User_Credentials WHERE Supervisor_Code = ? AND User_Role = 'Workstation'", (supervisor_code,))
    wksts = c.fetchall()
    wkst_names = [wkst[0] for wkst in wksts]  # List of workstation names
    
    # Get the date from the date picker
    start_date = datetime.now(pytz.timezone("Asia/Kolkata")) - timedelta(days=60)
    selected_date = st.date_input("Select Date", value=datetime.now(pytz.timezone("Asia/Kolkata")).date(), min_value=start_date.date(), max_value=datetime.now().date())
    
    # Dropdown to select workstation name
    selected_wkst = st.selectbox("Select Workstation", wkst_names)
    
    # Fetch existing data for the selected workstation and date
    c.execute("""
        SELECT running_repair, free_service, paid_service, body_shop, align, balance
        FROM Workstation_Data
        WHERE date = ? AND workstation_name = ?
    """, (selected_date, selected_wkst))
    result = c.fetchone()
    
    # Set initial values based on existing data if found, or default values if not
    if result:
        initial_running_repair, initial_free_service, initial_paid_service, initial_body_shop, initial_align, initial_balance = result
    else:
        initial_running_repair = initial_free_service = initial_paid_service = initial_body_shop = initial_align = initial_balance = 0

    # Input fields for the selected workstation
    st.markdown(
        "<style>div.row-header {display: flex; justify-content: space-between; font-weight: bold;}</style>",
        unsafe_allow_html=True
    )
    
    col1, col2, col3, col4, col5, col6, col7, col8, col9, col10 = st.columns([1.5, 1.5, 2, 2, 2, 2, 2, 2, 2, 2])
    with col1:
        st.write("WKSt Name")
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
    
    st.markdown('<div class="row-header">', unsafe_allow_html=True)
    
    # Display input fields for the selected workstation
    edit_row = st.checkbox("Edit", key=f"edit_{selected_wkst}")
    
    with col3:
        running_repair = st.number_input(f"Running Repair {selected_wkst}", min_value=0, value=initial_running_repair, step=1, key=f"rr_{selected_wkst}", disabled=not edit_row, max_value=9999, label_visibility="collapsed")
    with col4:
        free_service = st.number_input(f"Free Service {selected_wkst}", min_value=0, value=initial_free_service, step=1, key=f"fs_{selected_wkst}", disabled=not edit_row, max_value=9999, label_visibility="collapsed")
    with col5:
        paid_service = st.number_input(f"Paid Service {selected_wkst}", min_value=0, value=initial_paid_service, step=1, key=f"ps_{selected_wkst}", disabled=not edit_row, max_value=9999, label_visibility="collapsed")
    with col6:
        body_shop = st.number_input(f"Body Shop {selected_wkst}", min_value=0, value=initial_body_shop, step=1, key=f"bs_{selected_wkst}", disabled=not edit_row, max_value=9999, label_visibility="collapsed")
    
    # Total Calculation
    total = running_repair + free_service + paid_service + body_shop
    with col7:
        st.write(total)  # Display total for reference
    
    with col8:
        align = st.number_input(f"Align {selected_wkst}", min_value=0, value=initial_align, step=1, key=f"al_{selected_wkst}", disabled=not edit_row, max_value=9999, label_visibility="collapsed")
    with col9:
        balance = st.number_input(f"Balance {selected_wkst}", min_value=0, value=initial_balance, step=1, key=f"bal_{selected_wkst}", disabled=not edit_row, max_value=9999, label_visibility="collapsed")
    
    # Align and Balance Calculation
    align_and_balance = align + balance
    with col10:
        st.write(align_and_balance)  # Display align_and_balance for reference
    
    # Only add data to rows_data if the row is editable
    rows_data = []
    if edit_row:
        rows_data.append({
            "date": selected_date,
            "workstation_name": selected_wkst,
            "running_repair": running_repair,
            "free_service": free_service,
            "paid_service": paid_service,
            "body_shop": body_shop,
            "total": total,
            "align": align,
            "balance": balance,
            "align_and_balance": align_and_balance
        })

    # Submit data
    if st.button("Submit Data"):
        for row in rows_data:
            # Check if a record exists for the current workstation and date
            c.execute("""
                SELECT COUNT(*)
                FROM Workstation_Data
                WHERE date = ? AND workstation_name = ?
            """, (row["date"], row["workstation_name"]))
            record_exists = c.fetchone()[0] > 0

            if record_exists:
                timestamp = datetime.now(pytz.timezone("Asia/Kolkata")).strftime("%Y-%m-%d %H:%M:%S")
                # Update existing record without changing the timestamp
                c.execute('''
                    UPDATE Workstation_Data
                    SET running_repair = ?, free_service = ?, timestamp = ?, paid_service = ?, body_shop = ?, total = ?, align = ?, balance = ?, align_and_balance = ?
                    WHERE date = ? AND workstation_name = ?
                ''', (
                    row["running_repair"], row["free_service"], timestamp, row["paid_service"], row["body_shop"],
                    row["total"], row["align"], row["balance"], row["align_and_balance"],
                    row["date"], row["workstation_name"]
                ))
                
            else:
                # Insert new record with timestamp
                timestamp = datetime.now(pytz.timezone("Asia/Kolkata")).strftime("%Y-%m-%d %H:%M:%S")
                c.execute('''
                    INSERT INTO Workstation_Data (date, workstation_name, supervisor_name, running_repair, free_service, paid_service, body_shop, total, align, balance, align_and_balance, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    row["date"], row["workstation_name"], supervisor_code, row["running_repair"], row["free_service"], row["paid_service"], row["body_shop"],
                    row["total"], row["align"], row["balance"], row["align_and_balance"], timestamp
                ))

            conn.commit()
        st.success("Data submitted successfully.")


#===============================================================================================
def sales_admin_workshop_report(user_role, supervisor_code):
    """View workshop report filtered by Supervisor."""
    st.subheader("Workshop Report")
    user_role = st.session_state.user_data['role']
    supervisor_code = st.session_state.user_data.get('code')

    conn = sqlite3.connect('Tools_And_Tools.sqlite')

    # Filter workstation data based on user role
    if user_role == "Super Admin":
        df = pd.read_sql_query("SELECT * FROM Workstation_Data", conn)
    elif user_role == "Supervisor":
        df = pd.read_sql_query(
            "SELECT * FROM Workstation_Data WHERE supervisor_name = ?", conn, params=(supervisor_code,)
        )
    else:
        st.error("Unauthorized access")
        return

    if df.empty:
        st.write("Empty")
    else:
        st.write("Filter by Date Range")
        start_date = st.date_input("Start Date")
        end_date = st.date_input("End Date")

        if start_date and end_date:
            filtered_df = df[(df['date'] >= str(start_date)) & (df['date'] <= str(end_date))]
            if filtered_df.empty:
                st.write("No data found for the selected date range.")
            else:
                summary = filtered_df.groupby('workstation_name').agg(
                    Running_Repair=('running_repair', 'sum'),
                    Free_Service=('free_service', 'sum'),
                    Paid_Service=('paid_service', 'sum'),
                    Body_Shop=('body_shop', 'sum'),
                    Total=('total', 'sum'),
                    Align=('align', 'sum'),
                    Balance=('balance', 'sum'),
                    Align_and_Balance=('align_and_balance', 'sum'),
                ).reset_index()
                st.dataframe(summary)

    conn.close()
# =====================================================================

def advisor_admin_workshop_data(user_role, supervisor_code):
    """View and upload workstation data with Supervisor filtering."""
    st.subheader("Advisor Data")
    user_role = st.session_state.user_data['role']
    supervisor_code = st.session_state.user_data.get('code')

    conn = sqlite3.connect('Tools_And_Tools.sqlite')

    # Filter workstation data based on the user role
    if user_role == "Super Admin":
        df = pd.read_sql_query("SELECT * FROM Advisor_Data", conn)
        #--------------------------------

        # Option to upload new data
        st.write("Upload Data")
        uploaded_file = st.file_uploader("Choose an Excel file", type=["xlsx"])  # Accept only .xlsx files

        if uploaded_file is not None:
            try:
                # Read the Excel file
                new_data = pd.read_excel(uploaded_file, sheet_name=None)  # sheet_name=None reads all sheets into a dictionary
                # If you know the sheet name you want to load, use sheet_name="YourSheetName"
                
                # Assuming you know the sheet name, you can access it like this:
                sheet_name = "Sheet1"  # Replace with the actual sheet name
                if sheet_name in new_data:
                    df = new_data[sheet_name]  # Get the data from the specified sheet
                else:
                    raise ValueError(f"Sheet '{sheet_name}' not found in the uploaded file.")
                
                # Open the connection to the SQLite database
                conn = sqlite3.connect('Tools_And_Tools.sqlite')
                c = conn.cursor()

                # Delete all existing data from the Workstation_Data table
                c.execute("DELETE FROM Advisor_Data")
                conn.commit()  # Commit the delete operation
                
                # Now upload the new data
                df.to_sql("Advisor_Data", conn, if_exists="append", index=False)
                conn.close()
                
                st.success("Data uploaded successfully and previous data cleared.")
            except Exception as e:
                st.error(f"Error uploading data: {e}")


        #--------------------------------

    elif user_role == "Supervisor":
        df = pd.read_sql_query(
            "SELECT * FROM Advisor_Data WHERE supervisor_name = ?", conn, params=(supervisor_code,)
        )
    else:
        st.error("Unauthorized access")
        return

    if df.empty:
        st.write("Empty")
    else:
        st.dataframe(df)

    # conn.close()


def advisor_admin_workshop_report(user_role, supervisor_code):
    """View workshop report filtered by Supervisor."""
    st.subheader("Advisor Report")
    user_role = st.session_state.user_data['role']
    supervisor_code = st.session_state.user_data.get('code')

    conn = sqlite3.connect('Tools_And_Tools.sqlite')

    # Filter workstation data based on user role
    if user_role == "Super Admin":
        df = pd.read_sql_query("SELECT * FROM Advisor_Data", conn)
    elif user_role == "Supervisor":
        df = pd.read_sql_query(
            "SELECT * FROM Advisor_Data WHERE supervisor_name = ?", conn, params=(supervisor_code,)
        )
    else:
        st.error("Unauthorized access")
        return

    if df.empty:
        st.write("Empty")
    else:
        st.write("Filter by Date Range")
        start_date = st.date_input("Start Date")
        end_date = st.date_input("End Date")

        if start_date and end_date:
            filtered_df = df[(df['date'] >= str(start_date)) & (df['date'] <= str(end_date))]
            if filtered_df.empty:
                st.write("No data found for the selected date range.")
            else:
                summary = filtered_df.groupby(['supervisor_name','workstation_name','advisor_name']).agg(
                    Running_Repair=('running_repair', 'sum'),
                    Free_Service=('free_service', 'sum'),
                    Paid_Service=('paid_service', 'sum'),
                    Body_Shop=('body_shop', 'sum'),
                    Total=('total', 'sum'),
                    Align=('align', 'sum'),
                    Balance=('balance', 'sum'),
                    Align_and_Balance=('align_and_balance', 'sum'),
                ).reset_index()
                st.dataframe(summary)

    conn.close()
# =====================================================================



# Create SQLite Tables
def create_tables():
    try:
        conn = sqlite3.connect('Tools_And_Tools.sqlite')
        c = conn.cursor()

        # User Credentials Table
        c.execute('''CREATE TABLE IF NOT EXISTS User_Credentials
                     (
                        Code TEXT PRIMARY KEY,
                        Name TEXT,
                        Password TEXT,
                        Supervisor_Code TEXT,
                        User_Role TEXT,
                        Target INTEGER 
                     )''')

        # Attendance Table (with In_Time, Out_Time, and Shift_Duration)
        c.execute('''CREATE TABLE IF NOT EXISTS Attendance
                     (
                        Code TEXT,
                        Name TEXT,
                        Workstation_Name TEXT,
                        Attendance_Date TEXT,
                        In_Time TEXT,
                        In_Time_Photo_Link TEXT,
                        Out_Time TEXT,
                        Out_Time_Photo_Link TEXT,
                        Supervisor_Name TEXT,
                        Shift_Duration TEXT
                     )''')
        
        #Advisor data table
        c.execute('''CREATE TABLE IF NOT EXISTS Advisor_Data
                    (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        date DATE NOT NULL,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                        workstation_name TEXT,
                        supervisor_name TEXT,
                        advisor_name TEXT,
                        running_repair INTEGER DEFAULT 0,
                        free_service INTEGER DEFAULT 0,
                        paid_service INTEGER DEFAULT 0,
                        body_shop INTEGER DEFAULT 0,
                        total INTEGER,
                        align INTEGER DEFAULT 0,
                        balance INTEGER DEFAULT 0,
                        align_and_balance INTEGER
                    )''')
        #Workstation data table
        c.execute('''CREATE TABLE IF NOT EXISTS Workstation_Data
                    (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        date DATE NOT NULL,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                        workstation_name TEXT,
                        supervisor_name TEXT,
                        running_repair INTEGER DEFAULT 0,
                        free_service INTEGER DEFAULT 0,
                        paid_service INTEGER DEFAULT 0,
                        body_shop INTEGER DEFAULT 0,
                        total INTEGER,
                        align INTEGER DEFAULT 0,
                        balance INTEGER DEFAULT 0,
                        align_and_balance INTEGER
                    )''')
        
        conn.commit()
        conn.close()
    except Exception as e:
        st.write("Error creating tables:", e)

st.set_page_config(
    page_title="Dhuwalia Sites Management",
    # page_icon="👨‍👨‍👧‍👧"
    page_icon='car.png'
)

# User Authentication Function
def authenticate_user(code, password):
    conn = sqlite3.connect('Tools_And_Tools.sqlite')
    c = conn.cursor()
    c.execute('SELECT * FROM User_Credentials WHERE Code = ? AND Password = ?', (code, password))
    user = c.fetchone()
    conn.close()
    return user

# Fetch workstations from User_Credentials table
def fetch_workstations():
    conn = sqlite3.connect('Tools_And_Tools.sqlite')
    c = conn.cursor()
    c.execute('SELECT Name FROM User_Credentials WHERE User_Role = "Workstation"')
    workstations = [row[0] for row in c.fetchall()]
    conn.close()
    return workstations

# Fetch supervisor name for the logged-in user
def fetch_supervisor_name(code):
    conn = sqlite3.connect('Tools_And_Tools.sqlite')
    c = conn.cursor()
    c.execute('SELECT Supervisor_Name FROM User_Credentials WHERE Code = ?', (code,))
    supervisor_name = c.fetchone()[0]
    conn.close()
    return supervisor_name

# Ensure Images folder exists
def ensure_images_folder():
    if not os.path.exists("Images"):
        os.makedirs("Images")

# Check and manage folder size
def manage_folder_size(max_folder_size=50 * 1024 * 1024):
    folder = "Images"
    total_size = 0
    files = []

    # Calculate total folder size and list files
    for filename in os.listdir(folder):
        file_path = os.path.join(folder, filename)
        if os.path.isfile(file_path):
            file_size = os.path.getsize(file_path)
            total_size += file_size
            files.append((file_path, file_size))

    # Sort files by creation time (oldest first)
    files.sort(key=lambda x: os.path.getctime(x[0]))

    # Delete the oldest files until the folder size is under the limit
    while total_size > max_folder_size:
        oldest_file, oldest_file_size = files.pop(0)
        os.remove(oldest_file)
        total_size -= oldest_file_size


def get_ist_time():
    # Define the IST timezone
    ist = pytz.timezone('Asia/Kolkata')
    # Get the current time in UTC and convert to IST
    ist_time = datetime.now(ist)
    return ist_time.strftime('%Y-%m-%d %H:%M:%S')

# Example usage while capturing in/out time
in_time = get_ist_time()
out_time = get_ist_time()


# Function to capture in time
def capture_in_time(user_data, selected_workstation, photo_link):
    in_time = get_ist_time()
    st.session_state['in_time'] = in_time
    # Insert into your attendance table (assuming insert_attendance is defined elsewhere)
    insert_attendance(user_data['code'], user_data['name'], selected_workstation, in_time, photo_link, None, None, None)
    st.success(f"In Time captured successfully! {in_time}")

# Function to capture out time
def capture_out_time(user_data, selected_workstation, photo_link):
    out_time = get_ist_time()
    in_time = st.session_state.get('in_time')
    if not in_time:
        st.error("In Time is not captured yet!")
        return
    
    # Calculate shift duration
    shift_duration = calculate_shift_duration(in_time, out_time)  # assuming this function is defined elsewhere
    insert_attendance(user_data['code'], user_data['name'], selected_workstation, None, None, out_time, photo_link, None, shift_duration)
    st.success(f"Out Time captured successfully! Shift duration: {shift_duration}")

# Function to check if In Time has already been recorded for the day
def has_in_time_recorded_today(code):
    conn = sqlite3.connect('Tools_And_Tools.sqlite')
    c = conn.cursor()
    ist = pytz.timezone('Asia/Kolkata')
    # Check if the current date's attendance for this user already exists
    today_date = datetime.now(ist).strftime("%d-%m-%Y")
    c.execute('SELECT * FROM Attendance WHERE Code = ? AND Attendance_Date = ?', (code, today_date))
    existing_entry = c.fetchone()

    conn.close()
    return existing_entry is not None

# Save image to "Images" folder with simple filename overwrite
def save_image(image, code, punch_type):
    ensure_images_folder()
    manage_folder_size()
    ist = pytz.timezone('Asia/Kolkata')
    # Create image name with format: "id_date_punchtype"
    current_date = datetime.now(ist).strftime("%d-%m-%Y")
    image_name = f"{code}_{current_date}_{punch_type}.jpg"
    image_path = os.path.join("Images", image_name)
    # image_path = os.path.join(image_name)

    # Save image as JPEG with max size of 50KB
    image_pil = Image.open(io.BytesIO(image))
    image_pil = image_pil.convert('RGB')  # Ensure it's in RGB mode

    # Save image in multiple attempts to respect 50KB limit
    quality = 95
    while True:
        img_byte_arr = io.BytesIO()
        image_pil.save(img_byte_arr, format='JPEG', quality=quality)
        if len(img_byte_arr.getvalue()) <= 50 * 1024 or quality <= 5:
            break
        quality -= 5

    # Save the compressed image to the "Images" folder, overwrite if it exists
    image_pil.save(image_path, format='JPEG', quality=quality)

    return image_path


# Example function to calculate shift duration
def calculate_shift_duration(in_time_str, out_time_str):
    # Convert string time to datetime objects using the correct format for 12-hour time with AM/PM
    in_time = datetime.strptime(in_time_str, '%I.%M.%S %p')  # Adjusting for format like '08.32.09 PM'
    out_time = datetime.strptime(out_time_str, '%I.%M.%S %p')
    
    # Calculate the difference
    shift_duration = out_time - in_time
    return shift_duration

# Fetch supervisor name for the logged-in user based on Supervisor_Code
def fetch_supervisor_name(code):
    conn = sqlite3.connect('Tools_And_Tools.sqlite')
    c = conn.cursor()

    # First, get the Supervisor_Code for the logged-in user
    c.execute('SELECT Supervisor_Code FROM User_Credentials WHERE Code = ?', (code,))
    supervisor_code = c.fetchone()[0]

    # Now, fetch the Name of the supervisor where the Code matches the Supervisor_Code
    c.execute('SELECT Name FROM User_Credentials WHERE Code = ?', (supervisor_code,))
    supervisor_name = c.fetchone()[0]

    conn.close()
    return supervisor_name



# Insert attendance data into the table
def insert_attendance(code, name, workstation, in_time, in_photo_link, out_time, out_photo_link, supervisor_name, shift_duration):
    conn = sqlite3.connect('Tools_And_Tools.sqlite')
    c = conn.cursor()

    ist = pytz.timezone('Asia/Kolkata')
    # Check if the entry for the given date and user already exists
    today_date = datetime.now(ist).strftime("%d-%m-%Y")
    c.execute('SELECT * FROM Attendance WHERE Code = ? AND Attendance_Date = ?', (code, today_date))
    existing_entry = c.fetchone()

    # Convert shift_duration (timedelta) to a string in "HH:MM:SS" format if it's not None
    if shift_duration is not None:
        shift_duration_str = str(shift_duration)  # Convert timedelta to string "HH:MM:SS"
    else:
        shift_duration_str = None

    if existing_entry:
        # Update Out_Time, Out_Time_Photo_Link, and Shift_Duration
        c.execute('''UPDATE Attendance 
                     SET Out_Time = ?, Out_Time_Photo_Link = ?, Shift_Duration = ? 
                     WHERE Code = ? AND Attendance_Date = ?''',
                  (out_time, out_photo_link, shift_duration_str, code, today_date))
    else:
        # Insert new attendance entry
        supervisor_name = fetch_supervisor_name(code)
        c.execute('''INSERT INTO Attendance (Code, Name, Workstation_Name, Attendance_Date, In_Time, In_Time_Photo_Link, Supervisor_Name)
                     VALUES (?, ?, ?, ?, ?, ?, ?)''',
                  (code, name, workstation, today_date, in_time, in_photo_link, supervisor_name))

    conn.commit()
    conn.close()



# Main attendance capturing logic with updated button visibility for In Time
def main():
    st.markdown('### :rainbow[Dhuwalia Sales and Attendance Management System]')

    # Add CSS to reduce the camera frame size
    st.markdown(
        """
        <style>
        .stCamera {
            max-width: 500px;  /* Set the desired width */
            margin: auto;
        }
        </style>
        """,
        unsafe_allow_html=True
    )

    # Create tables if they don't exist
    create_tables()

    # Manage session state to preserve login state
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False
        st.session_state.user_data = None

    # Fix the single-click login issue by ensuring session state is properly handled
    if not st.session_state.get('logged_in'):
        code = st.text_input("Enter Code")
        password = st.text_input("Enter Password", type="password")

        if st.button("Login"):
            if code == "Amit" and password == "@&17":
                # Treat Amit as Super Admin
                st.session_state.logged_in = True
                st.session_state.user_data = {
                    'code': code,
                    'name': "Amit",
                    'role': "Super Admin"
                }
                st.success("Welcome, Amit (Super Admin)!")
                st.rerun()
            else:
                user = authenticate_user(code, password)
                if user:
                    st.session_state.logged_in = True
                    st.session_state.user_data = {
                        'code': user[0],
                        'name': user[1],
                        'role': user[4]
                    }
                    st.success(f"Welcome, {user[1]}!")
                    st.rerun()
                else:
                    st.error("Invalid credentials. Please try again.")

    # Show attendance page after login
    if st.session_state.logged_in:
        user_data = st.session_state.user_data
        if user_data['role'] == 'Technician':
            technician_data()            
        elif user_data['role'] == 'Super Admin':
            manage_super_admin_data()
        elif user_data['role'] == 'Supervisor':
            manage_Supervisor_data()
        elif user_data['role'] == 'Workstation':
            # Check if the workstation ID is stored under a different key
            user_workstation_id = user_data.get('code')  # Replace 'Code' with the correct key if different
            # st.write("user_workstation_id:", user_workstation_id)  # Confirm the output here
            Advisor.workstation_interface(user_workstation_id)
        else:
            st.error("Unauthorized user role for attendance capture!")

def technician_data():
    user_data = st.session_state.user_data
    st.success(f"Welcome {user_data['name']}, please mark your attendance.")

   
    # Display workstation dropdown
    workstations = fetch_workstations()
    selected_workstation = st.selectbox("Select Workstation", workstations)

    # Set the timezone to Indian Standard Time (UTC+5:30)
    ist = pytz.timezone('Asia/Kolkata')

    # Show attendance date (Indian timezone)
    attendance_date = datetime.now(ist).strftime("%d-%m-%Y")
    st.write(f"Attendance Date: {attendance_date}")

    # In time photo and capture
    if not has_in_time_recorded_today(user_data['code']):
        in_photo = st.camera_input("Start Shift (In Time)")
        if in_photo:
            in_time = datetime.now(ist).strftime("%I.%M.%S %p")

            # Read the image data from the uploaded file
            in_photo_bytes = in_photo.read()

            if in_photo_bytes:
                supervisor_name = fetch_supervisor_name(user_data['code'])
                in_photo_link = save_image(in_photo_bytes, user_data['code'], "in")
                insert_attendance(user_data['code'], user_data['name'], selected_workstation, in_time, in_photo_link, None, None, supervisor_name, None)
                st.success("In Time and photo captured successfully!")
    else:
        st.warning("You have already recorded your In Time for today!")
        

    # Out time photo and capture
    out_photo = st.camera_input("End Shift (Out Time)")
    if out_photo:
        out_time = datetime.now(ist).strftime("%I.%M.%S %p")

        # Read the image data from the uploaded file
        out_photo_bytes = out_photo.read()

        # Fetch in_time to calculate shift duration
        conn = sqlite3.connect('Tools_And_Tools.sqlite')
        c = conn.cursor()
        c.execute('SELECT In_Time FROM Attendance WHERE Code = ? AND Attendance_Date = ?', (user_data['code'], attendance_date))
        in_time_result = c.fetchone()  # Fetch the result

        if in_time_result:
            in_time = in_time_result[0]  # Extract the In_Time value from the tuple
            st.success(f"In Time found: {in_time}")
        else:
            # If no record is found, handle the error appropriately
            st.error("No in_time found for the given code and date")
            conn.close()  # Close the connection
            return  # Stop further execution

        conn.close()

        if out_photo_bytes and in_time:
            shift_duration = calculate_shift_duration(in_time, out_time)  # Pass in_time as a string
            out_photo_link = save_image(out_photo_bytes, user_data['code'], "out")
            insert_attendance(user_data['code'], user_data['name'], selected_workstation, None, None, out_time, out_photo_link, None, shift_duration)
            st.success(f"Out Time and photo captured successfully! Shift duration: {shift_duration}")

                   

# Function to download the Image folder
def download_image_folder():
    # Path to the Image folder
    folder_path = "Images"

    # Create a zip file
    zip_filename = "Images.zip"
    with zipfile.ZipFile(zip_filename, 'w') as zipf:
        for root, dirs, files in os.walk(folder_path):
            for file in files:
                zipf.write(os.path.join(root, file), os.path.relpath(os.path.join(root, file), folder_path))

    # Read the zip file content
    with open(zip_filename, "rb") as f:
        zip_data = f.read()

    # Provide a download button for the zip file
    st.download_button(label="Download Image Folder", data=zip_data, file_name=zip_filename, mime="application/zip")

# Function to calculate attendance summary with total hours and count of Sundays

def generate_attendance_report(start_date, end_date):
    # Ensure start_date and end_date are in DD-MM-YYYY format for consistency
    start_date = datetime.strptime(start_date, '%d-%m-%Y').strftime('%Y-%m-%d')
    end_date = datetime.strptime(end_date, '%d-%m-%Y').strftime('%Y-%m-%d')
    
    # Connect to the SQLite database
    conn = sqlite3.connect('Tools_And_Tools.sqlite')
    
    # Fetch attendance data with date filtering and text-to-date conversion in SQL query
    query = '''
    SELECT u.Name AS Technician_Name, u.Supervisor_Code, s.Name AS Supervisor_Name, 
           a.Attendance_Date, a.Shift_Duration
    FROM Attendance a
    JOIN User_Credentials u ON a.Code = u.Code
    JOIN User_Credentials s ON u.Supervisor_Code = s.Code
    WHERE DATE(substr(a.Attendance_Date, 7, 4) || '-' || substr(a.Attendance_Date, 4, 2) || '-' || substr(a.Attendance_Date, 1, 2))
          BETWEEN DATE(?) AND DATE(?)
    '''
    
    # Load the query results into a DataFrame, filtered by start_date and end_date
    df = pd.read_sql_query(query, conn, params=[start_date, end_date])
    conn.close()
    
    # Display the initial data for verification
    # Activate to test
    # st.write("Data from query after date filtering:", df)
    
    # Convert Attendance_Date to datetime format to enable additional filtering and calculations
    df['Attendance_Date'] = pd.to_datetime(df['Attendance_Date'], format='%d-%m-%Y', errors='coerce')
    df['Shift_Duration'] = pd.to_timedelta(df['Shift_Duration'], errors='coerce')
    
    # Identify Sundays in the attendance data
    df['Is_Sunday'] = df['Attendance_Date'].dt.dayofweek == 6  # Sunday = 6
    # Activate to test
    # st.write("Data with Is_Sunday flag:", df)
    
    # Calculate Total_Days, Sundays, and Total_Hours by grouping
    summary = df.groupby(['Supervisor_Name', 'Technician_Name']).agg(
        Total_Days=('Attendance_Date', 'nunique'),
        Total_Hours=('Shift_Duration', 'sum'),
        Sundays=('Is_Sunday', 'sum')
    ).reset_index()
    
    # Convert total hours back to HH:MM:SS format
    summary['Total_Hours'] = summary['Total_Hours'].apply(lambda x: f"{int(x.total_seconds() // 3600):02}:{int((x.total_seconds() % 3600) // 60):02}:{int(x.total_seconds() % 60):02}")
    
    # Display the summary results
    # Activate to test
    # st.write("Attendance Summary Report:", summary)
    
    # Show the data in a Streamlit table format
    st.dataframe(summary)

        # Provide an option to download the report as Excel
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        summary.to_excel(writer, index=False)
    output.seek(0)

    st.download_button(label="Download Attendance Report", data=output, file_name="Attendance_Report.xlsx", mime="application/vnd.ms-excel")


# # Adding the report generation functionality in a new tab


def display_admin_report():
    st.header("Supervisor and Technician-wise Attendance Report")

    # Select date range
    start_date = st.date_input("Start Date", value=datetime.today() - timedelta(days=30))
    end_date = st.date_input("End Date", value=datetime.today())

    if start_date > end_date:
        st.error("Start date cannot be after end date.")
    else:
        if st.button("Generate Report"):
            generate_attendance_report(start_date.strftime("%d-%m-%Y"), end_date.strftime("%d-%m-%Y"))


# Super Admin Data Management
def manage_super_admin_data():
    st.header("Super Admin Data Management")

    # User role and supervisor code
    user_role = st.session_state.get("user_role")  # Replace with actual session data
    supervisor_code = st.session_state.get("supervisor_code")  # Replace with actual session data
    menu = st.sidebar.selectbox("Options", ["Download All Reports", "Sales Admin", "Attendance Management", "Advisor Admin"])
        
    if menu == "Download All Reports":
        if st.button("Download Reports"):
            # Trigger the report download process
            zip_content = download_all_reports()

            if zip_content:
                st.download_button(
                    label="Download All Reports",
                    data=zip_content,
                    file_name=datetime.now(pytz.timezone("Asia/Kolkata")).strftime("%d-%B-%Y") + ".zip",
                    mime="application/zip"  # Correct MIME type for ZIP files
                )
            else:
                st.error("Failed to generate the ZIP file. Please try again.")
    
    elif menu == "Sales Admin":
        sub_menu = st.sidebar.radio("Sub Options", ["Workshop Data", "Workshop Report"])
        
        if sub_menu == "Workshop Data":
            sales_admin_workshop_data(user_role, supervisor_code)
        elif sub_menu == "Workshop Report":
            sales_admin_workshop_report(user_role, supervisor_code)
    
    elif menu=="Advisor Admin":
        sub_menu = st.sidebar.radio("Sub Options", ["Advisor Data", "Advisor Report"])

        if sub_menu == "Advisor Data":
            advisor_admin_workshop_data(user_role, supervisor_code)
        elif sub_menu == "Advisor Report":
            advisor_admin_workshop_report(user_role, supervisor_code)

    elif menu == "Attendance Management":

        # Tabs for User_Credentials, Attendance, and Report tables
        tab1, tab2, tab3 = st.tabs(["User Credentials", "Attendance Data", "Attendance Report"])

        # User Credentials Table Management
        with tab1:
            st.subheader("User Credentials Data")
            # if st.button("Download User Credentials as Excel"):
            #     download_data_as_excel('User_Credentials')

            uploaded_user_file = st.file_uploader("Upload Excel for User Credentials", type=["xlsx"])
            if uploaded_user_file:
                user_df = pd.read_excel(uploaded_user_file)
                if validate_user_data(user_df):
                    overwrite_table('User_Credentials', user_df)
                    st.success("User Credentials table successfully updated.")
                else:
                    st.error("Invalid data in User Credentials. Please check the row and column errors displayed.")
            
            display_table('User_Credentials')

        # Attendance Table Management
        with tab2:
            st.subheader("Attendance Data")
            
            col1, col2 = st.columns(2)

            with col1:
                if st.button("Download Attendance as Excel"):
                    download_data_as_excel('Attendance')
            
            with col2:
                download_image_folder()

            uploaded_attendance_file = st.file_uploader("Upload Excel for Attendance", type=["xlsx"])
            if uploaded_attendance_file:
                attendance_df = pd.read_excel(uploaded_attendance_file)
                if validate_attendance_data(attendance_df):
                    overwrite_table('Attendance', attendance_df)
                    st.success("Attendance table successfully updated.")
                else:
                    st.error("Invalid data in Attendance. Please check the row and column errors displayed.")
            
            display_table('Attendance')

        # Attendance Report
        with tab3:
            display_admin_report()
#=================================================================

# Supervisor Data Management
def manage_Supervisor_data():
    st.header("Supervisor Data Management")
    
    st.markdown(f"#### :blue[Welcome: ] :rainbow[{st.session_state.user_data['name']}] 🤝")

    # User role and supervisor code
    user_role = st.session_state.get("user_role")  # Replace with actual session data
    supervisor_code = st.session_state.get("supervisor_code")  # Replace with actual session data
    menu = st.sidebar.selectbox("Options", ["Sales Admin", "Attendance Management", "Advisor Admin"])
        
    if menu == "Download All Reports":
        if st.button("Download Reports"):
            # Trigger the report download process
            zip_content = download_all_reports()

            if zip_content:
                st.download_button(
                    label="Download All Reports",
                    data=zip_content,
                    file_name="all_reports.zip",
                    mime="application/zip"  # Correct MIME type for ZIP files
                )
            else:
                st.error("Failed to generate the ZIP file. Please try again.")
    
    elif menu == "Sales Admin":
        sub_menu = st.sidebar.radio("Sub Options", ["Workshop Data", "Workshop Report"])
        
        if sub_menu == "Workshop Data":
            sales_admin_workshop_data(user_role, supervisor_code)
        elif sub_menu == "Workshop Report":
            sales_admin_workshop_report(user_role, supervisor_code)
    
    elif menu=="Advisor Admin":
        sub_menu = st.sidebar.radio("Sub Options", ["Advisor Data", "Advisor Report"])

        if sub_menu == "Advisor Data":
            advisor_admin_workshop_data(user_role, supervisor_code)
        elif sub_menu == "Advisor Report":
            advisor_admin_workshop_report(user_role, supervisor_code)

    elif menu == "Attendance Management":

        # Tabs for User_Credentials, Attendance, and Report tables
        tab1, tab2, tab3, tab4 = st.tabs(["User Credentials", "Attendance Data", "Attendance Report", "Mark Attendance"])

        # User Credentials Table Management
        with tab1:
            st.subheader("User Credentials Data")
            if st.button("Download User Credentials as Excel"):
                download_data_as_excel('User_Credentials')

            # Show only User_Credentials where Supervisor_Code matches the logged-in user
            user_code = st.session_state.user_data['code']
            conn = sqlite3.connect('Tools_And_Tools.sqlite')
            user_df = pd.read_sql_query("SELECT * FROM User_Credentials WHERE Supervisor_Code = ?", conn, params=(user_code,))
            conn.close()

            st.dataframe(user_df)

        # Attendance Table Management
        with tab2:
            st.subheader("Attendance Data")
            
            col1, col2 = st.columns(2)

            with col1:
                if st.button("Download Attendance as Excel"):
                    download_data_as_excel('Attendance')
            
            with col2:
                download_image_folder()

            # Show only Attendance data where Supervisor_Name matches the logged-in user
            conn = sqlite3.connect('Tools_And_Tools.sqlite')
            attendance_df = pd.read_sql_query("SELECT * FROM Attendance WHERE Supervisor_Name = (SELECT Name FROM User_Credentials WHERE Code = ?)", conn, params=(user_code,))
            conn.close()
            
            st.dataframe(attendance_df)

        # Attendance Report
        with tab3:
            display_supervisor_report()
        with tab4:
            mark_attendance()
    

#---------------------
def mark_attendance():
    st.title("Attendance Management System")

    user_data = st.session_state.user_data
        
    if user_data['role'] == "Supervisor":  # Check if user role is Supervisor
        st.write(f"Welcome back, {user_data['name']}")

        # Fetch technicians
        technicians = fetch_technicians(user_data['code'])
        
        if technicians:  # Check if technicians list is not empty
            technician_codes = [tech[0] for tech in technicians]
            technician_names = [tech[1] for tech in technicians]
            
            # Select technician
            selected_technician = st.selectbox("Select Technician", technician_names)

            # Fetch selected technician's code
            selected_technician_code = technician_codes[technician_names.index(selected_technician)]

            workstations = fetch_workstations()
            selected_workstation = st.selectbox("Select Workstation", workstations)

            ist = pytz.timezone('Asia/Kolkata')
            # Show attendance date (Indian timezone)
            attendance_date = datetime.now(ist).strftime("%d-%m-%Y")
            st.write(f"Attendance Date: {attendance_date}")

            # In time attendance capture for the technician by Supervisor
            if not has_in_time_recorded_today(selected_technician_code):
                if st.button("Start Shift (In Time)"):
                    in_time = datetime.now(ist).strftime("%I.%M.%S %p")

                    # Fetch the supervisor name
                    supervisor_name = fetch_supervisor_name(user_data['code'])

                    # Set the In_Time_Photo_Link to supervisor's name
                    in_time_photo_link = user_data['name']  # Logged-in user's name

                    # Insert attendance record with supervisor's name in the photo link field
                    insert_attendance(selected_technician_code, selected_technician, selected_workstation, in_time, in_time_photo_link, None, None, supervisor_name, None)
                    st.success("In Time captured successfully by the supervisor!")
            else:
                st.warning("This technician has already recorded their In Time for today!")

            # Out time attendance capture for the technician by Supervisor
            if st.button("End Shift (Out Time)"):
                out_time = datetime.now(ist).strftime("%I.%M.%S %p")

                # Fetch in_time to calculate shift duration
                conn = sqlite3.connect('Tools_And_Tools.sqlite')
                c = conn.cursor()
                c.execute('SELECT In_Time FROM Attendance WHERE Code = ? AND Attendance_Date = ?', (selected_technician_code, attendance_date))
                in_time = c.fetchone()
                conn.close()

                if in_time and in_time[0]:  # Check if in_time is not None
                    in_time = in_time[0]

                    # Fetch the supervisor name
                    supervisor_name = fetch_supervisor_name(user_data['code'])

                    # Set the Out_Time_Photo_Link to supervisor's name
                    out_time_photo_link = user_data['name']  # Logged-in user's name

                    # Calculate shift duration
                    shift_duration = calculate_shift_duration(in_time, out_time)

                    # Insert attendance record with supervisor's name in the photo link field
                    insert_attendance(selected_technician_code, selected_technician, selected_workstation, None, None, out_time, out_time_photo_link, supervisor_name, shift_duration)
                    st.success(f"Out Time captured successfully by the supervisor! Shift duration: {shift_duration}")
                else:
                    st.warning("No In Time recorded for this technician today.")
      
    else:
        st.error("Access Denied: Only Supervisors can access this feature.")

#---------------------

# Fetch technicians under the supervisor
def fetch_technicians(supervisor_code):
    conn = sqlite3.connect('Tools_And_Tools.sqlite')
    c = conn.cursor()
    c.execute('SELECT Code, Name FROM User_Credentials WHERE Supervisor_Code = ?', (supervisor_code,))
    technicians = c.fetchall()
    conn.close()
    return technicians


# Adding the report generation functionality in a new tab 
def display_supervisor_report(): 
    st.header("Supervisor and Technician-wise Attendance Report") 
    # Select date range 
    start_date = st.date_input("Start Date", value=datetime.today() - timedelta(days=30)) 
    end_date = st.date_input("End Date", value=datetime.today()) 
    if start_date > end_date: 
        st.error("Start date cannot be after end date.") 
    else: 
        if st.button("Generate Report"): 
            user_code = st.session_state.user_data['code'] 
            sname = fetch_name(user_code) 
            generate_sv_attendance_report(start_date.strftime("%d-%m-%Y"), end_date.strftime("%d-%m-%Y"), sname)


#---------------------

# Fetch supervisor name for the logged-in user
def fetch_name(code):
    conn = sqlite3.connect('Tools_And_Tools.sqlite')
    c = conn.cursor()
    c.execute('SELECT name FROM User_Credentials WHERE Code = ?', (code,))
    sname = c.fetchone()[0]
    conn.close()
    return sname


def generate_sv_attendance_report(start_date, end_date, sname):
    # Ensure start_date and end_date are in the format YYYY-MM-DD for SQL query
    start_date = datetime.strptime(start_date, '%d-%m-%Y').strftime('%Y-%m-%d')
    end_date = datetime.strptime(end_date, '%d-%m-%Y').strftime('%Y-%m-%d')

    supervisor_name = sname
    if not supervisor_name:
        st.warning("Unable to fetch supervisor name. Please ensure you are logged in correctly.")
        return

    conn = sqlite3.connect('Tools_And_Tools.sqlite')

    # Query with date filtering and case-insensitive supervisor name filtering
    query = '''
    SELECT u.Name AS Technician_Name, u.Supervisor_Code, s.Name AS Supervisor_Name, 
           a.Attendance_Date, a.Shift_Duration
    FROM Attendance a
    JOIN User_Credentials u ON a.Code = u.Code
    JOIN User_Credentials s ON u.Supervisor_Code = s.Code
    WHERE DATE(substr(a.Attendance_Date, 7, 4) || '-' || substr(a.Attendance_Date, 4, 2) || '-' || substr(a.Attendance_Date, 1, 2)) 
          BETWEEN DATE(?) AND DATE(?)
          AND s.Name = ? COLLATE NOCASE
    '''

    # Execute query with parameters
    df = pd.read_sql_query(query, conn, params=(start_date, end_date, supervisor_name))
    conn.close()

    # Debugging information
    st.write("Attendance data for technicians under: ", supervisor_name)

    # Display the initial data for verification
    # Activate to test
    # st.write("Filtered data from query:", df)

    if df.empty:
        st.warning("No attendance data found for the selected date range.")
        return

    # Data transformations
    df['Attendance_Date'] = pd.to_datetime(df['Attendance_Date'], format='%d-%m-%Y', errors='coerce')
    df['Shift_Duration'] = pd.to_timedelta(df['Shift_Duration'], errors='coerce')
    df['Is_Sunday'] = df['Attendance_Date'].dt.dayofweek == 6  # Sundays

    # Group by supervisor and technician to get the required summary
    summary = df.groupby(['Supervisor_Name', 'Technician_Name']).agg(
        Total_Days=('Attendance_Date', 'nunique'),
        Total_Hours=('Shift_Duration', 'sum'),
        Sundays=('Is_Sunday', 'sum')
    ).reset_index()

    # Format total hours
    summary['Total_Hours'] = summary['Total_Hours'].apply(
        lambda x: f"{int(x.total_seconds() // 3600):02}:{int((x.total_seconds() % 3600) // 60):02}:{int(x.total_seconds() % 60):02}"
    )

    # Rearrange and display data
    summary = summary[['Supervisor_Name', 'Technician_Name', 'Total_Days', 'Sundays', 'Total_Hours']]
    st.dataframe(summary)

    # Export to Excel for download
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        summary.to_excel(writer, index=False)
    output.seek(0)

    st.download_button(label="Download Attendance Report", data=output, file_name="Attendance_Report.xlsx", mime="application/vnd.ms-excel")

#=================================================================
# Function to download data as Excel
def download_data_as_excel(table_name):
    conn = sqlite3.connect('Tools_And_Tools.sqlite')
    df = pd.read_sql_query(f"SELECT * FROM {table_name}", conn)
    conn.close()

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False)
    output.seek(0)

    st.download_button(label=f"Download {table_name} Data", data=output, file_name=f"{table_name}.xlsx", mime="application/vnd.ms-excel")

# Function to validate user data before inserting it into the User_Credentials table
def validate_user_data(df):
    required_columns = ['Code', 'Name', 'Password', 'Supervisor_Code', 'User_Role', 'Target']
    for column in required_columns:
        if column not in df.columns:
            st.error(f"Missing column: {column}")
            return False

    for index, row in df.iterrows():
        if pd.isnull(row['Code']) or pd.isnull(row['Name']) or pd.isnull(row['Password']) or pd.isnull(row['User_Role']):
            st.error(f"Error in row {index + 1}: Missing required data.")
            return False
        # Allow Supervisor_Code to be blank or null for non-Technician roles
        if row['User_Role'] == 'Technician' and pd.isnull(row['Supervisor_Code']):
            st.error(f"Error in row {index + 1}: Supervisor_Code is required for Technician.")
            return False

    return True


# Function to validate attendance data before inserting it into the Attendance table
def validate_attendance_data(df):
    required_columns = ['Code', 'Name', 'Workstation_Name', 'Attendance_Date', 'In_Time', 'In_Time_Photo_Link', 'Out_Time', 'Out_Time_Photo_Link', 'Supervisor_Name', 'Shift_Duration']
    for column in required_columns:
        if column not in df.columns:
            st.error(f"Missing column: {column}")
            return False

    for index, row in df.iterrows():
        if pd.isnull(row['Code']) or pd.isnull(row['Name']) or pd.isnull(row['Attendance_Date']) or pd.isnull(row['In_Time']) or pd.isnull(row['Supervisor_Name']):
            st.error(f"Error in row {index + 1}: Missing required data.")
            return False

    return True

# Function to overwrite table data with the newly uploaded file
def overwrite_table(table_name, df):
    conn = sqlite3.connect('Tools_And_Tools.sqlite')
    c = conn.cursor()
    
    # Delete existing data
    c.execute(f"DELETE FROM {table_name}")

    # Insert new data
    if table_name == 'User_Credentials':
        for _, row in df.iterrows():
            c.execute("INSERT INTO User_Credentials (Code, Name, Password, Supervisor_Code, User_Role, Target) VALUES (?, ?, ?, ?, ?, ?)",
                      (row['Code'], row['Name'], row['Password'], row['Supervisor_Code'], row['User_Role'], row['Target']))
    elif table_name == 'Attendance':
        for _, row in df.iterrows():
            c.execute('''INSERT INTO Attendance (Code, Name, Workstation_Name, Attendance_Date, In_Time, In_Time_Photo_Link, Out_Time, Out_Time_Photo_Link, Supervisor_Name, Shift_Duration) 
                         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                      (row['Code'], row['Name'], row['Workstation_Name'], row['Attendance_Date'], row['In_Time'], row['In_Time_Photo_Link'], row['Out_Time'], row['Out_Time_Photo_Link'], row['Supervisor_Name'], row['Shift_Duration']))

    conn.commit()
    conn.close()

# Display data in the table
def display_table(table_name):
    conn = sqlite3.connect('Tools_And_Tools.sqlite')
    df = pd.read_sql_query(f"SELECT * FROM {table_name}", conn)
    conn.close()
    st.dataframe(df)


if __name__ == '__main__':
    main()