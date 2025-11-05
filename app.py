import streamlit as st
import pandas as pd
import csv
from datetime import datetime, date, time, timedelta

# Page configuration
st.set_page_config(
    page_title="Pet Scheduler",
    page_icon="🐾",
    layout="wide"
)

# File paths
SERVICES_CSV = "services.csv"
SERVICE_TYPES_CSV = "service_types.csv"


def load_csv(file_path):
    """Load CSV file with proper quoting"""
    try:
        df = pd.read_csv(file_path, quoting=csv.QUOTE_ALL, keep_default_na=False)
        return df
    except FileNotFoundError:
        st.error(f"File {file_path} not found!")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Error loading {file_path}: {str(e)}")
        return pd.DataFrame()


def save_csv(df, file_path):
    """Save DataFrame to CSV with proper quoting to match original format"""
    try:
        # Convert DataFrame to CSV string with proper quoting
        output = df.to_csv(
            index=False,
            quoting=csv.QUOTE_ALL,
            lineterminator="\n",
            doublequote=True  # Use double quotes to escape quotes within fields
        )
        
        # Write to file
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(output)
        
        return True
    except Exception as e:
        st.error(f"Error saving {file_path}: {str(e)}")
        return False


def get_next_id(df, id_column="id"):
    """Generate next ID by finding max ID and incrementing"""
    if df.empty or id_column not in df.columns:
        return 1
    try:
        # Convert to numeric, handling any non-numeric values
        numeric_ids = pd.to_numeric(df[id_column], errors='coerce')
        max_id = numeric_ids.max()
        if pd.isna(max_id):
            return 1
        return int(max_id) + 1
    except Exception:
        return 1


def duplicate_rows(df, row_indices, id_column="id"):
    """Duplicate selected rows and return updated dataframe"""
    if not row_indices or len(row_indices) == 0:
        return df
    
    # Ensure indices are valid
    valid_indices = [idx for idx in row_indices if 0 <= idx < len(df)]
    if not valid_indices:
        return df
    
    duplicated_rows = df.iloc[valid_indices].copy()
    
    # Generate new IDs for duplicated rows
    if id_column in duplicated_rows.columns:
        next_id = get_next_id(df, id_column)
        for idx in range(len(duplicated_rows)):
            duplicated_rows.iloc[idx, duplicated_rows.columns.get_loc(id_column)] = next_id + idx
    
    # Append duplicated rows to dataframe
    new_df = pd.concat([df, duplicated_rows], ignore_index=True)
    return new_df


def create_new_row(df, id_column="id"):
    """Create a new row with default values"""
    new_row = {}
    for col in df.columns:
        if col == id_column:
            new_row[col] = get_next_id(df, id_column)
        elif col == "created_at":
            from datetime import datetime
            new_row[col] = f'"{datetime.now().isoformat()}Z"'
        else:
            # Set default values based on column type and sample data
            if df[col].dtype == 'int64':
                new_row[col] = 0
            elif df[col].dtype == 'float64':
                new_row[col] = 0.0
            elif df[col].dtype == 'object':
                # Check if it's a boolean-like column or other string type
                if len(df) > 0:
                    sample_val = str(df[col].iloc[0]).lower()
                    if sample_val in ['true', 'false']:
                        new_row[col] = "false"
                    elif sample_val.startswith('"') and sample_val.endswith('"'):
                        new_row[col] = '""'
                    else:
                        new_row[col] = ""
                else:
                    new_row[col] = ""
            else:
                new_row[col] = ""
    
    return new_row


def render_editable_table(df, file_path, title, id_column="id"):
    """Render an editable table with CRUD operations"""
    st.header(title)
    
    if df.empty:
        st.info(f"No data found in {file_path}")
        return df
    
    # Initialize session state for this table
    state_key = f"df_{title.replace(' ', '_').lower()}"
    editor_key = f"editor_{title.replace(' ', '_').lower()}"
    
    # Load initial data if not in session state
    if state_key not in st.session_state:
        st.session_state[state_key] = df.copy()
    
    current_df = st.session_state[state_key]
    
    # Reload button in top right
    col1, col2 = st.columns([1, 1])
    with col2:
        if st.button(f"🔄 Reload from File", key=f"reload_{title}", use_container_width=True):
            reloaded_df = load_csv(file_path)
            st.session_state[state_key] = reloaded_df
            st.success(f"Reloaded {title} from {file_path}")
            st.rerun()
    
    # Editable dataframe
    edited_df = st.data_editor(
        current_df,
        num_rows="dynamic",
        use_container_width=True,
        key=editor_key,
        hide_index=False
    )
    
    # Update session state when dataframe is edited
    # Streamlit automatically updates editor_key in session_state when edited
    st.session_state[state_key] = edited_df.copy()
    
    return edited_df


def get_service_types():
    """Load service types and return dataframe with name and uses_end_date"""
    df = load_csv(SERVICE_TYPES_CSV)
    if df.empty:
        return df
    # Filter to active service types
    if 'is_active' in df.columns:
        # Convert to string to handle any type issues
        df['is_active'] = df['is_active'].astype(str)
        df = df[df['is_active'].str.lower() == 'true']
    return df


def get_service_type_id(service_type_name, service_types_df):
    """Get service_type_id for a given service type name"""
    if service_types_df.empty or 'name' not in service_types_df.columns:
        return None
    matching_row = service_types_df[service_types_df['name'] == service_type_name]
    if matching_row.empty or 'id' not in matching_row.columns:
        return None
    return str(matching_row.iloc[0]['id'])


