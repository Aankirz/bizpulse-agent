import os
import requests
import logging
import google.auth
import google.auth.transport.requests
import google.oauth2.id_token
import google.cloud.logging
from dotenv import load_dotenv
from google.adk import Agent
from google.adk.agents import SequentialAgent
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
    """Saves collected business profile to state. Call once all details collected."""
    tool_context.state["business_type"] = business_type
    tool_context.state["city"] = city
    tool_context.state["bestsellers"] = bestsellers
    tool_context.state["daily_customers"] = daily_customers
    tool_context.state["biggest_challenge"] = biggest_challenge
    tool_context.state["monthly_revenue"] = monthly_revenue
    logging.info(f"[BizPulse] Profile saved: {business_type} in {city}")
    return {"status": "profile_saved"}


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


# --- Agent 1: Greeter ---
# Collects business profile from user and saves to state

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
# Fetches live news and competitor data using state from greeter

research_agent = Agent(
    name="research_agent",
    model=model_name,
    description="Fetches live market news and competitor intelligence.",
    instruction="""
You are a market research engine.

Read the business profile from state:
- business_type
- city

Call get_business_news with business_type and city.
Call get_competitor_intelligence with business_type and city.

Compile ALL raw findings into a structured research report.
Include every article title, description and source.
Do not summarize yet — just compile everything.
""",
    tools=[get_business_news, get_competitor_intelligence],
    output_key="research_data"
)


# --- Agent 3: Briefing Agent ---
# Reads research data and business profile, generates final briefing

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

If multiple businesses in state: add PORTFOLIO section
comparing risk and opportunity across all businesses.

Rules:
- Use their actual prices and numbers from state
- Ground headwinds and tailwinds in research_data
- Never give generic advice
"""
)


# --- Sequential Workflow ---
# Runs research → briefing in sequence after greeter

bizpulse_workflow = SequentialAgent(
    name="bizpulse_workflow",
    description="Runs market research then generates the intelligence briefing.",
    sub_agents=[
        research_agent,
        briefing_agent
    ]
)


# --- Root Agent ---
# Entry point — collects profile then hands off to workflow

root_agent = Agent(
    name="bizpulse",
    model=model_name,
    description="BizPulse AI — Market intelligence for Indian small business owners.",
    instruction="""
You are the entry point for BizPulse AI.

Step 1: Use greeter_agent to collect the business profile.
Step 2: Once profile is saved, transfer to bizpulse_workflow.

Do not generate any briefing yourself.
""",
    sub_agents=[greeter_agent, bizpulse_workflow]
)
