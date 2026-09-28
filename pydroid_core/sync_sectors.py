import csv
import json
import logging
import sqlite3
import urllib.request
import urllib.error
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional

# Setup basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

PRIMARY_SECTORS = [
    'AUTO', 'FINSERV', 'CAPGOODS', 'CHEMICALS', 'REALTY', 'CONSDUR',
    'FMCG', 'PHARMA', 'IT', 'METALS', 'ENERGY', 'INFRA_MEDIA'
]

INDUSTRY_TO_SECTOR = {
    'Automobile and Auto Components': 'AUTO',
    'Financial Services': 'FINSERV',
    'Capital Goods': 'CAPGOODS',
    'Chemicals': 'CHEMICALS',
    'Construction': 'REALTY',
    'Construction Materials': 'REALTY',
    'Realty': 'REALTY',
    'Consumer Durables': 'CONSDUR',
    'Consumer Services': 'CONSDUR',
    'Textiles': 'CONSDUR',
    'Fast Moving Consumer Goods': 'FMCG',
    'Healthcare': 'PHARMA',
    'Information Technology': 'IT',
    'Metals & Mining': 'METALS',
    'Oil Gas & Consumable Fuels': 'ENERGY',
    'Power': 'ENERGY',
    'Telecommunication': 'INFRA_MEDIA',
    'Media Entertainment & Publication': 'INFRA_MEDIA',
    'Utilities': 'INFRA_MEDIA',
    'Services': 'INFRA_MEDIA',
    'Diversified': 'INFRA_MEDIA',
    'Forest Materials': 'INFRA_MEDIA',
}

