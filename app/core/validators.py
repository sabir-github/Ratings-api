import re
from typing import Optional, Dict, Any, List
from datetime import datetime, date
from email_validator import validate_email, EmailNotValidError
import phonenumbers
from pydantic import BaseModel, ValidationError
import logging

logger = logging.getLogger(__name__)

class ValidationResult:
    def __init__(self, is_valid: bool, message: str = "", details: Optional[Dict] = None):
        self.is_valid = is_valid
        self.message = message
        self.details = details or {}

    def __bool__(self):
        return self.is_valid

# Email validation
def validate_email_address(email: str) -> ValidationResult:
    """
    Validate email address format and deliverability
    """
    try:
        # Validate the email
        email_info = validate_email(email, check_deliverability=False)
        
        # Return normalized email
        return ValidationResult(
            is_valid=True,
            message="Valid email address",
            details={"normalized_email": email_info.normalized}
        )
    except EmailNotValidError as e:
        return ValidationResult(
            is_valid=False,
            message=str(e)
        )

# Phone number validation
def validate_phone_number(phone: str, country_code: str = "US") -> ValidationResult:
    """
    Validate phone number format for a specific country
    """
    try:
        parsed_number = phonenumbers.parse(phone, country_code)
        
        if not phonenumbers.is_valid_number(parsed_number):
            return ValidationResult(
                is_valid=False,
                message="Invalid phone number format"
            )
        
        # Format the number in international format
        formatted_number = phonenumbers.format_number(
            parsed_number, 
            phonenumbers.PhoneNumberFormat.INTERNATIONAL
        )
        
        return ValidationResult(
            is_valid=True,
            message="Valid phone number",
            details={
                "formatted_number": formatted_number,
                "country_code": phonenumbers.region_code_for_number(parsed_number),
                "number_type": phonenumbers.number_type(parsed_number)
            }
        )
    except phonenumbers.NumberParseException as e:
        return ValidationResult(
            is_valid=False,
            message="Unable to parse phone number"
        )

# Password strength validation (without 72-byte limit)
def validate_password_strength(password: str, min_length: int = 8) -> ValidationResult:
    """
    Validate password strength with multiple criteria
    """
    issues = []
    
    # Check minimum length only (no maximum length restriction)
    if len(password) < min_length:
        issues.append(f"Password must be at least {min_length} characters long")
    
    # Check for uppercase letters
    if not re.search(r'[A-Z]', password):
        issues.append("Password must contain at least one uppercase letter")
    
    # Check for lowercase letters
    if not re.search(r'[a-z]', password):
        issues.append("Password must contain at least one lowercase letter")
    
    # Check for numbers
    if not re.search(r'[0-9]', password):
        issues.append("Password must contain at least one number")
    
    # Check for special characters
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        issues.append("Password must contain at least one special character")
    
    # Check for common patterns (optional)
    common_patterns = [
        '123456', 'password', 'qwerty', 'admin', 'welcome'
    ]
    
    for pattern in common_patterns:
        if pattern.lower() in password.lower():
            issues.append("Password contains common patterns that are easy to guess")
            break
    
    if issues:
        return ValidationResult(
            is_valid=False,
            message="Password does not meet security requirements",
            details={"issues": issues}
        )
    
    # Calculate password strength score
    strength_score = calculate_password_strength(password)
    
    return ValidationResult(
        is_valid=True,
        message="Password meets security requirements",
        details={"strength_score": strength_score}
    )

def calculate_password_strength(password: str) -> int:
    """
    Calculate password strength score (0-100)
    """
    score = 0
    
    # Length contributes up to 40 points (no upper limit)
    length_score = min(40, len(password) * 2)
    score += length_score
    
    # Character variety contributes up to 60 points
    char_types = 0
    if re.search(r'[a-z]', password):
        char_types += 1
    if re.search(r'[A-Z]', password):
        char_types += 1
    if re.search(r'[0-9]', password):
        char_types += 1
    if re.search(r'[^a-zA-Z0-9]', password):
        char_types += 1
    
    variety_score = (char_types / 4) * 60
    score += variety_score
    
    return min(100, int(score))

