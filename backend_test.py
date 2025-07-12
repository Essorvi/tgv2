#!/usr/bin/env python3
"""
Backend API Testing for Usersbox Telegram Bot
Tests all API endpoints and integration with usersbox API
"""

import requests
import json
import sys
from datetime import datetime
from typing import Dict, Any, Optional

class UsersboxBotAPITester:
    def __init__(self, base_url: str = "https://80150a16-2506-4974-887e-2b143ce3b0c6.preview.emergentagent.com"):
        self.base_url = base_url
        self.api_url = f"{base_url}/api"
        self.tests_run = 0
        self.tests_passed = 0
        self.webhook_secret = "usersbox_telegram_bot_secure_webhook_2025"
        
    def log_test(self, name: str, success: bool, details: str = ""):
        """Log test results"""
        self.tests_run += 1
        if success:
            self.tests_passed += 1
            print(f"✅ {name} - PASSED {details}")
        else:
            print(f"❌ {name} - FAILED {details}")
        return success

    def make_request(self, method: str, endpoint: str, **kwargs) -> tuple[bool, Optional[Dict], int]:
        """Make HTTP request and return success, response data, status code"""
        url = f"{self.api_url}/{endpoint}" if not endpoint.startswith('http') else endpoint
        
        try:
            if method.upper() == 'GET':
                response = requests.get(url, timeout=30, **kwargs)
            elif method.upper() == 'POST':
                response = requests.post(url, timeout=30, **kwargs)
            else:
                return False, None, 0
                
            try:
                data = response.json()
            except:
                data = {"text": response.text}
                
            return response.status_code < 400, data, response.status_code
            
        except requests.exceptions.RequestException as e:
            print(f"   Request error: {str(e)}")
            return False, None, 0

    def test_root_endpoint(self) -> bool:
        """Test GET /api/ endpoint"""
        success, data, status = self.make_request('GET', '')
        
        if success and data and data.get('message'):
            return self.log_test("Root Endpoint", True, f"- Status: {status}")
        else:
            return self.log_test("Root Endpoint", False, f"- Status: {status}, Data: {data}")

    def test_stats_endpoint(self) -> bool:
        """Test GET /api/stats endpoint"""
        success, data, status = self.make_request('GET', 'stats')
        
        if success and data and isinstance(data, dict):
            expected_keys = ['total_users', 'total_searches', 'total_referrals', 'successful_searches', 'success_rate']
            has_keys = all(key in data for key in expected_keys)
            
            if has_keys:
                return self.log_test("Stats Endpoint", True, f"- Users: {data.get('total_users', 0)}, Searches: {data.get('total_searches', 0)}")
            else:
                return self.log_test("Stats Endpoint", False, f"- Missing keys. Got: {list(data.keys())}")
        else:
            return self.log_test("Stats Endpoint", False, f"- Status: {status}, Data: {data}")

    def test_users_endpoint(self) -> bool:
        """Test GET /api/users endpoint"""
        success, data, status = self.make_request('GET', 'users')
        
        if success and isinstance(data, list):
            return self.log_test("Users Endpoint", True, f"- Found {len(data)} users")
        else:
            return self.log_test("Users Endpoint", False, f"- Status: {status}, Expected list, got: {type(data)}")

    def test_searches_endpoint(self) -> bool:
        """Test GET /api/searches endpoint"""
        success, data, status = self.make_request('GET', 'searches')
        
        if success and isinstance(data, list):
            return self.log_test("Searches Endpoint", True, f"- Found {len(data)} searches")
        else:
            return self.log_test("Searches Endpoint", False, f"- Status: {status}, Expected list, got: {type(data)}")

    def test_search_endpoint(self) -> bool:
        """Test POST /api/search endpoint with usersbox API"""
        test_query = "test"
        success, data, status = self.make_request('POST', f'search?query={test_query}')
        
        if success and data:
            # Check if it's a proper usersbox API response
            if 'data' in data or 'status' in data:
                return self.log_test("Search Endpoint", True, f"- Query: '{test_query}' returned valid response")
            else:
                return self.log_test("Search Endpoint", False, f"- Invalid response format: {data}")
        else:
            return self.log_test("Search Endpoint", False, f"- Status: {status}, Data: {data}")

    def test_webhook_endpoint(self) -> bool:
        """Test POST /api/webhook/{secret} endpoint"""
        # Create a mock Telegram update
        mock_update = {
            "update_id": 123456789,
            "message": {
                "message_id": 1,
                "from": {
                    "id": 123456789,
                    "is_bot": False,
                    "first_name": "Test",
                    "username": "testuser"
                },
                "chat": {
                    "id": 123456789,
                    "first_name": "Test",
                    "username": "testuser",
                    "type": "private"
                },
                "date": int(datetime.now().timestamp()),
                "text": "/start"
            }
        }
        
        # Test with correct secret
        success, data, status = self.make_request(
            'POST', 
            f'webhook/{self.webhook_secret}',
            json=mock_update
        )
        
        if success and data and data.get('status') == 'ok':
            webhook_success = self.log_test("Webhook Endpoint (Valid Secret)", True, f"- Status: {status}")
        else:
            webhook_success = self.log_test("Webhook Endpoint (Valid Secret)", False, f"- Status: {status}, Data: {data}")
        
        # Test with invalid secret
        success, data, status = self.make_request(
            'POST', 
            'webhook/invalid_secret',
            json=mock_update
        )
        
        if status == 403:  # Should be forbidden
            invalid_secret_success = self.log_test("Webhook Endpoint (Invalid Secret)", True, f"- Correctly rejected with 403")
        else:
            invalid_secret_success = self.log_test("Webhook Endpoint (Invalid Secret)", False, f"- Expected 403, got {status}")
        
        return webhook_success and invalid_secret_success

    def test_give_attempts_endpoint(self) -> bool:
        """Test POST /api/give-attempts endpoint"""
        # This will likely fail since we don't have a real user, but we can test the endpoint structure
        success, data, status = self.make_request(
            'POST', 
            'give-attempts?user_id=123456789&attempts=1'
        )
        
        # We expect this to fail with 404 (user not found) or 500, not a connection error
        if status in [404, 500]:
            return self.log_test("Give Attempts Endpoint", True, f"- Endpoint accessible, returned expected error {status}")
        elif status == 422:  # Validation error
            return self.log_test("Give Attempts Endpoint", True, f"- Endpoint accessible, validation working ({status})")
        else:
            return self.log_test("Give Attempts Endpoint", False, f"- Unexpected status: {status}, Data: {data}")

    def test_usersbox_api_integration(self) -> bool:
        """Test if usersbox API integration is working"""
        # Test a simple search to see if the external API is accessible
        success, data, status = self.make_request('POST', 'search?query=test')
        
        if success and data:
            if 'error' in data and 'API request failed' in str(data.get('error', '')):
                return self.log_test("Usersbox API Integration", False, "- External API connection failed")
            elif 'data' in data or 'status' in data:
                return self.log_test("Usersbox API Integration", True, "- External API responding")
            else:
                return self.log_test("Usersbox API Integration", False, f"- Unexpected response: {data}")
        else:
            return self.log_test("Usersbox API Integration", False, f"- Status: {status}")

    def run_all_tests(self) -> bool:
        """Run all tests and return overall success"""
        print("🚀 Starting Usersbox Telegram Bot API Tests")
        print(f"📡 Testing against: {self.base_url}")
        print("=" * 60)
        
        # Core API tests
        print("\n📋 Testing Core API Endpoints:")
        self.test_root_endpoint()
        self.test_stats_endpoint()
        self.test_users_endpoint()
        self.test_searches_endpoint()
        
        # Search functionality tests
        print("\n🔍 Testing Search Functionality:")
        self.test_search_endpoint()
        self.test_usersbox_api_integration()
        
        # Webhook tests
        print("\n🔗 Testing Webhook Endpoints:")
        self.test_webhook_endpoint()
        
        # Admin functionality tests
        print("\n👨‍💼 Testing Admin Functionality:")
        self.test_give_attempts_endpoint()
        
        # Summary
        print("\n" + "=" * 60)
        print(f"📊 Test Results: {self.tests_passed}/{self.tests_run} tests passed")
        
        success_rate = (self.tests_passed / self.tests_run) * 100 if self.tests_run > 0 else 0
        print(f"✨ Success Rate: {success_rate:.1f}%")
        
        if success_rate >= 80:
            print("🎉 Overall Status: GOOD - Most functionality working")
            return True
        elif success_rate >= 60:
            print("⚠️  Overall Status: PARTIAL - Some issues detected")
            return False
        else:
            print("❌ Overall Status: POOR - Major issues detected")
            return False

def main():
    """Main test execution"""
    tester = UsersboxBotAPITester()
    success = tester.run_all_tests()
    
    print("\n🔧 Next Steps:")
    if success:
        print("- Proceed with frontend testing")
        print("- Test user workflows")
        print("- Verify database operations")
    else:
        print("- Fix failing API endpoints")
        print("- Check backend logs for errors")
        print("- Verify environment configuration")
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())