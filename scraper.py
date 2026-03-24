import time
import re
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from playwright.sync_api import sync_playwright
import tkinter as tk
from tkinter import ttk
from tkinter import messagebox
import tkintermapview

# --- CONFIGURATION ---
SHEET_NAME = "Mures_Cégek"
LOCATION_FIX = "Târgu Mureș"

def setup_google_sheets():
    lbl_status.config(text="Resetting Sheet...")
    root.update_idletasks() 
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
    client = gspread.authorize(creds)
    sheet = client.open(SHEET_NAME).sheet1
    sheet.clear()
    # A Reviews oszlop törölve, marad a többi fontos adat
    sheet.append_row(["Business Name", "Category", "Address", "Phone", "Website", "Rating", "Status"])
    return sheet

def run_single_category(page, lat, lng, zoom, search_term):
    query = f"{search_term} {LOCATION_FIX}"
    url = f"https://www.google.com/maps/search/{query}/@{lat},{lng},{zoom}z"
    page.goto(url)
    page.wait_for_timeout(5000)
    
    try:
        page.locator("button:has-text('Accept'), button:has-text('Acceptă'), button:has-text('Összes elfogadása')").first.click(timeout=3000)
    except: pass

    for _ in range(3):
        page.mouse.wheel(0, 3000)
        page.wait_for_timeout(1000)

    links = page.locator("a[href*='/maps/place/']").all()
    urls = [link.get_attribute("href") for link in links if link.get_attribute("href")]
    return list(dict.fromkeys(urls))

def start_scrape_process():
    cat_selection = combo_category.get()
    lat, lng = map_widget.get_position()
    zoom = map_widget.zoom
    
    try:
        sheet = setup_google_sheets()
        tasks = {"Restaurant": "restaurant", "IT Company": "it_company", "Car Service": "service auto", "Cafe": "cafenea"} if cat_selection == "--- ALL BUSINESSES (Smart) ---" else {cat_selection: CATEGORIES_DICT[cat_selection]}

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            
            all_urls = []
            for label, term in tasks.items():
                lbl_status.config(text=f"Searching: {label}")
                root.update_idletasks()
                found = run_single_category(page, lat, lng, zoom, term)
                for u in found: all_urls.append((u, label))

            total = len(all_urls)
            for i, (url, original_cat) in enumerate(all_urls):
                lbl_status.config(text=f"Analyzing {i+1}/{total}")
                progress_bar["value"] = ((i+1) / total) * 100
                root.update_idletasks()

                try:
                    page.goto(url)
                    page.wait_for_timeout(4000)
                    
                    name = page.locator("h1").inner_text() if page.locator("h1").count() > 0 else "N/A"
                    addr = page.locator("button[data-item-id='address']").inner_text() if page.locator("button[data-item-id='address']").count() > 0 else "N/A"
                    phone = page.locator("button[data-item-id^='phone:tel:']").inner_text() if page.locator("button[data-item-id^='phone:tel:']").count() > 0 else "N/A"
                    
                    web = "MISSING"
                    web_loc = page.locator("a[data-item-id='authority']")
                    if web_loc.count() > 0: web = web_loc.get_attribute("href") or "MISSING"

                    # Csak a Rating (csillag) kinyerése
                    stars = 0.0
                    try:
                        rating_block = page.locator('div.F7nice').first
                        rating_text = rating_block.get_attribute("aria-label") or rating_block.inner_text()
                        if rating_text:
                            # Megkeressük az első tizedes számot (pl 4.6 vagy 4,6)
                            nums = re.findall(r"\d+[\.,]\d+|\d+", rating_text)
                            if len(nums) >= 1:
                                stars = float(nums[0].replace(",", "."))
                    except: pass

                    status = "Website Found" if web != "MISSING" else "No Website"

                    # Mentés Reviews oszlop nélkül
                    sheet.append_row([name, original_cat, addr, phone, web, stars, status])
                except: continue

            browser.close()
            lbl_status.config(text="Finished!")
            messagebox.showinfo("Success", "Scraping completed! Table updated without Reviews.")

    except Exception as e:
        messagebox.showerror("Error", str(e))

# --- UI ---
CATEGORIES_DICT = {
    "--- ALL BUSINESSES (Smart) ---": "multi",
    "Restaurant": "restaurant", "IT Company": "it_company", "Car Service": "service auto", "Cafe": "cafenea"
}

root = tk.Tk(); root.title("Business Scraper v24 - Clean Edition"); root.geometry("600x750")
map_widget = tkintermapview.TkinterMapView(root, width=550, height=350)
map_widget.set_tile_server("https://mt0.google.com/vt/lyrs=m&hl=en&x={x}&y={y}&z={z}&s=Ga")
map_widget.pack(pady=10); map_widget.set_position(46.54245, 24.55747); map_widget.set_zoom(15)
combo_category = ttk.Combobox(root, values=list(CATEGORIES_DICT.keys()), width=40)
combo_category.pack(pady=10); combo_category.set(list(CATEGORIES_DICT.keys())[0])
btn_start = tk.Button(root, text="START SCRAPE", command=start_scrape_process, bg="#2c3e50", fg="white", font=("Arial", 11, "bold"))
btn_start.pack(pady=10)
lbl_status = tk.Label(root, text="Ready", fg="gray"); lbl_status.pack()
progress_bar = ttk.Progressbar(root, length=500, mode="determinate"); progress_bar.pack(pady=10)
root.mainloop()