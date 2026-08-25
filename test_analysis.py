import asyncio
from app.api.routes.analysis import run_analysis_endpoint, RunAnalysisParams

async def main():
    params = RunAnalysisParams(symbol="RELIANCE", timeframe="15m", mode="all")
    try:
        res = await run_analysis_endpoint(params)
        print("Success")
    except Exception as e:
        import traceback
        traceback.print_exc()

asyncio.run(main())
