import time
import base64
from collections import defaultdict
from typing import Optional, List
from fastapi import FastAPI, Header, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

app = FastAPI()

# Enable CORS for all origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Retry-After"],
)

# Constants
TOTAL_ORDERS = 52
RATE_LIMIT = 15
WINDOW_SECONDS = 10

# In-memory stores
idempotency_store = {}
rate_limit_store = defaultdict(list)
catalog = [{"id": i, "data": f"Order #{i}"} for i in range(1, TOTAL_ORDERS + 1)]

class Order(BaseModel):
    id: int
    data: str

@app.post("/orders")
async def create_order(idempotency_key: str = Header(...)):
    if idempotency_key in idempotency_store:
        return idempotency_store[idempotency_key]
    
    new_order = {"id": len(idempotency_store) + 1, "data": "New Order"}
    idempotency_store[idempotency_key] = new_order
    return new_order

@app.get("/orders")
async def get_orders(
    limit: int = 10,
    cursor: Optional[str] = None,
    x_client_id: str = Header(default="anonymous")
):
    # 1. Rate Limiting Check
    now = time.time()
    user_requests = rate_limit_store[x_client_id]
    
    # Filter requests within the last 10 seconds
    rate_limit_store[x_client_id] = [t for t in user_requests if now - t < WINDOW_SECONDS]
    
    # if len(rate_limit_store[x_client_id]) >= RATE_LIMIT:
    #     return Response(
    #         status_code=429,
    #         headers={"Retry-After": "10"},
    #         content="Rate limit exceeded"
    #     )

    # Rate limiting check
    # if len(rate_limit_store[x_client_id]) >= RATE_LIMIT:
    #     raise HTTPException(
    #         status_code=429,
    #         detail="Rate limit exceeded",
    #         headers={"Retry-After": str(WINDOW_SECONDS)}
    #     )
    if len(rate_limit_store[x_client_id]) >= RATE_LIMIT:
        return JSONResponse(
            status_code=429,
            content={"detail": "Rate limit exceeded"},
            headers={"Retry-After": str(WINDOW_SECONDS)}
        )    
    rate_limit_store[x_client_id].append(now)

    # 2. Cursor Pagination
    start_idx = 0
    if cursor:
        try:
            start_idx = int(base64.b64decode(cursor).decode('utf-8'))
        except:
            raise HTTPException(status_code=400, detail="Invalid cursor")

    items = catalog[start_idx : start_idx + limit]
    next_idx = start_idx + len(items)
    
    next_cursor = None
    if next_idx < len(catalog):
        next_cursor = base64.b64encode(str(next_idx).encode('utf-8')).decode('utf-8')

    return {"items": items, "next_cursor": next_cursor}
