#!/usr/bin/env python3
"""Capture frames of a real chat session on the running SQL Assistant app,
then assemble them into a demo GIF.

Requires: backend on :2024 and frontend on :5173 running.
Frames are written to /tmp/demo_frames/frame_XXXX.png
"""
import asyncio, pathlib
from playwright.async_api import async_playwright

QUESTION = (
    "Quel est le département avec le plus grand nombre d'arrêts dans la table "
    "downtime ? Donne le nombre et la durée moyenne."
)

OUT = pathlib.Path("/tmp/demo_frames")
OUT.mkdir(exist_ok=True)
# clean old frames
for f in OUT.glob("*.png"):
    f.unlink()

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={"width": 1200, "height": 820})
        await page.goto("http://localhost:5173", wait_until="networkidle")
        await page.wait_for_timeout(800)

        idx = 0
        def snap(name=""):
            nonlocal idx
            idx += 1
            return OUT / f"frame_{idx:04d}.png"

        # 1. empty state
        await page.screenshot(path=str(snap("empty")))

        # 2. type the question
        input_sel = 'input[type="text"]'
        await page.click(input_sel)
        await page.fill(input_sel, QUESTION)
        await page.screenshot(path=str(snap("typed")))

        # 3. submit (Enter) and capture during streaming
        await page.keyboard.press("Enter")
        # capture ~30 frames over ~18s to catch streaming + final answer
        for i in range(30):
            await page.wait_for_timeout(600)
            await page.screenshot(path=str(snap("stream")))

        await browser.close()
        print(f"FRAMES={idx} in {OUT}")

asyncio.run(main())
