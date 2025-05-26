import pandas as pd
from datetime import datetime
from models import BadgeAccess
import os
from sqlalchemy.exc import IntegrityError

ALLOWED_EXTENSIONS = {'csv'}
REQUIRED_COLUMNS = ['SiteName', 'GlobalId', 'Initial Login Date', 'Badge ID']

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def validate_date_format(date_str):
    try:
        datetime.strptime(date_str, '%Y-%m-%d')
        return True
    except ValueError:
        return False

def validate_csv(filepath):
    try:
        # Read CSV file
        df = pd.read_csv(filepath)
        
        # Check for required columns
        missing_columns = set(REQUIRED_COLUMNS) - set(df.columns)
        if missing_columns:
            return {
                'valid': False,
                'error': f'Missing required columns: {", ".join(missing_columns)}'
            }
        
        # Validate date format
        invalid_dates = []
        for date in df['Initial Login Date']:
            if not validate_date_format(str(date)):
                invalid_dates.append(str(date))
        
        if invalid_dates:
            return {
                'valid': False,
                'error': f'Invalid date format found. Dates must be in YYYY-MM-DD format. Invalid dates: {", ".join(invalid_dates)}'
            }
        
        # Check for duplicate (GID, Login Date) pairs
        duplicates = df.duplicated(subset=['GlobalId', 'Initial Login Date'])
        if duplicates.any():
            duplicate_rows = df[duplicates].index.tolist()
            return {
                'valid': False,
                'error': f'Duplicate (GlobalId, Initial Login Date) pairs found in rows: {", ".join(map(str, duplicate_rows))}'
            }
        
        return {'valid': True}
    
    except Exception as e:
        return {
            'valid': False,
            'error': f'Error processing CSV file: {str(e)}'
        }

def process_csv(filepath, db_session):
    df = pd.read_csv(filepath)
    
    for _, row in df.iterrows():
        try:
            badge_access = BadgeAccess(
                site_name=row['SiteName'],
                global_id=row['GlobalId'],
                initial_login_date=datetime.strptime(str(row['Initial Login Date']), '%Y-%m-%d').date(),
                badge_id=str(row['Badge ID'])
            )
            db_session.add(badge_access)
            db_session.commit()
        except IntegrityError:
            # Roll back the failed transaction
            db_session.rollback()
            # Skip duplicate entries (due to unique constraint)
            continue
        except Exception as e:
            db_session.rollback()
            raise Exception(f'Error processing row: {row.to_dict()}, Error: {str(e)}')