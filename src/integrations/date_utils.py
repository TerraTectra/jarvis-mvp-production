import re
from datetime import datetime, timedelta
from typing import Optional

def parse_kwork_date(raw_text: str) -> Optional[str]:
    """
    Parse date strings from Kwork into ISO format.
    
    Handles formats like:
    - "Сегодня" (Today)
    - "Вчера" (Yesterday)
    - "2 дня назад" (2 days ago)
    - "15.05.2025" (DD.MM.YYYY)
    
    Args:
        raw_text: Raw date string from Kwork
        
    Returns:
        str: Date in ISO format (YYYY-MM-DD) or None if parsing fails
    """
    if not raw_text or not isinstance(raw_text, str):
        return None
        
    raw_text = raw_text.strip().lower()
    today = datetime.now().date()
    
    try:
        # Handle "Сегодня" (Today)
        if raw_text == 'сегодня':
            return today.isoformat()
            
        # Handle "Вчера" (Yesterday)
        if raw_text == 'вчера':
            return (today - timedelta(days=1)).isoformat()
            
        # Handle "N дней/дня назад" (N days ago)
        days_ago_match = re.match(r'(\d+)\s+(день|дня|дней)\s+назад', raw_text)
        if days_ago_match:
            days = int(days_ago_match.group(1))
            return (today - timedelta(days=days)).isoformat()
            
        # Handle "DD.MM.YYYY" format
        date_match = re.match(r'(\d{1,2})\.(\d{1,2})\.(\d{2,4})', raw_text)
        if date_match:
            day = int(date_match.group(1))
            month = int(date_match.group(2))
            year = int(date_match.group(3))
            
            # Handle 2-digit years
            if year < 100:
                year += 2000 if year < 50 else 1900
                
            return f"{year:04d}-{month:02d}-{day:02d}"
            
        # Handle "HH:MM" (time only) - assume today
        time_match = re.match(r'(\d{1,2}):(\d{2})', raw_text)
        if time_match:
            return today.isoformat()
            
    except (ValueError, AttributeError) as e:
        pass
        
    return None
