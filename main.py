from playwright.sync_api import sync_playwright
import google.generativeai as genai
import os
import time
import json
import gspread
import hashlib
from dotenv import load_dotenv
from oauth2client.service_account import ServiceAccountCredentials
import requests # Add this import

# === Load environment variables and API keys ===
load_dotenv()
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

# === Setup Google Sheet ===
scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
creds = ServiceAccountCredentials.from_json_keyfile_name("service_account.json", scope)
client = gspread.authorize(creds)
sheet = client.open("Swiggy Zomato Dashboard").worksheet("swiggy_review") # Swiggy review input sheet

# === Brand List ===
BRAND_NAMES = [
    "Frosty Crumble",
    "Frosty Crumble By Art Of Delight",
    "Art Of Delight - Crafted Ice Creams And Desserts"
]

# === Utils ===
def generate_review_hash(parsed_review: dict) -> str:
    # Use Order ID as the primary key for deduplication, fallback to empty if missing
    order_id = parsed_review.get("Order ID", "").strip()
    timestamp = parsed_review.get("Timestamp", "").strip()
    unique_str = order_id if order_id else timestamp  # Prioritize Order ID, use Timestamp as fallback
    return hashlib.sha256(unique_str.encode('utf-8')).hexdigest()

def scroll_reviews(frame, max_scrolls=100):
    print("🔽 Scrolling to load all review cards...")
    for _ in range(max_scrolls):
        try:
            frame.evaluate("""
                const container = document.querySelector('[class*="sc-khLCKb"]');
                if (container) container.scrollBy(0, 500);
            """)
            time.sleep(0.4)
        except:
            break

def extract_entire_visible_text(frame):
    try:
        return frame.locator("body").inner_text().strip()
    except Exception as e:
        print(f"⚠️ Failed to extract text: {e}")
        return ""

def parse_review_with_gemini(raw_text):
    prompt = f"""
You are an expert at parsing customer review text from Swiggy's partner portal. Parse the text by starting from the bottom and working upward, stopping at the first occurrence of an Order ID (a string starting with '#'). Extract the following fields based solely on the text within this range (from the bottom up to and including the first Order ID), ignoring all data from reviews above this Order ID:

Required Fields (must always be present):
- Order ID: The first string starting with '#' found from the bottom upward.
- Timestamp: The date and time (e.g., 'Jul 19, 10:59 PM') closest to and below the Order ID within the same review range.
- Outlet: The location name immediately following "Orders & Complaints are based on the last 90 days" within the same review range.
- Item Ordered: The item name(s) (e.g., 'Nostalgia Ice Cream Sandwiches - Pack Of 4') listed closest to and below the Order ID within the same review.

Optional Fields (include only if found within the same bottom-to-top range for the identified Order ID):
- Rating: A single digit (e.g., '4') indicating the customer rating within the same review.
- Status: Either 'UNRESOLVED' or 'EXPIRED' if present within the same review.
- Customer Name: The first name appearing immediately below the Order ID within the defined range, ignoring any names from reviews above the Order ID (e.g., ignore 'Abhishek Eswarappa' if it appears above). If no name is found below the Order ID in this range, leave it empty.
- Customer Info: Text including 'New Customer' or 'Repeat Customer' with a date (e.g., 'New Customer | Sunday, Jul 20, 2025') within the same review.
- Total Orders (90d): The number next to 'Orders 🍛' within the same review.
- Order Value (90d): The amount Below Bill Total.
- Complaints (90d): The number next to 'Complaints ⚠️' within the same review.
- Delivery Remark: Text indicating delivery status (e.g., 'This order was delivered on time') within the same review.

Instructions:
- Begin parsing from the bottom of the text and stop at the first Order ID encountered (e.g., '#21191574063-9546'). Include only the text below and up to this Order ID in the parsing range, completely disregarding any text or names (e.g., 'Abhishek Eswarappa') from reviews above this Order ID.
- For Customer Name, select only the first name that appears directly below the Order ID within this range. Do not consider names from prior reviews or text above the Order ID. If no name is found below the Order ID, set Customer Name to an empty string.
- Return the result as a compact JSON object. Do NOT use markdown or code block wrappers.
- If a required field is missing, use an empty string ("").
- For debugging, include a string field named "debug_context" with the 5 lines of text immediately surrounding the Order ID to verify the parsing range and name selection.

Review Text:
{raw_text}
"""
    try:
        model = genai.GenerativeModel('gemini-1.5-flash') # Using the recommended model
        response = model.generate_content(
            [{"role": "user", "parts": [prompt]}],
            generation_config={"temperature": 0}
        )

        raw_content = response.text.strip()
        cleaned = raw_content.replace("```json", "").replace("```", "").strip()
        parsed_data = json.loads(cleaned)
        return parsed_data

    except json.JSONDecodeError as e:
        print(f"⚠️ Failed to parse response as JSON: {e}")
        print("Raw Response:", raw_content)
        return None
    except Exception as e:
        print(f"⚠️ Gemini API error: {e}")
        return None

