import streamlit as st
import pandas as pd
import pdfplumber
import re
from io import StringIO
import io
import json
import base64
import os
from pathlib import Path
from streamlit_oauth import OAuth2Component

# OAuth Configuration
CLIENT_ID = st.secrets["google"]["client_id"]
CLIENT_SECRET = st.secrets["google"]["client_secret"]
AUTHORIZE_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
REVOKE_ENDPOINT = "https://oauth2.googleapis.com/revoke"
REDIRECT_URI = st.secrets["google"]["redirect_uri"]

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

# def render_pdf_viewer(pdf_file):
#     """Function to render PDF in iframe"""
#     pdf_base64 = base64.b64encode(pdf_file.read()).decode("utf-8")
#     pdf_url = f"data:application/pdf;base64,{pdf_base64}"
#     st.markdown(f'<iframe src="{pdf_url}" width="700" height="600" type="application/pdf"></iframe>', unsafe_allow_html=True)

def render_pdf_viewer(pdf_bytes):
    """Function to render PDF in iframe"""
    pdf_base64 = base64.b64encode(pdf_bytes).decode("utf-8")
    pdf_display = f'<iframe src="data:application/pdf;base64,{pdf_base64}" width="700" height="600" type="application/pdf"></iframe>'
    st.markdown(pdf_display, unsafe_allow_html=True)

def main():
    st.set_page_config(page_title="T-Mobile Bill Splitter", layout="wide")
    st.title("T-Mobile Bill Splitter")

    # Initialize OAuth2Component
    oauth2 = OAuth2Component(CLIENT_ID, CLIENT_SECRET, AUTHORIZE_ENDPOINT, TOKEN_ENDPOINT, TOKEN_ENDPOINT, REVOKE_ENDPOINT)

    # Check if user is authenticated
    if 'auth' not in st.session_state:
        # Show login button
        result = oauth2.authorize_button(
            name="Continue with Google",
            icon="https://www.google.com.tw/favicon.ico",
            redirect_uri=REDIRECT_URI,
            scope="openid email profile",
            key="google",
            extras_params={"prompt": "consent", "access_type": "offline"},
            use_container_width=True,
            pkce='S256',
        )
        
        if result:
            # Handle authorization response
            id_token = result["token"]["id_token"]
            payload = id_token.split(".")[1]
            payload += "=" * (-len(payload) % 4)
            payload = json.loads(base64.b64decode(payload))
            st.session_state["auth"] = payload["email"]
            st.session_state["token"] = result["token"]
            st.rerun()
    else:
        # User is logged in
        user_email = st.session_state["auth"]
        contacts = load_user_contacts(user_email)
        
        # Logout button
        st.sidebar.success(f"Logged in as {user_email}")
        if st.sidebar.button("Sign Out"):
            del st.session_state["auth"]
            del st.session_state["token"]
            st.rerun()

        # Contact management
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
                        save_user_contacts(user_email, contacts)
                        st.success(f"Added {new_name} with number {new_phone}")
                    else:
                        st.warning("Please fill in both fields")
            
            # Display existing contacts
            st.subheader("Existing Contacts")
            if contacts:
                for phone, name in contacts.items():
                    col1, col2 = st.columns([3, 1])
                    col1.text(f"{name}: {phone}")
                    if col2.button("Delete", key=phone):
                        del contacts[phone]
                        save_user_contacts(user_email, contacts)
                        st.rerun()
            else:
                st.info("No contacts added yet")

        # Main content
        col1, col2 = st.columns([2, 1])
        
        with col1:
            uploaded_file = st.file_uploader("Upload T-Mobile PDF Bill", type="pdf")
            plan_cost_divided_equally = st.checkbox("Split Plan Cost Equally", value=True)
        
        if uploaded_file is not None:
            try:
                render_pdf_viewer(uploaded_file.read())
                full_text = extract_text(uploaded_file)
                result_df = process_bill(full_text, contacts, plan_cost_divided_equally)
                
                if result_df is not None:
                    st.header("📊 Bill Summary")
                    
                    for _, row in result_df.iterrows():
                        with st.container():
                            cols = st.columns([3, 2, 1])
                            with cols[0]:
                                st.subheader(row['Name'])
                                st.text(row['Phone_number'])
                            with cols[1]:
                                st.metric("Amount Due", f"${row['total_amount']:.2f}")
                    
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
