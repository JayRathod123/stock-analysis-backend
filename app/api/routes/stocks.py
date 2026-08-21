from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from pydantic import BaseModel
import urllib.request
import csv
import io
import time
import threading
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

class StockSchema(BaseModel):
    symbol: str
    name: str
    exchange: str = "NSE"
    series: Optional[str] = None
    isin: Optional[str] = None
    current_price: Optional[float] = None
    last_update: Optional[str] = None

_CACHE: List[dict] = []
_CACHE_TIMESTAMP: float = 0.0
_CACHE_LOCK = threading.Lock()
_CACHE_TTL_SECONDS = 86400  # 24 hours
NSE_EQUITY_CSV_URL = "https://archives.nseindia.com/content/equities/EQUITY_L.csv"
NSE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Referer": "https://www.nseindia.com/",
}

def _fetch_nse_equity_list() -> List[dict]:
    req = urllib.request.Request(NSE_EQUITY_CSV_URL, headers=NSE_HEADERS)
    with urllib.request.urlopen(req, timeout=15) as resp:
        raw = resp.read().decode("utf-8", errors="ignore")
    reader = csv.DictReader(io.StringIO(raw))
    stocks = []
    for row in reader:
        symbol = row.get("SYMBOL", "").strip()
        name = row.get("NAME OF COMPANY", "").strip()
        series = row.get("SERIES", "").strip()
        isin = row.get("ISIN NUMBER", "").strip()
        if symbol and name and series == "EQ":
            stocks.append({"symbol": symbol, "name": name, "exchange": "NSE", "series": series, "isin": isin, "current_price": None, "last_update": None})
    return stocks