EXPLICIT_OVERRIDES = {
    'CUPID': 'PHARMA', 'STLTECH': 'INFRA_MEDIA', 'MTARTECH': 'CAPGOODS',
    'ATHERENERG': 'AUTO', 'SANSERA': 'AUTO', 'HFCL': 'INFRA_MEDIA',
    'WELCORP': 'METALS', 'LAURUSLABS': 'PHARMA', 'CPPLUS': 'CAPGOODS',
    'RRKABEL': 'CAPGOODS', 'TDPOWERSYS': 'CAPGOODS', 'SKYGOLD': 'CONSDUR',
    'AETHER': 'CHEMICALS', 'FEDERALBNK': 'FINSERV', 'AVALON': 'CAPGOODS',
    'GRWRHITECH': 'CHEMICALS', 'MCX': 'FINSERV', 'SHILPAMED': 'PHARMA',
    'DIACABS': 'CAPGOODS', 'ACUTAAS': 'CHEMICALS', 'DIXON': 'CONSDUR',
    'TRENT': 'CONSDUR', 'POLYCAB': 'CAPGOODS', 'NAUKRI': 'IT',
    'LTTS': 'IT', 'BHARTI': 'INFRA_MEDIA', 'BEL': 'CAPGOODS',
    'HAL': 'CAPGOODS', 'SUNPHAR': 'PHARMA', 'APOLLOH': 'PHARMA',
    'MAXHEAL': 'PHARMA', 'CHOLAF': 'FINSERV', 'TVSMOTO': 'AUTO',
    'BAJAJ_A': 'AUTO', 'HEROMOT': 'AUTO', 'EICHERM': 'AUTO',
    'RELIANCE': 'ENERGY', 'TCS': 'IT', 'INFY': 'IT',
    'HDFCBANK': 'FINSERV', 'ICICIBANK': 'FINSERV', 'SBIN': 'FINSERV',
    'ITC': 'FMCG', 'HINDUNILVR': 'FMCG',
    'LTI': 'IT', 'LTIM': 'IT', 'LTIMINDTRE': 'IT',
    'ADANIENT': 'INFRA_MEDIA', 'ADANIPORTS': 'INFRA_MEDIA',
    'ADANIGREEN': 'INFRA_MEDIA', 'ADANIPOWER': 'INFRA_MEDIA',
    'ATGL': 'ENERGY', 'AWL': 'FMCG',
    'TATAMOTORS': 'AUTO', 'M&M': 'AUTO', 'MARUTI': 'AUTO',
    'BAJAJ-AUTO': 'AUTO', 'EICHERMOT': 'AUTO', 'HEROMOTOCO': 'AUTO',
    'TVSMOTOR': 'AUTO', 'BHARATFORG': 'AUTO', 'SONACOMS': 'AUTO',
    'MOTHERSON': 'AUTO', 'BOSCHLTD': 'AUTO', 'MRF': 'AUTO',
    'APOLLOTYRE': 'AUTO', 'BALKRISIND': 'AUTO', 'CEAT': 'AUTO',
    'EXIDEIND': 'AUTO', 'AMARAJABAT': 'AUTO', 'ARE&M': 'AUTO',
    'UNOMINDA': 'AUTO', 'CRAFTSMAN': 'AUTO', 'ENDURANCE': 'AUTO',
    'SUNPHARMA': 'PHARMA', 'DRREDDY': 'PHARMA', 'DIVISLAB': 'PHARMA',
    'CIPLA': 'PHARMA', 'LUPIN': 'PHARMA', 'AUROPHARMA': 'PHARMA',
    'TORNTPHARM': 'PHARMA', 'ALKEM': 'PHARMA', 'MANKIND': 'PHARMA',
    'ZYDUSLIFE': 'PHARMA', 'BIOCON': 'PHARMA', 'GLENMARK': 'PHARMA',
    'IPCALAB': 'PHARMA', 'AJANTPHARM': 'PHARMA', 'NATCOPHARM': 'PHARMA',
    'GRANULES': 'PHARMA', 'JBCHEPHARM': 'PHARMA', 'GLAND': 'PHARMA',
    'SYNGENE': 'PHARMA', 'APOLLOHOSP': 'PHARMA', 'MAXHEALTH': 'PHARMA',
    'FORTIS': 'PHARMA', 'MEDANTA': 'PHARMA', 'NH': 'PHARMA',
    'METROPOLIS': 'PHARMA', 'LALPATHLAB': 'PHARMA',
    'WIPRO': 'IT', 'HCLTECH': 'IT', 'TECHM': 'IT',
    'PERSISTENT': 'IT', 'COFORGE': 'IT', 'MPHASIS': 'IT',
    'TATATECH': 'IT', 'TATAELXSI': 'IT', 'KPITTECH': 'IT',
    'CYIENT': 'IT', 'BIRLASOFT': 'IT', 'ZENSARTECH': 'IT',
    'SONATSOFTW': 'IT', 'TANLA': 'IT', 'NETWEB': 'IT',
    'NEWGEN': 'IT', 'AURIONPRO': 'IT', 'INTELLECT': 'IT',
    'HAPPSTMNDS': 'IT', 'OFSS': 'IT',
    'KOTAKBANK': 'FINSERV', 'AXISBANK': 'FINSERV',
    'INDUSINDBK': 'FINSERV', 'BANKBARODA': 'FINSERV',
    'PNB': 'FINSERV', 'CANBK': 'FINSERV', 'UNIONBANK': 'FINSERV',
    'IDFCFIRSTB': 'FINSERV', 'BANDHANBNK': 'FINSERV',
    'BAJFINANCE': 'FINSERV', 'BAJAJFINSV': 'FINSERV',
    'CHOLAFIN': 'FINSERV', 'SHRIRAMFIN': 'FINSERV',
    'MUTHOOTFIN': 'FINSERV', 'MANAPPURAM': 'FINSERV',
    'SUNDARMFIN': 'FINSERV', 'LTF': 'FINSERV',
    'POONAWALLA': 'FINSERV', 'LICI': 'FINSERV',
    'HDFCLIFE': 'FINSERV', 'SBILIFE': 'FINSERV',
    'ICICIPRULI': 'FINSERV', 'ICICIGI': 'FINSERV',
    'BSE': 'FINSERV', 'CDSL': 'FINSERV', 'CAMSLTD': 'FINSERV',
    'ANGELONE': 'FINSERV', '360ONE': 'FINSERV',
    'MOTILALOFS': 'FINSERV', 'NAM-INDIA': 'FINSERV',
    'HDFCAMC': 'FINSERV', 'UTIAMC': 'FINSERV',
    'JIOFIN': 'FINSERV', 'CRISIL': 'FINSERV',
    'ICRA': 'FINSERV', 'CAREERP': 'FINSERV',
    'LT': 'CAPGOODS', 'SIEMENS': 'CAPGOODS', 'ABB': 'CAPGOODS',
    'CUMMINSIND': 'CAPGOODS', 'BHEL': 'CAPGOODS',
    'MAZDOCK': 'CAPGOODS', 'COCHINSHIP': 'CAPGOODS',
    'GRSE': 'CAPGOODS', 'BEML': 'CAPGOODS',
    'DATAPATTNS': 'CAPGOODS', 'KAYNES': 'CAPGOODS',
    'SYRMA': 'CAPGOODS', 'ASTRAL': 'CAPGOODS',
    'KEI': 'CAPGOODS', 'HAVELLS': 'CAPGOODS',
    'FINCABLES': 'CAPGOODS', 'THERMAX': 'CAPGOODS',
    'AIAENG': 'CAPGOODS', 'TIMKEN': 'CAPGOODS',
    'SKFINDIA': 'CAPGOODS', 'SCHAEFFLER': 'CAPGOODS',
    'SUZLON': 'CAPGOODS', 'INOXWIND': 'CAPGOODS',
    'CGPOWER': 'CAPGOODS', 'SOLARINDS': 'CAPGOODS', 'ACE': 'CAPGOODS',
    'VOLTAS': 'CONSDUR', 'BLUESTARCO': 'CONSDUR',
    'TITAN': 'CONSDUR', 'KALYANKJIL': 'CONSDUR',
    'SENCO': 'CONSDUR', 'DMART': 'CONSDUR',
    'PAGEIND': 'CONSDUR', 'MANYAVAR': 'CONSDUR',
    'RAYMOND': 'CONSDUR', 'CAMPUS': 'CONSDUR',
    'METROBRAND': 'CONSDUR', 'BATAINDIA': 'CONSDUR',
    'RELAXO': 'CONSDUR', 'WHIRLPOOL': 'CONSDUR',
    'CROMPTON': 'CONSDUR', 'VGUARD': 'CONSDUR',
    'AMBER': 'CONSDUR', 'CELLO': 'CONSDUR',
    'VIPIND': 'CONSDUR', 'ETHOSLTD': 'CONSDUR',
    'INDHOTEL': 'CONSDUR', 'EIHOTEL': 'CONSDUR',
    'CHALET': 'CONSDUR', 'LEMONTREE': 'CONSDUR',
    'TATASTEEL': 'METALS', 'JSWSTEEL': 'METALS',
    'JINDALSTEL': 'METALS', 'SAIL': 'METALS',
    'NMDC': 'METALS', 'COALINDIA': 'METALS',
    'HINDALCO': 'METALS', 'NATIONALUM': 'METALS',
    'VEDL': 'METALS', 'HINDZINC': 'METALS',
    'JSL': 'METALS', 'RATNAMANI': 'METALS', 'APLAPOLLO': 'METALS',
    'MAHLOG': 'INFRA_MEDIA', 'CONCOR': 'INFRA_MEDIA',
    'DELHIVERY': 'INFRA_MEDIA', 'BHARTIARTL': 'INFRA_MEDIA',
    'INDUSTOWER': 'INFRA_MEDIA', 'TATACOMM': 'INFRA_MEDIA',
    'IDEA': 'INFRA_MEDIA', 'TEJASNET': 'INFRA_MEDIA',
    'RAILTEL': 'INFRA_MEDIA', 'ZEEL': 'INFRA_MEDIA',
    'SUNTV': 'INFRA_MEDIA', 'PVRINOX': 'INFRA_MEDIA',
    'SAREGAMA': 'INFRA_MEDIA', 'NTPC': 'INFRA_MEDIA',
    'POWERGRID': 'INFRA_MEDIA', 'TATAPOWER': 'INFRA_MEDIA',
    'JSWENERGY': 'INFRA_MEDIA', 'TORNTPOWER': 'INFRA_MEDIA',
    'NHPC': 'INFRA_MEDIA', 'SJVN': 'INFRA_MEDIA',
    'CESC': 'INFRA_MEDIA',
    'DLF': 'REALTY', 'LODHA': 'REALTY', 'MACROTECH': 'REALTY',
    'GODREJPROP': 'REALTY', 'OBEROIRLTY': 'REALTY',
    'PRESTIGE': 'REALTY', 'BRIGADE': 'REALTY',
    'SOBHA': 'REALTY', 'PHOENIXLTD': 'REALTY',
    'SUNTECK': 'REALTY', 'ULTRACEMCO': 'REALTY',
    'AMBUJACEM': 'REALTY', 'ACC': 'REALTY',
    'DALBHARAT': 'REALTY', 'SHREECEM': 'REALTY',
    'RAMCOCEM': 'REALTY', 'JKCEMENT': 'REALTY',
    'PIDILITIND': 'CHEMICALS', 'SRF': 'CHEMICALS',
    'AARTIIND': 'CHEMICALS', 'FLUOROCHEM': 'CHEMICALS',
    'DEEPAKNTR': 'CHEMICALS', 'TATACHEM': 'CHEMICALS',
    'ATUL': 'CHEMICALS', 'VINATIORGA': 'CHEMICALS',
    'CLEAN': 'CHEMICALS', 'NAVINFLUOR': 'CHEMICALS',
    'PIIND': 'CHEMICALS', 'UPL': 'CHEMICALS',
    'COROMANDEL': 'CHEMICALS', 'CHAMBLFERT': 'CHEMICALS',
    'GNFC': 'CHEMICALS', 'GSFC': 'CHEMICALS', 'SUMICHEM': 'CHEMICALS',
    'ONGC': 'ENERGY', 'OIL': 'ENERGY', 'BPCL': 'ENERGY',
    'IOC': 'ENERGY', 'HINDPETRO': 'ENERGY', 'GAIL': 'ENERGY',
    'PETRONET': 'ENERGY', 'IGL': 'ENERGY', 'MGL': 'ENERGY',
    'GUJGASLTD': 'ENERGY', 'CASTROLIND': 'ENERGY',
    'MRPL': 'ENERGY', 'CHENNPETRO': 'ENERGY',
    'NESTLEIND': 'FMCG', 'BRITANNIA': 'FMCG',
    'DABUR': 'FMCG', 'MARICO': 'FMCG',
    'GODREJCP': 'FMCG', 'COLPAL': 'FMCG',
    'VBL': 'FMCG', 'TATACONSUM': 'FMCG',
    'EMAMILTD': 'FMCG', 'BIKAJI': 'FMCG',
    'BECTORFOOD': 'FMCG', 'JYOTHYLAB': 'FMCG',
    'RADICO': 'FMCG', 'UNITDSPR': 'FMCG', 'UBL': 'FMCG',
}