def get_service_type_uses_end_date(service_type_name, service_types_df):
    """Get uses_end_date value for a given service type name"""
    if service_types_df.empty or 'name' not in service_types_df.columns:
        return "false"
    matching_row = service_types_df[service_types_df['name'] == service_type_name]
    if matching_row.empty or 'uses_end_date' not in matching_row.columns:
        return "false"
    return str(matching_row.iloc[0]['uses_end_date']).lower()


def get_duration_options(service_type_id):
    """Get duration options from services.csv filtered by service_type_id"""
    if not service_type_id:
        return []
    
    services_df = load_csv(SERVICES_CSV)
    if services_df.empty:
        return []
    
    # Filter to active services matching the service_type_id
    if 'is_active' in services_df.columns:
        services_df['is_active'] = services_df['is_active'].astype(str)
        services_df = services_df[services_df['is_active'].str.lower() == 'true']
    
    if 'service_type_id' not in services_df.columns:
        return []
    
    # Filter by service_type_id
    matching_services = services_df[services_df['service_type_id'].astype(str) == str(service_type_id)]
    
    if matching_services.empty:
        return []
    
    duration_options = set()
    
    for _, service in matching_services.iterrows():
        try:
            min_duration = int(float(service.get('min_duration', 0)))
            max_duration_val = service.get('max_duration', 0)
            granularity = int(float(service.get('duration_granularity', 1)))
            
            # Handle max_duration = 0 (unlimited) - generate options up to a reasonable limit
            if max_duration_val == 0 or max_duration_val == '0':
                # Generate options up to 1440 minutes (24 hours) in granularity steps
                max_duration = 1440
                current = min_duration
                while current <= max_duration:
                    duration_options.add(current)
                    current += granularity
            else:
                max_duration = int(float(max_duration_val))
                # Generate options from min to max with granularity step
                current = min_duration
                while current <= max_duration:
                    duration_options.add(current)
                    current += granularity
            
            # Always include min_duration
            duration_options.add(min_duration)
            
        except (ValueError, TypeError):
            continue
    
    # Sort and return as list
    return sorted(list(duration_options))


def add_months(start_date, months):
    """Add months to a date, handling edge cases like month-end dates"""
    year = start_date.year
    month = start_date.month + months
    
    # Handle year overflow
    while month > 12:
        month -= 12
        year += 1
    while month < 1:
        month += 12
        year -= 1
    
    # Handle day overflow (e.g., Jan 31 + 1 month = Feb 28/29)
    try:
        return date(year, month, start_date.day)
    except ValueError:
        # Day doesn't exist in target month (e.g., Jan 31 -> Feb 31)
        # Go to last day of target month
        if month == 12:
            next_month = date(year + 1, 1, 1)
        else:
            next_month = date(year, month + 1, 1)
        last_day = (next_month - timedelta(days=1)).day
        return date(year, month, last_day)


def initialize_appointment_sections():
    """Initialize appointment sections in session state"""
    if 'appointment_sections' not in st.session_state:
        st.session_state['appointment_sections'] = [{}]


def add_appointment_section():
    """Add a new appointment section"""
    if 'appointment_sections' not in st.session_state:
        st.session_state['appointment_sections'] = []
    st.session_state['appointment_sections'].append({})


def remove_appointment_section(section_idx):
    """Remove an appointment section by index"""
    if 'appointment_sections' in st.session_state:
        if 0 <= section_idx < len(st.session_state['appointment_sections']):
            st.session_state['appointment_sections'].pop(section_idx)
            st.rerun()


