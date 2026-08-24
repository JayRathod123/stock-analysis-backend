from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import health, stocks, candles, analysis, zones, backtests, ai, screener, market
from app.core.config import settings
from app.core.logging import setup_logging
from app.database.connection import init_db

setup_logging()

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="A personal stock-market research and analysis engine for Indian stocks.",
    version="0.1.0",
    lifespan=lifespan,
)

# Enable CORS for frontend cross-origin requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routes
app.include_router(health.router, prefix=f"{settings.API_V1_STR}/health", tags=["Health"])
app.include_router(stocks.router, prefix=f"{settings.API_V1_STR}/stocks", tags=["Stocks"])
app.include_router(candles.router, prefix=f"{settings.API_V1_STR}/candles", tags=["Candles"])
app.include_router(analysis.router, prefix=f"{settings.API_V1_STR}/analysis", tags=["Analysis"])
app.include_router(zones.router, prefix=f"{settings.API_V1_STR}/zones", tags=["Zones"])
app.include_router(backtests.router, prefix=f"{settings.API_V1_STR}/backtests", tags=["Backtests"])
app.include_router(ai.router, prefix=f"{settings.API_V1_STR}/ai", tags=["AI"])
app.include_router(screener.router, prefix=f"{settings.API_V1_STR}/screener", tags=["Screener"])
app.include_router(market.router, prefix=f"{settings.API_V1_STR}/market", tags=["Market"])
app.include_router(screener.router, prefix=f"{settings.API_V1_STR}/screener", tags=["Screener"])
app.include_router(market.router, prefix=f"{settings.API_V1_STR}/market", tags=["Market"])




