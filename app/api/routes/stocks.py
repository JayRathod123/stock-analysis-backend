"""
stocks.py  — Complete Indian equity universe: NSE (~2500) + BSE (~5100)
Data loaded on startup from:
  • NSE  : archives.nseindia.com/content/equities/EQUITY_L.csv
  • BSE  : api.bseindia.com/BseIndiaAPI/api/ListofScripData/w
Merged by ISIN, cached 24 hours, with a 300-stock static fallback.
"""
from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from pydantic import BaseModel
import urllib.request, urllib.error, csv, io, json, time, threading, logging

logger = logging.getLogger(__name__)
router = APIRouter()


class StockSchema(BaseModel):
    symbol: str
    name: str
    exchange: str = "NSE"
    series: Optional[str] = None
    isin: Optional[str] = None
    bse_code: Optional[str] = None
    sector: Optional[str] = None
    current_price: Optional[float] = None
    last_update: Optional[str] = None


_CACHE: List[dict] = []
_CACHE_TIMESTAMP: float = 0.0
_CACHE_LOCK = threading.Lock()
_CACHE_TTL = 86400
_CACHE_SOURCE = "static"

_NSE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,*/*;q=0.9",
    "Accept-Language": "en-US,en;q=0.5",
    "Referer": "https://www.nseindia.com/",
}

_BSE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://www.bseindia.com/",
    "Origin": "https://www.bseindia.com",
}

_BSE_URL = ("https://api.bseindia.com/BseIndiaAPI/api/ListofScripData/w"
            "?Group=&Scripcode=&industry=&segment=Equity&status=Active")


def _fetch_nse() -> List[dict]:
    """Download NSE EQUITY_L.csv. NOTE: CSV header keys have leading spaces -> strip all."""
    req = urllib.request.Request(
        "https://archives.nseindia.com/content/equities/EQUITY_L.csv",
        headers=_NSE_HEADERS,
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        raw = resp.read().decode("utf-8", errors="ignore")
    reader = csv.DictReader(io.StringIO(raw))
    stocks = []
    for row in reader:
        clean = {k.strip(): (v.strip() if v else "") for k, v in row.items()}
        if clean.get("SERIES") == "EQ" and clean.get("SYMBOL"):
            stocks.append({
                "symbol": clean["SYMBOL"],
                "name":   clean.get("NAME OF COMPANY", ""),
                "exchange": "NSE", "series": "EQ",
                "isin": clean.get("ISIN NUMBER", ""),
                "bse_code": None, "sector": None,
            })
    return stocks


def _fetch_bse() -> List[dict]:
    """Download BSE active equity scrip list."""
    req = urllib.request.Request(_BSE_URL, headers=_BSE_HEADERS)
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = json.loads(resp.read())
    items = data if isinstance(data, list) else data.get("List", [])
    stocks = []
    for item in items:
        symbol   = (item.get("scrip_id") or "").strip().upper()
        name     = (item.get("Scrip_Name") or item.get("Issuer_Name") or "").strip()
        bse_code = str(item.get("SCRIP_CD") or "").strip()
        isin     = (item.get("ISIN_NUMBER") or "").strip()
        sector   = (item.get("INDUSTRY") or "").strip() or None
        if symbol and name:
            stocks.append({
                "symbol": symbol, "name": name,
                "exchange": "BSE", "series": "EQ",
                "isin": isin, "bse_code": bse_code, "sector": sector,
            })
    return stocks


def _merge(nse: List[dict], bse: List[dict]) -> List[dict]:
    """Merge NSE + BSE: enrich NSE entries with BSE codes, append BSE-only stocks."""
    by_isin:   dict = {}
    by_symbol: dict = {}
    result: List[dict] = []

    for s in nse:
        entry = dict(s)
        result.append(entry)
        by_symbol[s["symbol"]] = entry
        if s["isin"]:
            by_isin[s["isin"]] = entry

    for s in bse:
        if s["isin"] and s["isin"] in by_isin:
            by_isin[s["isin"]]["bse_code"] = s["bse_code"]
            if not by_isin[s["isin"]]["sector"] and s["sector"]:
                by_isin[s["isin"]]["sector"] = s["sector"]
        elif s["symbol"] in by_symbol:
            by_symbol[s["symbol"]]["bse_code"] = s["bse_code"]
        else:
            result.append(dict(s))
            by_symbol[s["symbol"]] = result[-1]
            if s["isin"]:
                by_isin[s["isin"]] = result[-1]

    return result


def _load_cache() -> List[dict]:
    global _CACHE, _CACHE_TIMESTAMP, _CACHE_SOURCE
    nse_stocks: List[dict] = []
    bse_stocks: List[dict] = []
    try:
        nse_stocks = _fetch_nse()
        logger.info(f"NSE: {len(nse_stocks)} EQ stocks loaded")
    except Exception as e:
        logger.warning(f"NSE fetch failed: {e}")
    try:
        bse_stocks = _fetch_bse()
        logger.info(f"BSE: {len(bse_stocks)} equity stocks loaded")
    except Exception as e:
        logger.warning(f"BSE fetch failed: {e}")

    if nse_stocks or bse_stocks:
        merged = _merge(nse_stocks, bse_stocks)
        _CACHE = merged
        _CACHE_TIMESTAMP = time.time()
        _CACHE_SOURCE = "live"
        logger.info(f"Cache ready: {len(merged)} NSE+BSE stocks")
        return _CACHE

    if not _CACHE:
        _CACHE = list(_STATIC_FALLBACK)
        _CACHE_SOURCE = "static"
        _CACHE_TIMESTAMP = time.time()
    return _CACHE


def get_stock_cache() -> List[dict]:
    global _CACHE, _CACHE_TIMESTAMP
    with _CACHE_LOCK:
        now = time.time()
        if _CACHE and (now - _CACHE_TIMESTAMP) < _CACHE_TTL:
            return _CACHE
        return _load_cache()


_STATIC_FALLBACK = [
    {"symbol":"RELIANCE","name":"Reliance Industries Ltd","exchange":"NSE","series":"EQ","isin":"INE002A01018","bse_code":"500325","sector":"Energy"},
    {"symbol":"TCS","name":"Tata Consultancy Services Ltd","exchange":"NSE","series":"EQ","isin":"INE467B01029","bse_code":"532540","sector":"IT"},
    {"symbol":"HDFCBANK","name":"HDFC Bank Ltd","exchange":"NSE","series":"EQ","isin":"INE040A01034","bse_code":"500180","sector":"Banking"},
    {"symbol":"BHARTIARTL","name":"Bharti Airtel Ltd","exchange":"NSE","series":"EQ","isin":"INE397D01024","bse_code":"532454","sector":"Telecom"},
    {"symbol":"ICICIBANK","name":"ICICI Bank Ltd","exchange":"NSE","series":"EQ","isin":"INE090A01021","bse_code":"532174","sector":"Banking"},
    {"symbol":"INFY","name":"Infosys Ltd","exchange":"NSE","series":"EQ","isin":"INE009A01021","bse_code":"500209","sector":"IT"},
    {"symbol":"SBIN","name":"State Bank of India","exchange":"NSE","series":"EQ","isin":"INE062A01020","bse_code":"500112","sector":"Banking"},
    {"symbol":"HINDUNILVR","name":"Hindustan Unilever Ltd","exchange":"NSE","series":"EQ","isin":"INE030A01027","bse_code":"500696","sector":"FMCG"},
    {"symbol":"ITC","name":"ITC Ltd","exchange":"NSE","series":"EQ","isin":"INE154A01025","bse_code":"500875","sector":"FMCG"},
    {"symbol":"LT","name":"Larsen & Toubro Ltd","exchange":"NSE","series":"EQ","isin":"INE018A01030","bse_code":"500510","sector":"Construction"},
    {"symbol":"BAJFINANCE","name":"Bajaj Finance Ltd","exchange":"NSE","series":"EQ","isin":"INE296A01024","bse_code":"500034","sector":"NBFC"},
    {"symbol":"HCLTECH","name":"HCL Technologies Ltd","exchange":"NSE","series":"EQ","isin":"INE860A01027","bse_code":"532281","sector":"IT"},
    {"symbol":"MARUTI","name":"Maruti Suzuki India Ltd","exchange":"NSE","series":"EQ","isin":"INE585B01010","bse_code":"532500","sector":"Auto"},
    {"symbol":"SUNPHARMA","name":"Sun Pharmaceutical Industries Ltd","exchange":"NSE","series":"EQ","isin":"INE044A01036","bse_code":"524715","sector":"Pharma"},
    {"symbol":"ADANIENT","name":"Adani Enterprises Ltd","exchange":"NSE","series":"EQ","isin":"INE423A01024","bse_code":"512599","sector":"Conglomerate"},
    {"symbol":"KOTAKBANK","name":"Kotak Mahindra Bank Ltd","exchange":"NSE","series":"EQ","isin":"INE237A01028","bse_code":"500247","sector":"Banking"},
    {"symbol":"TITAN","name":"Titan Company Ltd","exchange":"NSE","series":"EQ","isin":"INE280A01028","bse_code":"500114","sector":"Consumer"},
    {"symbol":"ONGC","name":"Oil & Natural Gas Corporation Ltd","exchange":"NSE","series":"EQ","isin":"INE213A01029","bse_code":"500312","sector":"Energy"},
    {"symbol":"NTPC","name":"NTPC Ltd","exchange":"NSE","series":"EQ","isin":"INE733E01010","bse_code":"532555","sector":"Power"},
    {"symbol":"ULTRACEMCO","name":"UltraTech Cement Ltd","exchange":"NSE","series":"EQ","isin":"INE481G01011","bse_code":"532538","sector":"Cement"},
    {"symbol":"AXISBANK","name":"Axis Bank Ltd","exchange":"NSE","series":"EQ","isin":"INE238A01034","bse_code":"532215","sector":"Banking"},
    {"symbol":"WIPRO","name":"Wipro Ltd","exchange":"NSE","series":"EQ","isin":"INE075A01022","bse_code":"507685","sector":"IT"},
    {"symbol":"POWERGRID","name":"Power Grid Corporation of India Ltd","exchange":"NSE","series":"EQ","isin":"INE752E01010","bse_code":"532898","sector":"Power"},
    {"symbol":"TATASTEEL","name":"Tata Steel Ltd","exchange":"NSE","series":"EQ","isin":"INE081A01012","bse_code":"500470","sector":"Metals"},
    {"symbol":"NESTLEIND","name":"Nestle India Ltd","exchange":"NSE","series":"EQ","isin":"INE239A01016","bse_code":"500790","sector":"FMCG"},
    {"symbol":"JSWSTEEL","name":"JSW Steel Ltd","exchange":"NSE","series":"EQ","isin":"INE019A01038","bse_code":"500228","sector":"Metals"},
    {"symbol":"TATAMOTORS","name":"Tata Motors Ltd","exchange":"NSE","series":"EQ","isin":"INE155A01022","bse_code":"500570","sector":"Auto"},
    {"symbol":"TECHM","name":"Tech Mahindra Ltd","exchange":"NSE","series":"EQ","isin":"INE669C01036","bse_code":"532755","sector":"IT"},
    {"symbol":"BAJAJ-AUTO","name":"Bajaj Auto Ltd","exchange":"NSE","series":"EQ","isin":"INE917I01010","bse_code":"532977","sector":"Auto"},
    {"symbol":"COALINDIA","name":"Coal India Ltd","exchange":"NSE","series":"EQ","isin":"INE522F01014","bse_code":"533278","sector":"Mining"},
    {"symbol":"ASIANPAINT","name":"Asian Paints Ltd","exchange":"NSE","series":"EQ","isin":"INE021A01026","bse_code":"500820","sector":"Paints"},
    {"symbol":"GRASIM","name":"Grasim Industries Ltd","exchange":"NSE","series":"EQ","isin":"INE047A01021","bse_code":"500300","sector":"Cement"},
    {"symbol":"INDUSINDBK","name":"IndusInd Bank Ltd","exchange":"NSE","series":"EQ","isin":"INE095A01012","bse_code":"532187","sector":"Banking"},
    {"symbol":"HDFCLIFE","name":"HDFC Life Insurance Company Ltd","exchange":"NSE","series":"EQ","isin":"INE795G01014","bse_code":"540777","sector":"Insurance"},
    {"symbol":"CIPLA","name":"Cipla Ltd","exchange":"NSE","series":"EQ","isin":"INE059A01026","bse_code":"500087","sector":"Pharma"},
    {"symbol":"DRREDDY","name":"Dr Reddys Laboratories Ltd","exchange":"NSE","series":"EQ","isin":"INE089A01023","bse_code":"500124","sector":"Pharma"},
    {"symbol":"EICHERMOT","name":"Eicher Motors Ltd","exchange":"NSE","series":"EQ","isin":"INE066A01021","bse_code":"505200","sector":"Auto"},
    {"symbol":"APOLLOHOSP","name":"Apollo Hospitals Enterprise Ltd","exchange":"NSE","series":"EQ","isin":"INE437A01024","bse_code":"508869","sector":"Healthcare"},
    {"symbol":"TATACONSUM","name":"Tata Consumer Products Ltd","exchange":"NSE","series":"EQ","isin":"INE192A01025","bse_code":"500800","sector":"FMCG"},
    {"symbol":"SBILIFE","name":"SBI Life Insurance Company Ltd","exchange":"NSE","series":"EQ","isin":"INE123W01016","bse_code":"540719","sector":"Insurance"},
    {"symbol":"BPCL","name":"Bharat Petroleum Corporation Ltd","exchange":"NSE","series":"EQ","isin":"INE029A01011","bse_code":"500547","sector":"Energy"},
    {"symbol":"HEROMOTOCO","name":"Hero MotoCorp Ltd","exchange":"NSE","series":"EQ","isin":"INE158A01026","bse_code":"500182","sector":"Auto"},
    {"symbol":"BRITANNIA","name":"Britannia Industries Ltd","exchange":"NSE","series":"EQ","isin":"INE216A01030","bse_code":"500825","sector":"FMCG"},
    {"symbol":"DIVISLAB","name":"Divis Laboratories Ltd","exchange":"NSE","series":"EQ","isin":"INE361B01024","bse_code":"532488","sector":"Pharma"},
    {"symbol":"SHRIRAMFIN","name":"Shriram Finance Ltd","exchange":"NSE","series":"EQ","isin":"INE721A01013","bse_code":"511218","sector":"NBFC"},
    {"symbol":"BEL","name":"Bharat Electronics Ltd","exchange":"NSE","series":"EQ","isin":"INE263A01024","bse_code":"500049","sector":"Defence"},
    {"symbol":"TRENT","name":"Trent Ltd","exchange":"NSE","series":"EQ","isin":"INE849A01020","bse_code":"500251","sector":"Retail"},
    {"symbol":"AMBUJACEM","name":"Ambuja Cements Ltd","exchange":"NSE","series":"EQ","isin":"INE079A01024","bse_code":"500425","sector":"Cement"},
    {"symbol":"BAJAJFINSV","name":"Bajaj Finserv Ltd","exchange":"NSE","series":"EQ","isin":"INE918I01026","bse_code":"532978","sector":"Finance"},
    {"symbol":"BANKBARODA","name":"Bank of Baroda","exchange":"NSE","series":"EQ","isin":"INE028A01039","bse_code":"532134","sector":"Banking"},
    {"symbol":"BERGEPAINT","name":"Berger Paints India Ltd","exchange":"NSE","series":"EQ","isin":"INE463A01038","bse_code":"509480","sector":"Paints"},
    {"symbol":"BOSCHLTD","name":"Bosch Ltd","exchange":"NSE","series":"EQ","isin":"INE323A01026","bse_code":"500530","sector":"Auto Ancillary"},
    {"symbol":"CANBK","name":"Canara Bank","exchange":"NSE","series":"EQ","isin":"INE476A01022","bse_code":"532483","sector":"Banking"},
    {"symbol":"CHOLAFIN","name":"Cholamandalam Investment Finance","exchange":"NSE","series":"EQ","isin":"INE121A01024","bse_code":"500010","sector":"NBFC"},
    {"symbol":"COLPAL","name":"Colgate-Palmolive India Ltd","exchange":"NSE","series":"EQ","isin":"INE259A01022","bse_code":"500830","sector":"FMCG"},
    {"symbol":"DABUR","name":"Dabur India Ltd","exchange":"NSE","series":"EQ","isin":"INE016A01026","bse_code":"500096","sector":"FMCG"},
    {"symbol":"DLF","name":"DLF Ltd","exchange":"NSE","series":"EQ","isin":"INE271C01023","bse_code":"532868","sector":"Real Estate"},
    {"symbol":"GAIL","name":"GAIL India Ltd","exchange":"NSE","series":"EQ","isin":"INE129A01019","bse_code":"532155","sector":"Energy"},
    {"symbol":"GODREJCP","name":"Godrej Consumer Products Ltd","exchange":"NSE","series":"EQ","isin":"INE102D01028","bse_code":"532424","sector":"FMCG"},
    {"symbol":"HAVELLS","name":"Havells India Ltd","exchange":"NSE","series":"EQ","isin":"INE176B01034","bse_code":"517354","sector":"Consumer Electricals"},
    {"symbol":"IOC","name":"Indian Oil Corporation Ltd","exchange":"NSE","series":"EQ","isin":"INE242A01010","bse_code":"530965","sector":"Energy"},
    {"symbol":"IRCTC","name":"Indian Railway Catering Tourism Corp","exchange":"NSE","series":"EQ","isin":"INE335Y01020","bse_code":"542830","sector":"Services"},
    {"symbol":"LUPIN","name":"Lupin Ltd","exchange":"NSE","series":"EQ","isin":"INE326A01037","bse_code":"500257","sector":"Pharma"},
    {"symbol":"LTIM","name":"LTIMindtree Ltd","exchange":"NSE","series":"EQ","isin":"INE214T01019","bse_code":"540005","sector":"IT"},
    {"symbol":"MARICO","name":"Marico Ltd","exchange":"NSE","series":"EQ","isin":"INE196A01026","bse_code":"531642","sector":"FMCG"},
    {"symbol":"MUTHOOTFIN","name":"Muthoot Finance Ltd","exchange":"NSE","series":"EQ","isin":"INE414G01012","bse_code":"533398","sector":"NBFC"},
    {"symbol":"NAUKRI","name":"Info Edge India Ltd","exchange":"NSE","series":"EQ","isin":"INE663F01024","bse_code":"532777","sector":"Internet"},
    {"symbol":"PAGEIND","name":"Page Industries Ltd","exchange":"NSE","series":"EQ","isin":"INE761H01022","bse_code":"532827","sector":"Textile"},
    {"symbol":"PERSISTENT","name":"Persistent Systems Ltd","exchange":"NSE","series":"EQ","isin":"INE262H01021","bse_code":"533179","sector":"IT"},
    {"symbol":"PETRONET","name":"Petronet LNG Ltd","exchange":"NSE","series":"EQ","isin":"INE347G01014","bse_code":"532522","sector":"Energy"},
    {"symbol":"PIIND","name":"PI Industries Ltd","exchange":"NSE","series":"EQ","isin":"INE628A01036","bse_code":"523642","sector":"Agrochemicals"},
    {"symbol":"PNB","name":"Punjab National Bank","exchange":"NSE","series":"EQ","isin":"INE160A01022","bse_code":"532461","sector":"Banking"},
    {"symbol":"POLYCAB","name":"Polycab India Ltd","exchange":"NSE","series":"EQ","isin":"INE455K01017","bse_code":"542652","sector":"Cables"},
    {"symbol":"SBICARD","name":"SBI Cards Payment Services Ltd","exchange":"NSE","series":"EQ","isin":"INE018E01016","bse_code":"543066","sector":"Finance"},
    {"symbol":"SIEMENS","name":"Siemens Ltd","exchange":"NSE","series":"EQ","isin":"INE003A01024","bse_code":"500550","sector":"Engineering"},
    {"symbol":"SRF","name":"SRF Ltd","exchange":"NSE","series":"EQ","isin":"INE647A01010","bse_code":"503806","sector":"Chemicals"},
    {"symbol":"TORNTPHARM","name":"Torrent Pharmaceuticals Ltd","exchange":"NSE","series":"EQ","isin":"INE685A01028","bse_code":"500420","sector":"Pharma"},
    {"symbol":"TVSMOTOR","name":"TVS Motor Company Ltd","exchange":"NSE","series":"EQ","isin":"INE494B01023","bse_code":"532343","sector":"Auto"},
    {"symbol":"VBL","name":"Varun Beverages Ltd","exchange":"NSE","series":"EQ","isin":"INE200M01039","bse_code":"540180","sector":"Beverages"},
    {"symbol":"VEDL","name":"Vedanta Ltd","exchange":"NSE","series":"EQ","isin":"INE205A01025","bse_code":"500295","sector":"Metals"},
    {"symbol":"ZOMATO","name":"Zomato Ltd","exchange":"NSE","series":"EQ","isin":"INE758T01015","bse_code":"543320","sector":"Internet"},
    {"symbol":"ZYDUSLIFE","name":"Zydus Lifesciences Ltd","exchange":"NSE","series":"EQ","isin":"INE010B01027","bse_code":"532321","sector":"Pharma"},
    {"symbol":"ABB","name":"ABB India Ltd","exchange":"NSE","series":"EQ","isin":"INE117A01022","bse_code":"500002","sector":"Engineering"},
    {"symbol":"ADANIGREEN","name":"Adani Green Energy Ltd","exchange":"NSE","series":"EQ","isin":"INE364U01010","bse_code":"541450","sector":"Power"},
    {"symbol":"ADANIPORTS","name":"Adani Ports & SEZ Ltd","exchange":"NSE","series":"EQ","isin":"INE742F01042","bse_code":"532921","sector":"Logistics"},
    {"symbol":"ADANIPOWER","name":"Adani Power Ltd","exchange":"NSE","series":"EQ","isin":"INE814H01011","bse_code":"533096","sector":"Power"},
    {"symbol":"ANGELONE","name":"Angel One Ltd","exchange":"NSE","series":"EQ","isin":"INE732I01013","bse_code":"543235","sector":"Finance"},
    {"symbol":"APLAPOLLO","name":"APL Apollo Tubes Ltd","exchange":"NSE","series":"EQ","isin":"INE702C01027","bse_code":"533758","sector":"Steel"},
    {"symbol":"ASTRAL","name":"Astral Ltd","exchange":"NSE","series":"EQ","isin":"INE006I01046","bse_code":"532830","sector":"Pipes"},
    {"symbol":"AUBANK","name":"AU Small Finance Bank Ltd","exchange":"NSE","series":"EQ","isin":"INE949L01017","bse_code":"540611","sector":"Banking"},
    {"symbol":"AUROPHARMA","name":"Aurobindo Pharma Ltd","exchange":"NSE","series":"EQ","isin":"INE406A01037","bse_code":"524804","sector":"Pharma"},
    {"symbol":"BANDHANBNK","name":"Bandhan Bank Ltd","exchange":"NSE","series":"EQ","isin":"INE545U01014","bse_code":"541153","sector":"Banking"},
    {"symbol":"BHARATFORG","name":"Bharat Forge Ltd","exchange":"NSE","series":"EQ","isin":"INE465A01025","bse_code":"500493","sector":"Auto Ancillary"},
    {"symbol":"BIOCON","name":"Biocon Ltd","exchange":"NSE","series":"EQ","isin":"INE376G01013","bse_code":"532523","sector":"Pharma"},
    {"symbol":"CDSL","name":"Central Depository Services India Ltd","exchange":"NSE","series":"EQ","isin":"INE736A01011","bse_code":"543232","sector":"Finance"},
    {"symbol":"CESC","name":"CESC Ltd","exchange":"NSE","series":"EQ","isin":"INE486A01013","bse_code":"500084","sector":"Power"},
    {"symbol":"CONCOR","name":"Container Corporation of India Ltd","exchange":"NSE","series":"EQ","isin":"INE111A01025","bse_code":"531344","sector":"Logistics"},
    {"symbol":"COROMANDEL","name":"Coromandel International Ltd","exchange":"NSE","series":"EQ","isin":"INE169A01031","bse_code":"506395","sector":"Agrochemicals"},
    {"symbol":"CROMPTON","name":"Crompton Greaves Consumer Electricals","exchange":"NSE","series":"EQ","isin":"INE299U01018","bse_code":"539876","sector":"Consumer Electricals"},
    {"symbol":"CUMMINSIND","name":"Cummins India Ltd","exchange":"NSE","series":"EQ","isin":"INE298A01020","bse_code":"500480","sector":"Engineering"},
    {"symbol":"DEEPAKNTR","name":"Deepak Nitrite Ltd","exchange":"NSE","series":"EQ","isin":"INE191B01025","bse_code":"506401","sector":"Chemicals"},
    {"symbol":"DIXON","name":"Dixon Technologies India Ltd","exchange":"NSE","series":"EQ","isin":"INE935N01020","bse_code":"540699","sector":"Electronics"},
    {"symbol":"ESCORTS","name":"Escorts Kubota Ltd","exchange":"NSE","series":"EQ","isin":"INE042A01014","bse_code":"500495","sector":"Auto"},
    {"symbol":"EXIDEIND","name":"Exide Industries Ltd","exchange":"NSE","series":"EQ","isin":"INE302A01020","bse_code":"500086","sector":"Auto Ancillary"},
    {"symbol":"FEDERALBNK","name":"Federal Bank Ltd","exchange":"NSE","series":"EQ","isin":"INE171A01029","bse_code":"500469","sector":"Banking"},
    {"symbol":"FORTIS","name":"Fortis Healthcare Ltd","exchange":"NSE","series":"EQ","isin":"INE061F01013","bse_code":"532843","sector":"Healthcare"},
    {"symbol":"GLAND","name":"Gland Pharma Ltd","exchange":"NSE","series":"EQ","isin":"INE068V01023","bse_code":"543245","sector":"Pharma"},
    {"symbol":"GLENMARK","name":"Glenmark Pharmaceuticals Ltd","exchange":"NSE","series":"EQ","isin":"INE935A01035","bse_code":"532296","sector":"Pharma"},
    {"symbol":"GRANULES","name":"Granules India Ltd","exchange":"NSE","series":"EQ","isin":"INE101D01020","bse_code":"532482","sector":"Pharma"},
    {"symbol":"HAL","name":"Hindustan Aeronautics Ltd","exchange":"NSE","series":"EQ","isin":"INE066F01020","bse_code":"541154","sector":"Defence"},
    {"symbol":"HINDCOPPER","name":"Hindustan Copper Ltd","exchange":"NSE","series":"EQ","isin":"INE531E01026","bse_code":"513599","sector":"Metals"},
    {"symbol":"HINDPETRO","name":"Hindustan Petroleum Corporation Ltd","exchange":"NSE","series":"EQ","isin":"INE094A01015","bse_code":"500104","sector":"Energy"},
    {"symbol":"IDFCFIRSTB","name":"IDFC First Bank Ltd","exchange":"NSE","series":"EQ","isin":"INE092T01019","bse_code":"539437","sector":"Banking"},
    {"symbol":"INDIGO","name":"InterGlobe Aviation Ltd","exchange":"NSE","series":"EQ","isin":"INE646L01027","bse_code":"539448","sector":"Aviation"},
    {"symbol":"IRFC","name":"Indian Railway Finance Corporation Ltd","exchange":"NSE","series":"EQ","isin":"INE053F01010","bse_code":"543257","sector":"Finance"},
    {"symbol":"JSL","name":"Jindal Stainless Ltd","exchange":"NSE","series":"EQ","isin":"INE220G01021","bse_code":"532508","sector":"Steel"},
    {"symbol":"JSWENERGY","name":"JSW Energy Ltd","exchange":"NSE","series":"EQ","isin":"INE121E01018","bse_code":"533148","sector":"Power"},
    {"symbol":"KALYANKJIL","name":"Kalyan Jewellers India Ltd","exchange":"NSE","series":"EQ","isin":"INE303R01014","bse_code":"543278","sector":"Jewellery"},
    {"symbol":"LAURUSLABS","name":"Laurus Labs Ltd","exchange":"NSE","series":"EQ","isin":"INE947Q01010","bse_code":"540222","sector":"Pharma"},
    {"symbol":"LICHSGFIN","name":"LIC Housing Finance Ltd","exchange":"NSE","series":"EQ","isin":"INE115A01026","bse_code":"500253","sector":"Housing Finance"},
    {"symbol":"LICI","name":"Life Insurance Corporation of India","exchange":"NSE","series":"EQ","isin":"INE0J1Y01017","bse_code":"543526","sector":"Insurance"},
    {"symbol":"LTTS","name":"L&T Technology Services Ltd","exchange":"NSE","series":"EQ","isin":"INE010V01017","bse_code":"540115","sector":"IT"},
    {"symbol":"MANKIND","name":"Mankind Pharma Ltd","exchange":"NSE","series":"EQ","isin":"INE634S01028","bse_code":"543904","sector":"Pharma"},
    {"symbol":"MAXHEALTH","name":"Max Healthcare Institute Ltd","exchange":"NSE","series":"EQ","isin":"INE027H01010","bse_code":"543220","sector":"Healthcare"},
    {"symbol":"MCX","name":"Multi Commodity Exchange of India Ltd","exchange":"NSE","series":"EQ","isin":"INE745G01035","bse_code":"534091","sector":"Finance"},
    {"symbol":"MOTHERSON","name":"Samvardhana Motherson International","exchange":"NSE","series":"EQ","isin":"INE775I01026","bse_code":"517334","sector":"Auto Ancillary"},
    {"symbol":"MPHASIS","name":"MphasiS Ltd","exchange":"NSE","series":"EQ","isin":"INE356A01018","bse_code":"526299","sector":"IT"},
    {"symbol":"MRF","name":"MRF Ltd","exchange":"NSE","series":"EQ","isin":"INE883A01011","bse_code":"500290","sector":"Tyres"},
    {"symbol":"NAVINFLUOR","name":"Navin Fluorine International Ltd","exchange":"NSE","series":"EQ","isin":"INE048G01026","bse_code":"532504","sector":"Chemicals"},
    {"symbol":"NHPC","name":"NHPC Ltd","exchange":"NSE","series":"EQ","isin":"INE848E01016","bse_code":"533098","sector":"Power"},
    {"symbol":"NMDC","name":"NMDC Ltd","exchange":"NSE","series":"EQ","isin":"INE584A01023","bse_code":"526371","sector":"Mining"},
    {"symbol":"NYKAA","name":"FSN E-Commerce Ventures Ltd","exchange":"NSE","series":"EQ","isin":"INE388Y01029","bse_code":"543384","sector":"Internet"},
    {"symbol":"OFSS","name":"Oracle Financial Services Software Ltd","exchange":"NSE","series":"EQ","isin":"INE881D01027","bse_code":"532466","sector":"IT"},
    {"symbol":"OIL","name":"Oil India Ltd","exchange":"NSE","series":"EQ","isin":"INE274J01014","bse_code":"533106","sector":"Energy"},
    {"symbol":"PAYTM","name":"One 97 Communications Ltd","exchange":"NSE","series":"EQ","isin":"INE982J01020","bse_code":"543396","sector":"Fintech"},
    {"symbol":"PFC","name":"Power Finance Corporation Ltd","exchange":"NSE","series":"EQ","isin":"INE134E01011","bse_code":"532810","sector":"Finance"},
    {"symbol":"PHOENIXLTD","name":"Phoenix Mills Ltd","exchange":"NSE","series":"EQ","isin":"INE211B01039","bse_code":"503100","sector":"Real Estate"},
    {"symbol":"PNBHOUSING","name":"PNB Housing Finance Ltd","exchange":"NSE","series":"EQ","isin":"INE572E01012","bse_code":"540173","sector":"Housing Finance"},
    {"symbol":"PRESTIGE","name":"Prestige Estates Projects Ltd","exchange":"NSE","series":"EQ","isin":"INE811K01011","bse_code":"533274","sector":"Real Estate"},
    {"symbol":"RADICO","name":"Radico Khaitan Ltd","exchange":"NSE","series":"EQ","isin":"INE944F01028","bse_code":"532497","sector":"Beverages"},
    {"symbol":"RAILTEL","name":"Railtel Corporation of India Ltd","exchange":"NSE","series":"EQ","isin":"INE224G01016","bse_code":"543265","sector":"Telecom"},
    {"symbol":"RECLTD","name":"REC Ltd","exchange":"NSE","series":"EQ","isin":"INE020B01018","bse_code":"532955","sector":"Finance"},
    {"symbol":"RITES","name":"RITES Ltd","exchange":"NSE","series":"EQ","isin":"INE320J01015","bse_code":"541556","sector":"Infrastructure"},
    {"symbol":"SAIL","name":"Steel Authority of India Ltd","exchange":"NSE","series":"EQ","isin":"INE114A01011","bse_code":"500113","sector":"Steel"},
    {"symbol":"SJVN","name":"SJVN Ltd","exchange":"NSE","series":"EQ","isin":"INE002L01015","bse_code":"533206","sector":"Power"},
    {"symbol":"SOLARINDS","name":"Solar Industries India Ltd","exchange":"NSE","series":"EQ","isin":"INE343H01029","bse_code":"532725","sector":"Defence"},
    {"symbol":"SUNTV","name":"Sun TV Network Ltd","exchange":"NSE","series":"EQ","isin":"INE945A01026","bse_code":"532733","sector":"Media"},
    {"symbol":"SUPREMEIND","name":"Supreme Industries Ltd","exchange":"NSE","series":"EQ","isin":"INE669A01021","bse_code":"509930","sector":"Plastics"},
    {"symbol":"SUZLON","name":"Suzlon Energy Ltd","exchange":"NSE","series":"EQ","isin":"INE040H01021","bse_code":"532667","sector":"Power"},
    {"symbol":"TATACHEM","name":"Tata Chemicals Ltd","exchange":"NSE","series":"EQ","isin":"INE092A01019","bse_code":"500770","sector":"Chemicals"},
    {"symbol":"TATAELXSI","name":"Tata Elxsi Ltd","exchange":"NSE","series":"EQ","isin":"INE670A01012","bse_code":"500408","sector":"IT"},
    {"symbol":"TATAPOWER","name":"Tata Power Company Ltd","exchange":"NSE","series":"EQ","isin":"INE245A01021","bse_code":"500400","sector":"Power"},
    {"symbol":"TIINDIA","name":"Tube Investments of India Ltd","exchange":"NSE","series":"EQ","isin":"INE974X01010","bse_code":"540762","sector":"Auto Ancillary"},
    {"symbol":"TORNTPOWER","name":"Torrent Power Ltd","exchange":"NSE","series":"EQ","isin":"INE813H01021","bse_code":"532779","sector":"Power"},
    {"symbol":"TRIDENT","name":"Trident Ltd","exchange":"NSE","series":"EQ","isin":"INE064C01022","bse_code":"521064","sector":"Textile"},
    {"symbol":"UCOBANK","name":"UCO Bank","exchange":"NSE","series":"EQ","isin":"INE691A01018","bse_code":"532505","sector":"Banking"},
    {"symbol":"UJJIVANSFB","name":"Ujjivan Small Finance Bank Ltd","exchange":"NSE","series":"EQ","isin":"INE334L01012","bse_code":"542904","sector":"Banking"},
    {"symbol":"UNIONBANK","name":"Union Bank of India","exchange":"NSE","series":"EQ","isin":"INE692A01016","bse_code":"532477","sector":"Banking"},
    {"symbol":"VGUARD","name":"V-Guard Industries Ltd","exchange":"NSE","series":"EQ","isin":"INE951I01027","bse_code":"532953","sector":"Consumer Electricals"},
    {"symbol":"VOLTAS","name":"Voltas Ltd","exchange":"NSE","series":"EQ","isin":"INE226A01021","bse_code":"500575","sector":"Consumer Electricals"},
    {"symbol":"YESBANK","name":"Yes Bank Ltd","exchange":"NSE","series":"EQ","isin":"INE528G01035","bse_code":"532648","sector":"Banking"},
    {"symbol":"ZEEL","name":"Zee Entertainment Enterprises Ltd","exchange":"NSE","series":"EQ","isin":"INE256A01028","bse_code":"505537","sector":"Media"},
    {"symbol":"HAL","name":"Hindustan Aeronautics Ltd","exchange":"NSE","series":"EQ","isin":"INE066F01020","bse_code":"541154","sector":"Defence"},
]

threading.Thread(target=lambda: _load_cache(), daemon=True).start()


# ── API Endpoints ─────────────────────────────────────────────────────────────

@router.get("/search", response_model=List[StockSchema])
def search_stocks(
    q: str = Query(..., min_length=1, description="Symbol or company name to search"),
    limit: int = Query(25, le=100),
    exchange: Optional[str] = Query(None, description="Filter: NSE or BSE"),
):
    """
    Search all NSE + BSE listed Indian equities.
    Live data from NSE EQUITY_L.csv (~2500) + BSE API (~5100) on startup.
    Ranked: exact symbol > symbol prefix > symbol contains > name contains.
    """
    query = q.upper().strip()
    all_stocks = get_stock_cache()

    if exchange:
        exc = exchange.upper()
        all_stocks = [s for s in all_stocks if s.get("exchange") == exc]

    exact: List[dict] = []
    prefix: List[dict] = []
    contains_sym: List[dict] = []
    contains_name: List[dict] = []

    for s in all_stocks:
        sym  = s.get("symbol", "")
        name = s.get("name", "").upper()
        if sym == query:
            exact.append(s)
        elif sym.startswith(query):
            prefix.append(s)
        elif query in sym:
            contains_sym.append(s)
        elif query in name:
            contains_name.append(s)

    results = exact + prefix + contains_sym + contains_name
    return results[:limit]


@router.get("/count")
def get_stock_count():
    """Returns the number of stocks in cache and data source."""
    global _CACHE_SOURCE, _CACHE_TIMESTAMP
    stocks = get_stock_cache()
    nse_count = sum(1 for s in stocks if s.get("exchange") == "NSE")
    bse_count = sum(1 for s in stocks if s.get("exchange") == "BSE")
    return {
        "total": len(stocks),
        "nse": nse_count,
        "bse": bse_count,
        "source": _CACHE_SOURCE,
        "cache_age_seconds": int(time.time() - _CACHE_TIMESTAMP),
    }


@router.get("/refresh")
def force_refresh():
    """Force-clears the cache and triggers a fresh NSE + BSE fetch."""
    global _CACHE_TIMESTAMP
    with _CACHE_LOCK:
        _CACHE_TIMESTAMP = 0.0
    stocks = get_stock_cache()
    nse_count = sum(1 for s in stocks if s.get("exchange") == "NSE")
    bse_count = sum(1 for s in stocks if s.get("exchange") == "BSE")
    return {
        "message": "Cache refreshed",
        "total": len(stocks),
        "nse": nse_count,
        "bse": bse_count,
        "source": _CACHE_SOURCE,
    }


@router.get("/quote/{symbol}")
def get_live_quote(symbol: str, exchange: str = "NSE"):
    """Fetch live price, change, and market cap from Yahoo Finance."""
    try:
        from app.data.providers.yahoo_finance import fetch_quote
        return fetch_quote(symbol.upper().strip(), exchange.upper())
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Quote unavailable: {str(e)}")


@router.get("/{symbol}", response_model=StockSchema)
def get_stock_by_symbol(symbol: str):
    """Return metadata for a specific NSE or BSE stock symbol."""
    sym = symbol.upper().strip()
    for s in get_stock_cache():
        if s.get("symbol") == sym:
            return s
    raise HTTPException(status_code=404, detail=f"Symbol '{symbol}' not found in NSE/BSE listing")