_STATIC_FALLBACK: List[dict] = [
    # NIFTY 50
    {"symbol":"RELIANCE","name":"Reliance Industries Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"TCS","name":"Tata Consultancy Services Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"HDFCBANK","name":"HDFC Bank Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"BHARTIARTL","name":"Bharti Airtel Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"ICICIBANK","name":"ICICI Bank Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"INFY","name":"Infosys Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"SBIN","name":"State Bank of India","exchange":"NSE","series":"EQ"},
    {"symbol":"HINDUNILVR","name":"Hindustan Unilever Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"ITC","name":"ITC Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"LT","name":"Larsen & Toubro Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"BAJFINANCE","name":"Bajaj Finance Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"HCLTECH","name":"HCL Technologies Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"MARUTI","name":"Maruti Suzuki India Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"SUNPHARMA","name":"Sun Pharmaceutical Industries Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"ADANIENT","name":"Adani Enterprises Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"KOTAKBANK","name":"Kotak Mahindra Bank Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"TITAN","name":"Titan Company Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"ONGC","name":"Oil & Natural Gas Corporation Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"NTPC","name":"NTPC Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"ULTRACEMCO","name":"UltraTech Cement Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"AXISBANK","name":"Axis Bank Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"WIPRO","name":"Wipro Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"POWERGRID","name":"Power Grid Corporation of India Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"TATASTEEL","name":"Tata Steel Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"NESTLEIND","name":"Nestle India Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"JSWSTEEL","name":"JSW Steel Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"TATAMOTORS","name":"Tata Motors Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"TECHM","name":"Tech Mahindra Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"BAJAJ-AUTO","name":"Bajaj Auto Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"COALINDIA","name":"Coal India Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"ASIANPAINT","name":"Asian Paints Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"GRASIM","name":"Grasim Industries Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"INDUSINDBK","name":"IndusInd Bank Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"HDFCLIFE","name":"HDFC Life Insurance Company Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"CIPLA","name":"Cipla Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"DRREDDY","name":"Dr Reddys Laboratories Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"EICHERMOT","name":"Eicher Motors Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"APOLLOHOSP","name":"Apollo Hospitals Enterprise Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"TATACONSUM","name":"Tata Consumer Products Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"SBILIFE","name":"SBI Life Insurance Company Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"BPCL","name":"Bharat Petroleum Corporation Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"HEROMOTOCO","name":"Hero MotoCorp Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"BRITANNIA","name":"Britannia Industries Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"DIVISLAB","name":"Divis Laboratories Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"SHRIRAMFIN","name":"Shriram Finance Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"BEL","name":"Bharat Electronics Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"TRENT","name":"Trent Ltd","exchange":"NSE","series":"EQ"},
    # NIFTY Next 50
    {"symbol":"AMBUJACEM","name":"Ambuja Cements Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"BAJAJFINSV","name":"Bajaj Finserv Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"BANKBARODA","name":"Bank of Baroda","exchange":"NSE","series":"EQ"},
    {"symbol":"BERGEPAINT","name":"Berger Paints India Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"BOSCHLTD","name":"Bosch Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"CANBK","name":"Canara Bank","exchange":"NSE","series":"EQ"},
    {"symbol":"CHOLAFIN","name":"Cholamandalam Investment Finance","exchange":"NSE","series":"EQ"},
    {"symbol":"COLPAL","name":"Colgate-Palmolive India Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"DABUR","name":"Dabur India Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"DLF","name":"DLF Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"GAIL","name":"GAIL India Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"GODREJCP","name":"Godrej Consumer Products Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"GODREJPROP","name":"Godrej Properties Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"HAVELLS","name":"Havells India Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"ICICIPRULI","name":"ICICI Prudential Life Insurance Co","exchange":"NSE","series":"EQ"},
    {"symbol":"INDUSTOWER","name":"Indus Towers Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"IOC","name":"Indian Oil Corporation Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"IRCTC","name":"Indian Railway Catering Tourism Corp","exchange":"NSE","series":"EQ"},
    {"symbol":"JUBLFOOD","name":"Jubilant Foodworks Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"LUPIN","name":"Lupin Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"LTIM","name":"LTIMindtree Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"MARICO","name":"Marico Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"MUTHOOTFIN","name":"Muthoot Finance Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"NAUKRI","name":"Info Edge India Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"OBEROIRLTY","name":"Oberoi Realty Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"PAGEIND","name":"Page Industries Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"PERSISTENT","name":"Persistent Systems Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"PETRONET","name":"Petronet LNG Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"PIIND","name":"PI Industries Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"PNB","name":"Punjab National Bank","exchange":"NSE","series":"EQ"},
    {"symbol":"POLYCAB","name":"Polycab India Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"SBICARD","name":"SBI Cards Payment Services Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"SIEMENS","name":"Siemens Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"SRF","name":"SRF Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"TORNTPHARM","name":"Torrent Pharmaceuticals Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"TVSMOTOR","name":"TVS Motor Company Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"VBL","name":"Varun Beverages Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"VEDL","name":"Vedanta Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"ZOMATO","name":"Zomato Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"ZYDUSLIFE","name":"Zydus Lifesciences Ltd","exchange":"NSE","series":"EQ"},
]

# Extend fallback with Midcap + Smallcap + Sector leaders
_STATIC_FALLBACK.extend([
    {"symbol":"ABB","name":"ABB India Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"ABCAPITAL","name":"Aditya Birla Capital Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"ABFRL","name":"Aditya Birla Fashion Retail Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"ALKEM","name":"Alkem Laboratories Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"APLAPOLLO","name":"APL Apollo Tubes Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"ASTRAL","name":"Astral Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"AUBANK","name":"AU Small Finance Bank Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"AUROPHARMA","name":"Aurobindo Pharma Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"BANDHANBNK","name":"Bandhan Bank Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"BHARATFORG","name":"Bharat Forge Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"BIOCON","name":"Biocon Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"CDSL","name":"Central Depository Services India Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"CESC","name":"CESC Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"COROMANDEL","name":"Coromandel International Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"CROMPTON","name":"Crompton Greaves Consumer Electricals Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"CUMMINSIND","name":"Cummins India Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"DALBHARAT","name":"Dalmia Bharat Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"DEEPAKNTR","name":"Deepak Nitrite Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"DIXON","name":"Dixon Technologies India Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"ESCORTS","name":"Escorts Kubota Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"EXIDEIND","name":"Exide Industries Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"FEDERALBNK","name":"Federal Bank Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"FINEORG","name":"Fine Organic Industries Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"FORTIS","name":"Fortis Healthcare Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"GLAND","name":"Gland Pharma Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"GLENMARK","name":"Glenmark Pharmaceuticals Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"GMRAIRPORT","name":"GMR Airports Infrastructure Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"GRANULES","name":"Granules India Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"HAL","name":"Hindustan Aeronautics Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"HINDCOPPER","name":"Hindustan Copper Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"HINDPETRO","name":"Hindustan Petroleum Corporation Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"IDFCFIRSTB","name":"IDFC First Bank Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"IIFL","name":"IIFL Finance Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"INDIANB","name":"Indian Bank","exchange":"NSE","series":"EQ"},
    {"symbol":"INDIGO","name":"InterGlobe Aviation Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"IPCALAB","name":"IPCA Laboratories Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"IRFC","name":"Indian Railway Finance Corporation Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"JKCEMENT","name":"JK Cement Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"JSL","name":"Jindal Stainless Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"JSWENERGY","name":"JSW Energy Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"KALYANKJIL","name":"Kalyan Jewellers India Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"KFINTECH","name":"KFin Technologies Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"LAURUSLABS","name":"Laurus Labs Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"LICHSGFIN","name":"LIC Housing Finance Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"LICI","name":"Life Insurance Corporation of India","exchange":"NSE","series":"EQ"},
    {"symbol":"LTTS","name":"L&T Technology Services Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"MANKIND","name":"Mankind Pharma Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"MAXHEALTH","name":"Max Healthcare Institute Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"MCX","name":"Multi Commodity Exchange of India Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"METROPOLIS","name":"Metropolis Healthcare Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"MOTHERSON","name":"Samvardhana Motherson International Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"MPHASIS","name":"MphasiS Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"MRF","name":"MRF Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"NAVINFLUOR","name":"Navin Fluorine International Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"NHPC","name":"NHPC Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"NMDC","name":"NMDC Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"NYKAA","name":"FSN E-Commerce Ventures Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"OFSS","name":"Oracle Financial Services Software Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"OIL","name":"Oil India Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"PAYTM","name":"One 97 Communications Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"PFC","name":"Power Finance Corporation Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"PHOENIXLTD","name":"Phoenix Mills Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"PNBHOUSING","name":"PNB Housing Finance Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"POLYPLEX","name":"Polyplex Corporation Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"PRESTIGE","name":"Prestige Estates Projects Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"RADICO","name":"Radico Khaitan Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"RAILTEL","name":"Railtel Corporation of India Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"RAYMOND","name":"Raymond Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"RECLTD","name":"REC Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"RITES","name":"RITES Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"SAIL","name":"Steel Authority of India Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"SCHAEFFLER","name":"Schaeffler India Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"SHREECEM","name":"Shree Cement Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"SJVN","name":"SJVN Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"SOLARINDS","name":"Solar Industries India Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"SONACOMS","name":"Sona BLW Precision Forgings Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"STARHEALTH","name":"Star Health & Allied Insurance Co Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"SUNTV","name":"Sun TV Network Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"SUPREMEIND","name":"Supreme Industries Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"SUZLON","name":"Suzlon Energy Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"TANLA","name":"Tanla Platforms Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"TATACHEM","name":"Tata Chemicals Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"TATAELXSI","name":"Tata Elxsi Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"TATAPOWER","name":"Tata Power Company Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"TIINDIA","name":"Tube Investments of India Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"TIMKEN","name":"Timken India Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"TORNTPOWER","name":"Torrent Power Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"TRIDENT","name":"Trident Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"UCOBANK","name":"UCO Bank","exchange":"NSE","series":"EQ"},
    {"symbol":"UJJIVANSFB","name":"Ujjivan Small Finance Bank Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"UNIONBANK","name":"Union Bank of India","exchange":"NSE","series":"EQ"},
    {"symbol":"VGUARD","name":"V-Guard Industries Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"VOLTAS","name":"Voltas Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"YESBANK","name":"Yes Bank Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"ZEEL","name":"Zee Entertainment Enterprises Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"ZENSARTECH","name":"Zensar Technologies Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"ADANIGREEN","name":"Adani Green Energy Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"ADANIPOWER","name":"Adani Power Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"ADANIPORTS","name":"Adani Ports & SEZ Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"ANGELONE","name":"Angel One Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"CLEAN","name":"Clean Science & Technology Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"CONCOR","name":"Container Corporation of India Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"CRISIL","name":"CRISIL Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"EIDPARRY","name":"EID Parry India Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"EMAMILTD","name":"Emami Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"ENGINERSIN","name":"Engineers India Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"FLUOROCHEM","name":"Gujarat Fluorochemicals Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"GNFC","name":"Gujarat Narmada Valley Fertilizers Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"GRINDWELL","name":"Grindwell Norton Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"HFCL","name":"HFCL Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"HINDCOPPER","name":"Hindustan Copper Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"INDIAGLYCO","name":"India Glycols Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"JUBILANT","name":"Jubilant Pharmova Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"KIMS","name":"Krishna Institute of Medical Sciences Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"LINDEINDIA","name":"Linde India Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"MFSL","name":"Max Financial Services Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"NLCINDIA","name":"NLC India Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"NOCIL","name":"NOCIL Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"PATANJALI","name":"Patanjali Foods Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"PEL","name":"Piramal Enterprises Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"PHOENIXLTD","name":"The Phoenix Mills Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"POONAWALLA","name":"Poonawalla Fincorp Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"SAPPHIRE","name":"Sapphire Foods India Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"SKFINDIA","name":"SKF India Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"SPANDANA","name":"Spandana Sphoorty Financial Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"SPICEJET","name":"SpiceJet Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"SUVENPHAR","name":"Suven Pharmaceuticals Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"TATAINVEST","name":"Tata Investment Corporation Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"UFLEX","name":"UFLEX Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"VBL","name":"Varun Beverages Ltd","exchange":"NSE","series":"EQ"},
    {"symbol":"VIJAYABANK","name":"Vijaya Bank","exchange":"NSE","series":"EQ"},
    {"symbol":"WONDERLA","name":"Wonderla Holidays Ltd","exchange":"NSE","series":"EQ"},
])


def _get_stock_cache() -> List[dict]:
    global _CACHE, _CACHE_TIMESTAMP
    with _CACHE_LOCK:
        now = time.time()
        if _CACHE and (now - _CACHE_TIMESTAMP) < _CACHE_TTL_SECONDS:
            return _CACHE
        try:
            logger.info("Fetching NSE equity list from archives.nseindia.com ...")
            stocks = _fetch_nse_equity_list()
            if len(stocks) > 100:
                _CACHE = stocks
                _CACHE_TIMESTAMP = now
                logger.info(f"NSE equity cache refreshed: {len(stocks)} stocks loaded.")
                return _CACHE
        except Exception as e:
            logger.warning(f"NSE fetch failed ({e}), falling back to static list.")
        if not _CACHE:
            _CACHE = _STATIC_FALLBACK
            _CACHE_TIMESTAMP = now
        return _CACHE

def _background_prefetch():
    try:
        _get_stock_cache()
    except Exception:
        pass

threading.Thread(target=_background_prefetch, daemon=True).start()


@router.get("/search", response_model=List[StockSchema])
def search_stocks(q: str = Query(..., min_length=1), limit: int = Query(20, le=100)):
    """Search Indian stocks by symbol or company name. Live NSE data with 24h cache."""
    query = q.upper().strip()
    all_stocks = _get_stock_cache()
    results = []
    # Exact symbol prefix match first
    for s in all_stocks:
        if s["symbol"].startswith(query):
            results.append(s)
    # Then name contains match
    for s in all_stocks:
        if s not in results and query in s["name"].upper():
            results.append(s)
    return results[:limit]


@router.get("/count")
def get_stock_count():
    """Returns the current number of stocks in the cache."""
    stocks = _get_stock_cache()
    return {
        "count": len(stocks),
        "source": "NSE Live (EQUITY_L.csv)" if len(stocks) > 200 else "Static Fallback (~150 stocks)"
    }


@router.get("/refresh")
def force_refresh():
    """Force-invalidates the cache to trigger a fresh NSE fetch."""
    global _CACHE_TIMESTAMP
    with _CACHE_LOCK:
        _CACHE_TIMESTAMP = 0.0
    stocks = _get_stock_cache()
    return {"message": "Cache refreshed", "count": len(stocks)}


@router.get("/{symbol}", response_model=StockSchema)
def get_stock_by_symbol(symbol: str):
    """Get metadata for a specific NSE stock symbol."""
    sym = symbol.upper().strip()
    for s in _get_stock_cache():
        if s["symbol"] == sym:
            return s
    raise HTTPException(status_code=404, detail=f"Symbol '{symbol}' not found in NSE equity list")


# ── Live Quote Endpoint ───────────────────────────────────────────────────────

@router.get("/quote/{symbol}")
def get_live_quote(symbol: str, exchange: str = "NSE"):
    """
    Fetch the live price quote for a single Indian stock from Yahoo Finance.
    Returns current price, previous close, day change, and market cap.
    """
    try:
        from app.data.providers.yahoo_finance import fetch_quote
        return fetch_quote(symbol.upper().strip(), exchange.upper())
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Live quote unavailable: {str(e)}")