# Username validation
def validate_username(username: str, min_length: int = 3, max_length: int = 50) -> ValidationResult:
    """
    Validate username format and availability
    """
    # Check length
    if len(username) < min_length or len(username) > max_length:
        return ValidationResult(
            is_valid=False,
            message=f"Username must be between {min_length} and {max_length} characters long"
        )
    
    # Check for invalid characters
    if not re.match(r'^[a-zA-Z0-9_-]+$', username):
        return ValidationResult(
            is_valid=False,
            message="Username can only contain letters, numbers, underscores, and hyphens"
        )
    
    # Check for reserved usernames
    reserved_usernames = [
        'admin', 'administrator', 'root', 'system', 'support',
        'help', 'info', 'contact', 'null', 'undefined'
    ]
    
    if username.lower() in reserved_usernames:
        return ValidationResult(
            is_valid=False,
            message="This username is reserved"
        )
    
    return ValidationResult(
        is_valid=True,
        message="Valid username"
    )

# Company name validation
def validate_company_name(name: str, min_length: int = 2, max_length: int = 255) -> ValidationResult:
    """
    Validate company name format
    """
    # Check length
    if len(name) < min_length or len(name) > max_length:
        return ValidationResult(
            is_valid=False,
            message=f"Company name must be between {min_length} and {max_length} characters long"
        )
    
    # Check for empty or whitespace-only names
    if not name or not name.strip():
        return ValidationResult(
            is_valid=False,
            message="Company name cannot be empty"
        )
    
    # Check for invalid characters
    if re.search(r'[<>"/\\|?*]', name):
        return ValidationResult(
            is_valid=False,
            message="Company name contains invalid characters"
        )
    
    return ValidationResult(
        is_valid=True,
        message="Valid company name"
    )

# Date validation
def validate_date_format(date_string: str, format: str = "%Y-%m-%d") -> ValidationResult:
    """
    Validate date string format
    """
    try:
        parsed_date = datetime.strptime(date_string, format)
        return ValidationResult(
            is_valid=True,
            message="Valid date format",
            details={"parsed_date": parsed_date}
        )
    except ValueError as e:
        return ValidationResult(
            is_valid=False,
            message=f"Invalid date format. Expected format: {format}"
        )

def validate_future_date(date_string: str, format: str = "%Y-%m-%d") -> ValidationResult:
    """
    Validate that a date is in the future
    """
    try:
        parsed_date = datetime.strptime(date_string, format).date()
        today = date.today()
        
        if parsed_date <= today:
            return ValidationResult(
                is_valid=False,
                message="Date must be in the future"
            )
    except ValueError as e:
        return ValidationResult(
            is_valid=False,
            message=f"Invalid date format. Expected format: {format}"
        )
    
    return ValidationResult(
        is_valid=True,
        message="Valid future date"
    )

# Numeric validation
def validate_positive_number(value: float, field_name: str = "Value") -> ValidationResult:
    """
    Validate that a number is positive
    """
    if value <= 0:
        return ValidationResult(
            is_valid=False,
            message=f"{field_name} must be greater than 0"
        )
    
    return ValidationResult(
        is_valid=True,
        message=f"Valid {field_name.lower()}"
    )

def validate_percentage(value: float) -> ValidationResult:
    """
    Validate percentage value (0-100)
    """
    if value < 0 or value > 100:
        return ValidationResult(
            is_valid=False,
            message="Percentage must be between 0 and 100"
        )
    
    return ValidationResult(
        is_valid=True,
        message="Valid percentage value"
    )

def validate_temperature(value: float, unit: str = "C") -> ValidationResult:
    """
    Validate temperature value
    """
    if unit.upper() == "C":
        if value < -273.15:  # Absolute zero in Celsius
            return ValidationResult(
                is_valid=False,
                message="Temperature cannot be below absolute zero (-273.15°C)"
            )
    elif unit.upper() == "F":
        if value < -459.67:  # Absolute zero in Fahrenheit
            return ValidationResult(
                is_valid=False,
                message="Temperature cannot be below absolute zero (-459.67°F)"
            )
    
    return ValidationResult(
        is_valid=True,
        message="Valid temperature value"
    )

