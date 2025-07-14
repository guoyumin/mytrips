"""
Application-wide constants for MyTrips
"""
from typing import List, Set

# Email classification categories
TRAVEL_CATEGORIES: List[str] = [
    'flight', 
    'hotel', 
    'car_rental', 
    'train', 
    'cruise', 
    'tour', 
    'travel_insurance', 
    'flight_change', 
    'hotel_change', 
    'other_travel'
]

# Convert to set for faster lookup
TRAVEL_CATEGORIES_SET: Set[str] = set(TRAVEL_CATEGORIES)

# Non-travel categories
NON_TRAVEL_CATEGORIES: List[str] = [
    'marketing', 
    'not_travel', 
    'general_info',
    'insurance',
    'account_management',
    'restaurant_reservation',
    'security',
    'car_rental_change',
    'tour_change',
    'classification_failed'
]

# Convert to set for faster lookup
NON_TRAVEL_CATEGORIES_SET: Set[str] = set(NON_TRAVEL_CATEGORIES)

# All valid categories
ALL_CATEGORIES: List[str] = TRAVEL_CATEGORIES + NON_TRAVEL_CATEGORIES
ALL_CATEGORIES_SET: Set[str] = set(ALL_CATEGORIES)


def is_travel_category(category: str) -> bool:
    """
    Check if a category is travel-related
    
    Args:
        category: The category to check
        
    Returns:
        True if the category is travel-related, False otherwise
    """
    return category in TRAVEL_CATEGORIES_SET


def is_valid_category(category: str) -> bool:
    """
    Check if a category is valid (either travel or non-travel)
    
    Args:
        category: The category to check
        
    Returns:
        True if the category is valid, False otherwise
    """
    return category in ALL_CATEGORIES_SET


def get_category_type(category: str) -> str:
    """
    Get the type of category (travel, non_travel, or unknown)
    
    Args:
        category: The category to check
        
    Returns:
        'travel' if travel-related, 'non_travel' if non-travel, 'unknown' if invalid
    """
    if category in TRAVEL_CATEGORIES_SET:
        return 'travel'
    elif category in NON_TRAVEL_CATEGORIES_SET:
        return 'non_travel'
    else:
        return 'unknown'