#!/usr/bin/env python3

import tkinter as tk
from tkinter import ttk, messagebox
import requests
import csv
import json
import os
from typing import Dict, List, Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class PhoenixAuctionAssistant:
    def __init__(self, root):
        self.root = root
        self.root.title("Phoenix Auction Assistant")
        self.root.geometry("600x500")
        
        # Load eBay API credentials
        self.ebay_client_id = os.getenv('EBAY_CLIENT_ID')
        self.ebay_client_secret = os.getenv('EBAY_CLIENT_SECRET')
        self.ebay_environment = os.getenv('EBAY_ENVIRONMENT', 'SANDBOX')
        self.ebay_access_token = None
        
        self.setup_gui()
        self.load_parts_list()
    
    def setup_gui(self):
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        ttk.Label(main_frame, text="VIN:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.vin_entry = ttk.Entry(main_frame, width=30)
        self.vin_entry.grid(row=0, column=1, padx=5, pady=5)
        
        self.calculate_btn = ttk.Button(main_frame, text="Calculate Bid", 
                                       command=self.calculate_bid)
        self.calculate_btn.grid(row=0, column=2, padx=5, pady=5)
        
        self.results_text = tk.Text(main_frame, height=25, width=70)
        self.results_text.grid(row=1, column=0, columnspan=3, pady=10)
        
        scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=self.results_text.yview)
        scrollbar.grid(row=1, column=3, sticky="ns")
        self.results_text.configure(yscrollcommand=scrollbar.set)
    
    def load_parts_list(self):
        try:
            with open('parts_list.csv', 'r') as file:
                reader = csv.DictReader(file)
                self.parts_list = []
                for row in reader:
                    if row['search_query'] and row['category_id']:
                        self.parts_list.append({
                            'search_query': row['search_query'],
                            'category_id': row['category_id'],
                            'min_price': float(row.get('min_price', 0))
                        })
        except FileNotFoundError:
            self.parts_list = [
                {"search_query": "engine", "category_id": "33615"},
                {"search_query": "transmission", "category_id": "33616"},
                {"search_query": "alternator", "category_id": "33555"}
            ]
    
    def decode_vin(self, vin: str) -> Optional[Dict]:
        url = f"https://vpic.nhtsa.dot.gov/api/vehicles/decodevin/{vin}?format=json"
        
        # Try 3 times with increasing timeout
        for attempt in range(3):
            try:
                timeout = 15 + (attempt * 10)  # 15s, 25s, 35s
                self.results_text.insert(tk.END, f"VIN decode attempt {attempt + 1} (timeout: {timeout}s)...\n")
                self.root.update()
                
                response = requests.get(url, timeout=timeout)
                response.raise_for_status()
                
                data = response.json()
                if data.get('Results'):
                    vehicle_info = {}
                    for result in data['Results']:
                        if result['Variable'] == 'Make':
                            vehicle_info['make'] = result['Value']
                        elif result['Variable'] == 'Model':
                            vehicle_info['model'] = result['Value']
                        elif result['Variable'] == 'Model Year':
                            vehicle_info['year'] = result['Value']
                    
                    if all(v for v in vehicle_info.values()):
                        self.results_text.insert(tk.END, f"VIN decoded successfully!\n")
                        self.root.update()
                        return vehicle_info
                        
            except Exception as e:
                self.results_text.insert(tk.END, f"Attempt {attempt + 1} failed: {str(e)}\n")
                self.root.update()
                if attempt == 2:  # Last attempt
                    self.display_error(f"VIN decode failed after 3 attempts: {str(e)}")
                    return None
    
    def get_ebay_access_token(self) -> bool:
        self.results_text.insert(tk.END, "Authenticating with eBay...\n")
        self.root.update()
        
        # Reload credentials in case .env was updated
        load_dotenv(override=True)
        self.ebay_client_id = os.getenv('EBAY_CLIENT_ID')
        self.ebay_client_secret = os.getenv('EBAY_CLIENT_SECRET')
        self.ebay_environment = os.getenv('EBAY_ENVIRONMENT', 'SANDBOX')
        
        if not self.ebay_client_id or not self.ebay_client_secret:
            self.display_error("eBay credentials not found in .env file")
            self.display_error(f"Client ID exists: {bool(self.ebay_client_id)}")
            self.display_error(f"Client Secret exists: {bool(self.ebay_client_secret)}")
            return False
        
        try:
            # eBay OAuth endpoint
            if self.ebay_environment == 'PRODUCTION':
                oauth_url = "https://api.ebay.com/identity/v1/oauth2/token"
            else:
                oauth_url = "https://api.sandbox.ebay.com/identity/v1/oauth2/token"
            
            self.results_text.insert(tk.END, f"Using environment: {self.ebay_environment}\n")
            self.results_text.insert(tk.END, f"OAuth URL: {oauth_url}\n")
            self.root.update()
            
            headers = {
                'Content-Type': 'application/x-www-form-urlencoded',
                'Authorization': f'Basic {self._encode_credentials()}'
            }
            
            data = {
                'grant_type': 'client_credentials',
                'scope': 'https://api.ebay.com/oauth/api_scope'
            }
            
            response = requests.post(oauth_url, headers=headers, data=data, timeout=10)
            
            self.results_text.insert(tk.END, f"eBay OAuth response: {response.status_code}\n")
            self.root.update()
            
            if response.status_code != 200:
                self.results_text.insert(tk.END, f"Response text: {response.text}\n")
                self.root.update()
            
            response.raise_for_status()
            
            token_data = response.json()
            self.results_text.insert(tk.END, f"Token response keys: {list(token_data.keys())}\n")
            self.root.update()
            
            self.ebay_access_token = token_data.get('access_token')
            
            if self.ebay_access_token:
                self.results_text.insert(tk.END, "eBay authentication successful!\n")
                return True
            else:
                self.display_error("No access token in response")
                self.display_error(f"Full response: {token_data}")
                return False
            
        except Exception as e:
            self.display_error(f"Failed to get eBay access token: {str(e)}")
            if hasattr(e, 'response') and e.response is not None:
                self.display_error(f"Response status: {e.response.status_code}")
                self.display_error(f"Response text: {e.response.text}")
            return False
    
    def _encode_credentials(self) -> str:
        import base64
        credentials = f"{self.ebay_client_id}:{self.ebay_client_secret}"
        return base64.b64encode(credentials.encode()).decode()
    
    def _analyze_price_distribution(self, raw_prices: List[float], part_name: str, raw_titles: List[str] = None, minimum_price: float = 0) -> Dict[str, float]:
        """
        Junkyard Parts Pricing Analysis System
        Implements sophisticated data cleaning and percentile-based pricing strategy
        """
        if not raw_prices:
            return {"low": 0, "average": 0, "high": 0, "items_removed": 0, "cleaned_count": 0}
        
        if len(raw_prices) < 3:
            avg = sum(raw_prices) / len(raw_prices)
            return {"low": avg, "average": avg, "high": avg, "items_removed": 0, "cleaned_count": len(raw_prices)}
        
        original_count = len(raw_prices)
        cleaned_prices = []
        removed_items = []
        
        # Step 1: Remove miscategorized items based on suspicious keywords
        suspicious_keywords = {
            'engine': ['oil filter', 'housing', 'gasket', 'seal', 'sensor', 'valve cover', 'dipstick', 'bracket', 'mount', 'belt', 'pulley'],
            'alternator': ['brush', 'pulley', 'wire', 'connector', 'regulator', 'belt'],
            'transmission': ['fluid', 'filter', 'gasket', 'cooler', 'mount', 'line'],
            'starter': ['solenoid', 'brush', 'drive', 'gear', 'bolt'],
            'brake caliper': ['pad', 'rotor', 'disc', 'fluid', 'line', 'hose'],
            'fuel pump': ['filter', 'line', 'hose', 'tank', 'sending unit'],
            'headlight': ['bulb', 'ballast', 'wire', 'connector', 'lens', 'cover']
        }
        
        keywords_to_check = suspicious_keywords.get(part_name.lower(), [])
        
        for i, price in enumerate(raw_prices):
            title = raw_titles[i].lower() if raw_titles and i < len(raw_titles) else ""
            
            # Check for suspicious keywords
            is_suspicious = any(keyword in title for keyword in keywords_to_check)
            
            if is_suspicious:
                removed_items.append(f"${price:.2f} - Miscategorized (contains suspicious keywords)")
                continue
                
            cleaned_prices.append(price)
        
        # Step 2: Apply configurable minimum prices from CSV
        if minimum_price > 0:
            further_cleaned = []
            for price in cleaned_prices:
                if price >= minimum_price:
                    further_cleaned.append(price)
                else:
                    removed_items.append(f"${price:.2f} - Below minimum (${minimum_price})")
            
            cleaned_prices = further_cleaned
        
        # Step 3: Optional IQR outlier detection (for extreme outliers only)
        if len(cleaned_prices) >= 10:
            sorted_prices = sorted(cleaned_prices)
            q1_idx = len(sorted_prices) // 4
            q3_idx = 3 * len(sorted_prices) // 4
            q1 = sorted_prices[q1_idx]
            q3 = sorted_prices[q3_idx]
            iqr = q3 - q1
            
            lower_bound = q1 - 1.5 * iqr
            upper_bound = q3 + 1.5 * iqr
            
            iqr_cleaned = []
            for price in cleaned_prices:
                if price < lower_bound or price > upper_bound:
                    removed_items.append(f"${price:.2f} - Statistical outlier (IQR method)")
                    continue
                iqr_cleaned.append(price)
            
            cleaned_prices = iqr_cleaned
        
        if not cleaned_prices:
            return {"low": 0, "average": 0, "high": 0, "items_removed": original_count, "cleaned_count": 0}
        
        # Calculate percentile-based pricing tiers
        sorted_prices = sorted(cleaned_prices)
        n = len(sorted_prices)
        
        # Calculate percentiles using proper interpolation
        def get_percentile(data, percentile):
            if len(data) == 1:
                return data[0]
            index = (percentile / 100.0) * (len(data) - 1)
            lower_index = int(index)
            upper_index = min(lower_index + 1, len(data) - 1)
            weight = index - lower_index
            return data[lower_index] * (1 - weight) + data[upper_index] * weight
        
        raw_p10 = get_percentile(sorted_prices, 10)
        raw_p30 = get_percentile(sorted_prices, 30)  
        raw_p50 = get_percentile(sorted_prices, 50)
        
        # Smart rounding based on price range
        def smart_round(price):
            if price < 100:
                return round(price / 5) * 5  # Round to nearest $5
            elif price < 500:
                return round(price / 10) * 10  # Round to nearest $10
            else:
                return round(price / 25) * 25  # Round to nearest $25
        
        budget_tier = smart_round(raw_p10)
        standard_tier = smart_round(raw_p30)
        premium_tier = smart_round(raw_p50)
        
        # Handle categories with very few results differently
        if n < 10:
            # For small datasets, use even more aggressive percentiles
            raw_p10 = get_percentile(sorted_prices, 5)   # Very low percentile
            raw_p30 = get_percentile(sorted_prices, 25)
            raw_p50 = get_percentile(sorted_prices, 50)
            
            # Use smaller rounding increments
            def small_round(price):
                if price < 50:
                    return round(price)  # Round to nearest $1
                elif price < 200:
                    return round(price / 5) * 5  # Round to nearest $5
                else:
                    return round(price / 10) * 10  # Round to nearest $10
            
            budget_tier = small_round(raw_p10)
            standard_tier = small_round(raw_p30)
            premium_tier = small_round(raw_p50)
        
        # Ensure tiers are different - if they're the same after rounding, adjust
        if budget_tier == standard_tier == premium_tier and n >= 3:
            # Force some separation
            price_range = max(sorted_prices) - min(sorted_prices)
            if price_range > 10:  # Only if there's meaningful range
                if price_range < 50:
                    step = 5
                elif price_range < 200:
                    step = 10
                else:
                    step = 25
                
                budget_tier = max(budget_tier - step, min(sorted_prices))
                premium_tier = premium_tier + step
        
        return {
            "low": budget_tier,           # 10th percentile (Budget tier)
            "average": standard_tier,     # 30th percentile (Standard tier)  
            "high": premium_tier,         # 50th percentile (Premium tier)
            "raw_p10": raw_p10,
            "raw_p30": raw_p30,
            "raw_p50": raw_p50,
            "items_removed": original_count - len(cleaned_prices),
            "cleaned_count": len(cleaned_prices),
            "removed_details": removed_items[:3],  # First 3 removed items for debugging
            "final_range": max(cleaned_prices) - min(cleaned_prices) if cleaned_prices else 0,
            "minimum_price": minimum_price
        }
    
    def search_ebay_parts(self, vehicle_info: Dict) -> Dict[str, float]:
        self.results_text.insert(tk.END, "Starting eBay parts search...\n")
        self.root.update()
        
        if not self.ebay_access_token and not self.get_ebay_access_token():
            self.results_text.insert(tk.END, "Failed to get eBay token, aborting search\n")
            self.root.update()
            return {}
        
        parts_prices = {}
        
        # eBay Browse API endpoint
        if self.ebay_environment == 'PRODUCTION':
            search_url = "https://api.ebay.com/buy/browse/v1/item_summary/search"
        else:
            search_url = "https://api.sandbox.ebay.com/buy/browse/v1/item_summary/search"
        
        headers = {
            'Authorization': f'Bearer {self.ebay_access_token}',
            'Content-Type': 'application/json'
        }
        
        for part in self.parts_list:
            try:
                # Just two targeted searches: full year and short year
                year = vehicle_info['year']
                short_year = str(year)[-2:]  # Last 2 digits (e.g., "12" for 2012)
                
                search_queries = [
                    f"{year} {vehicle_info['make']} {vehicle_info['model']} {part['search_query']}",
                    f"{short_year} {vehicle_info['make']} {vehicle_info['model']} {part['search_query']}"
                ]
                
                # Match your manual search - just Used condition (3000)
                condition_filter = "conditionIds:{3000}"  # Used only
                buying_filter = "buyingOptions:{FIXED_PRICE}"
                
                # Collect all unique items from both searches
                all_items = {}  # Use dict to dedupe by itemId
                total_found = 0
                
                for search_query in search_queries:
                    params = {
                        'q': search_query,
                        'category_ids': part['category_id'],
                        'filter': f"{condition_filter},{buying_filter}",
                        'sort': 'price',
                        'limit': '200'  # Expand to cast a wider net
                    }
                    
                    # Debug: Show actual API call for headlight issues
                    if part['search_query'] == 'headlight':
                        self.results_text.insert(tk.END, f"API params: {params}\n")
                        self.root.update()
                    
                    self.results_text.insert(tk.END, f"Searching: '{search_query}'...\n")
                    self.root.update()
                    
                    try:
                        response = requests.get(search_url, headers=headers, params=params, timeout=10)
                        if response.status_code == 200:
                            data = response.json()
                            items = data.get('itemSummaries', [])
                            self.results_text.insert(tk.END, f"  Found {len(items)} items\n")
                            
                            # Add items to our collection, using itemId to avoid duplicates
                            for item in items:
                                item_id = item.get('itemId', f"unknown_{len(all_items)}")
                                if item_id not in all_items:
                                    all_items[item_id] = item
                            
                        else:
                            self.results_text.insert(tk.END, f"  HTTP {response.status_code}\n")
                    except Exception as e:
                        self.results_text.insert(tk.END, f"  Error: {str(e)[:100]}\n")
                    
                    self.root.update()
                
                # Convert back to list format for processing
                if all_items:
                    combined_items = list(all_items.values())
                    data = {'itemSummaries': combined_items}
                    self.results_text.insert(tk.END, f"Combined unique results: {len(combined_items)} items\n")
                else:
                    data = None
                    self.results_text.insert(tk.END, f"No results found for {part['search_query']}\n")
                self.root.update()
                
                prices = []
                titles = []
                
                if 'itemSummaries' in data:
                    price_debug_count = 0
                    for item in data['itemSummaries']:
                        if 'price' in item and 'value' in item['price']:
                            try:
                                price = float(item['price']['value'])
                                
                                # Add shipping cost if present
                                shipping_cost = 0.0
                                if 'shippingOptions' in item and item['shippingOptions']:
                                    shipping_option = item['shippingOptions'][0]  # Take first shipping option
                                    if 'shippingCost' in shipping_option and 'value' in shipping_option['shippingCost']:
                                        shipping_cost = float(shipping_option['shippingCost']['value'])
                                
                                total_price = price + shipping_cost
                                
                                # Debug: Show first few prices for headlight issues
                                if part['search_query'] == 'headlight' and price_debug_count < 5:
                                    condition = item.get('condition', 'Unknown')
                                    condition_id = item.get('conditionId', 'Unknown')
                                    self.results_text.insert(tk.END, f"  Item {price_debug_count + 1}: ${price:.2f} + ${shipping_cost:.2f} = ${total_price:.2f} - Condition: {condition} ({condition_id}) - {item.get('title', '')[:40]}...\n")
                                    price_debug_count += 1
                                    self.root.update()
                                
                                # No minimum price filtering - we removed that
                                if total_price <= 5000:  # Just keep max filter
                                    prices.append(total_price)
                                    titles.append(item.get('title', ''))
                                elif part['search_query'] == 'headlight' and price_debug_count < 5:
                                    self.results_text.insert(tk.END, f"  Rejected: ${total_price:.2f} (over $5000 max)\n")
                                    self.root.update()
                                    
                            except (ValueError, TypeError) as e:
                                if part['search_query'] == 'headlight' and price_debug_count < 3:
                                    self.results_text.insert(tk.END, f"  Price parsing error: {str(e)} - {item.get('title', '')[:30]}...\n")
                                    self.root.update()
                                continue
                        elif part['search_query'] == 'headlight' and price_debug_count < 3:
                            self.results_text.insert(tk.END, f"  No price data in item: {item.get('title', '')[:30]}...\n")
                            price_debug_count += 1
                            self.root.update()
                
                if prices:
                    # Junkyard Parts Pricing Analysis System
                    price_analysis = self._analyze_price_distribution(prices, part['search_query'], titles, part.get('min_price', 0))
                    
                    # Store all three price points
                    parts_prices[part['search_query']] = {
                        'low': price_analysis["low"],
                        'average': price_analysis["average"], 
                        'high': price_analysis["high"]
                    }
                    
                    # Debug info with cleaning details
                    cleaned_count = price_analysis.get('cleaned_count', len(prices))
                    removed_count = price_analysis.get('items_removed', 0)
                    raw_p10 = price_analysis.get('raw_p10', 0)
                    raw_p30 = price_analysis.get('raw_p30', 0)
                    raw_p50 = price_analysis.get('raw_p50', 0)
                    
                    # Show detailed filtering breakdown
                    removed_details = price_analysis.get('removed_details', [])
                    
                    minimum_used = price_analysis.get('minimum_price', 0)
                    min_text = f" (min: ${minimum_used})" if minimum_used > 0 else ""
                    self.results_text.insert(tk.END, f"{part['search_query']}: {len(prices)} raw → {cleaned_count} cleaned "
                                                    f"({removed_count} removed{min_text})\n")
                    
                    if removed_details:
                        self.results_text.insert(tk.END, f"  Sample removed: {removed_details[0] if removed_details else 'None'}\n")
                    
                    self.results_text.insert(tk.END, f"  Raw percentiles: 10th=${raw_p10:.2f}, 30th=${raw_p30:.2f}, 50th=${raw_p50:.2f}\n")
                    
                    # Show price range to understand spread
                    if cleaned_count > 0:
                        # Since we removed domain minimums, just show the actual cleaned price range
                        final_range = price_analysis.get('final_range', 0)
                        if final_range > 0:
                            min_cleaned = raw_p10 - (final_range * 0.3)  # Approximate min
                            max_cleaned = raw_p50 + (final_range * 0.7)  # Approximate max
                            self.results_text.insert(tk.END, f"  Price range after cleaning: ${min_cleaned:.2f} - ${max_cleaned:.2f} (range: ${final_range:.2f})\n")
                    
                    self.results_text.insert(tk.END, f"  Final tiers: Budget=${price_analysis['low']:.2f}, "
                                                    f"Standard=${price_analysis['average']:.2f}, "
                                                    f"Premium=${price_analysis['high']:.2f}\n")
                    self.root.update()
                else:
                    parts_prices[part['search_query']] = {'low': 0.0, 'average': 0.0, 'high': 0.0}
                    self.results_text.insert(tk.END, f"{part['search_query']}: No valid prices found\n")
                    self.root.update()
                
            except Exception as e:
                error_msg = f"eBay search error for {part['search_query']}: {str(e)}"
                if hasattr(e, 'response') and e.response is not None:
                    error_msg += f" (HTTP {e.response.status_code})"
                    self.results_text.insert(tk.END, f"Response text for {part['search_query']}: {e.response.text[:200]}...\n")
                    self.root.update()
                    try:
                        error_data = e.response.json()
                        if 'errors' in error_data:
                            error_msg += f" - {error_data['errors'][0].get('message', 'Unknown error')}"
                    except:
                        pass
                self.display_error(error_msg)
                parts_prices[part['search_query']] = {'low': 0.0, 'average': 0.0, 'high': 0.0}
        
        return parts_prices
    
    def calculate_recommended_bid(self, parts_prices: Dict[str, dict], multiplier: float = 0.2) -> Dict[str, float]:
        # Calculate totals for low, average, and high scenarios
        totals = {'low': 0, 'average': 0, 'high': 0}
        
        for part_prices in parts_prices.values():
            if isinstance(part_prices, dict):
                totals['low'] += part_prices.get('low', 0)
                totals['average'] += part_prices.get('average', 0)
                totals['high'] += part_prices.get('high', 0)
            else:
                # Fallback for old format
                totals['low'] += part_prices
                totals['average'] += part_prices
                totals['high'] += part_prices
        
        # Calculate bids for each scenario
        bids = {
            'low': totals['low'] * multiplier,
            'average': totals['average'] * multiplier,
            'high': totals['high'] * multiplier
        }
        
        return {'totals': totals, 'bids': bids}
    
    def calculate_bid(self):
        vin = self.vin_entry.get().strip().upper()
        
        if not vin or len(vin) != 17:
            messagebox.showerror("Invalid VIN", "Please enter a valid 17-character VIN")
            return
        
        self.results_text.delete(1.0, tk.END)
        self.results_text.insert(tk.END, "Processing VIN...\n")
        self.root.update()
        
        vehicle_info = self.decode_vin(vin)
        if not vehicle_info:
            self.display_error("Could not decode VIN or retrieve vehicle information")
            return
        
        self.results_text.insert(tk.END, f"Vehicle: {vehicle_info['year']} {vehicle_info['make']} {vehicle_info['model']}\n")
        self.results_text.insert(tk.END, "Searching for parts prices...\n")
        self.root.update()
        
        parts_prices = self.search_ebay_parts(vehicle_info)
        bid_analysis = self.calculate_recommended_bid(parts_prices)
        
        self.display_results(vehicle_info, parts_prices, bid_analysis)
    
    def display_results(self, vehicle_info: Dict, parts_prices: Dict[str, dict], bid_analysis: Dict):
        # Don't clear the screen - append the analysis to the existing debug output
        self.results_text.insert(tk.END, "\n" + "="*80 + "\n")
        
        self.results_text.insert(tk.END, f"=== AUCTION BID ANALYSIS ===\n\n")
        self.results_text.insert(tk.END, f"Vehicle: {vehicle_info['year']} {vehicle_info['make']} {vehicle_info['model']}\n\n")
        
        # Display parts breakdown with pricing tiers
        self.results_text.insert(tk.END, "JUNKYARD PRICING ANALYSIS:\n")
        self.results_text.insert(tk.END, f"{'Part':<20} {'Budget':<10} {'Standard':<10} {'Premium':<10}\n")
        self.results_text.insert(tk.END, f"{'(10th %ile)':<20} {'(30th %ile)':<10} {'(50th %ile)':<10}\n")
        self.results_text.insert(tk.END, "-" * 60 + "\n")
        
        for part, prices in parts_prices.items():
            if isinstance(prices, dict):
                low = prices.get('low', 0)
                avg = prices.get('average', 0)
                high = prices.get('high', 0)
                self.results_text.insert(tk.END, f"{part.capitalize():<20} ${low:<9.2f} ${avg:<9.2f} ${high:<9.2f}\n")
            else:
                # Fallback for old format
                self.results_text.insert(tk.END, f"{part.capitalize():<20} ${prices:<9.2f} ${prices:<9.2f} ${prices:<9.2f}\n")
        
        # Display totals
        totals = bid_analysis['totals']
        bids = bid_analysis['bids']
        
        self.results_text.insert(tk.END, "-" * 60 + "\n")
        self.results_text.insert(tk.END, f"{'TOTALS:':<20} ${totals['low']:<9.2f} ${totals['average']:<9.2f} ${totals['high']:<9.2f}\n\n")
        
        # Display recommended bids based on pricing tiers
        self.results_text.insert(tk.END, "RECOMMENDED AUCTION BIDS (20% of parts value):\n")
        self.results_text.insert(tk.END, f"Budget-based bid:    ${bids['low']:.2f}  (if you expect lower-grade parts)\n")
        self.results_text.insert(tk.END, f"Standard bid:        ${bids['average']:.2f}  (typical market pricing)\n")
        self.results_text.insert(tk.END, f"Premium bid:         ${bids['high']:.2f}  (if vehicle is in great condition)\n\n")
        
        # Debug info at the end
        self.results_text.insert(tk.END, f"=== DEBUG INFO ===\n")
        self.results_text.insert(tk.END, f"Found {len(parts_prices)} parts\n")
        self.results_text.insert(tk.END, f"eBay token exists: {bool(self.ebay_access_token)}\n")
        self.results_text.insert(tk.END, f"Client ID loaded: {bool(self.ebay_client_id)}\n")
        self.results_text.insert(tk.END, f"Client Secret loaded: {bool(self.ebay_client_secret)}\n\n")
        
        # Show which parts failed and why
        failed_parts = []
        for part, prices in parts_prices.items():
            if isinstance(prices, dict):
                if prices['low'] == 0 and prices['average'] == 0 and prices['high'] == 0:
                    failed_parts.append(part)
            elif prices == 0:
                failed_parts.append(part)
        
        if failed_parts:
            self.results_text.insert(tk.END, f"FAILED PARTS: {', '.join(failed_parts)}\n")
            self.results_text.insert(tk.END, "Check search terms or category IDs for these parts.\n\n")
        
        # Auto-scroll to bottom to show the final analysis
        self.results_text.see(tk.END)
    
    def display_error(self, message: str):
        self.results_text.insert(tk.END, f"ERROR: {message}\n")

def main():
    root = tk.Tk()
    app = PhoenixAuctionAssistant(root)
    root.mainloop()

if __name__ == "__main__":
    main()