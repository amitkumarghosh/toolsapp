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
                        User_Role TEXT 
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

# Function to check if In Time has already been recorded for the day
def has_in_time_recorded_today(code):
    conn = sqlite3.connect('Tools_And_Tools.sqlite')
    c = conn.cursor()

    # Check if the current date's attendance for this user already exists
    today_date = datetime.now().strftime("%d-%m-%Y")
    c.execute('SELECT * FROM Attendance WHERE Code = ? AND Attendance_Date = ?', (code, today_date))
    existing_entry = c.fetchone()

    conn.close()
    return existing_entry is not None

# Save image to "Images" folder with simple filename overwrite
def save_image(image, code, punch_type):
    ensure_images_folder()
    manage_folder_size()

    # Create image name with format: "id_date_punchtype"
    current_date = datetime.now().strftime("%d-%m-%Y")
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


# Function to calculate shift duration
def calculate_shift_duration(in_time, out_time):
    in_time_obj = datetime.strptime(in_time, "%I.%M.%S %p")
    out_time_obj = datetime.strptime(out_time, "%I.%M.%S %p")
    shift_duration = out_time_obj - in_time_obj
    return str(shift_duration)

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

    # Check if the entry for the given date and user already exists
    today_date = datetime.now().strftime("%d-%m-%Y")
    c.execute('SELECT * FROM Attendance WHERE Code = ? AND Attendance_Date = ?', (code, today_date))
    existing_entry = c.fetchone()

    if existing_entry:
        # Update Out_Time, Out_Time_Photo_Link, and Shift_Duration
        c.execute('''UPDATE Attendance 
                     SET Out_Time = ?, Out_Time_Photo_Link = ?, Shift_Duration = ? 
                     WHERE Code = ? AND Attendance_Date = ?''',
                  (out_time, out_photo_link, shift_duration, code, today_date))
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
    st.markdown('### Dhuwalia Site and Attendance Management System')

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
        
        else:
            st.error("Unauthorized user role for attendance capture!")

def technician_data():

    user_data = st.session_state.user_data
    st.success(f"Welcome {user_data['name']}, please mark your attendance.")

            # Display workstation dropdown
    workstations = fetch_workstations()
    selected_workstation = st.selectbox("Select Workstation", workstations)

    # Show attendance date (Indian timezone)
    attendance_date = datetime.now().strftime("%d-%m-%Y")
    st.write(f"Attendance Date: {attendance_date}")

    # In time photo and capture
    if not has_in_time_recorded_today(user_data['code']):

        # Add CSS to reduce the camera frame size


        in_photo = st.camera_input("Start Shift (In Time)")
        if in_photo:
            in_time = datetime.now().strftime("%I.%M.%S %p")

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
        out_time = datetime.now().strftime("%I.%M.%S %p")

        # Read the image data from the uploaded file
        out_photo_bytes = out_photo.read()

        # Fetch in_time to calculate shift duration
        conn = sqlite3.connect('Tools_And_Tools.sqlite')
        c = conn.cursor()
        c.execute('SELECT In_Time FROM Attendance WHERE Code = ? AND Attendance_Date = ?', (user_data['code'], attendance_date))
        in_time = c.fetchone()[0]
        conn.close()

        if out_photo_bytes and in_time:
            shift_duration = calculate_shift_duration(in_time, out_time)
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
    conn = sqlite3.connect('Tools_And_Tools.sqlite')
    query = '''SELECT u.Name AS Technician_Name, u.Supervisor_Code, s.Name AS Supervisor_Name, a.Attendance_Date, a.Shift_Duration
               FROM Attendance a
               JOIN User_Credentials u ON a.Code = u.Code
               JOIN User_Credentials s ON u.Supervisor_Code = s.Code
               WHERE a.Attendance_Date BETWEEN ? AND ?'''

    df = pd.read_sql_query(query, conn, params=(start_date, end_date))
    conn.close()

    if df.empty:
        st.warning("No attendance data found for the selected date range.")
        return

    # Convert 'Attendance_Date' to datetime format and 'Shift_Duration' to timedelta
    df['Attendance_Date'] = pd.to_datetime(df['Attendance_Date'], format='%d-%m-%Y')
    df['Shift_Duration'] = pd.to_timedelta(df['Shift_Duration'])

    # Create a new column to check if the attendance date is a Sunday
    df['Is_Sunday'] = df['Attendance_Date'].dt.dayofweek == 6  # 6 means Sunday

    # Group by Supervisor and Technician, calculate total days, total hours, and count of Sundays
    summary = df.groupby(['Supervisor_Name', 'Technician_Name']).agg(
        Total_Days=('Attendance_Date', 'nunique'),
        Total_Hours=('Shift_Duration', 'sum'),
        Sundays=('Is_Sunday', 'sum')  # Count how many times 'Is_Sunday' is True
    ).reset_index()

    # Convert total hours back to HH:MM:SS format
    summary['Total_Hours'] = summary['Total_Hours'].dt.components.apply(lambda x: f"{int(x['days'])*24 + int(x['hours']):02}:{int(x['minutes']):02}:{int(x['seconds']):02}", axis=1)

    # Rearranging columns to place 'Sundays' before 'Total_Hours'
    summary = summary[['Supervisor_Name', 'Technician_Name', 'Total_Days', 'Sundays', 'Total_Hours']]

    st.dataframe(summary)

    # Provide an option to download the report as Excel
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        summary.to_excel(writer, index=False)
    output.seek(0)

    st.download_button(label="Download Attendance Report", data=output, file_name="Attendance_Report.xlsx", mime="application/vnd.ms-excel")