# Address validation
def validate_address(address_data: Dict[str, str]) -> ValidationResult:
    """
    Validate address components
    """
    required_fields = ['street', 'city', 'state', 'zip_code', 'country']
    missing_fields = [field for field in required_fields if not address_data.get(field)]
    
    if missing_fields:
        return ValidationResult(
            is_valid=False,
            message="Missing required address fields",
            details={"missing_fields": missing_fields}
        )
    
    # Validate zip code format (US)
    zip_code = address_data.get('zip_code', '')
    if not re.match(r'^\d{5}(-\d{4})?$', zip_code):
        return ValidationResult(
            is_valid=False,
            message="Invalid zip code format"
        )
    
    return ValidationResult(
        is_valid=True,
        message="Valid address"
    )

# File validation
def validate_file_extension(filename: str, allowed_extensions: List[str]) -> ValidationResult:
    """
    Validate file extension
    """
    if not filename:
        return ValidationResult(
            is_valid=False,
            message="Filename cannot be empty"
        )
    
    file_ext = filename.split('.')[-1].lower() if '.' in filename else ''
    
    if file_ext not in allowed_extensions:
        return ValidationResult(
            is_valid=False,
            message=f"File extension not allowed. Allowed extensions: {', '.join(allowed_extensions)}"
        )
    
    return ValidationResult(
        is_valid=True,
        message="Valid file extension"
    )

def validate_file_size(file_size: int, max_size_mb: int = 10) -> ValidationResult:
    """
    Validate file size
    """
    max_size_bytes = max_size_mb * 1024 * 1024
    
    if file_size > max_size_bytes:
        return ValidationResult(
            is_valid=False,
            message=f"File size exceeds maximum allowed size of {max_size_mb}MB"
        )
    
    return ValidationResult(
        is_valid=True,
        message="Valid file size"
    )

# Business logic validators
def validate_company_registration(data: Dict[str, Any]) -> ValidationResult:
    """
    Validate company registration data
    """
    issues = []
    
    # Validate company name
    name_result = validate_company_name(data.get('name', ''))
    if not name_result:
        issues.append(name_result.message)
    
    # Validate email
    email_result = validate_email_address(data.get('email', ''))
    if not email_result:
        issues.append(email_result.message)
    
    # Validate phone
    phone_result = validate_phone_number(data.get('phone', ''))
    if not phone_result:
        issues.append(phone_result.message)
    
    if issues:
        return ValidationResult(
            is_valid=False,
            message="Company registration validation failed",
            details={"issues": issues}
        )
    
    return ValidationResult(
        is_valid=True,
        message="Valid company registration data"
    )


# Composite validator for user registration
def validate_user_registration(data: Dict[str, Any]) -> ValidationResult:
    """
    Comprehensive validation for user registration
    """
    issues = []
    
    # Validate username
    username_result = validate_username(data.get('username', ''))
    if not username_result:
        issues.append(username_result.message)
    
    # Validate email
    email_result = validate_email_address(data.get('email', ''))
    if not email_result:
        issues.append(email_result.message)
    
    # Validate password (only minimum length, no maximum)
    password_result = validate_password_strength(data.get('password', ''))
    if not password_result:
        issues.append(password_result.message)
    
    # Validate first name and last name
    if not data.get('first_name') or len(data.get('first_name', '').strip()) == 0:
        issues.append("First name is required")
    
    if not data.get('last_name') or len(data.get('last_name', '').strip()) == 0:
        issues.append("Last name is required")
    
    if issues:
        return ValidationResult(
            is_valid=False,
            message="User registration validation failed",
            details={"issues": issues}
        )
    
    return ValidationResult(
        is_valid=True,
        message="Valid user registration data"
    )

# Async validators for database checks
async def validate_username_availability(username: str, user_service) -> ValidationResult:
    """
    Validate that username is not already taken
    """
    try:
        existing_user = await user_service.get_user_by_username(username)
        if existing_user:
            return ValidationResult(
                is_valid=False,
                message="Username already taken"
        )
    except Exception as e:
        logger.error(f"Error checking username availability: {e}")
        return ValidationResult(
            is_valid=False,
            message="Unable to verify username availability"
        )
    
    return ValidationResult(
        is_valid=True,
        message="Username is available"
    )