def append_to_sheet(parsed_review, seen_hashes):
    try:
        item_ordered = parsed_review.get("Item Ordered", "")
        if isinstance(item_ordered, list):
            item_ordered = ", ".join(item_ordered)

        order_id = parsed_review.get("Order ID", "").strip()
        if not order_id:
            print("⚠️ Skipping append: No valid Order ID found.")
            return

        review_hash = generate_review_hash(parsed_review)
        if review_hash in seen_hashes:
            print(f"⏭️ Duplicate review detected. Hash: {review_hash}, Existing Hashes: {seen_hashes}")
            return

        row = [
            parsed_review.get("Order ID", ""),
            parsed_review.get("Timestamp", ""),
            parsed_review.get("Outlet", ""),
            item_ordered,
            parsed_review.get("Rating", ""),
            parsed_review.get("Status", ""),
            parsed_review.get("Customer Name", ""),
            parsed_review.get("Customer Info", ""),
            parsed_review.get("Total Orders (90d)", ""),
            parsed_review.get("Order Value (90d)", ""),
            parsed_review.get("Complaints (90d)", ""),
            parsed_review.get("Delivery Remark", ""),
        ]
        sheet.append_row(row, value_input_option="USER_ENTERED")
        seen_hashes.add(review_hash)

        print("📤 Structured row appended to sheet:")
        print(row)
    except Exception as e:
        print(f"⚠️ Failed to write structured row to Google Sheet: {e}")

def click_and_extract_reviews(page):
    frame = page.frames[1]
    scroll_reviews(frame)

    print("📊 Loading existing reviews from sheet for deduplication...")
    existing_rows = sheet.get_all_values()[1:]  # Skip header
    seen_hashes = set()
    for row in existing_rows:
        oid = row[0].strip() if len(row) > 0 else ""
        ts = row[1].strip() if len(row) > 1 else ""
        if oid:
            review_hash = generate_review_hash({"Order ID": oid, "Timestamp": ts})
            seen_hashes.add(review_hash)

    expired = frame.locator("text=EXPIRED").all()
    unresolved = frame.locator("text=UNRESOLVED").all()
    all_labels = expired + unresolved
    print(f"🧾 Found {len(all_labels)} review labels")

    for idx, label in enumerate(all_labels):
        try:
            print(f"\n➡️ Clicking review label {idx + 1}...")
            label.click()
            time.sleep(2.5)

            full_text = extract_entire_visible_text(frame)
            print("📋 Raw Review Text Extracted")
            print("-" * 60)
            print(full_text[-1500:])
            print("-" * 60)

            parsed = parse_review_with_gemini(full_text)
            if parsed:
                if not parsed.get("Order ID", "").strip():
                    print("⚠️ Skipping review: No valid Order ID found.")
                    continue
                
                key_map = {
                    "OrderID": "Order ID",
                    "Timestamp": "Timestamp",
                    "Outlet": "Outlet",
                    "ItemOrdered": "Item Ordered",
                    "Rating": "Rating",
                    "Status": "Status",
                    "CustomerName": "Customer Name",
                    "CustomerInfo": "Customer Info",
                    "TotalOrders90d": "Total Orders (90d)",
                    "OrderValue90d": "Order Value (90d)",
                    "Complaints90d": "Complaints (90d)",
                    "DeliveryRemark": "Delivery Remark"
                }
                parsed = {key_map.get(k, k): v for k, v in parsed.items()}
                print("✅ Parsed Review:")
                print(json.dumps(parsed, indent=2))
                append_to_sheet(parsed, seen_hashes)
            else:
                print("❌ Skipped due to parsing error.")
        except Exception as e:
            print(f"⚠️ Error clicking or extracting review {idx + 1}: {e}")
        time.sleep(1)

