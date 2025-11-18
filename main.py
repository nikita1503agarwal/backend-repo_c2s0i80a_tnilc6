import os
from datetime import date, timedelta
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional

from database import db, create_document, get_documents

app = FastAPI(title="HVAC AI Campaign Analytics API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------------
# Models
# -----------------------------
class CreateMetric(BaseModel):
    channel: str  # inbound | outbound
    date: date
    leads_generated: int = 0
    calls_handled: int = 0
    conversations: int = 0
    booked_jobs: int = 0
    completed_jobs: int = 0
    response_time_sec: float = 0
    conversion_rate: float = 0
    appt_set_rate: float = 0
    no_show_rate: float = 0
    aov: float = 0
    revenue: float = 0
    cost: float = 0
    roi: float = 0
    csat: float = 0


# -----------------------------
# Seed sample data if empty
# -----------------------------

def seed_sample_data():
    if db is None:
        return
    collection = db["campaignmetric"]
    if collection.count_documents({}) > 0:
        return

    today = date.today()
    for i in range(14):
        d = today - timedelta(days=13 - i)
        for channel in ["inbound", "outbound"]:
            # Create realistic HVAC values
            leads = 10 + (i % 5) * (1 if channel == "inbound" else 2)
            conversations = int(leads * (0.6 if channel == "inbound" else 0.4))
            booked = int(conversations * (0.45 if channel == "inbound" else 0.35))
            completed = int(booked * 0.9)
            aov = 350.0 if channel == "inbound" else 420.0
            revenue = completed * aov
            cost = 60.0 * leads if channel == "outbound" else 35.0 * leads
            roi = (revenue - cost) / cost if cost > 0 else 0
            response = 18 if channel == "inbound" else 12
            csat = 4.6 if channel == "inbound" else 4.3
            doc = {
                "channel": channel,
                "date": d.isoformat(),
                "leads_generated": leads,
                "calls_handled": leads + conversations,
                "conversations": conversations,
                "booked_jobs": booked,
                "completed_jobs": completed,
                "response_time_sec": response,
                "conversion_rate": (booked / max(leads, 1)),
                "appt_set_rate": (booked / max(conversations, 1)),
                "no_show_rate": 0.1,
                "aov": aov,
                "revenue": revenue,
                "cost": cost,
                "roi": roi,
                "csat": csat,
            }
            collection.insert_one(doc)


seed_sample_data()


# -----------------------------
# Routes
# -----------------------------
@app.get("/")
def root():
    return {"message": "HVAC AI Analytics API running"}


@app.get("/api/metrics/summary")
def get_summary():
    if db is None:
        # Fallback demo
        return {
            "period": "last_14_days",
            "totals": {"leads": 320, "booked": 180, "revenue": 64000, "roi": 3.1},
            "inbound": {"leads": 170, "booked": 100, "revenue": 34000, "roi": 3.5},
            "outbound": {"leads": 150, "booked": 80, "revenue": 30000, "roi": 2.7},
        }

    docs = list(db["campaignmetric"].find({}))
    if not docs:
        seed_sample_data()
        docs = list(db["campaignmetric"].find({}))

    def agg(filter_channel: Optional[str] = None):
        f = [d for d in docs if (filter_channel is None or d.get("channel") == filter_channel)]
        leads = sum(d.get("leads_generated", 0) for d in f)
        booked = sum(d.get("booked_jobs", 0) for d in f)
        revenue = sum(d.get("revenue", 0.0) for d in f)
        cost = sum(d.get("cost", 0.0) for d in f)
        roi = ((revenue - cost) / cost) if cost > 0 else 0
        return {"leads": leads, "booked": booked, "revenue": revenue, "roi": roi}

    return {
        "period": "last_14_days",
        "totals": agg(),
        "inbound": agg("inbound"),
        "outbound": agg("outbound"),
    }


@app.get("/api/metrics/timeseries")
def get_timeseries(channel: Optional[str] = None):
    if db is None:
        # minimal demo series
        days = [
            {"date": "2024-01-01", "leads": 10, "booked": 4, "revenue": 1600},
            {"date": "2024-01-02", "leads": 12, "booked": 6, "revenue": 2100},
        ]
        return {"channel": channel or "all", "data": days}

    query = {"channel": channel} if channel else {}
    docs = list(db["campaignmetric"].find(query))
    # sort by date
    docs.sort(key=lambda d: d.get("date"))
    series = []
    for d in docs:
        series.append({
            "date": d.get("date"),
            "leads": d.get("leads_generated", 0),
            "booked": d.get("booked_jobs", 0),
            "revenue": d.get("revenue", 0.0),
        })
    return {"channel": channel or "all", "data": series}


@app.post("/api/metrics")
def create_metric(payload: CreateMetric):
    if db is None:
        raise HTTPException(status_code=503, detail="Database not configured")
    doc = payload.model_dump()
    doc["date"] = payload.date.isoformat()
    _id = create_document("campaignmetric", doc)
    return {"id": _id}


@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }
    try:
        if db is not None:
            response["database"] = "✅ Connected & Working"
            response["database_url"] = "✅ Set"
            response["database_name"] = db.name
            response["connection_status"] = "Connected"
            response["collections"] = db.list_collection_names()[:10]
        else:
            response["database"] = "⚠️ Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"

    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"
    return response


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