def render_appointment_section(section_idx, section_data, service_types_df, use_sidebar=False):
    """Render form for a single appointment section"""
    # Use sidebar widgets if requested
    streamlit_ref = st.sidebar if use_sidebar else st
    
    with streamlit_ref.expander(f"Section {section_idx + 1}", expanded=True):
        # Service Type Dropdown
        service_type_names = service_types_df['name'].tolist() if not service_types_df.empty else []
        if not service_type_names:
            streamlit_ref.warning("No service types available. Please add service types first.")
            return
        
        selected_service_type = streamlit_ref.selectbox(
            "Service Type",
            options=service_type_names,
            index=0 if section_data.get('service_type') not in service_type_names 
            else service_type_names.index(section_data.get('service_type', service_type_names[0])),
            key=f"service_type_{section_idx}"
        )
        
        # Get uses_end_date for selected service type
        uses_end_date = get_service_type_uses_end_date(selected_service_type, service_types_df)
        
        # Update section data
        section_data['service_type'] = selected_service_type
        section_data['uses_end_date'] = uses_end_date
        
        # Date/Time fields based on uses_end_date
        col1, col2 = streamlit_ref.columns(2)
        
        with col1:
            start_date = streamlit_ref.date_input(
                "Start Date",
                value=section_data.get('start_date', date.today()),
                key=f"start_date_{section_idx}"
            )
        
        with col2:
            start_time = streamlit_ref.time_input(
                "Start Time",
                value=section_data.get('start_time', time(9, 0)),
                key=f"start_time_{section_idx}"
            )
        
        # Update section data after widgets
        section_data['start_date'] = start_date
        section_data['start_time'] = start_time
        
        if uses_end_date == "false":
            # Show duration field with options from services.csv
            service_type_id = get_service_type_id(selected_service_type, service_types_df)
            duration_options = get_duration_options(service_type_id)
            
            if duration_options:
                current_duration = section_data.get('duration', duration_options[0])
                # Find closest option if current duration doesn't match exactly
                if current_duration not in duration_options:
                    current_duration = min(duration_options, key=lambda x: abs(x - current_duration))
                
                duration = streamlit_ref.selectbox(
                    "Duration (minutes)",
                    options=duration_options,
                    index=duration_options.index(current_duration) if current_duration in duration_options else 0,
                    key=f"duration_{section_idx}"
                )
            else:
                # Fallback to number input if no options found
                duration = streamlit_ref.number_input(
                    "Duration (minutes)",
                    min_value=1,
                    value=section_data.get('duration', 60),
                    key=f"duration_{section_idx}"
                )
            section_data['duration'] = duration
            # Clear end date/time if they exist
            if 'end_date' in section_data:
                del section_data['end_date']
            if 'end_time' in section_data:
                del section_data['end_time']
        else:
            # Show end date and end time
            col3, col4 = streamlit_ref.columns(2)
            with col3:
                end_date = streamlit_ref.date_input(
                    "End Date",
                    value=section_data.get('end_date', date.today()),
                    key=f"end_date_{section_idx}"
                )
                section_data['end_date'] = end_date
            
            with col4:
                end_time = streamlit_ref.time_input(
                    "End Time",
                    value=section_data.get('end_time', time(17, 0)),
                    key=f"end_time_{section_idx}"
                )
                section_data['end_time'] = end_time
            # Clear duration if it exists
            if 'duration' in section_data:
                del section_data['duration']
        
        # Customers Section - Multiple customers with number of pets
        streamlit_ref.subheader("Customers")
        
        # Initialize customers list if not exists
        if 'customers' not in section_data or not isinstance(section_data.get('customers'), list):
            section_data['customers'] = [{"number_of_pets": "1 pet", "price_tier": "Price Tier 1"}]
        
        # Ensure all existing customers have price_tier field
        for customer in section_data['customers']:
            if 'price_tier' not in customer:
                customer['price_tier'] = "Price Tier 1"
        
        customers_list = section_data['customers']
        
        # Display each customer
        for customer_idx, customer in enumerate(customers_list):
            col_cust1, col_cust2, col_cust3 = streamlit_ref.columns([2, 2, 1])
            with col_cust1:
                pets_options = ["1 pet", "2 pets", "3 pets", "4 pets"]
                current_pets = customer.get('number_of_pets', "1 pet")
                selected_pets = streamlit_ref.selectbox(
                    f"Customer {customer_idx + 1} - Number of Pets",
                    options=pets_options,
                    index=pets_options.index(current_pets) if current_pets in pets_options else 0,
                    key=f"customer_{section_idx}_{customer_idx}_pets"
                )
                customers_list[customer_idx]['number_of_pets'] = selected_pets
            
            with col_cust2:
                price_tier_options = ["Price Tier 1", "Price Tier 2", "Price Tier 3"]
                current_price_tier = customer.get('price_tier', "Price Tier 1")
                selected_price_tier = streamlit_ref.selectbox(
                    f"Customer {customer_idx + 1} - Price Tier",
                    options=price_tier_options,
                    index=price_tier_options.index(current_price_tier) if current_price_tier in price_tier_options else 0,
                    key=f"customer_{section_idx}_{customer_idx}_price_tier"
                )
                customers_list[customer_idx]['price_tier'] = selected_price_tier
            
            with col_cust3:
                # Allow removing customer if there's more than one
                if len(customers_list) > 1:
                    if streamlit_ref.button("Remove", key=f"remove_customer_{section_idx}_{customer_idx}", type="secondary"):
                        customers_list.pop(customer_idx)
                        st.session_state['appointment_sections'][section_idx] = section_data
                        st.rerun()
        
        # Add Customer button
        if streamlit_ref.button("➕ Add Customer", key=f"add_customer_{section_idx}"):
            customers_list.append({"number_of_pets": "1 pet", "price_tier": "Price Tier 1"})
            section_data['customers'] = customers_list
            st.session_state['appointment_sections'][section_idx] = section_data
            st.rerun()
        
        # Update section data
        section_data['customers'] = customers_list
        
        # Staff Pay Tier
        streamlit_ref.subheader("Staff Pay Tier")
        pay_tier_options = ["Pay Tier 1", "Pay Tier 2", "Pay Tier 3"]
        current_pay_tier = section_data.get('staff_pay_tier', "Pay Tier 1")
        selected_pay_tier = streamlit_ref.selectbox(
            "Staff Pay Tier",
            options=pay_tier_options,
            index=pay_tier_options.index(current_pay_tier) if current_pay_tier in pay_tier_options else 0,
            key=f"staff_pay_tier_{section_idx}"
        )
        section_data['staff_pay_tier'] = selected_pay_tier
        
        # Recurring Checkbox
        is_recurring = streamlit_ref.checkbox(
            "Recurring",
            value=section_data.get('is_recurring', False),
            key=f"is_recurring_{section_idx}"
        )
        section_data['is_recurring'] = is_recurring
        
        # Recurring fields (shown when checkbox is checked)
        if is_recurring:
            streamlit_ref.subheader("Recurring Options")
            
            # Recurring End Date - default to 1 month from start date
            start_date_value = section_data.get('start_date', date.today())
            default_end_date = add_months(start_date_value, 1) if 'recurring_end_date' not in section_data else section_data.get('recurring_end_date')
            recurring_end_date = streamlit_ref.date_input(
                "Recurring End Date",
                value=default_end_date,
                key=f"recurring_end_date_{section_idx}"
            )
            section_data['recurring_end_date'] = recurring_end_date
            
            # Recurring Every and Frequency (reordered)
            col5, col6 = streamlit_ref.columns(2)
            with col5:
                recurring_every = streamlit_ref.number_input(
                    "Recurring Every",
                    min_value=1,
                    max_value=30,
                    value=section_data.get('recurring_every', 1),
                    key=f"recurring_every_{section_idx}"
                )
                section_data['recurring_every'] = recurring_every
            
            with col6:
                frequency_options = ["day", "week", "month", "year"]
                recurring_frequency = streamlit_ref.selectbox(
                    "Recurring Frequency",
                    options=frequency_options,
                    index=frequency_options.index(section_data.get('recurring_frequency', "week"))
                    if section_data.get('recurring_frequency') in frequency_options else 1,
                    key=f"recurring_frequency_{section_idx}"
                )
                section_data['recurring_frequency'] = recurring_frequency
            
            # Days of Week Checkboxes (only show if frequency is "week")
            if recurring_frequency == "week":
                streamlit_ref.write("Days of Week:")
                days_of_week = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
                selected_days = section_data.get('recurring_days', [])
                
                # If no days selected yet, default to the weekday of the start date
                if not selected_days:
                    start_date_value = section_data.get('start_date', date.today())
                    start_weekday = start_date_value.strftime('%A')  # Returns full weekday name (Monday, Tuesday, etc.)
                    selected_days = [start_weekday]
                    # Update section_data with the default day
                    section_data['recurring_days'] = selected_days
                
                cols = streamlit_ref.columns(7)
                recurring_days = []
                for idx, day in enumerate(days_of_week):
                    with cols[idx]:
                        checkbox_key = f"recurring_day_{day}_{section_idx}"
                        # Initialize checkbox state if not in session state
                        should_be_checked = day in selected_days
                        if checkbox_key not in st.session_state:
                            st.session_state[checkbox_key] = should_be_checked
                        
                        is_checked = streamlit_ref.checkbox(
                            day[:3],  # Show abbreviated: Mon, Tue, etc.
                            value=st.session_state[checkbox_key],
                            key=checkbox_key
                        )
                        if is_checked:
                            recurring_days.append(day)
                section_data['recurring_days'] = recurring_days
            else:
                # Clear recurring_days if frequency is not week
                if 'recurring_days' in section_data:
                    del section_data['recurring_days']
        else:
            # Clear recurring fields if not recurring
            for key in ['recurring_end_date', 'recurring_days', 'recurring_frequency', 'recurring_every']:
                if key in section_data:
                    del section_data[key]
        
        # Remove Section button (hide for first section)
        if section_idx > 0:
            if streamlit_ref.button("Remove Section", key=f"remove_section_{section_idx}", type="secondary"):
                remove_appointment_section(section_idx)
        
        # Update session state
        st.session_state['appointment_sections'][section_idx] = section_data


