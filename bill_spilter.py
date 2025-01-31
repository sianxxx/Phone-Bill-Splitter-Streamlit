import streamlit as st
import pandas as pd
import pdfplumber
import re
from io import StringIO
import json
import base64
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
import os
import pickle
from pathlib import Path


# Configure OAuth 2.0 credentials
GOOGLE_CLIENT_CONFIG = {
    "web": {
        "client_id": st.secrets["google"]["client_id"],
        "client_secret": st.secrets["google"]["client_secret"],
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "redirect_uris": [st.secrets["google"]["redirect_uri"]],
        "javascript_origins": [st.secrets["google"]["redirect_uri"]]
    }
}

def create_google_oauth_flow():
    """Create and configure Google OAuth flow"""
    flow = Flow.from_client_config(
        GOOGLE_CLIENT_CONFIG,
        scopes=['openid', 'https://www.googleapis.com/auth/userinfo.email'],
        redirect_uri=GOOGLE_CLIENT_CONFIG['web']['redirect_uris'][0]
    )
    return flow

def get_google_credentials():
    """Get or refresh Google credentials"""
    if 'google_credentials' not in st.session_state:
        return None
    
    credentials = Credentials(**st.session_state.google_credentials)
    
    if credentials and credentials.expired and credentials.refresh_token:
        credentials.refresh(Request())
        st.session_state.google_credentials = {
            'token': credentials.token,
            'refresh_token': credentials.refresh_token,
            'token_uri': credentials.token_uri,
            'client_id': credentials.client_id,
            'client_secret': credentials.client_secret,
            'scopes': credentials.scopes
        }
    
    return credentials

def get_user_info(credentials):
    """Get Google user information"""
    try:
        service = build('oauth2', 'v2', credentials=credentials)
        user_info = service.userinfo().get().execute()
        return user_info
    except Exception as e:
        st.error(f"Error fetching user info: {str(e)}")
        return None

def save_user_contacts(user_email, contacts):
    """Save contacts to a JSON file for the specific user"""
    contacts_dir = Path("user_contacts")
    contacts_dir.mkdir(exist_ok=True)
    
    file_path = contacts_dir / f"{base64.urlsafe_b64encode(user_email.encode()).decode()}.json"
    with open(file_path, 'w') as f:
        json.dump(contacts, f)

def load_user_contacts(user_email):
    """Load contacts from JSON file for the specific user"""
    file_path = Path("user_contacts") / f"{base64.urlsafe_b64encode(user_email.encode()).decode()}.json"
    if file_path.exists():
        with open(file_path, 'r') as f:
            return json.load(f)
    return {}

def login_button():
    """Display Google login button"""
    if st.button("Sign in with Google"):
        flow = create_google_oauth_flow()
        authorization_url, state = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true'
        )
        st.session_state.oauth_state = state
        st.markdown(f'<a href="{authorization_url}" target="_self">Click here to complete Google sign-in</a>', 
                   unsafe_allow_html=True)

def handle_oauth_callback():
    """Handle OAuth callback and save credentials"""
    query_params = st.experimental_get_query_params()
    if 'code' in query_params:
        try:
            flow = create_google_oauth_flow()
            flow.fetch_token(code=query_params['code'][0])
            
            credentials = flow.credentials
            st.session_state.google_credentials = {
                'token': credentials.token,
                'refresh_token': credentials.refresh_token,
                'token_uri': credentials.token_uri,
                'client_id': credentials.client_id,
                'client_secret': credentials.client_secret,
                'scopes': credentials.scopes
            }
            
            # Clear query parameters
            st.experimental_set_query_params()
            st.rerun()
        except Exception as e:
            st.error(f"Error during authentication: {str(e)}")

def extract_text(uploaded_file):
    """Extracts data from an uploaded PDF"""
    all_text = []
    with pdfplumber.open(uploaded_file) as pdf:
        for page_number in [1]:  # Page 2 only
            page = pdf.pages[page_number]
            all_text.append(page.extract_text())
    return "\n".join(all_text)

def filter_text(data, start_match, end_match):
    lines = data.splitlines()
    try:
        start_pos = lines.index(start_match) + 1
        end_pos = lines.index(end_match)
        filtered_lines = lines[start_pos:end_pos]
        return "\n".join(filtered_lines)
    except ValueError:
        st.error("Could not find expected sections in the bill. Please check if this is a valid T-Mobile bill.")
        return None

def clean_and_convert(value):
    if isinstance(value, str) and value.strip() in ["Included", "-"]:
        return 0.0
    return float(value.replace("$", "").replace(",", "")) if isinstance(value, str) else value

