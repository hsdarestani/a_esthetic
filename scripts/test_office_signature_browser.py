"""Browser smoke for the Office intake on an isolated Django test server.

Never submits patient information. Tests German dates, hidden-step signature
canvas sizing, mouse drawing, and clearing with real Chromium.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright

URL = "http://127.0.0.1:8000/office/"


def run():
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page(locale="en-US", viewport={"width": 1150, "height": 880})
        errors = []
        page.on("pageerror", lambda err: errors.append(str(err)))
        page.goto(URL, wait_until="domcontentloaded")
        date = page.locator("#birthDateGerman")
        assert date.count() == 1, "German birthdate input not rendered"
        assert date.get_attribute("placeholder") == "TT.MM.JJJJ"
        assert date.get_attribute("type") == "text", "Birthdate should not depend on Chrome's US locale"

        page.locator('[name="first_name"]').fill("Synthetic")
        page.locator('[name="last_name"]').fill("BrowserTest")
        date.fill("15.03.1990")
        page.locator('[name="street"]').fill("Musterstrasse 1")
        page.locator('[name="postal_code"]').fill("60313")
        page.locator('[name="city"]').fill("Frankfurt")
        page.locator('[name="email"]').fill("never-submit@example.invalid")
        page.locator('[name="phone"]').fill("+491701234567")
        next_button = page.locator("[data-next]")
        next_button.click()
        assert page.locator(".step.active").get_attribute("data-step") == "1"
        assert page.locator(".step.active input:checked").count() == 0
        next_button.click()
        assert page.locator(".step.active").get_attribute("data-step") == "1"
        for field in ("allergies", "medications", "surgeries", "smoking", "alcohol"):
            page.locator(f'input[name="{field}"][value="Nein"]').check()
        page.locator('input[name="pregnancy"][value="Nicht zutreffend"]').check()
        page.locator('input[name="diseases"][value="Keine"]').check()

        for expected in ("2", "3"):
            page.locator("[data-next]").click()
            page.wait_for_function(
                "(step) => document.querySelector('.step.active')?.dataset.step === step",
                arg=expected,
            )
        canvas = page.locator("#signaturePad")
        page.wait_for_function("""() => {
          const c=document.querySelector('#signaturePad'),r=c.getBoundingClientRect(),dpr=Math.min(window.devicePixelRatio||1,2);
          return r.width>350 && c.width===Math.round(r.width*dpr) && c.height===Math.round(r.height*dpr);
        }""")
        size = page.evaluate("""() => {
          const c=document.querySelector('#signaturePad');
          return {w:c.width,h:c.height,rect:c.getBoundingClientRect().width};
        }""")
        assert size["w"] >= 350 and size["h"] >= 100, f"Canvas not matched to visible size: {size}"
        bbox = canvas.bounding_box()
        assert bbox is not None
        x, y = bbox["x"] + 25, bbox["y"] + 45
        page.mouse.move(x, y)
        page.mouse.down()
        page.mouse.move(x + 95, y + 17, steps=10)
        page.mouse.move(x + 180, y + 5, steps=8)
        page.mouse.up()
        marked = page.evaluate("""() => {
          const c=document.querySelector('#signaturePad');
          const pixels=c.getContext('2d').getImageData(0,0,c.width,c.height).data;
          let count=0;for(let i=3;i<pixels.length;i+=4)if(pixels[i])count++;
          return count;
        }""")
        assert marked > 25, f"Signature ink missing (nontransparent pixels={marked})"
        page.locator("#clearSignature").click()
        blank = page.evaluate("""() => {
          const c=document.querySelector('#signaturePad');
          const pixels=c.getContext('2d').getImageData(0,0,c.width,c.height).data;
          let count=0;for(let i=3;i<pixels.length;i+=4)if(pixels[i])count++;
          return count;
        }""")
        assert blank == 0, f"Signature clearing failed: {blank} pixels remain"
        assert not errors, f"Unexpected browser errors: {errors}"
        print(f"PASS: Chrome en-US displayed TT.MM.JJJJ and visible signature canvas {size['w']}x{size['h']}, {marked} ink pixels, cleared cleanly; NO SUBMISSION")
        browser.close()


if __name__ == "__main__":
    run()
