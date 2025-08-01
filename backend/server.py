from fastapi import FastAPI, APIRouter, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional
import uuid
from datetime import datetime
import asyncio
import tempfile
import base64

# Import Gemini LLM Chat
from emergentintegrations.llm.chat import LlmChat, UserMessage

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Create the main app without a prefix
app = FastAPI()

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# Models
class MeetingCreate(BaseModel):
    title: str
    description: Optional[str] = None

class Meeting(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str
    description: Optional[str] = None
    audio_filename: Optional[str] = None
    transcription: Optional[str] = None
    summary: Optional[str] = None
    action_items: List[str] = Field(default_factory=list)
    key_decisions: List[str] = Field(default_factory=list)
    speakers: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    processed_at: Optional[datetime] = None

class StatusCheck(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    client_name: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class StatusCheckCreate(BaseModel):
    client_name: str

# Helper function to simulate transcription (since we don't have Whisper API)
async def simulate_transcription(audio_content: bytes, filename: str) -> str:
    """
    Simulate audio transcription. In production, this would use Whisper API.
    For now, return a sample transcription based on filename patterns.
    """
    # For demo purposes, return a realistic meeting transcript
    sample_transcripts = {
        'default': """Speaker 1: Good morning everyone, thanks for joining today's product planning meeting. Let's start by reviewing our quarterly goals.

Speaker 2: Thanks for organizing this. I wanted to discuss the new feature roadmap we've been working on. We have three major initiatives planned for Q2.

Speaker 1: Perfect. Can you walk us through each one?

Speaker 2: Absolutely. First, we're implementing the user authentication system with OAuth integration. This should be completed by March 15th. I'll be leading this effort with the engineering team.

Speaker 3: That sounds great. For the second initiative, we're focusing on the mobile app optimization. The current loading times are too slow, and we need to improve performance by at least 40%.

Speaker 1: Excellent point. What's the timeline for the mobile optimization?

Speaker 3: We're targeting April 30th for completion. This will require coordination between the mobile team and backend infrastructure team.

Speaker 2: The third initiative is expanding our API capabilities. We need to add webhook support and improve our rate limiting system. This is crucial for our enterprise customers.

Speaker 1: Great. Let's make sure we have clear action items. Sarah, can you own the OAuth implementation? Mike, you'll handle mobile optimization? And James, you'll lead the API expansion?

Speaker 2: Yes, I can take ownership of the OAuth system.

Speaker 3: Absolutely, I'll coordinate the mobile optimization efforts.

Speaker 4: I'll handle the API expansion project and work with the enterprise team on requirements.

Speaker 1: Perfect. Let's schedule a follow-up meeting for next Friday to check on progress. Any questions or concerns before we wrap up?

Speaker 2: Just one thing - we might need additional resources for the OAuth integration. Can we discuss budget in the follow-up?

Speaker 1: Absolutely. Let's add that to the agenda. Thanks everyone, great meeting!"""
    }
    
    # Add some delay to simulate processing
    await asyncio.sleep(2)
    return sample_transcripts.get('default', sample_transcripts['default'])

# Helper function to analyze meeting with Gemini
async def analyze_meeting_with_gemini(transcription: str) -> dict:
    """Analyze meeting transcription using Gemini AI"""
    try:
        # Initialize Gemini chat
        chat = LlmChat(
            api_key=os.environ.get('GEMINI_API_KEY'),
            session_id=f"meeting-analysis-{uuid.uuid4()}",
            system_message="You are an expert meeting analyst. Analyze meeting transcripts and extract key information in a structured format."
        ).with_model("gemini", "gemini-2.0-flash")

        # Create analysis prompt
        analysis_prompt = f"""
        Please analyze this meeting transcript and provide a structured analysis in the following format:

        EXECUTIVE SUMMARY:
        [2-3 sentence summary of the meeting]

        KEY DECISIONS:
        - [Decision 1]
        - [Decision 2]
        - [etc.]

        ACTION ITEMS:
        - [Action item 1 with assignee]
        - [Action item 2 with assignee]
        - [etc.]

        SPEAKERS IDENTIFIED:
        - [Speaker 1 name/role]
        - [Speaker 2 name/role]
        - [etc.]

        TIMELINE HIGHLIGHTS:
        - [Important moment 1]
        - [Important moment 2]
        - [etc.]

        Meeting Transcript:
        {transcription}
        """

        user_message = UserMessage(text=analysis_prompt)
        response = await chat.send_message(user_message)
        
        # Parse the response into structured data
        analysis_text = response
        
        # Extract sections using simple parsing
        summary = ""
        decisions = []
        action_items = []
        speakers = []
        
        lines = analysis_text.split('\n')
        current_section = None
        
        for line in lines:
            line = line.strip()
            if 'EXECUTIVE SUMMARY:' in line:
                current_section = 'summary'
                continue
            elif 'KEY DECISIONS:' in line:
                current_section = 'decisions'
                continue
            elif 'ACTION ITEMS:' in line:
                current_section = 'actions'
                continue
            elif 'SPEAKERS IDENTIFIED:' in line:
                current_section = 'speakers'
                continue
            elif 'TIMELINE HIGHLIGHTS:' in line:
                current_section = 'timeline'
                continue
            
            if line and current_section:
                if current_section == 'summary' and not line.startswith('-'):
                    summary += line + " "
                elif line.startswith('-'):
                    if current_section == 'decisions':
                        decisions.append(line[1:].strip())
                    elif current_section == 'actions':
                        action_items.append(line[1:].strip())
                    elif current_section == 'speakers':
                        speakers.append(line[1:].strip())
        
        return {
            'summary': summary.strip(),
            'key_decisions': decisions,
            'action_items': action_items,
            'speakers': speakers,
            'full_analysis': analysis_text
        }
        
    except Exception as e:
        logging.error(f"Error analyzing meeting with Gemini: {str(e)}")
        # Return fallback analysis
        return {
            'summary': "Meeting analysis unavailable due to processing error.",
            'key_decisions': ["Unable to extract decisions"],
            'action_items': ["Unable to extract action items"],
            'speakers': ["Speaker identification unavailable"],
            'full_analysis': f"Error: {str(e)}"
        }

# Routes
@api_router.get("/")
async def root():
    return {"message": "Meeting Summarizer API"}

@api_router.post("/meetings", response_model=Meeting)
async def create_meeting(meeting_data: MeetingCreate):
    """Create a new meeting"""
    meeting = Meeting(**meeting_data.dict())
    await db.meetings.insert_one(meeting.dict())
    return meeting

@api_router.get("/meetings", response_model=List[Meeting])
async def get_meetings():
    """Get all meetings"""
    meetings = await db.meetings.find().sort("created_at", -1).to_list(100)
    return [Meeting(**meeting) for meeting in meetings]

@api_router.get("/meetings/{meeting_id}", response_model=Meeting)
async def get_meeting(meeting_id: str):
    """Get a specific meeting"""
    meeting = await db.meetings.find_one({"id": meeting_id})
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    return Meeting(**meeting)

@api_router.post("/meetings/{meeting_id}/upload-audio")
async def upload_audio(meeting_id: str, audio_file: UploadFile = File(...)):
    """Upload audio file for a meeting and process it"""
    try:
        # Find the meeting
        meeting = await db.meetings.find_one({"id": meeting_id})
        if not meeting:
            raise HTTPException(status_code=404, detail="Meeting not found")
        
        # Read the audio file
        audio_content = await audio_file.read()
        
        # Store audio as base64 (for demo purposes)
        audio_base64 = base64.b64encode(audio_content).decode()
        
        # Simulate transcription
        transcription = await simulate_transcription(audio_content, audio_file.filename)
        
        # Analyze with Gemini
        analysis = await analyze_meeting_with_gemini(transcription)
        
        # Update meeting with results
        update_data = {
            "audio_filename": audio_file.filename,
            "transcription": transcription,
            "summary": analysis['summary'],
            "action_items": analysis['action_items'],
            "key_decisions": analysis['key_decisions'],
            "speakers": analysis['speakers'],
            "processed_at": datetime.utcnow()
        }
        
        await db.meetings.update_one(
            {"id": meeting_id},
            {"$set": update_data}
        )
        
        # Return updated meeting
        updated_meeting = await db.meetings.find_one({"id": meeting_id})
        return Meeting(**updated_meeting)
        
    except HTTPException:
        # Re-raise HTTP exceptions (like 404) without modification
        raise
    except Exception as e:
        logging.error(f"Error processing audio: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error processing audio: {str(e)}")

@api_router.delete("/meetings/{meeting_id}")
async def delete_meeting(meeting_id: str):
    """Delete a meeting"""
    result = await db.meetings.delete_one({"id": meeting_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Meeting not found")
    return {"message": "Meeting deleted successfully"}

# Legacy routes for compatibility
@api_router.post("/status", response_model=StatusCheck)
async def create_status_check(input: StatusCheckCreate):
    status_dict = input.dict()
    status_obj = StatusCheck(**status_dict)
    _ = await db.status_checks.insert_one(status_obj.dict())
    return status_obj

@api_router.get("/status", response_model=List[StatusCheck])
async def get_status_checks():
    status_checks = await db.status_checks.find().to_list(1000)
    return [StatusCheck(**status_check) for status_check in status_checks]

# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()