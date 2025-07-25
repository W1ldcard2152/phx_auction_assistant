#!/usr/bin/env python3

import tkinter as tk
from tkinter import ttk, messagebox
import requests
import csv
import json
import os
from typing import Dict, List, Optional
from dotenv import load_dotenv
import google.generativeai as genai

# Load environment variables
load_dotenv()

class PhoenixAuctionAssistant:
    def __init__(self, root):
        self.root = root
        self.root.title("Phoenix Auction Assistant")
        self.root.geometry("1000x700")
        
        # Load eBay API credentials
        self.ebay_client_id = os.getenv('EBAY_CLIENT_ID')
        self.ebay_client_secret = os.getenv('EBAY_CLIENT_SECRET')
        self.ebay_environment = os.getenv('EBAY_ENVIRONMENT', 'SANDBOX')
        self.ebay_access_token = None
        
        # Load Gemini API credentials and configure
        self.gemini_api_key = os.getenv('GEMINI_API_KEY')
        self.use_ai_analysis = os.getenv('USE_AI_ANALYSIS', 'true').lower() == 'true'
        
        if self.gemini_api_key and self.use_ai_analysis:
            try:
                genai.configure(api_key=self.gemini_api_key)
                self.gemini_model = genai.GenerativeModel('gemini-2.0-flash-exp')
            except Exception as e:
                print(f"Failed to initialize Gemini model: {e}")
                self.gemini_model = None
        else:
            self.gemini_model = None
        
        self.setup_gui()
        self.load_parts_list()
    
    def setup_gui(self):
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Top controls
        ttk.Label(main_frame, text="VIN:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.vin_entry = ttk.Entry(main_frame, width=30)
        self.vin_entry.grid(row=0, column=1, padx=5, pady=5)
        
        self.calculate_btn = ttk.Button(main_frame, text="Calculate Bid", 
                                       command=self.calculate_bid)
        self.calculate_btn.grid(row=0, column=2, padx=5, pady=5)
        
        # Create notebook for tabs
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.grid(row=1, column=0, columnspan=3, pady=10, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configure grid weights for resizing
        main_frame.grid_rowconfigure(1, weight=1)
        main_frame.grid_columnconfigure(0, weight=1)
        
        # Tab 1: Final Output (Auction Bid Analysis)
        self.final_output_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.final_output_frame, text="Final Output")
        
        self.final_output_text = tk.Text(self.final_output_frame, height=25, width=70, wrap=tk.WORD)
        self.final_output_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        final_scrollbar = ttk.Scrollbar(self.final_output_frame, orient="vertical", command=self.final_output_text.yview)
        final_scrollbar.grid(row=0, column=1, sticky="ns")
        self.final_output_text.configure(yscrollcommand=final_scrollbar.set)
        
        self.final_output_frame.grid_rowconfigure(0, weight=1)
        self.final_output_frame.grid_columnconfigure(0, weight=1)
        
        # Tab 2: Debug/Activity
        self.debug_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.debug_frame, text="Debug/Activity")
        
        self.debug_text = tk.Text(self.debug_frame, height=25, width=70, wrap=tk.WORD)
        self.debug_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        debug_scrollbar = ttk.Scrollbar(self.debug_frame, orient="vertical", command=self.debug_text.yview)
        debug_scrollbar.grid(row=0, column=1, sticky="ns")
        self.debug_text.configure(yscrollcommand=debug_scrollbar.set)
        
        self.debug_frame.grid_rowconfigure(0, weight=1)
        self.debug_frame.grid_columnconfigure(0, weight=1)
        
        # Tab 3: AI Instructions
        self.ai_instructions_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.ai_instructions_frame, text="AI Instructions")
        
        # Create AI instructions interface
        self.setup_ai_instructions_tab()
        
        # Tab 4: Raw Search Results
        self.raw_results_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.raw_results_frame, text="Raw Search Results")
        
        # Create sub-notebook for parts
        self.parts_notebook = ttk.Notebook(self.raw_results_frame)
        self.parts_notebook.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        self.raw_results_frame.grid_rowconfigure(0, weight=1)
        self.raw_results_frame.grid_columnconfigure(0, weight=1)
        
        # Initialize part tabs (will be populated when search starts)
        self.part_frames = {}
        self.part_tables = {}
        
        # Keep reference to old results_text for backward compatibility during refactoring
        self.results_text = self.debug_text
        
        # Initialize storage for raw search results
        self.raw_search_results = {}
    
    def setup_ai_instructions_tab(self):
        """Set up the AI Instructions tab with input areas and examples"""
        # Main frame with padding
        main_frame = ttk.Frame(self.ai_instructions_frame, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        self.ai_instructions_frame.grid_rowconfigure(0, weight=1)
        self.ai_instructions_frame.grid_columnconfigure(0, weight=1)
        
        # Title
        title_label = ttk.Label(main_frame, text="AI Analysis Custom Instructions", 
                               font=('Arial', 12, 'bold'))
        title_label.grid(row=0, column=0, columnspan=2, pady=(0, 10), sticky=tk.W)
        
        # Description
        desc_text = """Use this tab to provide custom instructions to the AI for analyzing your specific vehicle's parts.
This is especially useful when you know specific details about your vehicle that affect pricing."""
        desc_label = ttk.Label(main_frame, text=desc_text, wraplength=800)
        desc_label.grid(row=1, column=0, columnspan=2, pady=(0, 15), sticky=tk.W)
        
        # Custom Instructions section
        instructions_label = ttk.Label(main_frame, text="Custom Instructions:", 
                                     font=('Arial', 10, 'bold'))
        instructions_label.grid(row=2, column=0, sticky=tk.W, pady=(0, 5))
        
        # Text area for custom instructions
        self.ai_instructions_text = tk.Text(main_frame, height=6, width=80, wrap=tk.WORD)
        self.ai_instructions_text.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        
        # Add scrollbar for instructions
        instructions_scrollbar = ttk.Scrollbar(main_frame, orient="vertical", 
                                             command=self.ai_instructions_text.yview)
        instructions_scrollbar.grid(row=3, column=2, sticky="ns", pady=(0, 10))
        self.ai_instructions_text.configure(yscrollcommand=instructions_scrollbar.set)
        
        # Examples section
        examples_label = ttk.Label(main_frame, text="Example Instructions:", 
                                 font=('Arial', 10, 'bold'))
        examples_label.grid(row=4, column=0, sticky=tk.W, pady=(10, 5))
        
        # Examples text (read-only)
        examples_text = """• "This vehicle has both turbo and non-turbo engine variants. Turbo engines cost significantly more - filter out non-turbo engines when analyzing turbo engine prices."

• "This model year had a mid-year engine redesign. Early production engines (VIN starts with 1-5) are different from late production (VIN starts with 6-9)."

• "This vehicle uses a CVT transmission which is expensive to replace. Regular automatic transmissions from other models should be filtered out."

• "Headlights for this model have adaptive/LED versions that cost 3x more than standard halogen. Focus on halogen versions for junkyard pricing."

• "This engine size (3.5L) was only available in premium trim levels. Lower trim engines (2.4L, 2.0L) should be excluded from analysis."

• "Brake calipers for this model have performance Brembo versions on sport trim. Standard calipers are much cheaper and more appropriate for junkyard analysis."

• "Fuel pumps for this model are known to fail frequently. There are aftermarket high-performance versions that cost more - focus on OEM replacements."

• "This model uses a unique alternator design that's not interchangeable with other years. Only consider parts specifically for this generation (2012-2015)."

• "The manual transmission version of this engine has different accessories and mounts. Focus only on automatic transmission setups."

• "This model had a recall for fuel pump issues, so there are many refurbished/updated versions available at premium prices. Focus on standard used parts."""
        
        self.examples_text = tk.Text(main_frame, height=15, width=80, wrap=tk.WORD)
        self.examples_text.grid(row=5, column=0, columnspan=2, sticky=(tk.W, tk.E))
        self.examples_text.insert(1.0, examples_text)
        self.examples_text.configure(state='disabled')  # Make read-only
        
        # Add scrollbar for examples
        examples_scrollbar = ttk.Scrollbar(main_frame, orient="vertical", 
                                         command=self.examples_text.yview)
        examples_scrollbar.grid(row=5, column=2, sticky="ns")
        self.examples_text.configure(yscrollcommand=examples_scrollbar.set)
        
        # Configure grid weights
        main_frame.grid_rowconfigure(3, weight=1)
        main_frame.grid_rowconfigure(5, weight=2)
        main_frame.grid_columnconfigure(0, weight=1)
        
        # Save/Clear buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=6, column=0, columnspan=2, pady=(10, 0), sticky=tk.W)
        
        save_btn = ttk.Button(button_frame, text="Save Instructions", 
                             command=self.save_ai_instructions)
        save_btn.grid(row=0, column=0, padx=(0, 10))
        
        clear_btn = ttk.Button(button_frame, text="Clear Instructions", 
                              command=self.clear_ai_instructions)
        clear_btn.grid(row=0, column=1, padx=(0, 10))
        
        load_btn = ttk.Button(button_frame, text="Load Instructions", 
                             command=self.load_ai_instructions)
        load_btn.grid(row=0, column=2)
        
        # Load any existing instructions
        self.load_ai_instructions()
    
    def save_ai_instructions(self):
        """Save AI instructions to a file"""
        instructions = self.ai_instructions_text.get(1.0, tk.END).strip()
        try:
            with open('ai_instructions.txt', 'w', encoding='utf-8') as f:
                f.write(instructions)
            messagebox.showinfo("Saved", "AI instructions saved successfully!")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save instructions: {str(e)}")
    
    def clear_ai_instructions(self):
        """Clear the AI instructions text area"""
        self.ai_instructions_text.delete(1.0, tk.END)
    
    def load_ai_instructions(self):
        """Load AI instructions from file if it exists"""
        try:
            with open('ai_instructions.txt', 'r', encoding='utf-8') as f:
                instructions = f.read()
                self.ai_instructions_text.delete(1.0, tk.END)
                self.ai_instructions_text.insert(1.0, instructions)
        except FileNotFoundError:
            pass  # File doesn't exist yet, that's fine
        except Exception as e:
            print(f"Error loading AI instructions: {e}")
    
    def get_custom_ai_instructions(self):
        """Get the current custom AI instructions"""
        return self.ai_instructions_text.get(1.0, tk.END).strip()
    
    def create_part_tab(self, part_name):
        """Create a new tab for a specific part in the Raw Search Results section"""
        if part_name in self.part_frames:
            return  # Tab already exists
        
        # Create frame for this part
        part_frame = ttk.Frame(self.parts_notebook)
        self.parts_notebook.add(part_frame, text=part_name.capitalize())
        self.part_frames[part_name] = part_frame
        
        # Create treeview for table display
        columns = ('Price', 'Shipping', 'Total', 'Title')
        tree = ttk.Treeview(part_frame, columns=columns, show='headings', height=20)
        
        # Define column headings and widths
        tree.heading('Price', text='Price')
        tree.heading('Shipping', text='Shipping')
        tree.heading('Total', text='Total')
        tree.heading('Title', text='Title')
        
        tree.column('Price', width=80, anchor='e')
        tree.column('Shipping', width=80, anchor='e')
        tree.column('Total', width=80, anchor='e')
        tree.column('Title', width=500, anchor='w')
        
        # Add scrollbars
        v_scrollbar = ttk.Scrollbar(part_frame, orient="vertical", command=tree.yview)
        h_scrollbar = ttk.Scrollbar(part_frame, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
        
        # Grid layout
        tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        v_scrollbar.grid(row=0, column=1, sticky="ns")
        h_scrollbar.grid(row=1, column=0, sticky="ew")
        
        part_frame.grid_rowconfigure(0, weight=1)
        part_frame.grid_columnconfigure(0, weight=1)
        
        self.part_tables[part_name] = tree
    
    def update_part_table(self, part_name, items):
        """Update the table for a specific part with search results"""
        if part_name not in self.part_tables:
            self.create_part_tab(part_name)
        
        tree = self.part_tables[part_name]
        
        # Clear existing items
        for item in tree.get_children():
            tree.delete(item)
        
        # Sort items by total price (price + shipping)
        sorted_items = sorted(items, key=lambda x: x.get('total_price', x.get('price', 0)))
        
        # Add items to table
        for item in sorted_items:
            price = item.get('price', 0)
            shipping = item.get('shipping', 0)
            total_price = item.get('total_price', price + shipping)
            title = item.get('title', 'No title')
            
            price_str = f"${price:.2f}"
            shipping_str = "FREE" if shipping == 0 else f"${shipping:.2f}"
            total_str = f"${total_price:.2f}"
            
            tree.insert('', 'end', values=(price_str, shipping_str, total_str, title))
    
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
                        variable = result['Variable']
                        value = result['Value']
                        
                        # Core vehicle identification
                        if variable == 'Make':
                            vehicle_info['make'] = value
                        elif variable == 'Model':
                            vehicle_info['model'] = value
                        elif variable == 'Model Year':
                            vehicle_info['year'] = value
                        elif variable == 'Trim':
                            vehicle_info['trim'] = value
                        
                        # Engine specifications
                        elif variable == 'Displacement (CC)' or variable == 'Displacement (L)':
                            if value and value != 'null':
                                vehicle_info['engine_displacement'] = value
                        elif variable == 'Engine Number of Cylinders':
                            if value and value != 'null':
                                vehicle_info['engine_cylinders'] = value
                        elif variable == 'Fuel Type - Primary':
                            if value and value != 'null':
                                vehicle_info['fuel_type'] = value
                        elif variable == 'Engine Configuration':
                            if value and value != 'null':
                                vehicle_info['engine_configuration'] = value
                        
                        # Drive and transmission
                        elif variable == 'Drive Type':
                            if value and value != 'null':
                                vehicle_info['drive_type'] = value
                        elif variable == 'Transmission Style':
                            if value and value != 'null':
                                vehicle_info['transmission_style'] = value
                        elif variable == 'Transmission Speeds':
                            if value and value != 'null':
                                vehicle_info['transmission_speeds'] = value
                        
                        # Body specifications
                        elif variable == 'Body Class':
                            if value and value != 'null':
                                vehicle_info['body_class'] = value
                        elif variable == 'Doors':
                            if value and value != 'null':
                                vehicle_info['doors'] = value
                        elif variable == 'Vehicle Type':
                            if value and value != 'null':
                                vehicle_info['vehicle_type'] = value
                    
                    # Extract engine designation from VIN 8th digit
                    if len(vin) >= 8:
                        vehicle_info['engine_designation'] = vin[7]  # 8th character (0-indexed)
                    
                    # Check if we have the core required fields
                    required_fields = ['make', 'model', 'year']
                    if all(vehicle_info.get(field) for field in required_fields):
                        # Log additional decoded information
                        additional_info = []
                        if vehicle_info.get('engine_displacement'):
                            additional_info.append(f"Engine: {vehicle_info['engine_displacement']}")
                        if vehicle_info.get('drive_type'):
                            additional_info.append(f"Drive: {vehicle_info['drive_type']}")
                        if vehicle_info.get('fuel_type'):
                            additional_info.append(f"Fuel: {vehicle_info['fuel_type']}")
                        if vehicle_info.get('body_class'):
                            additional_info.append(f"Body: {vehicle_info['body_class']}")
                        if vehicle_info.get('engine_designation'):
                            additional_info.append(f"Engine Code: {vehicle_info['engine_designation']}")
                        
                        self.results_text.insert(tk.END, f"VIN decoded successfully!\n")
                        if additional_info:
                            self.results_text.insert(tk.END, f"Additional specs: {', '.join(additional_info)}\n")
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
    
    def _analyze_prices_with_ai(self, raw_items: List[Dict], part_name: str, minimum_price: float = 0) -> Dict[str, float]:
        """Use AI to analyze pricing data instead of traditional statistical methods"""
        if not self.gemini_model or not self.use_ai_analysis:
            if not self.use_ai_analysis:
                self.results_text.insert(tk.END, f"AI analysis disabled, using traditional analysis for {part_name}\n")
            else:
                self.results_text.insert(tk.END, f"Gemini API not configured, falling back to traditional analysis for {part_name}\n")
            self.root.update()
            # Fall back to traditional method
            raw_prices = [item.get('total_price', item.get('price', 0)) for item in raw_items]
            raw_titles = [item.get('title', '') for item in raw_items]
            return self._analyze_price_distribution(raw_prices, part_name, raw_titles, minimum_price)
        
        if not raw_items:
            return {"low": 0, "average": 0, "high": 0, "items_analyzed": 0, "items_filtered_out": 0, "reasoning": "No data provided"}
        
        try:
            # Format data for AI analysis
            csv_data = self.format_raw_results_for_ai(part_name, raw_items)
            # We need vehicle_info for context, but it's not passed to this method
            # For now, we'll extract it from the search results or pass None
            prompt = self.create_ai_analysis_prompt(part_name, csv_data, minimum_price, getattr(self, 'current_vehicle_info', None))
            
            self.results_text.insert(tk.END, f"Analyzing {part_name} with AI ({len(raw_items)} items)...\n")
            self.root.update()
            
            # Send to Gemini for analysis with retry logic
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    response = self.gemini_model.generate_content(
                        prompt,
                        generation_config=genai.types.GenerationConfig(
                            temperature=0.1,  # Low temperature for consistent analysis
                            max_output_tokens=1000
                        )
                    )
                    break
                except Exception as api_error:
                    if attempt == max_retries - 1:
                        raise api_error
                    self.results_text.insert(tk.END, f"AI attempt {attempt + 1} failed, retrying...\n")
                    self.root.update()
                    import time
                    time.sleep(1)  # Brief delay before retry
            
            # Parse JSON response
            response_text = response.text.strip()
            
            # Clean up the response in case it has markdown formatting
            if response_text.startswith('```json'):
                response_text = response_text.replace('```json', '').replace('```', '').strip()
            elif response_text.startswith('```'):
                response_text = response_text.replace('```', '').strip()
            
            result = json.loads(response_text)
            
            # Validate the response structure
            required_keys = ['low_price', 'average_price', 'high_price', 'items_analyzed', 'items_filtered_out', 'reasoning']
            if not all(key in result for key in required_keys):
                raise ValueError(f"AI response missing required keys: {required_keys}")
            
            # Log AI reasoning for debugging
            self.results_text.insert(tk.END, f"AI Analysis: {result['items_analyzed']} analyzed, {result['items_filtered_out']} filtered\n")
            self.results_text.insert(tk.END, f"AI Reasoning: {result['reasoning'][:100]}...\n")
            self.root.update()
            
            return {
                "low": float(result['low_price']),
                "average": float(result['average_price']),
                "high": float(result['high_price']),
                "items_analyzed": result['items_analyzed'],
                "items_filtered_out": result['items_filtered_out'],
                "reasoning": result['reasoning'],
                "cleaned_count": result['items_analyzed'] - result['items_filtered_out'],
                "items_removed": result['items_filtered_out']
            }
            
        except json.JSONDecodeError as e:
            self.results_text.insert(tk.END, f"AI JSON parsing error for {part_name}: {str(e)}\n")
            self.results_text.insert(tk.END, f"Raw AI response: {response.text[:200]}...\n")
            self.root.update()
        except Exception as e:
            self.results_text.insert(tk.END, f"AI analysis error for {part_name}: {str(e)}\n")
            self.root.update()
        
        # Fall back to traditional method on error
        self.results_text.insert(tk.END, f"Falling back to traditional analysis for {part_name}\n")
        self.root.update()
        raw_prices = [item.get('total_price', item.get('price', 0)) for item in raw_items]
        raw_titles = [item.get('title', '') for item in raw_items]
        return self._analyze_price_distribution(raw_prices, part_name, raw_titles, minimum_price)
    
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
                raw_items = []  # Store raw items for table display
                
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
                                    
                                    # Store raw item data for table display
                                    raw_items.append({
                                        'price': price,
                                        'shipping': shipping_cost,
                                        'total_price': total_price,
                                        'title': item.get('title', 'No title'),
                                        'item_id': item.get('itemId', ''),
                                        'condition': item.get('condition', ''),
                                        'location': item.get('itemLocation', {}).get('country', '')
                                    })
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
                    # Store raw search results for table display
                    self.raw_search_results[part['search_query']] = raw_items
                    self.update_part_table(part['search_query'], raw_items)
                    
                    # AI-Powered Junkyard Parts Pricing Analysis System
                    price_analysis = self._analyze_prices_with_ai(raw_items, part['search_query'], part.get('min_price', 0))
                    
                    # Store all price points and AI analysis metadata
                    parts_prices[part['search_query']] = {
                        'low': price_analysis["low"],
                        'average': price_analysis["average"], 
                        'high': price_analysis["high"],
                        'reasoning': price_analysis.get("reasoning", ""),
                        'items_analyzed': price_analysis.get("items_analyzed", 0),
                        'items_filtered_out': price_analysis.get("items_filtered_out", 0),
                        'cleaned_count': price_analysis.get("cleaned_count", 0)
                    }
                    
                    # Debug info with AI analysis details
                    if self.gemini_model and self.use_ai_analysis:
                        # Show AI analysis results
                        items_analyzed = price_analysis.get('items_analyzed', len(raw_items))
                        items_filtered = price_analysis.get('items_filtered_out', 0)
                        reasoning = price_analysis.get('reasoning', 'No reasoning provided')
                        
                        self.results_text.insert(tk.END, f"{part['search_query']}: AI analyzed {items_analyzed} items, filtered {items_filtered}\n")
                        self.results_text.insert(tk.END, f"  AI reasoning: {reasoning[:150]}{'...' if len(reasoning) > 150 else ''}\n")
                        self.results_text.insert(tk.END, f"  AI tiers: Budget=${price_analysis['low']:.2f}, "
                                                        f"Standard=${price_analysis['average']:.2f}, "
                                                        f"Premium=${price_analysis['high']:.2f}\n")
                    else:
                        # Fallback to traditional analysis debug info
                        cleaned_count = price_analysis.get('cleaned_count', len(prices))
                        removed_count = price_analysis.get('items_removed', 0)
                        
                        minimum_used = price_analysis.get('minimum_price', 0)
                        min_text = f" (min: ${minimum_used})" if minimum_used > 0 else ""
                        self.results_text.insert(tk.END, f"{part['search_query']}: {len(prices)} raw → {cleaned_count} cleaned "
                                                        f"({removed_count} removed{min_text})\n")
                        
                        self.results_text.insert(tk.END, f"  Traditional tiers: Budget=${price_analysis['low']:.2f}, "
                                                        f"Standard=${price_analysis['average']:.2f}, "
                                                        f"Premium=${price_analysis['high']:.2f}\n")
                    self.root.update()
                else:
                    # Even with no prices, create empty table for consistency
                    self.raw_search_results[part['search_query']] = []
                    self.update_part_table(part['search_query'], [])
                    
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
    
    def format_raw_results_for_ai(self, part_name: str, raw_items: List[Dict]) -> str:
        """Format raw search results into CSV format for AI analysis"""
        csv_lines = []
        csv_lines.append("Price,Shipping,Total,Title")
        
        for item in raw_items:
            price = item.get('price', 0)
            shipping = item.get('shipping', 0)
            total_price = item.get('total_price', price + shipping)
            title = item.get('title', '').replace(',', ';').replace('\n', ' ').strip()
            
            csv_lines.append(f"{price:.2f},{shipping:.2f},{total_price:.2f},\"{title}\"")
        
        return "\n".join(csv_lines)
    
    def create_ai_analysis_prompt(self, part_name: str, csv_data: str, min_price: float = 0, vehicle_info: dict = None) -> str:
        """Create comprehensive prompt for AI analysis of eBay pricing data"""
        # Get custom user instructions
        custom_instructions = self.get_custom_ai_instructions()
        
        # Build comprehensive vehicle context
        vehicle_context = ""
        if vehicle_info:
            base_info = f"{vehicle_info.get('year', 'Unknown')} {vehicle_info.get('make', 'Unknown')} {vehicle_info.get('model', 'Unknown')}"
            vehicle_context = f"\n**VEHICLE CONTEXT:**\nYou are analyzing parts for a {base_info}.\n"
            
            # Add detailed specifications for better parts analysis
            detailed_specs = []
            if vehicle_info.get('trim'):
                detailed_specs.append(f"Trim: {vehicle_info['trim']}")
            if vehicle_info.get('engine_displacement'):
                detailed_specs.append(f"Engine: {vehicle_info['engine_displacement']}")
            if vehicle_info.get('engine_cylinders'):
                detailed_specs.append(f"Cylinders: {vehicle_info['engine_cylinders']}")
            if vehicle_info.get('engine_designation'):
                detailed_specs.append(f"Engine Code: {vehicle_info['engine_designation']} (VIN 8th digit)")
            if vehicle_info.get('fuel_type'):
                detailed_specs.append(f"Fuel Type: {vehicle_info['fuel_type']}")
            if vehicle_info.get('drive_type'):
                detailed_specs.append(f"Drive Type: {vehicle_info['drive_type']}")
            if vehicle_info.get('transmission_style'):
                detailed_specs.append(f"Transmission: {vehicle_info['transmission_style']}")
            if vehicle_info.get('body_class'):
                detailed_specs.append(f"Body Class: {vehicle_info['body_class']}")
            if vehicle_info.get('doors'):
                detailed_specs.append(f"Doors: {vehicle_info['doors']}")
            
            if detailed_specs:
                vehicle_context += f"Vehicle Specifications: {', '.join(detailed_specs)}\n"
            
            # Add parts fitment guidance based on vehicle specs
            fitment_guidance = []
            if vehicle_info.get('drive_type'):
                drive_type = vehicle_info['drive_type'].lower()
                if 'awd' in drive_type or 'all-wheel' in drive_type:
                    fitment_guidance.append("AWD systems have unique drivetrain components - exclude FWD/RWD specific parts")
                elif 'fwd' in drive_type or 'front-wheel' in drive_type:
                    fitment_guidance.append("FWD vehicle - exclude RWD/AWD specific drivetrain parts")
                elif 'rwd' in drive_type or 'rear-wheel' in drive_type:
                    fitment_guidance.append("RWD vehicle - exclude FWD/AWD specific drivetrain parts")
            
            if vehicle_info.get('fuel_type'):
                fuel_type = vehicle_info['fuel_type'].lower()
                if 'diesel' in fuel_type:
                    fitment_guidance.append("Diesel engine - fuel system parts differ significantly from gasoline")
                elif 'gasoline' in fuel_type:
                    fitment_guidance.append("Gasoline engine - exclude diesel-specific fuel system parts")
            
            if vehicle_info.get('body_class'):
                body_class = vehicle_info['body_class'].lower()
                if 'coupe' in body_class:
                    fitment_guidance.append("Coupe body - some parts may differ from sedan variants")
                elif 'sedan' in body_class:
                    fitment_guidance.append("Sedan body - some parts may differ from coupe/hatchback variants")
                elif 'suv' in body_class or 'truck' in body_class:
                    fitment_guidance.append("SUV/Truck body - larger/heavier duty components than car variants")
            
            if vehicle_info.get('engine_designation'):
                fitment_guidance.append(f"Engine designation '{vehicle_info['engine_designation']}' should match listings mentioning this code")
            
            if fitment_guidance:
                vehicle_context += f"\n**PARTS FITMENT CONSIDERATIONS:**\n"
                for guidance in fitment_guidance:
                    vehicle_context += f"• {guidance}\n"
        
        # Build custom instructions section
        custom_section = ""
        if custom_instructions:
            custom_section = f"""
**CUSTOM ANALYSIS INSTRUCTIONS:**
The user has provided these specific instructions for analyzing this vehicle's parts:

{custom_instructions}

Please incorporate these instructions into your analysis and filtering decisions.
"""
        
        return f"""You are an expert automotive parts pricing analyst for a junkyard business. You need to analyze eBay search results for "{part_name}" parts and provide pricing recommendations.{vehicle_context}{custom_section}

**DATA TO ANALYZE:**
The following CSV contains eBay search results with columns: Price,Shipping,Total,Title

{csv_data}

**YOUR TASK:**
Analyze this data and intelligently filter out inappropriate listings, then calculate three pricing tiers. You must be smart about identifying:

1. **Miscategorized Items**: Look for titles that contain accessories, small components, or items that aren't the actual part (e.g., for "engine" - filters, gaskets, mounts, belts; for "alternator" - brushes, pulleys, wires; for "headlight" - bulbs, ballasts, connectors)

2. **Obvious Outliers**: Items with suspiciously low prices (likely damaged/core parts) or extremely high prices (likely new/premium parts not suitable for junkyard comparison)

3. **Duplicate/Similar Listings**: If you see very similar titles and prices, they might be the same seller with multiple listings

4. **Non-Junkyard Appropriate**: New parts, aftermarket upgrades, or specialty items that don't represent typical junkyard inventory

**MINIMUM PRICE FILTER**: 
{"Apply a minimum price filter of $" + str(min_price) + ". Remove any items below this threshold." if min_price > 0 else "No minimum price filter specified."}

**REQUIRED OUTPUT FORMAT:**
Return your response as valid JSON with this exact structure:
{{
    "low_price": [budget tier price as number],
    "average_price": [standard tier price as number], 
    "high_price": [premium tier price as number],
    "items_analyzed": [total items in the dataset],
    "items_filtered_out": [number of items you removed],
    "reasoning": "[brief explanation of your filtering logic and price calculation method]"
}}

**PRICING GUIDANCE:**
- Low price: Should represent bottom 10-20% of valid listings (budget junkyard tier)
- Average price: Should represent 25-40% range of valid listings (standard junkyard tier)  
- High price: Should represent 45-60% range of valid listings (premium junkyard tier)
- Round prices to sensible increments ($5 for under $100, $10 for $100-500, $25 for over $500)
- Ensure the three tiers are meaningfully different from each other

Analyze the data carefully and return only the JSON response."""
    
    def clear_all_tabs(self):
        """Clear all tabs and reset for new calculation"""
        # Clear debug tab
        self.debug_text.delete(1.0, tk.END)
        
        # Clear final output tab
        self.final_output_text.delete(1.0, tk.END)
        
        # Clear raw search results and remove all part tabs
        self.raw_search_results.clear()
        for part_name in list(self.part_frames.keys()):
            self.parts_notebook.forget(self.part_frames[part_name])
        self.part_frames.clear()
        self.part_tables.clear()
    
    def calculate_bid(self):
        vin = self.vin_entry.get().strip().upper()
        
        if not vin or len(vin) != 17:
            messagebox.showerror("Invalid VIN", "Please enter a valid 17-character VIN")
            return
        
        # Clear all tabs for new calculation
        self.clear_all_tabs()
        
        # Start with debug tab selected to show progress
        self.notebook.select(self.debug_frame)
        
        self.results_text.insert(tk.END, "Processing VIN...\n")
        self.root.update()
        
        vehicle_info = self.decode_vin(vin)
        if not vehicle_info:
            self.display_error("Could not decode VIN or retrieve vehicle information")
            return
        
        # Store vehicle info for AI analysis
        self.current_vehicle_info = vehicle_info
        
        self.results_text.insert(tk.END, f"Vehicle: {vehicle_info['year']} {vehicle_info['make']} {vehicle_info['model']}\n")
        self.results_text.insert(tk.END, "Searching for parts prices...\n")
        self.root.update()
        
        parts_prices = self.search_ebay_parts(vehicle_info)
        bid_analysis = self.calculate_recommended_bid(parts_prices)
        
        self.display_results(vehicle_info, parts_prices, bid_analysis)
    
    def display_results(self, vehicle_info: Dict, parts_prices: Dict[str, dict], bid_analysis: Dict):
        # Clear and populate the Final Output tab
        self.final_output_text.delete(1.0, tk.END)
        
        self.final_output_text.insert(tk.END, f"=== AUCTION BID ANALYSIS ===\n\n")
        
        # Display comprehensive vehicle information
        base_vehicle = f"{vehicle_info['year']} {vehicle_info['make']} {vehicle_info['model']}"
        self.final_output_text.insert(tk.END, f"Vehicle: {base_vehicle}")
        if vehicle_info.get('trim'):
            self.final_output_text.insert(tk.END, f" {vehicle_info['trim']}")
        self.final_output_text.insert(tk.END, f"\n")
        
        # Add vehicle specifications that affect parts compatibility
        spec_lines = []
        if vehicle_info.get('engine_displacement'):
            engine_info = vehicle_info['engine_displacement']
            if vehicle_info.get('engine_cylinders'):
                engine_info += f" ({vehicle_info['engine_cylinders']} cyl)"
            if vehicle_info.get('engine_designation'):
                engine_info += f" [Code: {vehicle_info['engine_designation']}]"
            spec_lines.append(f"Engine: {engine_info}")
        
        if vehicle_info.get('drive_type'):
            spec_lines.append(f"Drive: {vehicle_info['drive_type']}")
        
        if vehicle_info.get('fuel_type'):
            spec_lines.append(f"Fuel: {vehicle_info['fuel_type']}")
        
        if vehicle_info.get('body_class'):
            spec_lines.append(f"Body: {vehicle_info['body_class']}")
        
        if spec_lines:
            self.final_output_text.insert(tk.END, f"Specs: {' | '.join(spec_lines)}\n")
        
        self.final_output_text.insert(tk.END, f"\n")
        
        # Display parts breakdown with pricing tiers
        self.final_output_text.insert(tk.END, "AI-POWERED JUNKYARD PRICING ANALYSIS:\n")
        self.final_output_text.insert(tk.END, f"{'Part':<20} {'Budget':<10} {'Standard':<10} {'Premium':<10}\n")
        self.final_output_text.insert(tk.END, f"{'Tier':<20} {'Tier':<10} {'Tier':<10} {'Tier':<10}\n")
        self.final_output_text.insert(tk.END, "-" * 60 + "\n")
        
        for part, prices in parts_prices.items():
            if isinstance(prices, dict):
                low = prices.get('low', 0)
                avg = prices.get('average', 0)
                high = prices.get('high', 0)
                self.final_output_text.insert(tk.END, f"{part.capitalize():<20} ${low:<9.2f} ${avg:<9.2f} ${high:<9.2f}\n")
            else:
                # Fallback for old format
                self.final_output_text.insert(tk.END, f"{part.capitalize():<20} ${prices:<9.2f} ${prices:<9.2f} ${prices:<9.2f}\n")
        
        # Display totals
        totals = bid_analysis['totals']
        bids = bid_analysis['bids']
        
        self.final_output_text.insert(tk.END, "-" * 60 + "\n")
        self.final_output_text.insert(tk.END, f"{'TOTALS:':<20} ${totals['low']:<9.2f} ${totals['average']:<9.2f} ${totals['high']:<9.2f}\n\n")
        
        # Show AI analysis insights if available
        ai_insights = []
        for part, prices in parts_prices.items():
            if isinstance(prices, dict):
                reasoning = prices.get('reasoning')
                items_analyzed = prices.get('items_analyzed', 0)
                items_filtered = prices.get('items_filtered_out', 0)
                if reasoning and items_analyzed > 0:
                    ai_insights.append(f"• {part.capitalize()}: {items_analyzed} items analyzed, {items_filtered} filtered")
        
        if ai_insights:
            self.final_output_text.insert(tk.END, "AI ANALYSIS SUMMARY:\n")
            for insight in ai_insights:
                self.final_output_text.insert(tk.END, f"{insight}\n")
            self.final_output_text.insert(tk.END, "\n")
        
        # Display recommended bids based on pricing tiers
        self.final_output_text.insert(tk.END, "RECOMMENDED AUCTION BIDS (20% of parts value):\n")
        self.final_output_text.insert(tk.END, f"Budget-based bid:    ${bids['low']:.2f}  (if you expect lower-grade parts)\n")
        self.final_output_text.insert(tk.END, f"Standard bid:        ${bids['average']:.2f}  (typical market pricing)\n")
        self.final_output_text.insert(tk.END, f"Premium bid:         ${bids['high']:.2f}  (if vehicle is in great condition)\n\n")
        
        # Show which parts failed and why
        failed_parts = []
        for part, prices in parts_prices.items():
            if isinstance(prices, dict):
                if prices['low'] == 0 and prices['average'] == 0 and prices['high'] == 0:
                    failed_parts.append(part)
            elif prices == 0:
                failed_parts.append(part)
        
        if failed_parts:
            self.final_output_text.insert(tk.END, f"FAILED PARTS: {', '.join(failed_parts)}\n")
            self.final_output_text.insert(tk.END, "Check search terms or category IDs for these parts.\n\n")
        
        # Auto-scroll to top to show the final analysis
        self.final_output_text.see(1.0)
        
        # Also add debug info to the debug tab
        self.results_text.insert(tk.END, "\n" + "="*80 + "\n")
        self.results_text.insert(tk.END, f"=== PROCESSING COMPLETE ===\n")
        self.results_text.insert(tk.END, f"Found {len(parts_prices)} parts\n")
        self.results_text.insert(tk.END, f"eBay token exists: {bool(self.ebay_access_token)}\n")
        self.results_text.insert(tk.END, f"Client ID loaded: {bool(self.ebay_client_id)}\n")
        self.results_text.insert(tk.END, f"Client Secret loaded: {bool(self.ebay_client_secret)}\n")
        if failed_parts:
            self.results_text.insert(tk.END, f"FAILED PARTS: {', '.join(failed_parts)}\n")
        self.results_text.insert(tk.END, f"Results displayed in Final Output tab.\n")
        self.results_text.see(tk.END)
        
        # Switch to the Final Output tab to show the results
        self.notebook.select(self.final_output_frame)
    
    def display_error(self, message: str):
        self.results_text.insert(tk.END, f"ERROR: {message}\n")

def main():
    root = tk.Tk()
    app = PhoenixAuctionAssistant(root)
    root.mainloop()

if __name__ == "__main__":
    main()