def format_duration_minutes(minutes):
    """Convert minutes to human-readable format"""
    try:
        minutes = int(float(minutes))
        if minutes == 0:
            return "0 minutes"
        
        days = minutes // 1440
        hours = (minutes % 1440) // 60
        mins = minutes % 60
        
        parts = []
        if days > 0:
            parts.append(f"{days} day{'s' if days != 1 else ''}")
        if hours > 0:
            parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
        if mins > 0:
            parts.append(f"{mins} minute{'s' if mins != 1 else ''}")
        
        return " ".join(parts) if parts else "0 minutes"
    except (ValueError, TypeError):
        return str(minutes)


def calculate_pay_rate_per_hour(service, tier):
    """Calculate pay rate per hour based on tier"""
    try:
        recommended_staff_rate = float(service.get('recommended_staff_rate', 0))
        charge_block_duration = float(service.get('charge_block_duration', 60))
        
        # Convert to per-hour rate (charge_block_duration is in minutes)
        if charge_block_duration > 0:
            rate_per_hour = (recommended_staff_rate / charge_block_duration) * 60
        else:
            rate_per_hour = recommended_staff_rate
        
        # Add tier adjustment
        tier_adjustment = float(tier) * 0.01  # tier 1 = 0.01, tier 2 = 0.02, tier 3 = 0.03
        return rate_per_hour + tier_adjustment
    except (ValueError, TypeError):
        return 0.0


def calculate_price_rate(service, tier):
    """Calculate price based on tier"""
    try:
        recommended_customer_rate = float(service.get('recommended_customer_rate', 0))
        # Add tier adjustment
        tier_adjustment = float(tier) * 0.01  # tier 1 = 0.01, tier 2 = 0.02, tier 3 = 0.03
        return recommended_customer_rate + tier_adjustment
    except (ValueError, TypeError):
        return 0.0


def render_pay_tiers_tab():
    """Render the Pay Tiers tab"""
    st.header("Pay Tiers")
    
    # Load services and service types
    services_df = load_csv(SERVICES_CSV)
    service_types_df = load_csv(SERVICE_TYPES_CSV)
    
    if services_df.empty:
        st.warning("No services found. Please add services first.")
        return
    
    if service_types_df.empty:
        st.warning("No service types found. Please add service types first.")
        return
    
    # Filter to active services
    if 'is_active' in services_df.columns:
        services_df['is_active'] = services_df['is_active'].astype(str)
        services_df = services_df[services_df['is_active'].str.lower() == 'true']
    
    # Join with service types to get service type names
    services_df['service_type_id'] = services_df['service_type_id'].astype(str)
    service_types_df['id'] = service_types_df['id'].astype(str)
    merged_df = services_df.merge(
        service_types_df[['id', 'name']],
        left_on='service_type_id',
        right_on='id',
        how='left'
    )
    
    # Tier selection dropdown
    tier_options = ["Pay Tier 1", "Pay Tier 2", "Pay Tier 3"]
    selected_tier = st.selectbox("Select Pay Tier", options=tier_options, key="pay_tier_select")
    
    # Extract tier number (1, 2, or 3)
    tier_num = int(selected_tier.split()[-1])
    
    # Calculate rates for each service
    display_data = []
    for _, service in merged_df.iterrows():
        rate_per_hour = calculate_pay_rate_per_hour(service, tier_num)
        charge_block_duration = service.get('charge_block_duration', '')
        duration_display = format_duration_minutes(charge_block_duration)
        display_data.append({
            'Service Type': service.get('name', 'Unknown'),
            'Number of Pets': service.get('number_of_pets', ''),
            'Charge Block Duration': duration_display,
            'Rate per Hour': f"£{rate_per_hour:.2f}"
        })
    
    # Create dataframe and display
    if display_data:
        display_df = pd.DataFrame(display_data)
        display_df = display_df.sort_values(['Service Type', 'Number of Pets'])
        st.dataframe(display_df, use_container_width=True, hide_index=True)
    else:
        st.info("No services available to display.")