# Adding the report generation functionality in a new tab
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

    # Tabs for User_Credentials, Attendance, and Report tables
    tab1, tab2, tab3 = st.tabs(["User Credentials", "Attendance Data", "Attendance Report"])

    # User Credentials Table Management
    with tab1:
        st.subheader("User Credentials Data")
        if st.button("Download User Credentials as Excel"):
            download_data_as_excel('User_Credentials')

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

            # Show attendance date (Indian timezone)
            attendance_date = datetime.now().strftime("%d-%m-%Y")
            st.write(f"Attendance Date: {attendance_date}")

            # In time attendance capture for the technician by Supervisor
            if not has_in_time_recorded_today(selected_technician_code):
                if st.button("Start Shift (In Time)"):
                    in_time = datetime.now().strftime("%I.%M.%S %p")

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
                out_time = datetime.now().strftime("%I.%M.%S %p")

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
    # Try to get the supervisor's name from the session state
    supervisor_name = sname
     # Check if the supervisor name exists, else show an error
    if not supervisor_name:
        st.warning("Unable to fetch supervisor name. Please ensure you are logged in correctly.")
        return

    conn = sqlite3.connect('Tools_And_Tools.sqlite')

    # Modify the query to include a filter for the supervisor's name
    query = '''SELECT u.Name AS Technician_Name, u.Supervisor_Code, s.Name AS Supervisor_Name, a.Attendance_Date, a.Shift_Duration
               FROM Attendance a
               JOIN User_Credentials u ON a.Code = u.Code
               JOIN User_Credentials s ON u.Supervisor_Code = s.Code
               WHERE a.Attendance_Date BETWEEN ? AND ?
               AND s.Name = ?'''  # Filter by supervisor name

    # Pass the supervisor's name as a parameter to the SQL query
    df = pd.read_sql_query(query, conn, params=(start_date, end_date, supervisor_name))
    conn.close()

    if df.empty:
        st.warning("No attendance data found for the selected date range.")
        return

    # Convert 'Attendance_Date' to datetime format and 'Shift_Duration' to timedelta
    df['Attendance_Date'] = pd.to_datetime(df['Attendance_Date'], format='%d-%m-%Y')
    df['Shift_Duration'] = pd.to_timedelta(df['Shift_Duration'])

    # Create a new column to check if the attendance date is a Sunday
    df['Is_Sunday'] = df['Attendance_Date'].dt.dayofweek == 6  # 6 means Sunday

    # Group by Supervisor and Technician, calculate total days, total hours, and count of Sundays
    summary = df.groupby(['Supervisor_Name', 'Technician_Name']).agg(
        Total_Days=('Attendance_Date', 'nunique'),
        Total_Hours=('Shift_Duration', 'sum'),
        Sundays=('Is_Sunday', 'sum')  # Count how many times 'Is_Sunday' is True
    ).reset_index()

    # Convert total hours back to HH:MM:SS format
    summary['Total_Hours'] = summary['Total_Hours'].dt.components.apply(
        lambda x: f"{int(x['days'])*24 + int(x['hours']):02}:{int(x['minutes']):02}:{int(x['seconds']):02}", axis=1)

    # Rearranging columns to place 'Sundays' before 'Total_Hours'
    summary = summary[['Supervisor_Name', 'Technician_Name', 'Total_Days', 'Sundays', 'Total_Hours']]

    st.dataframe(summary)

    # Provide an option to download the report as Excel
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
    required_columns = ['Code', 'Name', 'Password', 'Supervisor_Code', 'User_Role']
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
            c.execute("INSERT INTO User_Credentials (Code, Name, Password, Supervisor_Code, User_Role) VALUES (?, ?, ?, ?, ?)",
                      (row['Code'], row['Name'], row['Password'], row['Supervisor_Code'], row['User_Role']))
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