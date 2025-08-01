#!/usr/bin/env python3
"""
Backend API Testing for AI Meeting Summarizer
Tests all CRUD operations, audio upload, and AI integration
"""

import requests
import json
import os
import tempfile
import time
from datetime import datetime
from pathlib import Path

# Load environment variables
from dotenv import load_dotenv
load_dotenv('/app/frontend/.env')

# Get backend URL from frontend environment
BACKEND_URL = os.environ.get('REACT_APP_BACKEND_URL', 'http://localhost:8001')
API_BASE = f"{BACKEND_URL}/api"

print(f"Testing backend at: {API_BASE}")

class MeetingSummarizerTester:
    def __init__(self):
        self.session = requests.Session()
        self.created_meeting_ids = []
        
    def test_api_health(self):
        """Test if the API is responding"""
        print("\n=== Testing API Health ===")
        try:
            response = self.session.get(f"{API_BASE}/")
            print(f"Status Code: {response.status_code}")
            print(f"Response: {response.json()}")
            return response.status_code == 200
        except Exception as e:
            print(f"API Health Check Failed: {e}")
            return False
    
    def test_create_meeting(self):
        """Test creating a new meeting"""
        print("\n=== Testing Create Meeting ===")
        try:
            meeting_data = {
                "title": "Product Planning Meeting",
                "description": "Q2 planning session for new features and roadmap"
            }
            
            response = self.session.post(
                f"{API_BASE}/meetings",
                json=meeting_data,
                headers={"Content-Type": "application/json"}
            )
            
            print(f"Status Code: {response.status_code}")
            print(f"Response: {response.json()}")
            
            if response.status_code == 200:
                meeting = response.json()
                self.created_meeting_ids.append(meeting['id'])
                print(f"✅ Meeting created successfully with ID: {meeting['id']}")
                return meeting
            else:
                print(f"❌ Failed to create meeting")
                return None
                
        except Exception as e:
            print(f"❌ Create meeting test failed: {e}")
            return None
    
    def test_get_meetings(self):
        """Test getting all meetings"""
        print("\n=== Testing Get All Meetings ===")
        try:
            response = self.session.get(f"{API_BASE}/meetings")
            print(f"Status Code: {response.status_code}")
            
            if response.status_code == 200:
                meetings = response.json()
                print(f"✅ Retrieved {len(meetings)} meetings")
                for meeting in meetings[:3]:  # Show first 3
                    print(f"  - {meeting['title']} (ID: {meeting['id']})")
                return meetings
            else:
                print(f"❌ Failed to get meetings: {response.text}")
                return None
                
        except Exception as e:
            print(f"❌ Get meetings test failed: {e}")
            return None
    
    def test_get_single_meeting(self, meeting_id):
        """Test getting a specific meeting"""
        print(f"\n=== Testing Get Single Meeting (ID: {meeting_id}) ===")
        try:
            response = self.session.get(f"{API_BASE}/meetings/{meeting_id}")
            print(f"Status Code: {response.status_code}")
            
            if response.status_code == 200:
                meeting = response.json()
                print(f"✅ Retrieved meeting: {meeting['title']}")
                print(f"  Description: {meeting['description']}")
                print(f"  Created: {meeting['created_at']}")
                return meeting
            else:
                print(f"❌ Failed to get meeting: {response.text}")
                return None
                
        except Exception as e:
            print(f"❌ Get single meeting test failed: {e}")
            return None
    
    def test_get_nonexistent_meeting(self):
        """Test getting a meeting that doesn't exist"""
        print("\n=== Testing Get Non-existent Meeting ===")
        try:
            fake_id = "non-existent-meeting-id"
            response = self.session.get(f"{API_BASE}/meetings/{fake_id}")
            print(f"Status Code: {response.status_code}")
            
            if response.status_code == 404:
                print("✅ Correctly returned 404 for non-existent meeting")
                return True
            else:
                print(f"❌ Expected 404, got {response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ Non-existent meeting test failed: {e}")
            return False
    
    def create_test_audio_file(self):
        """Create a small test audio file for upload testing"""
        # Create a small WAV file (just header + minimal data)
        wav_header = b'RIFF\x24\x08\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00\x44\xac\x00\x00\x88X\x01\x00\x02\x00\x10\x00data\x00\x08\x00\x00'
        wav_data = b'\x00\x00' * 1000  # 1000 samples of silence
        
        temp_file = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
        temp_file.write(wav_header + wav_data)
        temp_file.close()
        
        return temp_file.name
    
    def test_audio_upload(self, meeting_id):
        """Test uploading audio file to a meeting"""
        print(f"\n=== Testing Audio Upload (Meeting ID: {meeting_id}) ===")
        try:
            # Create test audio file
            audio_file_path = self.create_test_audio_file()
            
            with open(audio_file_path, 'rb') as audio_file:
                files = {
                    'audio_file': ('test_meeting.wav', audio_file, 'audio/wav')
                }
                
                print("Uploading audio file and processing with AI...")
                response = self.session.post(
                    f"{API_BASE}/meetings/{meeting_id}/upload-audio",
                    files=files
                )
            
            # Clean up temp file
            os.unlink(audio_file_path)
            
            print(f"Status Code: {response.status_code}")
            
            if response.status_code == 200:
                meeting = response.json()
                print("✅ Audio uploaded and processed successfully!")
                print(f"  Audio filename: {meeting.get('audio_filename')}")
                print(f"  Transcription length: {len(meeting.get('transcription', ''))}")
                print(f"  Summary: {meeting.get('summary', 'N/A')[:100]}...")
                print(f"  Action items: {len(meeting.get('action_items', []))}")
                print(f"  Key decisions: {len(meeting.get('key_decisions', []))}")
                print(f"  Speakers: {meeting.get('speakers', [])}")
                print(f"  Processed at: {meeting.get('processed_at')}")
                return meeting
            else:
                print(f"❌ Audio upload failed: {response.text}")
                return None
                
        except Exception as e:
            print(f"❌ Audio upload test failed: {e}")
            return None
    
    def test_audio_upload_invalid_meeting(self):
        """Test uploading audio to non-existent meeting"""
        print("\n=== Testing Audio Upload to Invalid Meeting ===")
        try:
            audio_file_path = self.create_test_audio_file()
            
            with open(audio_file_path, 'rb') as audio_file:
                files = {
                    'audio_file': ('test_meeting.wav', audio_file, 'audio/wav')
                }
                
                response = self.session.post(
                    f"{API_BASE}/meetings/invalid-meeting-id/upload-audio",
                    files=files
                )
            
            os.unlink(audio_file_path)
            
            print(f"Status Code: {response.status_code}")
            
            if response.status_code == 404:
                print("✅ Correctly returned 404 for invalid meeting ID")
                return True
            else:
                print(f"❌ Expected 404, got {response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ Invalid meeting audio upload test failed: {e}")
            return False
    
    def test_delete_meeting(self, meeting_id):
        """Test deleting a meeting"""
        print(f"\n=== Testing Delete Meeting (ID: {meeting_id}) ===")
        try:
            response = self.session.delete(f"{API_BASE}/meetings/{meeting_id}")
            print(f"Status Code: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                print(f"✅ Meeting deleted successfully: {result['message']}")
                return True
            else:
                print(f"❌ Failed to delete meeting: {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ Delete meeting test failed: {e}")
            return False
    
    def test_delete_nonexistent_meeting(self):
        """Test deleting a meeting that doesn't exist"""
        print("\n=== Testing Delete Non-existent Meeting ===")
        try:
            fake_id = "non-existent-meeting-id"
            response = self.session.delete(f"{API_BASE}/meetings/{fake_id}")
            print(f"Status Code: {response.status_code}")
            
            if response.status_code == 404:
                print("✅ Correctly returned 404 for non-existent meeting")
                return True
            else:
                print(f"❌ Expected 404, got {response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ Delete non-existent meeting test failed: {e}")
            return False
    
    def run_comprehensive_test(self):
        """Run all tests in sequence"""
        print("🚀 Starting Comprehensive Backend API Testing")
        print("=" * 60)
        
        results = {}
        
        # Test 1: API Health
        results['api_health'] = self.test_api_health()
        
        # Test 2: Create Meeting
        meeting = self.test_create_meeting()
        results['create_meeting'] = meeting is not None
        
        if not meeting:
            print("❌ Cannot continue tests without a valid meeting")
            return results
        
        meeting_id = meeting['id']
        
        # Test 3: Get All Meetings
        results['get_meetings'] = self.test_get_meetings() is not None
        
        # Test 4: Get Single Meeting
        results['get_single_meeting'] = self.test_get_single_meeting(meeting_id) is not None
        
        # Test 5: Get Non-existent Meeting
        results['get_nonexistent_meeting'] = self.test_get_nonexistent_meeting()
        
        # Test 6: Audio Upload and AI Processing
        processed_meeting = self.test_audio_upload(meeting_id)
        results['audio_upload'] = processed_meeting is not None
        
        # Test 7: Audio Upload to Invalid Meeting
        results['audio_upload_invalid'] = self.test_audio_upload_invalid_meeting()
        
        # Test 8: Delete Meeting
        results['delete_meeting'] = self.test_delete_meeting(meeting_id)
        
        # Test 9: Delete Non-existent Meeting
        results['delete_nonexistent'] = self.test_delete_nonexistent_meeting()
        
        # Summary
        print("\n" + "=" * 60)
        print("🏁 TEST RESULTS SUMMARY")
        print("=" * 60)
        
        passed = 0
        total = len(results)
        
        for test_name, passed_test in results.items():
            status = "✅ PASS" if passed_test else "❌ FAIL"
            print(f"{test_name.replace('_', ' ').title()}: {status}")
            if passed_test:
                passed += 1
        
        print(f"\nOverall: {passed}/{total} tests passed ({passed/total*100:.1f}%)")
        
        if passed == total:
            print("🎉 All tests passed! Backend API is working correctly.")
        else:
            print("⚠️  Some tests failed. Check the detailed output above.")
        
        return results

def main():
    """Main test execution"""
    tester = MeetingSummarizerTester()
    results = tester.run_comprehensive_test()
    
    # Return exit code based on results
    all_passed = all(results.values())
    return 0 if all_passed else 1

if __name__ == "__main__":
    exit(main())