def render_price_tiers_tab():
    """Render the Price Tiers tab"""
    st.header("Price Tiers")
    
    # Load services and service types
    services_df = load_csv(SERVICES_CSV)
    service_types_df = load_csv(SERVICE_TYPES_CSV)
    
    if services_df.empty:
        st.warning("No services found. Please add services first.")
        return
    
    if service_types_df.empty:
        st.warning("No service types found. Please add service types first.")
        return
    
    # Filter to active services
    if 'is_active' in services_df.columns:
        services_df['is_active'] = services_df['is_active'].astype(str)
        services_df = services_df[services_df['is_active'].str.lower() == 'true']
    
    # Join with service types to get service type names
    services_df['service_type_id'] = services_df['service_type_id'].astype(str)
    service_types_df['id'] = service_types_df['id'].astype(str)
    merged_df = services_df.merge(
        service_types_df[['id', 'name']],
        left_on='service_type_id',
        right_on='id',
        how='left'
    )
    
    # Tier selection dropdown
    tier_options = ["Price Tier 1", "Price Tier 2", "Price Tier 3"]
    selected_tier = st.selectbox("Select Price Tier", options=tier_options, key="price_tier_select")
    
    # Extract tier number (1, 2, or 3)
    tier_num = int(selected_tier.split()[-1])
    
    # Calculate rates for each service
    display_data = []
    for _, service in merged_df.iterrows():
        price = calculate_price_rate(service, tier_num)
        charge_block_duration = service.get('charge_block_duration', '')
        duration_display = format_duration_minutes(charge_block_duration)
        display_data.append({
            'Service Type': service.get('name', 'Unknown'),
            'Number of Pets': service.get('number_of_pets', ''),
            'Charge Block Duration': duration_display,
            'Price': f"£{price:.2f}"
        })
    
    # Create dataframe and display
    if display_data:
        display_df = pd.DataFrame(display_data)
        display_df = display_df.sort_values(['Service Type', 'Number of Pets'])
        st.dataframe(display_df, use_container_width=True, hide_index=True)
    else:
        st.info("No services available to display.")


def generate_recurring_dates(start_date, end_date, frequency, every, days_of_week):
    """Generate list of dates based on recurring rules"""
    dates = []
    
    if frequency == "week":
        # For weekly recurrence, check all selected days within each week
        # Start from the beginning of the week containing start_date
        days_mapping = {'Monday': 0, 'Tuesday': 1, 'Wednesday': 2, 'Thursday': 3, 
                       'Friday': 4, 'Saturday': 5, 'Sunday': 6}
        
        # Get the weekday of start_date (0=Monday, 6=Sunday)
        start_weekday = start_date.weekday()
        
        # Find the Monday of the week containing start_date
        days_since_monday = start_weekday  # 0=Monday, 1=Tuesday, etc.
        week_start = start_date - timedelta(days=days_since_monday)
        
        # Iterate through each week
        current_week_start = week_start
        week_count = 0
        
        while True:
            # Check if we should process this week (based on 'every' parameter)
            if week_count % every == 0:
                # Check all days in this week that match selected days_of_week
                for day_name in days_of_week:
                    day_offset = days_mapping[day_name]
                    check_date = current_week_start + timedelta(days=day_offset)
                    
                    # Only add dates that are >= start_date and <= end_date
                    if check_date >= start_date and check_date <= end_date:
                        dates.append(check_date)
            
            # Move to next week
            current_week_start += timedelta(weeks=1)
            week_count += 1
            
            # Stop if the entire next week is past the end date
            if current_week_start > end_date:
                break
    else:
        # For other frequencies, use the original logic
        current_date = start_date
        
        while current_date <= end_date:
            # Check if current date matches selected days of week (if applicable)
            if frequency == "day" or not days_of_week:
                # For daily or no day filter, add all dates
                dates.append(current_date)
            else:
                weekday_name = current_date.strftime('%A')
                if weekday_name in days_of_week:
                    dates.append(current_date)
            
            # Move to next date based on frequency
            if frequency == "day":
                current_date += timedelta(days=every)
            elif frequency == "month":
                # Approximate month as 30 days
                current_date += timedelta(days=30 * every)
            elif frequency == "year":
                # Approximate year as 365 days
                current_date += timedelta(days=365 * every)
            else:
                break
    
    # Sort dates to ensure chronological order
    dates.sort()
    return dates