def main():
    # Apps Script Web App URL - REPLACED WITH YOUR PROVIDED URL!
    SWIGGY_MATCH_GAS_WEB_APP_URL = "https://script.google.com/macros/s/AKfycbyHt37GPrtXQ64aYwNCz5huxX0wKHCysB4T1xf5M6Jfdl8DqEXQU3CvcAtVgJMqNwWtmQ/exec" 

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-gpu"])
        context = browser.new_context(storage_state="swiggy_login.json")
        page = context.new_page()

        for brand in BRAND_NAMES:
            print(f"\n🌐 Opening Swiggy Ratings for: {brand}")
            try:
                page.goto("https://partner.swiggy.com/business-metrics/customer-ratings", timeout=60000)
                page.wait_for_load_state("networkidle")

                try:
                    popup = page.locator("text=No! Not needed").first
                    if popup.is_visible():
                        popup.click()
                        print("✅ Closed popup")
                except:
                    pass

                iframe = page.frame_locator("iframe").first
                iframe.locator("input").first.fill(brand)
                time.sleep(2)
                iframe.locator(f"text={brand}").first.click()
                iframe.locator("text=Continue").first.click()
                print("✅ Brand selected and continued")
                time.sleep(5)

                click_and_extract_reviews(page)

            except Exception as e:
                print(f"❌ Error processing brand '{brand}': {e}")
            print("🔁 Moving to next brand...\n")
            time.sleep(2)

        browser.close()
        print("✅ Swiggy scraping complete.")

        # --- Call the Google Apps Script Web App after scraping ---
        print("\n📞 Triggering Swiggy review matching via Google Apps Script...")
        if SWIGGY_MATCH_GAS_WEB_APP_URL == "": # Added an explicit check for empty string
            print("⚠️ WARNING: SWIGGY_MATCH_GAS_WEB_APP_URL is not set. Cannot trigger Apps Script.")
            print("Please deploy your Apps Script as a Web App and paste its URL into the Python code.")
        else:
            try:
                # Make a GET request to the deployed Apps Script URL
                response = requests.get(SWIGGY_MATCH_GAS_WEB_APP_URL)
                response.raise_for_status() # Raise an exception for HTTP errors (4xx or 5xx)
                
                # Apps Script returns JSON, so parse it
                gas_response = response.json() 
                if gas_response.get('success'):
                    print(f"✅ Apps Script triggered successfully. Message: {gas_response.get('message')}")
                else:
                    print(f"❌ Apps Script reported an error. Error: {gas_response.get('error')}")
                    print(f"Raw Apps Script response: {response.text}") # For debugging
            except requests.exceptions.RequestException as e:
                print(f"❌ Error triggering Apps Script: {e}")
                # Try to print response text even if an HTTP error occurred
                if 'response' in locals() and response.text:
                    print(f"Raw Apps Script response (on error): {response.text}")
            except json.JSONDecodeError:
                print(f"❌ Could not decode JSON from Apps Script response. Raw: {response.text}")


        print("✅ All processes completed.")

if __name__ == "__main__":
    main()