async def validate_email_availability(email: str, user_service) -> ValidationResult:
    """
    Validate that email is not already registered
    """
    try:
        existing_user = await user_service.get_user_by_email(email)
        if existing_user:
            return ValidationResult(
                is_valid=False,
                message="Email already registered"
        )
    except Exception as e:
        logger.error(f"Error checking email availability: {e}")
        return ValidationResult(
            is_valid=False,
            message="Unable to verify email availability"
        )
    
    return ValidationResult(
        is_valid=True,
        message="Email is available"
    )

# Validation decorator
def validate_with(validator_func):
    """
    Decorator to validate function arguments
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            # Extract data to validate (you might need to adjust this)
            validation_result = validator_func(kwargs)
            if not validation_result:
                raise ValueError(validation_result.message)
            return func(*args, **kwargs)
        return wrapper
    return decorator

# Utility function to format validation errors
def format_validation_errors(validation_result: ValidationResult) -> Dict[str, Any]:
    """
    Format validation errors for API responses
    """
    return {
        "valid": validation_result.is_valid,
        "message": validation_result.message,
        "details": validation_result.details
    }
# LOB validation functions
def validate_lob_code(lob_code: str) -> ValidationResult:
    """
    Validate LOB code format
    """
    if len(lob_code) < 2 or len(lob_code) > 20:
        return ValidationResult(
            is_valid=False,
            message="LOB code must be between 2 and 20 characters long"
        )
    
    # Allow letters, numbers, hyphens, underscores
    if not re.match(r'^[A-Za-z0-9_-]+$', lob_code):
        return ValidationResult(
            is_valid=False,
            message="LOB code can only contain letters, numbers, hyphens, and underscores"
        )
    
    return ValidationResult(
        is_valid=True,
        message="Valid LOB code"
    )

def validate_lob_name(lob_name: str) -> ValidationResult:
    """
    Validate LOB name
    """
    if len(lob_name) < 2 or len(lob_name) > 100:
        return ValidationResult(
            is_valid=False,
            message="LOB name must be between 2 and 100 characters long"
        )
    
    # Allow letters, numbers, spaces, hyphens, underscores
    if not re.match(r'^[a-zA-Z0-9\s_-]+$', lob_name):
        return ValidationResult(
            is_valid=False,
            message="LOB name can only contain letters, numbers, spaces, hyphens, and underscores"
        )
    
    return ValidationResult(
        is_valid=True,
        message="Valid LOB name"
    )

def validate_lob_abbreviation(abbreviation: str) -> ValidationResult:
    """
    Validate LOB abbreviation
    """
    if len(abbreviation) < 1 or len(abbreviation) > 10:
        return ValidationResult(
            is_valid=False,
            message="LOB abbreviation must be between 1 and 10 characters long"
        )
    
    # Allow only uppercase letters and numbers
    if not re.match(r'^[A-Z0-9]+$', abbreviation):
        return ValidationResult(
            is_valid=False,
            message="LOB abbreviation can only contain uppercase letters and numbers"
        )
    
    return ValidationResult(
        is_valid=True,
        message="Valid LOB abbreviation"
    )

def validate_lob_data(data: Dict[str, Any]) -> ValidationResult:
    """
    Validate LOB data
    """
    issues = []
    
    # Validate LOB code
    code_result = validate_lob_code(data.get('lob_code', ''))
    if not code_result:
        issues.append(code_result.message)
    
    # Validate LOB name
    name_result = validate_lob_name(data.get('lob_name', ''))
    if not name_result:
        issues.append(name_result.message)
    
    # Validate LOB abbreviation
    abbreviation_result = validate_lob_abbreviation(data.get('lob_abbreviation', ''))
    if not abbreviation_result:
        issues.append(abbreviation_result.message)
    
    if issues:
        return ValidationResult(
            is_valid=False,
            message="LOB data validation failed",
            details={"issues": issues}
        )
    
    return ValidationResult(
        is_valid=True,
        message="Valid LOB data"
    )
# PRODUCT validation functions
def validate_product_code(lob_code: str) -> ValidationResult:
    """
    Validate LOB code format
    """
    if len(product_code) < 2 or len(product_code) > 20:
        return ValidationResult(
            is_valid=False,
            message="PRODUCT code must be between 2 and 20 characters long"
        )
    
    # Allow letters, numbers, hyphens, underscores
    if not re.match(r'^[A-Za-z0-9_-]+$', product_code):
        return ValidationResult(
            is_valid=False,
            message="PRODUCT code can only contain letters, numbers, hyphens, and underscores"
        )
    
    return ValidationResult(
        is_valid=True,
        message="Valid PRODUCT code"
    )

def validate_product_name(product_name: str) -> ValidationResult:
    """
    Validate PRODUCT name
    """
    if len(product_name) < 2 or len(product_name) > 100:
        return ValidationResult(
            is_valid=False,
            message="PRODUCT name must be between 2 and 100 characters long"
        )
    
    # Allow letters, numbers, spaces, hyphens, underscores
    if not re.match(r'^[a-zA-Z0-9\s_-]+$', product_name):
        return ValidationResult(
            is_valid=False,
            message="PRODUCT name can only contain letters, numbers, spaces, hyphens, and underscores"
        )
    
    return ValidationResult(
        is_valid=True,
        message="Valid PRODUCT name"
    )


def validate_product_data(data: Dict[str, Any]) -> ValidationResult:
    """
    Validate PRODUCT data
    """
    issues = []
    
    # Validate PRODUCT code
    code_result = validate_product_code(data.get('product_code', ''))
    if not code_result:
        issues.append(code_result.message)
    
    # Validate PRODUCT name
    name_result = validate_product_name(data.get('product_name', ''))
    if not name_result:
        issues.append(name_result.message)
        
    if issues:
        return ValidationResult(
            is_valid=False,
            message="PRODUCT data validation failed",
            details={"issues": issues}
        )
    
    return ValidationResult(
        is_valid=True,
        message="Valid PRODUCT data"
    )
# COMPANY validation functions
def validate_company_code(company_code: str) -> ValidationResult:
    """
    Validate COMPANY code format
    """
    if len(company_code) < 2 or len(company_code) > 20:
        return ValidationResult(
            is_valid=False,
            message="COMPANY code must be between 2 and 20 characters long"
        )
    
    # Allow letters, numbers, hyphens, underscores
    if not re.match(r'^[A-Za-z0-9_-]+$', company_code):
        return ValidationResult(
            is_valid=False,
            message="COMPANY code can only contain letters, numbers, hyphens, and underscores"
        )
    
    return ValidationResult(
        is_valid=True,
        message="Valid COMPANY code"
    )

def validate_company_name(company_name: str) -> ValidationResult:
    """
    Validate COMPANY name
    """
    if len(company_name) < 2 or len(company_name) > 100:
        return ValidationResult(
            is_valid=False,
            message="COMPANY name must be between 2 and 100 characters long"
        )
    
    # Allow letters, numbers, spaces, hyphens, underscores
    if not re.match(r'^[a-zA-Z0-9\s_-]+$', company_name):
        return ValidationResult(
            is_valid=False,
            message="COMPANY name can only contain letters, numbers, spaces, hyphens, and underscores"
        )
    
    return ValidationResult(
        is_valid=True,
        message="Valid COMPANY name"
    )


def validate_company_data(data: Dict[str, Any]) -> ValidationResult:
    """
    Validate COMPANY data
    """
    issues = []
    
    # Validate COMPANY code
    code_result = validate_company_code(data.get('company_code', ''))
    if not code_result:
        issues.append(code_result.message)
    
    # Validate COMPANY name
    name_result = validate_company_name(data.get('company_name', ''))
    if not name_result:
        issues.append(name_result.message)
        
    if issues:
        return ValidationResult(
            is_valid=False,
            message="COMPANY data validation failed",
            details={"issues": issues}
        )
    
    return ValidationResult(
        is_valid=True,
        message="Valid COMPANY data"
    )
# STATE validation functions
def validate_state_code(state_code: str) -> ValidationResult:
    """
    Validate STATE code format
    """
    if len(state_code) < 2 or len(state_code) > 20:
        return ValidationResult(
            is_valid=False,
            message="STATE code must be between 2 and 20 characters long"
        )
    
    # Allow letters, numbers, hyphens, underscores
    if not re.match(r'^[A-Za-z0-9_-]+$', state_code):
        return ValidationResult(
            is_valid=False,
            message="STATE code can only contain letters, numbers, hyphens, and underscores"
        )
    
    return ValidationResult(
        is_valid=True,
        message="Valid STATE code"
    )

def validate_state_name(state_name: str) -> ValidationResult:
    """
    Validate STATE name
    """
    if len(state_name) < 2 or len(state_name) > 100:
        return ValidationResult(
            is_valid=False,
            message="STATE name must be between 2 and 100 characters long"
        )
    
    # Allow letters, numbers, spaces, hyphens, underscores
    if not re.match(r'^[a-zA-Z0-9\s_-]+$', state_name):
        return ValidationResult(
            is_valid=False,
            message="STATE name can only contain letters, numbers, spaces, hyphens, and underscores"
        )
    
    return ValidationResult(
        is_valid=True,
        message="Valid STATE name"
    )


def validate_state_data(data: Dict[str, Any]) -> ValidationResult:
    """
    Validate STATE data
    """
    issues = []
    
    # Validate STATE code
    code_result = validate_state_code(data.get('state_code', ''))
    if not code_result:
        issues.append(code_result.message)
    
    # Validate STATE name
    name_result = validate_state_name(data.get('state_name', ''))
    if not name_result:
        issues.append(name_result.message)
        
    if issues:
        return ValidationResult(
            is_valid=False,
            message="STATE data validation failed",
            details={"issues": issues}
        )
    
    return ValidationResult(
        is_valid=True,
        message="Valid STATE data"
    )

# CONTEXT validation functions
def validate_context_code(context_code: str) -> ValidationResult:
    """
    Validate STATE code format
    """
    if len(context_code) < 2 or len(context_code) > 20:
        return ValidationResult(
            is_valid=False,
            message="STATE code must be between 2 and 20 characters long"
        )
    
    # Allow letters, numbers, hyphens, underscores
    if not re.match(r'^[A-Za-z0-9_-]+$', context_code):
        return ValidationResult(
            is_valid=False,
            message="CONTEXT code can only contain letters, numbers, hyphens, and underscores"
        )
    
    return ValidationResult(
        is_valid=True,
        message="Valid CONTEXT code"
    )

def validate_context_name(context_name: str) -> ValidationResult:
    """
    Validate STATE name
    """
    if len(context_name) < 2 or len(context_name) > 100:
        return ValidationResult(
            is_valid=False,
            message="CONTEXT name must be between 2 and 100 characters long"
        )
    
    # Allow letters, numbers, spaces, hyphens, underscores
    if not re.match(r'^[a-zA-Z0-9\s_-]+$', context_name):
        return ValidationResult(
            is_valid=False,
            message="CONTEXT name can only contain letters, numbers, spaces, hyphens, and underscores"
        )
    
    return ValidationResult(
        is_valid=True,
        message="Valid CONTEXT name"
    )


def validate_context_data(data: Dict[str, Any]) -> ValidationResult:
    """
    Validate CONTEXT data
    """
    issues = []
    
    # Validate CONTEXT code
    code_result = validate_context_code(data.get('context_code', ''))
    if not code_result:
        issues.append(code_result.message)
    
    # Validate CONTEXT name
    name_result = validate_context_name(data.get('context_name', ''))
    if not name_result:
        issues.append(name_result.message)
        
    if issues:
        return ValidationResult(
            is_valid=False,
            message="CONTEXT data validation failed",
            details={"issues": issues}
        )
    
    return ValidationResult(
        is_valid=True,
        message="Valid CONTEXT data"
    )