def get_session():
    """Get HTTP session, trying curl_cffi first with requests fallback."""
    try:
        from curl_cffi import requests
        return requests.Session(impersonate="chrome")
    except ImportError:
        import requests
        return requests.Session()

def classify_symbol(symbol: str, company_name: str = '') -> str:
    """Fallback classification for unknown industries based on keywords."""
    text = f"{symbol} {company_name}".upper()
    
    if any(k in text for k in ['BANK', 'FINANCE', 'FINANCIAL', 'INSURANCE', 'CAPITAL', 'WEALTH', 'ASSET']):
        return 'FINSERV'
    if any(k in text for k in ['PHARMA', 'HEALTH', 'HOSPITAL', 'LIFE', 'BIO', 'MED', 'DRUGS']):
        return 'PHARMA'
    if any(k in text for k in ['TECH', 'INFOTECH', 'SOFTWARE', 'IT ', 'COMPUTERS']):
        return 'IT'
    if any(k in text for k in ['CHEM', 'FERTILIZER', 'POLYMER', 'PLASTIC']):
        return 'CHEMICALS'
    if any(k in text for k in ['MOTOR', 'AUTO', 'TYRE', 'WHEEL']):
        return 'AUTO'
    if any(k in text for k in ['STEEL', 'IRON', 'MINING', 'ALUMINIUM', 'METAL']):
        return 'METALS'
    if any(k in text for k in ['OIL', 'PETRO', 'GAS', 'ENERGY']):
        return 'ENERGY'
    if any(k in text for k in ['FOOD', 'BEVERAGE', 'AGRO', 'DAIRY']):
        return 'FMCG'
    if any(k in text for k in ['REALTY', 'REAL ESTATE', 'CONSTRUCTION', 'CEMENT', 'BUILD']):
        return 'REALTY'
    if any(k in text for k in ['JEWEL', 'FOOTWEAR', 'RETAIL', 'FASHION']):
        return 'CONSDUR'
    if any(k in text for k in ['TELECOM', 'MEDIA', 'POWER', 'ENTERTAINMENT', 'BROADCAST']):
        return 'INFRA_MEDIA'
        
    return 'CAPGOODS' # Default fallback