def generate_appointments_from_sections():
    """Generate appointments from all sections in session state"""
    appointments = []
    sections = st.session_state.get('appointment_sections', [])
    
    for section_idx, section in enumerate(sections):
        # Skip if section doesn't have required fields
        if not section.get('service_type') or not section.get('start_date') or not section.get('start_time'):
            continue
        
        service_type = section.get('service_type')
        start_date = section.get('start_date')
        start_time = section.get('start_time')
        uses_end_date = section.get('uses_end_date', 'false')
        customers = section.get('customers', [])
        staff_pay_tier = section.get('staff_pay_tier', 'Pay Tier 1')
        is_recurring = section.get('is_recurring', False)
        
        # Determine appointment dates
        if is_recurring:
            recurring_end_date = section.get('recurring_end_date', start_date)
            frequency = section.get('recurring_frequency', 'week')
            every = section.get('recurring_every', 1)
            days_of_week = section.get('recurring_days', [])
            
            if days_of_week:
                appointment_dates = generate_recurring_dates(
                    start_date, recurring_end_date, frequency, every, days_of_week
                )
            else:
                # If no days selected, use start date only
                appointment_dates = [start_date]
        else:
            appointment_dates = [start_date]
        
        # Generate appointments for each date and each customer
        for appointment_date in appointment_dates:
            for customer_idx, customer in enumerate(customers):
                number_of_pets = customer.get('number_of_pets', '1 pet')
                price_tier = customer.get('price_tier', 'Price Tier 1')
                
                # Create appointment entry
                appointment = {
                    'service_type': service_type,
                    'customer': f"Customer {customer_idx + 1}",
                    'number_of_pets': number_of_pets,
                    'date': appointment_date,
                    'start_time': start_time,
                    'staff_pay_tier': staff_pay_tier,
                    'price_tier': price_tier,
                    'is_recurring': is_recurring,
                    'section_index': section_idx
                }
                
                # Add duration or end_time based on uses_end_date
                if uses_end_date == 'false':
                    appointment['duration'] = section.get('duration', 60)
                    appointment['end_time'] = None
                else:
                    appointment['duration'] = None
                    appointment['end_time'] = section.get('end_time', time(17, 0))
                
                appointments.append(appointment)
    
    return appointments


def calculate_invoice_data(appointments):
    """Calculate invoice data grouped by service type and duration"""
    if not appointments:
        return []
    
    # Load services and service types
    services_df = load_csv(SERVICES_CSV)
    service_types_df = get_service_types()
    
    if services_df.empty or service_types_df.empty:
        return []
    
    # Filter to active services
    if 'is_active' in services_df.columns:
        services_df['is_active'] = services_df['is_active'].astype(str)
        services_df = services_df[services_df['is_active'].str.lower() == 'true']
    
    # Join with service types to get service type names
    services_df['service_type_id'] = services_df['service_type_id'].astype(str)
    service_types_df['id'] = service_types_df['id'].astype(str)
    merged_services = services_df.merge(
        service_types_df[['id', 'name']],
        left_on='service_type_id',
        right_on='id',
        how='left'
    )
    
    # Group appointments by service type and duration
    invoice_dict = {}
    
    for apt in appointments:
        service_type_name = apt.get('service_type', 'Unknown')
        duration = apt.get('duration')
        price_tier = apt.get('price_tier', 'Price Tier 1')
        
        # Skip if no duration (end_time based appointments)
        if duration is None:
            continue
        
        # Format duration for display
        duration_display = format_duration_minutes(duration)
        
        # Create key: "Service Type - Duration"
        key = f"{service_type_name} - {duration_display}"
        
        # Calculate price using the same function that considers number_of_pets
        price = calculate_appointment_price(apt, merged_services)
        if price is None:
            price = 0.0
        
        # Aggregate
        if key not in invoice_dict:
            invoice_dict[key] = {
                'Service Type - Duration': key,
                'Count': 0,
                'Total': 0.0
            }
        
        invoice_dict[key]['Count'] += 1
        invoice_dict[key]['Total'] += price
    
    # Convert to list and sort
    invoice_data = list(invoice_dict.values())
    invoice_data.sort(key=lambda x: x['Service Type - Duration'])
    
    return invoice_data


def calculate_appointment_price(apt, merged_services):
    """Calculate price for a single appointment"""
    service_type_name = apt.get('service_type', 'Unknown')
    duration = apt.get('duration')
    number_of_pets = apt.get('number_of_pets', '1 pet')
    price_tier = apt.get('price_tier', 'Price Tier 1')
    
    # Skip if no duration (end_time based appointments)
    if duration is None:
        return None
    
    # Extract numeric value from number_of_pets (e.g., "1 pet" -> 1, "2 pets" -> 2)
    pets_str = number_of_pets.strip().lower()
    pets_num = None
    for word in pets_str.split():
        try:
            pets_num = int(word)
            break
        except ValueError:
            continue
    
    # If we couldn't extract a number, default to 1
    if pets_num is None:
        pets_num = 1
    
    # Find matching service by service type, duration, and number of pets
    # First filter by service type and duration
    matching_services = merged_services[
        (merged_services['name'] == service_type_name) &
        (merged_services['charge_block_duration'].astype(str) == str(duration))
    ]
    
    if matching_services.empty:
        return None
    
    # Now try to match by number_of_pets
    if 'number_of_pets' in matching_services.columns:
        # Try to match exactly first
        pets_exact_match = matching_services['number_of_pets'].astype(str).str.strip().str.lower() == pets_str
        exact_matches = matching_services[pets_exact_match]
        
        if not exact_matches.empty:
            matching_services = exact_matches
        else:
            # Try to extract number from service's number_of_pets and match
            def extract_pets_num(service_pets_str):
                if pd.isna(service_pets_str):
                    return None
                service_pets_str = str(service_pets_str).strip().lower()
                for word in service_pets_str.split():
                    try:
                        return int(word)
                    except ValueError:
                        continue
                return None
            
            matching_services['_pets_num'] = matching_services['number_of_pets'].apply(extract_pets_num)
            pets_num_match = matching_services['_pets_num'] == pets_num
            num_matches = matching_services[pets_num_match]
            
            if not num_matches.empty:
                matching_services = num_matches
            # If still no match, don't fall back - we need exact match for correct pricing
    
    # Remove the temporary column if it exists
    if '_pets_num' in matching_services.columns:
        matching_services = matching_services.drop(columns=['_pets_num'])
    
    if matching_services.empty:
        return None
    
    service = matching_services.iloc[0]
    tier_num = int(price_tier.split()[-1]) if 'Tier' in price_tier else 1
    price = calculate_price_rate(service, tier_num)
    
    return price