def process_bill(full_text, contacts, plan_cost_divided_equally):
    filtered_text = filter_text(full_text, "THIS BILL SUMMARY", "DETAILED CHARGES")
    if filtered_text is None:
        return None
    
    df = pd.read_csv(StringIO(filtered_text), delim_whitespace=True)
    total_plan_cost = df.loc[df['Line'] == "Totals", "Type"].iloc[0].strip("$")
    
    regex_pattern = r"\(\d{3}\)"
    filtered_df = df[df['Line'].str.contains(regex_pattern, regex=True)].copy()
    
    filtered_df["Phone_number"] = filtered_df["Line"] + " " + filtered_df["Type"]
    filtered_df = filtered_df.drop(columns=["Line", "Type", "Total"])
    
    new_column_names = {
        "Plans": "Plan_Type",
        "Equipment": "Plans_Cost",
        "Services": "Equipment",
        "One-time": "Services",
        "charges": "One_time_charges",
    }
    filtered_df = filtered_df.rename(columns=new_column_names)
    
    for col in ["Plans_Cost", "Equipment", "Services", "One_time_charges"]:
        filtered_df[col] = filtered_df[col].apply(clean_and_convert)
    
    if plan_cost_divided_equally:
        filtered_df["equal_plan_cost"] = float(total_plan_cost)/len(filtered_df)
        filtered_df["total_amount"] = filtered_df["equal_plan_cost"] + filtered_df["Equipment"] + filtered_df["Services"] + filtered_df["One_time_charges"]
    else:
        filtered_df["total_amount"] = filtered_df["Plans_Cost"] + filtered_df["Equipment"] + filtered_df["Services"] + filtered_df["One_time_charges"]
    
    filtered_df["Name"] = filtered_df["Phone_number"].map(contacts)
    filtered_df["Name"] = filtered_df["Name"].fillna("Unknown")
    
    return filtered_df

def render_pdf_viewer(pdf_file):
    """Function to render PDF in iframe"""
    pdf_base64 = base64.b64encode(pdf_file.read()).decode("utf-8")
    pdf_url = f"data:application/pdf;base64,{pdf_base64}"
    st.markdown(f'<iframe src="{pdf_url}" width="700" height="600" type="application/pdf"></iframe>', unsafe_allow_html=True)

def main():
    st.set_page_config(page_title="T-Mobile Bill Splitter", layout="wide")
    
    st.title("T-Mobile Bill Splitter")
    
    # Handle OAuth callback
    handle_oauth_callback()
    
    # Get credentials and user info
    credentials = get_google_credentials()
    user_info = None
    if credentials:
        user_info = get_user_info(credentials)
    
    # Initialize or load contacts based on authentication status
    if user_info:
        contacts = load_user_contacts(user_info['email'])
        st.sidebar.success(f"Logged in as {user_info['email']}")
        st.sidebar.button("Sign Out", on_click=lambda: st.session_state.clear())
    else:
        contacts = {}
        login_button()
    
    # Sidebar for contacts management
    with st.sidebar:
        st.header("👥 Contact Management")
        
        # Add new contact
        with st.form("add_contact"):
            st.subheader("Add New Contact")
            new_phone = st.text_input("Phone Number (e.g., (940) 218-8816)")
            new_name = st.text_input("Name")
            
            if st.form_submit_button("Add Contact"):
                if new_phone and new_name:
                    contacts[new_phone] = new_name
                    if user_info:
                        save_user_contacts(user_info['email'], contacts)
                    st.success(f"Added {new_name} with number {new_phone}")
                else:
                    st.warning("Please fill in both fields")
        
        # Display and manage existing contacts
        st.subheader("Existing Contacts")
        if contacts:
            for phone, name in contacts.items():
                col1, col2 = st.columns([3, 1])
                col1.text(f"{name}: {phone}")
                if col2.button("Delete", key=phone):
                    del contacts[phone]
                    if user_info:
                        save_user_contacts(user_info['email'], contacts)
                    st.rerun()
        else:
            st.info("No contacts added yet")
    
    # Main content area
    col1, col2 = st.columns([2, 1])
    
    with col1:
        uploaded_file = st.file_uploader("Upload T-Mobile PDF Bill", type="pdf")
        plan_cost_divided_equally = st.checkbox("Split Plan Cost Equally", value=True)
    
    if uploaded_file is not None:
        try:
            # Render PDF viewer
            render_pdf_viewer(uploaded_file)

            full_text = extract_text(uploaded_file)
            result_df = process_bill(full_text, contacts, plan_cost_divided_equally)
            
            if result_df is not None:
                st.header("📊 Bill Summary")
                
                # Display results in a side-by-side layout
                for _, row in result_df.iterrows():
                    with st.container():
                        cols = st.columns([3, 2, 1])  # Adjust columns for reduced gaps
                        with cols[0]:
                            st.subheader(row['Name'])
                            st.text(row['Phone_number'])
                        with cols[1]:
                            st.metric("Amount Due", f"${row['total_amount']:.2f}")
                
                # Detailed view in an expander
                with st.expander("View Detailed Breakdown"):
                    st.dataframe(
                        result_df[[
                            'Name', 'Phone_number', 'Plan_Type', 'Plans_Cost',
                            'Equipment', 'Services', 'One_time_charges', 'total_amount'
                        ]].style.format({
                            'Plans_Cost': '${:.2f}',
                            'Equipment': '${:.2f}',
                            'Services': '${:.2f}',
                            'One_time_charges': '${:.2f}',
                            'total_amount': '${:.2f}'
                        })
                    )
        
        except Exception as e:
            st.error(f"Error processing the bill: {str(e)}")
            st.info("Please make sure you've uploaded a valid T-Mobile bill PDF")

if __name__ == "__main__":
    main()