def sync_nse_sectors(base_dir: Optional[Path] = None) -> Dict[str, str]:
    """
    Downloads NSE industry data, builds symbol->sector mapping, 
    merges with DB universe, and exports to JSON.
    """
    if base_dir is None:
        from pydroid_core.data_engine import get_base_dir
        base_dir = get_base_dir()
    else:
        base_dir = Path(base_dir)
        
    raw_dir = base_dir / 'data' / 'raw_reference'
    raw_dir.mkdir(parents=True, exist_ok=True)
    
    files_to_sync = [
        ("ind_niftytotalmarket_list.csv", "https://www.niftyindices.com/IndexConstituent/ind_niftytotalmarket_list.csv"),
        ("ind_nifty500list.csv", "https://www.niftyindices.com/IndexConstituent/ind_nifty500list.csv"),
    ]
    
    session = get_session()
    for fname, url in files_to_sync:
        csv_path = raw_dir / fname
        logger.info(f"Downloading NSE Index list: {fname} from {url}")
        try:
            response = session.get(url, timeout=15)
            response.raise_for_status()
            csv_path.write_bytes(response.content)
            logger.info(f"Successfully downloaded {fname} ({len(response.content):,} bytes)")
        except Exception as e:
            logger.warning(f"Session download failed for {fname} ({e}). Trying urllib fallback...")
            try:
                req = urllib.request.Request(
                    url, 
                    headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
                )
                with urllib.request.urlopen(req) as response:
                    csv_path.write_bytes(response.read())
                logger.info(f"Fallback download succeeded for {fname}")
            except Exception as e_url:
                logger.error(f"Fallback download failed for {fname}: {e_url}")
                if not csv_path.exists():
                    logger.warning(f"No cached version of {fname} available.")

    # Parse downloaded NSE mappings (Total Market + Nifty 500)
    nse_map = {}
    for fname, _ in files_to_sync:
        fpath = raw_dir / fname
        if not fpath.exists():
            continue
        with open(fpath, 'r', encoding='utf-8', errors='ignore') as f:
            reader = csv.DictReader(f)
            for row in reader:
                symbol = row.get('Symbol', '').strip()
                industry = row.get('Industry', '').strip()
                company = row.get('Company Name', '').strip()
                if not symbol:
                    continue
                if industry in INDUSTRY_TO_SECTOR:
                    nse_map[symbol] = INDUSTRY_TO_SECTOR[industry]
                elif symbol not in nse_map:
                    nse_map[symbol] = classify_symbol(symbol, company)

    # Get Universe symbols
    logger.info("Fetching universe symbols from database...")
    universe_symbols = []
    try:
        from pydroid_core.data_engine import get_connection
        conn = get_connection(read_only=True)
        cursor = conn.cursor()
        cursor.execute('SELECT DISTINCT symbol FROM prices ORDER BY symbol;')
        universe_symbols = [row[0] for row in cursor.fetchall()]
    except Exception as e:
        logger.warning(f"Could not load universe from db: {e}")
        # If DB query fails for any reason, at least export what we have + overrides
        universe_symbols = list(set(list(nse_map.keys()) + list(EXPLICIT_OVERRIDES.keys())))
        
    logger.info(f"Loaded {len(universe_symbols)} symbols from universe.")

    # Build final map
    final_map = {}
    sector_counts = {s: 0 for s in PRIMARY_SECTORS}
    
    for symbol in universe_symbols:
        if symbol in EXPLICIT_OVERRIDES:
            sector = EXPLICIT_OVERRIDES[symbol]
        elif symbol in nse_map:
            sector = nse_map[symbol]
        else:
            sector = classify_symbol(symbol)
            
        final_map[symbol] = sector
        if sector in sector_counts:
            sector_counts[sector] += 1
        else:
            sector_counts[sector] = 1

    # Export to JSON
    json_path = base_dir / 'data' / 'symbol_sector_map.json'
    json_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(final_map, f, indent=2, sort_keys=True)
        
    logger.info(f"Successfully mapped {len(final_map)} symbols to sectors.")
    logger.info("Sector Distribution:")
    for sector, count in sorted(sector_counts.items()):
        logger.info(f"  {sector}: {count}")
        
    return final_map

if __name__ == '__main__':
    sync_nse_sectors()