def get_unique_months(appointments):
    """Extract unique months from appointments and return formatted list"""
    if not appointments:
        return []
    
    months_set = set()
    for apt in appointments:
        apt_date = apt.get('date')
        if apt_date and isinstance(apt_date, date):
            # Format as "Month YYYY" (e.g., "November 2025")
            month_str = apt_date.strftime('%B %Y')
            months_set.add((month_str, apt_date.year, apt_date.month))
    
    # Sort by year and month
    sorted_months = sorted(months_set, key=lambda x: (x[1], x[2]))
    return [month[0] for month in sorted_months]


def filter_appointments_by_month(appointments, selected_month):
    """Filter appointments by selected month"""
    if not appointments or selected_month == "All appointments":
        return appointments
    
    filtered = []
    for apt in appointments:
        apt_date = apt.get('date')
        if apt_date and isinstance(apt_date, date):
            month_str = apt_date.strftime('%B %Y')
            if month_str == selected_month:
                filtered.append(apt)
    
    return filtered


def render_appointments_list_tab():
    """Render the Appointments tab showing preview and created appointments"""
    # Show preview of appointments that will be created from sidebar form
    # Generate preview of appointments from current sidebar form state
    preview_appointments = generate_appointments_from_sections()
    
    # Month filter - placed above the header
    if preview_appointments:
        unique_months = get_unique_months(preview_appointments)
        month_options = ["All appointments"] + unique_months
        
        selected_month = st.selectbox(
            "Filter by Month",
            options=month_options,
            index=0,  # Default to "All appointments"
            key="appointment_month_filter"
        )
        
        # Filter appointments based on selected month
        filtered_appointments = filter_appointments_by_month(preview_appointments, selected_month)
    else:
        filtered_appointments = []
        selected_month = "All appointments"
    
    st.header("Appointments")
    
    # Customer Invoice Section - placed above appointments
    if filtered_appointments:
        invoice_data = calculate_invoice_data(filtered_appointments)
        if invoice_data:
            st.subheader("Customer Invoice")
            
            # Format the invoice data for display
            invoice_display = []
            for item in invoice_data:
                invoice_display.append({
                    'Service Type - Duration': item['Service Type - Duration'],
                    'Count': item['Count'],
                    'Total': f"£{item['Total']:.2f}"
                })
            
            invoice_df = pd.DataFrame(invoice_display)
            st.dataframe(invoice_df, use_container_width=True, hide_index=True)
            
            # Calculate grand total
            grand_total = sum(item['Total'] for item in invoice_data)
            st.caption(f"Grand Total: £{grand_total:.2f}")
            
            st.divider()
    
    # Appointments Section
    st.subheader("Appointments")
    
    if filtered_appointments:
        # Load services and service types for price calculation
        services_df = load_csv(SERVICES_CSV)
        service_types_df = get_service_types()
        
        # Prepare merged services if available
        merged_services = pd.DataFrame()
        if not services_df.empty and not service_types_df.empty:
            # Filter to active services
            if 'is_active' in services_df.columns:
                services_df['is_active'] = services_df['is_active'].astype(str)
                services_df = services_df[services_df['is_active'].str.lower() == 'true']
            
            # Join with service types to get service type names
            services_df['service_type_id'] = services_df['service_type_id'].astype(str)
            service_types_df['id'] = service_types_df['id'].astype(str)
            merged_services = services_df.merge(
                service_types_df[['id', 'name']],
                left_on='service_type_id',
                right_on='id',
                how='left'
            )
        
        # Convert to dataframe for display
        preview_data = []
        for apt in filtered_appointments:
            # Format date and time
            date_str = apt['date'].strftime('%Y-%m-%d') if isinstance(apt['date'], date) else str(apt['date'])
            time_str = apt['start_time'].strftime('%H:%M') if isinstance(apt['start_time'], time) else str(apt['start_time'])
            
            # Format duration/end time
            if apt.get('duration'):
                duration_display = format_duration_minutes(apt['duration'])
            elif apt.get('end_time'):
                end_time_str = apt['end_time'].strftime('%H:%M') if isinstance(apt['end_time'], time) else str(apt['end_time'])
                duration_display = f"Until {end_time_str}"
            else:
                duration_display = "N/A"
            
            # Calculate price and format Price Tier column
            price_tier = apt.get('price_tier', '')
            price = None
            if not merged_services.empty:
                price = calculate_appointment_price(apt, merged_services)
            
            if price is not None:
                price_tier_display = f"{price_tier} (£{price:.2f})"
            else:
                price_tier_display = price_tier
            
            preview_data.append({
                'Date': date_str,
                'Start Time': time_str,
                'Service Type': apt.get('service_type', 'Unknown'),
                'Customer': apt.get('customer', 'Unknown'),
                'Number of Pets': apt.get('number_of_pets', ''),
                'Duration/End Time': duration_display,
                'Price Tier': price_tier_display,
                'Staff Pay Tier': apt.get('staff_pay_tier', ''),
                'Recurring': 'Yes' if apt.get('is_recurring', False) else 'No'
            })
        
        if preview_data:
            preview_df = pd.DataFrame(preview_data)
            # Sort by date and time
            preview_df['_sort_date'] = pd.to_datetime(preview_df['Date'] + ' ' + preview_df['Start Time'])
            preview_df = preview_df.sort_values('_sort_date')
            preview_df = preview_df.drop(columns=['_sort_date'])
            
            st.dataframe(preview_df, use_container_width=True, hide_index=True)
    elif preview_appointments:
        # Preview appointments exist but filter returned no results
        st.info(f"No appointments found for the selected month.")
    else:
        st.info("Complete the form in the sidebar to see a preview of appointments that will be created.")
    
    # Show created appointments (if any)
    if 'appointments' in st.session_state and st.session_state['appointments']:
        st.divider()
        st.subheader("Created Appointments")
        
        created_appointments = st.session_state.get('appointments', [])
        
        # Load services and service types for price calculation
        services_df = load_csv(SERVICES_CSV)
        service_types_df = get_service_types()
        
        # Prepare merged services if available
        merged_services = pd.DataFrame()
        if not services_df.empty and not service_types_df.empty:
            # Filter to active services
            if 'is_active' in services_df.columns:
                services_df['is_active'] = services_df['is_active'].astype(str)
                services_df = services_df[services_df['is_active'].str.lower() == 'true']
            
            # Join with service types to get service type names
            services_df['service_type_id'] = services_df['service_type_id'].astype(str)
            service_types_df['id'] = service_types_df['id'].astype(str)
            merged_services = services_df.merge(
                service_types_df[['id', 'name']],
                left_on='service_type_id',
                right_on='id',
                how='left'
            )
        
        # Convert to dataframe for display
        created_data = []
        for apt in created_appointments:
            # Format date and time
            date_str = apt['date'].strftime('%Y-%m-%d') if isinstance(apt['date'], date) else str(apt['date'])
            time_str = apt['start_time'].strftime('%H:%M') if isinstance(apt['start_time'], time) else str(apt['start_time'])
            
            # Format duration/end time
            if apt.get('duration'):
                duration_display = format_duration_minutes(apt['duration'])
            elif apt.get('end_time'):
                end_time_str = apt['end_time'].strftime('%H:%M') if isinstance(apt['end_time'], time) else str(apt['end_time'])
                duration_display = f"Until {end_time_str}"
            else:
                duration_display = "N/A"
            
            # Calculate price and format Price Tier column
            price_tier = apt.get('price_tier', '')
            price = None
            if not merged_services.empty:
                price = calculate_appointment_price(apt, merged_services)
            
            if price is not None:
                price_tier_display = f"{price_tier} (£{price:.2f})"
            else:
                price_tier_display = price_tier
            
            created_data.append({
                'Date': date_str,
                'Start Time': time_str,
                'Service Type': apt.get('service_type', 'Unknown'),
                'Customer': apt.get('customer', 'Unknown'),
                'Number of Pets': apt.get('number_of_pets', ''),
                'Duration/End Time': duration_display,
                'Price Tier': price_tier_display,
                'Staff Pay Tier': apt.get('staff_pay_tier', ''),
                'Recurring': 'Yes' if apt.get('is_recurring', False) else 'No'
            })
        
        if created_data:
            created_df = pd.DataFrame(created_data)
            # Sort by date and time
            created_df['_sort_date'] = pd.to_datetime(created_df['Date'] + ' ' + created_df['Start Time'])
            created_df = created_df.sort_values('_sort_date')
            created_df = created_df.drop(columns=['_sort_date'])
            
            st.dataframe(created_df, use_container_width=True, hide_index=True)
            st.caption(f"Total: {len(created_appointments)} created appointment(s)")


