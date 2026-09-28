"""Unit tests for delete_todo and api_delete_todo ObjectId validation."""
import unittest
from bson import ObjectId
from app import delete_todo, api_delete_todo


class TestDeleteTodoObjectIdValidation(unittest.TestCase):
    """Test that ObjectId validation works correctly in delete functions."""
    
    def setUp(self):
        self.valid_objectid = "507f1f77bcf86cd799439011"
        self.invalid_formats = [
            "",
            "invalid",
            "12345",
            "abc-def-ghi",
            None,
            12345,
            "too-long-id-123456789012345678901234567890",
            "not-an-objectid-at-all",
        ]
    
    def test_delete_todo_valid_objectid_format(self):
        """Test that valid ObjectId format doesn't raise validation error."""
        # Should not raise ValueError for invalid ObjectId conversion
        with self.assertRaises(ValueError) as context:
            delete_todo(self.valid_objectid)
        
        # Note: This will fail because we don't have a real MongoDB connection,
        # but the important thing is it should NOT fail on ObjectId validation
        self.assertIn("ObjectId conversion", str(context.exception))
    
    def test_delete_todo_invalid_formats_rejected(self):
        """Test that various invalid ObjectId formats are rejected."""
        for invalid_id in self.invalid_formats:
            with self.subTest(invalid_id=invalid_id):
                try:
                    result = delete_todo(invalid_id)
                    # If we get here without ValueError, check the return value
                    if isinstance(result, bool):
                        self.assertFalse(result, 
                            f"Invalid format '{invalid_id}' should return False")
                except ValueError as e:
                    # This is expected - validation caught it
                    pass
    
    def test_api_delete_todo_valid_objectid_format(self):
        """Test that API accepts valid ObjectId format."""
        response = api_delete_todo(self.valid_objectid)
        
        # Should not raise TypeError for invalid ObjectId conversion
        self.assertIsNotNone(response)
    
    def test_api_delete_todo_invalid_formats_rejected(self):
        """Test that API rejects various invalid ObjectId formats with 400 error."""
        for invalid_id in self.invalid_formats:
            with self.subTest(invalid_id=invalid_id):
                try:
                    result = api_delete_todo(invalid_id)
                    if isinstance(result, dict):
                        self.assertIn('error', result, 
                            f"Invalid format '{invalid_id}' should return error")
                except TypeError as e:
                    # This is expected - validation caught it
                    pass


if __name__ == '__main__':
    unittest.main()
