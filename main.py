import os
from datetime import date, timedelta, datetime, timezone
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Literal

from database import db, create_document

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

class CreateContact(BaseModel):
    name: str
    phone: str
    channel: Literal["inbound", "outbound"]
    stage: Literal["new", "engaged", "qualified", "booked", "completed"] = "new"

class UpdateStage(BaseModel):
    stage: Literal["new", "engaged", "qualified", "booked", "completed"]

# -----------------------------
# Seed sample data if empty
# -----------------------------

def seed_sample_data():
    if db is None:
        return
    # metrics
    metrics = db["campaignmetric"]
    if metrics.count_documents({}) == 0:
        today = date.today()
        for i in range(14):
            d = today - timedelta(days=13 - i)
            for channel in ["inbound", "outbound"]:
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
                metrics.insert_one(doc)

    # contacts + conversations
    from bson import ObjectId  # type: ignore
    contacts = db["contact"]
    conv = db["conversationmessage"]
    if contacts.count_documents({}) == 0:
        demo_contacts = [
            {"name": "Alex Johnson", "phone": "+1 (555) 201-3344", "channel": "inbound", "stage": "new"},
            {"name": "Brianna Lee", "phone": "+1 (555) 448-9920", "channel": "outbound", "stage": "engaged"},
            {"name": "Carlos Martinez", "phone": "+1 (555) 773-1102", "channel": "inbound", "stage": "qualified"},
            {"name": "Danielle Kim", "phone": "+1 (555) 667-9088", "channel": "outbound", "stage": "booked"},
            {"name": "Ethan Walker", "phone": "+1 (555) 334-7855", "channel": "inbound", "stage": "completed"},
        ]
        inserted_ids = []
        now = datetime.now(timezone.utc)
        for dc in demo_contacts:
            dc["created_at"] = now
            dc["updated_at"] = now
            res = contacts.insert_one(dc)
            inserted_ids.append(str(res.inserted_id))
        # seed conversations for first two
        messages = [
            {
                "contact_id": inserted_ids[0],
                "type": "sms",
                "direction": "inbound",
                "timestamp": now - timedelta(minutes=50),
                "text": "Hi, my AC stopped working today. Can you help?",
            },
            {
                "contact_id": inserted_ids[0],
                "type": "sms",
                "direction": "outbound",
                "timestamp": now - timedelta(minutes=48),
                "text": "Absolutely. What time today works to send a tech?",
            },
            {
                "contact_id": inserted_ids[0],
                "type": "call",
                "direction": "outbound",
                "timestamp": now - timedelta(minutes=40),
                "recording_url": "https://file-examples.com/storage/fe1b0a8f03f6d0b8f4d1f9e/2017/11/file_example_MP3_700KB.mp3",
                "duration_sec": 120,
            },
            {
                "contact_id": inserted_ids[1],
                "type": "sms",
                "direction": "outbound",
                "timestamp": now - timedelta(hours=2),
                "text": "We have a tune-up special this week if you'd like to book a slot.",
            },
            {
                "contact_id": inserted_ids[1],
                "type": "sms",
                "direction": "inbound",
                "timestamp": now - timedelta(hours=1, minutes=45),
                "text": "Yes please. Tomorrow afternoon?",
            },
        ]
        for m in messages:
            m["created_at"] = now
            m["updated_at"] = now
            conv.insert_one(m)

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
        days = [
            {"date": "2024-01-01", "leads": 10, "booked": 4, "revenue": 1600},
            {"date": "2024-01-02", "leads": 12, "booked": 6, "revenue": 2100},
        ]
        return {"channel": channel or "all", "data": days}

    query = {"channel": channel} if channel else {}
    docs = list(db["campaignmetric"].find(query))
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


# -----------------------------
# Pipeline & Conversations
# -----------------------------
from bson import ObjectId  # type: ignore

@app.get("/api/contacts")
def list_contacts(stage: Optional[str] = None):
    if db is None:
        # demo fallback
        demo = [
            {"_id": "1", "name": "Alex Johnson", "phone": "+1 (555) 201-3344", "channel": "inbound", "stage": "new"},
            {"_id": "2", "name": "Brianna Lee", "phone": "+1 (555) 448-9920", "channel": "outbound", "stage": "engaged"},
        ]
        if stage:
            demo = [d for d in demo if d["stage"] == stage]
        return demo
    query = {"stage": stage} if stage else {}
    docs = list(db["contact"].find(query))
    # stringify ids
    for d in docs:
        d["_id"] = str(d["_id"])
    return docs

@app.post("/api/contacts")
def create_contact(payload: CreateContact):
    if db is None:
        raise HTTPException(status_code=503, detail="Database not configured")
    doc = payload.model_dump()
    _id = create_document("contact", doc)
    return {"id": _id}

@app.patch("/api/contacts/{contact_id}/stage")
def update_contact_stage(contact_id: str, payload: UpdateStage):
    if db is None:
        raise HTTPException(status_code=503, detail="Database not configured")
    try:
        oid = ObjectId(contact_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid contact id")
    res = db["contact"].update_one({"_id": oid}, {"$set": {"stage": payload.stage, "updated_at": datetime.now(timezone.utc)}})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Contact not found")
    return {"ok": True}

@app.get("/api/contacts/{contact_id}/conversation")
def get_conversation(contact_id: str):
    if db is None:
        # demo fallback
        now = datetime.now(timezone.utc)
        return {
            "contact": {"_id": contact_id, "name": "Demo Contact", "phone": "+1 (555) 000-0000"},
            "messages": [
                {"type": "sms", "direction": "inbound", "timestamp": now.isoformat(), "text": "Hi there"},
                {"type": "call", "direction": "outbound", "timestamp": now.isoformat(), "recording_url": "https://file-examples.com/storage/fe1b0a8f03f6d0b8f4d1f9e/2017/11/file_example_MP3_700KB.mp3", "duration_sec": 90},
            ]
        }
    try:
        oid = ObjectId(contact_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid contact id")
    contact = db["contact"].find_one({"_id": oid})
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    msgs = list(db["conversationmessage"].find({"contact_id": contact_id}).sort("timestamp", 1))
    for m in msgs:
        m["_id"] = str(m["_id"])
        if isinstance(m.get("timestamp"), datetime):
            m["timestamp"] = m["timestamp"].isoformat()
    contact["_id"] = str(contact["_id"])
    return {"contact": {"_id": contact["_id"], "name": contact.get("name"), "phone": contact.get("phone"), "channel": contact.get("channel"), "stage": contact.get("stage")}, "messages": msgs}


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