def render_create_appointment_sidebar():
    """Render the create appointment form in the sidebar"""
    st.sidebar.header("Create Appointment")
    
    # Initialize sections
    initialize_appointment_sections()
    
    # Load service types
    service_types_df = get_service_types()
    
    if service_types_df.empty:
        st.sidebar.warning("No service types found. Please add service types in the Service Types tab first.")
        return
    
    # Render each section in sidebar
    sections = st.session_state.get('appointment_sections', [{}])
    for idx, section_data in enumerate(sections):
        render_appointment_section(idx, section_data, service_types_df, use_sidebar=True)
        if idx < len(sections) - 1:
            st.sidebar.divider()
    
    # Buttons at the bottom
    st.sidebar.divider()
    if st.sidebar.button("➕ Add Section", type="secondary", use_container_width=True):
        add_appointment_section()
        st.rerun()


def main():
    st.title("🐾 Pet Scheduler")
    st.markdown("Manage appointments, services, and service types")
    
    # Render create appointment form in sidebar
    render_create_appointment_sidebar()
    
    # Create tabs - Appointments is now first
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["Appointments", "Services", "Service Types", "Pay Tiers", "Price Tiers"])
    
    # Appointments tab (now first/default)
    with tab1:
        render_appointments_list_tab()
    
    # Services tab
    with tab2:
        services_df = load_csv(SERVICES_CSV)
        render_editable_table(
            services_df,
            SERVICES_CSV,
            "Services",
            id_column="id"
        )
    
    # Service Types tab
    with tab3:
        service_types_df = load_csv(SERVICE_TYPES_CSV)
        render_editable_table(
            service_types_df,
            SERVICE_TYPES_CSV,
            "Service Types",
            id_column="id"
        )
    
    # Pay Tiers tab
    with tab4:
        render_pay_tiers_tab()
    
    # Price Tiers tab
    with tab5:
        render_price_tiers_tab()


if __name__ == "__main__":
    main()

