import os
import requests
import logging
import psycopg2
from psycopg2.extras import RealDictCursor
import google.cloud.logging
from dotenv import load_dotenv
from google.adk.agents import Agent, SequentialAgent
from google.adk.tools.tool_context import ToolContext

load_dotenv()

model_name = os.getenv("MODEL")
news_api_key = os.getenv("NEWS_API_KEY")

try:
    cloud_logging_client = google.cloud.logging.Client(
        project=os.getenv("PROJECT_ID")
    )
    cloud_logging_client.setup_logging()
except Exception:
    logging.basicConfig(level=logging.INFO)


# --- DB Connection ---

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv("ALLOYDB_HOST"),
        port=os.getenv("ALLOYDB_PORT"),
        dbname=os.getenv("ALLOYDB_DATABASE"),
        user=os.getenv("ALLOYDB_USER"),
        password=os.getenv("ALLOYDB_PASSWORD")
    )


# --- Tools ---

def save_business_profile(
    tool_context: ToolContext,
    business_type: str,
    city: str,
    bestsellers: str,
    daily_customers: str,
    biggest_challenge: str,
    monthly_revenue: str,
) -> dict:
    """Saves collected business profile to AlloyDB and state."""
    tool_context.state["business_type"] = business_type
    tool_context.state["city"] = city
    tool_context.state["bestsellers"] = bestsellers
    tool_context.state["daily_customers"] = daily_customers
    tool_context.state["biggest_challenge"] = biggest_challenge
    tool_context.state["monthly_revenue"] = monthly_revenue

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO businesses
            (business_type, city, bestsellers,
             daily_customers, biggest_challenge, monthly_revenue)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING business_id
        """, (business_type, city, bestsellers,
              daily_customers, biggest_challenge, monthly_revenue))
        business_id = str(cur.fetchone()[0])
        conn.commit()
        conn.close()
        tool_context.state["business_id"] = business_id
        logging.info(f"[BizPulse] Profile saved to AlloyDB: {business_id}")
        return {"status": "profile_saved", "business_id": business_id}
    except Exception as e:
        logging.error(f"[BizPulse] DB save error: {e}")
        return {"status": "profile_saved_memory_only", "error": str(e)}


def get_business_news(business_type: str, city: str) -> dict:
    """Fetches live market news for a business type and city in India."""
    try:
        r = requests.get(
            "https://newsapi.org/v2/everything",
            params={
                "q": f"{business_type} business India {city}",
                "apiKey": news_api_key,
                "pageSize": 7,
                "language": "en",
                "sortBy": "publishedAt"
            },
            timeout=10
        )
        data = r.json()
        if data.get("status") != "ok":
            return {"error": "failed", "details": data}
        articles = [
            {
                "title": a.get("title"),
                "description": a.get("description"),
                "source": a.get("source", {}).get("name")
            }
            for a in data.get("articles", [])
        ]
        logging.info(f"[BizPulse] Fetched {len(articles)} news articles")
        return {"status": "success", "articles": articles}
    except Exception as e:
        logging.error(f"[BizPulse] News fetch error: {e}")
        return {"error": str(e)}


def get_competitor_intelligence(business_type: str, city: str) -> dict:
    """Fetches competitor activity and market signals for a business type in a city."""
    try:
        r = requests.get(
            "https://newsapi.org/v2/everything",
            params={
                "q": f"{business_type} opening closing {city} India 2026",
                "apiKey": news_api_key,
                "pageSize": 5,
                "language": "en",
                "sortBy": "publishedAt"
            },
            timeout=10
        )
        data = r.json()
        if data.get("status") != "ok":
            return {"error": "failed"}
        signals = [
            {
                "title": a.get("title"),
                "description": a.get("description"),
                "source": a.get("source", {}).get("name")
            }
            for a in data.get("articles", [])
        ]
        logging.info(f"[BizPulse] Fetched {len(signals)} competitor signals")
        return {"status": "success", "signals": signals}
    except Exception as e:
        logging.error(f"[BizPulse] Competitor fetch error: {e}")
        return {"error": str(e)}


def save_briefing_and_actions(
    tool_context: ToolContext,
    briefing_text: str,
    alert_level: str,
    action_this_week: str,
) -> dict:
    """Saves the final briefing and action item to AlloyDB."""
    business_id = tool_context.state.get("business_id")
    results = {}
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO briefings (business_id, alert_level, briefing_text)
            VALUES (%s, %s, %s)
            RETURNING briefing_id
        """, (business_id, alert_level, briefing_text))
        briefing_id = str(cur.fetchone()[0])
        results["briefing_id"] = briefing_id

        cur.execute("""
            INSERT INTO actions (business_id, action_text, source, status)
            VALUES (%s, %s, %s, %s)
            RETURNING action_id
        """, (business_id, action_this_week, "bizpulse_agent", "pending"))
        action_id = str(cur.fetchone()[0])
        results["action_id"] = action_id

        conn.commit()
        conn.close()
        tool_context.state["briefing_id"] = briefing_id
        tool_context.state["action_this_week"] = action_this_week
        logging.info(f"[BizPulse] Briefing + action saved: {briefing_id}")
        results["status"] = "saved"
        return results
    except Exception as e:
        logging.error(f"[BizPulse] Save briefing error: {e}")
        return {"status": "error", "error": str(e)}


