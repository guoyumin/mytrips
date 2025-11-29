import sqlite3
import json

def check_recent_emails():
    try:
        conn = sqlite3.connect('data/mytrips.db')
        cursor = conn.cursor()
        
        # Get the 5 most recent emails
        cursor.execute("""
            SELECT id, email_id, subject, labels, created_at 
            FROM emails 
            ORDER BY id DESC 
            LIMIT 5
        """)
        
        emails = cursor.fetchall()
        
        print(f"Found {len(emails)} recent emails:")
        print("-" * 120)
        print(f"{'ID':<5} | {'Email ID':<20} | {'Created At':<25} | {'Labels':<20} | {'Subject':<40}")
        print("-" * 120)
        
        for email in emails:
            id, email_id, subject, labels, created_at = email
            subject_display = (subject[:37] + '...') if subject and len(subject) > 37 else subject
            labels_display = labels if labels else "None"
            print(f"{id:<5} | {email_id:<20} | {created_at:<25} | {labels_display:<20} | {subject_display:<40}")
            
        conn.close()
        
    except Exception as e:
        print(f"Error checking database: {e}")

if __name__ == "__main__":
    check_recent_emails()
