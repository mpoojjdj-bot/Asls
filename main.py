import asyncio, base64, os, re
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

app = FastAPI(title='Moonlight Reflection Perchance Bridge')
app.add_middleware(CORSMiddleware, allow_origins=['*'], allow_credentials=False, allow_methods=['*'], allow_headers=['*'])

class GenerateRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=4000)
    resolution: str = '512x512'
    seed: int | None = None
    guidance_scale: float = 7
    remove_background: bool = False
    timeout: int = 180

@app.get('/health')
def health():
    return {'ok': True, 'service': 'Moonlight Reflection Perchance bridge'}

@app.post('/api/generate')
async def generate(req: GenerateRequest):
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=['--no-sandbox'])
            page = await browser.new_page(viewport={'width': 1280, 'height': 900})
            try:
                await page.goto('https://perchance.org/ai-text-to-image-generator', wait_until='domcontentloaded', timeout=60000)
                await page.wait_for_timeout(2500)
                textareas = page.locator('textarea')
                if await textareas.count() == 0:
                    raise HTTPException(502, 'لم يظهر حقل الوصف في Perchance؛ قد يكون الموقع طلب تحققًا أو غيّر واجهته.')
                await textareas.first.fill(req.prompt)
                buttons = page.get_by_role('button', name=re.compile('generate|create|توليد', re.I))
                if await buttons.count() == 0:
                    raise HTTPException(502, 'لم أجد زر التوليد في Perchance؛ ربما تغيّرت الواجهة.')
                before = set(await page.locator('img').evaluate_all("els => els.map(e => e.currentSrc || e.src).filter(Boolean)"))
                await buttons.first.click()
                deadline = asyncio.get_event_loop().time() + min(max(req.timeout, 30), 240)
                while asyncio.get_event_loop().time() < deadline:
                    await page.wait_for_timeout(1500)
                    imgs = await page.locator('img').evaluate_all("els => els.map(e => ({src:e.currentSrc||e.src, complete:e.complete, width:e.naturalWidth})).filter(x => x.src && x.complete && x.width > 64)")
                    for item in reversed(imgs):
                        src = item['src']
                        if src not in before and not src.startswith('data:image/svg'):
                            response = await page.request.get(src, timeout=30000)
                            if response.ok:
                                raw = await response.body()
                                mime = response.headers.get('content-type', 'image/png').split(';')[0]
                                if mime.startswith('image/') and raw:
                                    return {'image': f'data:{mime};base64,' + base64.b64encode(raw).decode()}
                body = (await page.locator('body').inner_text())[:1000]
                if re.search(r'cloudflare|turnstile|verify you are human|captcha', body, re.I):
                    raise HTTPException(503, 'Perchance طلب تحققًا أمنيًا. لم يتم تجاوز التحقق؛ افتح Perchance في Safari وتحقق يدويًا.')
                raise HTTPException(504, 'انتهت مهلة انتظار الصورة. لم يرجع Perchance صورة جديدة.')
            finally:
                await browser.close()
    except HTTPException:
        raise
    except PlaywrightTimeoutError:
        raise HTTPException(504, 'انتهت مهلة الاتصال بـ Perchance.')
    except Exception as e:
        raise HTTPException(502, f'تعذر الاتصال بـ Perchance: {str(e)[:300]}')