def get_past_briefings(tool_context: ToolContext) -> dict:
    """Fetches past briefings for this business from AlloyDB."""
    business_type = tool_context.state.get("business_type", "")
    city = tool_context.state.get("city", "")
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            SELECT b.alert_level, b.briefing_text, b.created_at
            FROM briefings b
            JOIN businesses biz ON b.business_id = biz.business_id
            WHERE biz.business_type = %s AND biz.city = %s
            ORDER BY b.created_at DESC
            LIMIT 2
        """, (business_type, city))
        past = cur.fetchall()
        conn.close()
        if past:
            return {"status": "found", "past_briefings": [dict(r) for r in past]}
        return {"status": "no_history"}
    except Exception as e:
        logging.error(f"[BizPulse] Past briefings error: {e}")
        return {"status": "error", "error": str(e)}


# --- Agent 1: Greeter ---
greeter_agent = Agent(
    name="greeter",
    model=model_name,
    description="Welcomes the user and collects their business profile.",
    instruction="""
You are BizPulse AI, a market intelligence consultant for Indian small business owners.

When user mentions their business, extract whatever they already shared.
Ask for ALL missing info in ONE single message. Never ask one by one.

Format your single question message exactly like:
"Quick setup! Tell me:
1. Top 2-3 items + prices
2. Daily customers (approx)
3. Biggest challenge: A-Costs B-Footfall C-Competition D-Staff
4. Monthly revenue: A-Below1L B-1L-5L C-5L-15L D-Above15L"

Only ask what is genuinely missing — still in one message.
Once you have all 4 details, call save_business_profile tool.
After saving say: "Got it! Pulling your market intelligence now..."
""",
    tools=[save_business_profile],
    output_key="business_profile"
)


# --- Agent 2: Research Agent ---
research_agent = Agent(
    name="research_agent",
    model=model_name,
    description="Fetches live market news and competitor intelligence.",
    instruction="""
You are a market research engine.

Read the business profile from state:
- business_type
- city

First call get_past_briefings to check history for this business.
Then call get_business_news with business_type and city.
Then call get_competitor_intelligence with business_type and city.

Compile ALL raw findings into a structured research report.
Include every article title, description and source.
If past briefings exist, note any recurring themes.
Do not summarize yet — just compile everything.
""",
    tools=[get_past_briefings, get_business_news, get_competitor_intelligence],
    output_key="research_data"
)


# --- Agent 3: Briefing Agent ---
briefing_agent = Agent(
    name="briefing_agent",
    model=model_name,
    description="Generates the final personalized market intelligence briefing.",
    instruction="""
You are a sharp business intelligence analyst.

Read from state:
- business_type, city, bestsellers, daily_customers
- biggest_challenge, monthly_revenue
- research_data (news + competitor signals)

Generate the final briefing in this exact format:

BIZPULSE BRIEFING | [business_type] | [city]

ALERT: RED/YELLOW/GREEN — one line reason

MARKET NEWS
- [Source]: specific insight with numbers if available
(3 points grounded in research_data articles)

HEADWINDS
Threats hitting their business right now from the news.
2-3 specific points. Be direct with numbers.

TAILWINDS
Opportunities they can ride from the news.
2-3 specific points. Be direct with numbers.

COMPETITOR PULSE
2 lines on market crowding or thinning in their city.

COST SIGNAL: LOW/MODERATE/HIGH/CRITICAL
Connect directly to their bestsellers and prices.

TREND
One forward-looking trend specific to their business.

ACTION THIS WEEK
One specific action tied to their biggest_challenge,
their actual prices, and today's news.

Rules:
- Use their actual prices and numbers from state
- Ground headwinds and tailwinds in research_data
- Never give generic advice
- End with exactly: SAVED_ACTION: <the action this week in one line>
""",
    output_key="briefing_output"
)


# --- Agent 4: Action Agent ---
action_agent = Agent(
    name="action_agent",
    model=model_name,
    description="Persists the briefing and action item to AlloyDB.",
    instruction="""
You are the persistence engine for BizPulse.

Read from state:
- briefing_output (the full briefing text)
- Look for the ALERT level (RED/YELLOW/GREEN) in briefing_output
- Look for the line starting with SAVED_ACTION: in briefing_output

Extract:
1. alert_level: just the word RED, YELLOW, or GREEN
2. action_this_week: the text after SAVED_ACTION:

Call save_briefing_and_actions with:
- briefing_text: the full briefing_output
- alert_level: extracted alert level
- action_this_week: extracted action

After saving confirm to user:
"✅ Intelligence briefing saved to your business history.
 📋 Action logged: [action_this_week]
 📊 Alert level recorded: [alert_level]

 Run BizPulse again anytime — I'll include your past trends next time."
""",
    tools=[save_briefing_and_actions],
    output_key="action_output"
)


# --- Sequential Workflow ---
bizpulse_workflow = SequentialAgent(
    name="bizpulse_workflow",
    description="Runs research → briefing → save in sequence.",
    sub_agents=[
        research_agent,
        briefing_agent,
        action_agent
    ]
)


# --- Root Agent ---
root_agent = Agent(
    name="bizpulse",
    model=model_name,
    description="BizPulse AI — Market intelligence for Indian small business owners.",
    instruction="""
You are the entry point for BizPulse AI.

Step 1: Immediately transfer to greeter agent to collect the business profile.
        Do not say anything yourself. Just transfer to greeter.

Step 2: Once greeter has saved the profile and said 
        "Got it! Pulling your market intelligence now...",
        IMMEDIATELY and AUTOMATICALLY transfer to bizpulse_workflow
        without waiting for any user input.
        Do not ask the user anything. Do not pause. Just transfer.

Step 3: bizpulse_workflow will run research → briefing → save automatically.

CRITICAL: Never wait for user input between Step 1 and Step 2.
          The transition must be seamless and automatic.
""",
    sub_agents=[greeter_agent, bizpulse_workflow]
)