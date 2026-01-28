# src/services.py

SERVICES = {
    "identity_card": {
        "name": "Identity Card Issue (14yo)",
        "description": "Application for the first Identity Card issuance for minors.",
        "template_file": "template_id.pdf",
        "pdf_enabled": True,
        "required_fields": {
            "LastName": "Family Name", 
            "FirstName": "First Name", 
            "CNP": "Personal Numerical Code (CNP)",
            "FatherName": "Father's First Name", 
            "MotherName": "Mother's First Name", 
            "City": "City / Sector", 
            "Street": "Street Name", 
            "Number": "Street Number"
        }
    },
    "passport_renewal": {
        "name": "Passport Renewal Application",
        "description": "Application to renew an expired electronic passport.",
        "template_file": "template_passport.pdf",
        "pdf_enabled": True,
        "required_fields": {
            "LastName": "Current Family Name",
            "FirstName": "First Name",
            "PassportNo": "Old Passport Number",
            "ExpiryDate": "Old Expiry Date (DD/MM/YYYY)",
            "CNP": "Personal Numerical Code",
            "Reason": "Reason for Renewal"
        }
    },
    "vehicle_registration": {
        "name": "Vehicle Registration Form",
        "description": "Registering a newly purchased vehicle.",
        "template_file": "template_vehicle.pdf",
        "pdf_enabled": True,
        "required_fields": {
            "OwnerName": "New Owner Name",
            "VIN": "Chassis Number (VIN)",
            "CarMake": "Car Brand (Make)",
            "CarModel": "Car Model",
            "ProductionYear": "Year of Production",
            "Date": "Purchase Date"
        }
    }
}