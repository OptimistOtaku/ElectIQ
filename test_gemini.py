import os, time
from datetime import datetime, timezone, timedelta
from google import genai
from google.genai import types

ist = timezone(timedelta(hours=5, minutes=30))
today = datetime.now(ist).strftime('%d %B %Y, %I:%M %p IST')
prompt = f"""Today is {today}.
Search for the latest information on Indian state and national elections.
Return ONLY a valid JSON object (no markdown, no explanation) with this exact structure:
{{
  "current": [
    {{
      "state": "State name in English",
      "state_hi": "State name in Hindi (Devanagari)",
      "election_type": "Assembly" | "Lok Sabha" | "By-election" | "Panchayat",
      "status": "voting_today" | "voting_soon" | "counting" | "results_out",
      "status_label": "Short human-readable status in English",
      "polling_date": "DD Month YYYY or 'Phase 1: DD Mon, Phase 2: DD Mon'",
      "counting_date": "DD Month YYYY",
      "total_seats": 123,
      "phases": 1,
      "note": "Brief context e.g. 'Phase 2 of 3' or 'Results declared'"
    }}
  ],
  "upcoming": [
    {{
      "state": "State name in English",
      "state_hi": "State name in Hindi (Devanagari)",
      "election_type": "Assembly" | "Lok Sabha" | "By-election",
      "expected_period": "Month–Month YYYY",
      "total_seats": 123,
      "note": "Brief context"
    }}
  ],
  "next_major_event": {{
    "name": "Name of the very next election event from today, specifying state and phase (e.g., 'West Bengal Phase 2 Polling' or 'Bihar Vote Counting')",
    "name_hi": "Same event name in Hindi",
    "date_iso": "YYYY-MM-DDTHH:MM:SS+05:30"
  }}
}}
IMPORTANT RULES:
- "current" = elections where ANY phase (notification, nomination, polling, counting) is happening within 30 days before or after today ({today}).
- "upcoming" = elections expected in the next 12 months that haven't started yet.
- next_major_event must be the chronologically NEXT event AFTER today {today}. Ensure the event specifies the state.
- All dates must be EXACT dates from ECI announcements, not approximate.
- Do NOT include elections whose results were declared more than 30 days ago.
- Return ONLY the JSON object, nothing else."""

client = genai.Client()
response = client.models.generate_content(
    model='gemini-2.5-flash',
    contents=prompt,
    config=types.GenerateContentConfig(
        max_output_tokens=2048,
        temperature=0.1,
        tools=[types.Tool(google_search=types.GoogleSearch())],
    )
)
print(response.text)
