import math
import os
import requests
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed
from hyderabad_metro_stations import STATION_COORDINATES, METRO_LINES
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class HyderabadStationFinder:
    def __init__(self):
        self.stations = STATION_COORDINATES
        self.api_key = os.getenv('GOOGLE_MAPS_API_KEY')
        if not self.api_key:
            raise ValueError("GOOGLE_MAPS_API_KEY not found in .env file")
        self.base_url = "https://maps.googleapis.com/maps/api"
        
        # Load metro data
        self.metro_data = self.load_metro_data()
    
    def load_metro_data(self):
        """Load metro route data from CSV"""
        try:
            df = pd.read_csv('station_pairs_with_times.csv')
            metro_data = {}
            
            for _, row in df.iterrows():
                station1 = row['start_station']
                station2 = row['end_station']
                metro_data[(station1, station2)] = {
                    'distance': row.get('metro_distance_km', 0),
                    'time': row.get('directions_time_min', 0),
                    'same_line': row.get('same_line', False),
                    'interchange': row.get('interchange_station', ''),
                    'transfer_count': 0 if row.get('same_line', False) else (1 if row.get('interchange_station', '') else 0),
                    'start_line': self.get_station_line(station1),
                    'end_line': self.get_station_line(station2)
                }
            
            print(f"[SUCCESS] Loaded {len(metro_data)} Hyderabad metro routes")
            return metro_data
            
        except Exception as e:
            print(f"[ERROR] Error loading metro data: {e}")
            return {}
    
    def get_station_line(self, station_name):
        """Get the metro line for a station"""
        for line, info in METRO_LINES.items():
            if station_name in info['stations']:
                return info['name']  # Return the line name (Red Line, Blue Line, Green Line)
        return "Unknown"
    
    def get_line_color(self, line_name):
        """Get the color for a metro line"""
        color_map = {
            'Red Line': '#FF0000',
            'Blue Line': '#0066CC', 
            'Green Line': '#00AA00'
        }
        return color_map.get(line_name, '#666666')
    
    def calculate_simple_distance(self, lat1, lng1, lat2, lng2):
        """Calculate simple distance using |lat1-lat2| + |lng1-lng2|"""
        return abs(lat1 - lat2) + abs(lng1 - lng2)
    
    def find_nearest_stations(self, lat, lng, top_n=7):
        """Find top N nearest stations to given coordinates"""
        print(f"\n📍 STEP 1: Finding nearest metro stations")
        print(f"   Location: ({lat:.6f}, {lng:.6f})")
        print(f"   Looking for: {top_n} closest stations")
        
        # Calculate distances to all stations
        station_distances = []
        
        for station_name, coords in self.stations.items():
            station_lat = coords[0]  # First element is latitude
            station_lng = coords[1]  # Second element is longitude
            simple_dist = self.calculate_simple_distance(lat, lng, station_lat, station_lng)
            straight_line_dist = self.calculate_straight_line_distance(lat, lng, station_lat, station_lng)
            
            # Determine mode based on straight-line distance
            mode = 'walking' if straight_line_dist <= 0.5 else 'taxi'  # 500m = 0.5km
            
            station_distances.append({
                'name': station_name,
                'lat': station_lat,
                'lng': station_lng,
                'distance': simple_dist,
                'straight_line_distance': straight_line_dist,
                'mode': mode
            })
        
        # Sort by distance and get top N
        station_distances.sort(key=lambda x: x['distance'])
        nearest_stations = station_distances[:top_n]
        
        print(f"   ✅ Found {len(nearest_stations)} stations:")
        for i, station in enumerate(nearest_stations, 1):
            mode_icon = "🚶" if station['mode'] == 'walking' else "🚕"
            print(f"      {i}. {station['name']} {mode_icon} ({station['distance']:.4f})")
        
        return nearest_stations
    
    def calculate_taxi_leg(self, origin_lat, origin_lng, dest_lat, dest_lng):
        """Calculate single taxi leg using Google Directions API with traffic"""
        url = f"{self.base_url}/directions/json"
        params = {
            'origin': f"{origin_lat},{origin_lng}",
            'destination': f"{dest_lat},{dest_lng}",
            'mode': 'driving',
            'departure_time': 'now',
            'traffic_model': 'best_guess',
            'key': self.api_key
        }
        
        try:
            response = requests.get(url, params=params, timeout=10)
            data = response.json()
            
            if data['status'] == 'OK' and data['routes']:
                route = data['routes'][0]
                leg = route['legs'][0]
                
                distance_km = leg['distance']['value'] / 1000
                
                # Use traffic-aware duration if available
                if 'duration_in_traffic' in leg:
                    duration_seconds = leg['duration_in_traffic']['value']
                    traffic_status = "Current Traffic"
                else:
                    duration_seconds = leg['duration']['value']
                    traffic_status = "Normal"
                
                # Convert to meaningful time format
                duration_min = int(duration_seconds // 60)
                duration_sec = int(duration_seconds % 60)
                
                if duration_sec == 0:
                    time_display = f"{duration_min} min"
                else:
                    time_display = f"{duration_min} min {duration_sec} sec"
                
                return {
                    'distance_km': distance_km,
                    'duration_min': duration_min,
                    'duration_sec': duration_sec,
                    'time_display': time_display,
                    'traffic_status': traffic_status,
                    'success': True
                }
            else:
                return {'success': False, 'error': data.get('status')}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def calculate_walking_leg(self, origin_lat, origin_lng, dest_lat, dest_lng):
        """Calculate single walking leg using custom Haversine distance and time calculation"""
        try:
            # Calculate distance using Haversine formula
            distance_km = self.calculate_straight_line_distance(origin_lat, origin_lng, dest_lat, dest_lng)
            
            # Calculate walking time: 1 meter = 1 second (3.6 km/h walking speed)
            duration_seconds = distance_km * 1000  # Convert km to meters, 1m = 1s
            
            # Convert to meaningful time format
            duration_min = int(duration_seconds // 60)
            duration_sec = int(duration_seconds % 60)
            
            if duration_sec == 0:
                time_display = f"{duration_min} min"
            else:
                time_display = f"{duration_min} min {duration_sec} sec"
            
            return {
                'distance_km': distance_km,
                'duration_min': duration_min,
                'duration_sec': duration_sec,
                'time_display': time_display,
                'mode': 'walking',
                'success': True
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def calculate_straight_line_distance(self, lat1, lng1, lat2, lng2):
        """Calculate straight-line distance between two points in kilometers"""
        # Using Haversine formula for accurate distance calculation
        R = 6371  # Earth's radius in kilometers
        
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lat = math.radians(lat2 - lat1)
        delta_lng = math.radians(lng2 - lng1)
        
        a = (math.sin(delta_lat / 2) ** 2 + 
             math.cos(lat1_rad) * math.cos(lat2_rad) * 
             math.sin(delta_lng / 2) ** 2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        
        return R * c
    
    def check_direct_taxi_conditions(self, direct_taxi, best_multimodal_route, leg_results, initial_stations, dest_stations):
        """Check if direct taxi should be suggested based on 6 rules"""
        if not direct_taxi:
            return {'suggest': False, 'reasons': []}
        
        direct_distance = direct_taxi['distance_km']
        direct_time_min = direct_taxi['duration_min'] + (direct_taxi['duration_sec'] / 60)
        
        # Get best multimodal route data
        best_multimodal_time = best_multimodal_route['total_journey_time']
        best_transfer_count = best_multimodal_route['transfer_count']
        
        # Calculate first+last mile access distances for best route
        best_initial = best_multimodal_route['initial']
        best_dest = best_multimodal_route['destination']
        
        leg1_key = f"initial_to_station_{best_initial}"
        leg2_key = f"station_to_dest_{best_dest}"
        
        first_access_km = 0
        last_access_km = 0
        
        if leg1_key in leg_results:
            first_access_km = leg_results[leg1_key]['distance_km']
        if leg2_key in leg_results:
            last_access_km = leg_results[leg2_key]['distance_km']
        
        total_first_last_km = first_access_km + last_access_km
        
        # Check 6 rules
        reasons = []
        
        # Rule 1: Direct distance <= 7 km
        if direct_distance <= 7:
            reasons.append(f"Direct distance <= 7 km ({direct_distance:.1f} km)")
        
        # Rule 2: Multimodal time >= 1.5 * direct time
        if best_multimodal_time >= 1.5 * direct_time_min:
            reasons.append(f"Multimodal time >= 1.5x direct time ({best_multimodal_time:.1f} min >= {1.5 * direct_time_min:.1f} min)")
        
        # Rule 3: Absolute saving >= 20 minutes
        time_saving = best_multimodal_time - direct_time_min
        if time_saving >= 20:
            reasons.append(f"Time saving >= 20 minutes ({time_saving:.1f} min)")
        
        # Rule 4: (first_access_km + last_access_km) >= 0.8 * direct_distance
        if total_first_last_km >= 0.8 * direct_distance:
            reasons.append(f"First+last mile >= 80% of direct distance ({total_first_last_km:.1f} km >= {0.8 * direct_distance:.1f} km)")
        
        # Rule 5: Either first OR last access leg >= 0.7 * direct_distance
        if first_access_km >= 0.7 * direct_distance or last_access_km >= 0.7 * direct_distance:
            reasons.append(f"First or last leg >= 70% of direct distance (first: {first_access_km:.1f} km, last: {last_access_km:.1f} km)")
        
        # Rule 6: Transfers >= 2 AND multimodal time >= 1.3 * direct time
        if best_transfer_count >= 2 and best_multimodal_time >= 1.3 * direct_time_min:
            reasons.append(f"Transfers >= 2 AND multimodal time >= 1.3x direct time ({best_transfer_count} transfers, {best_multimodal_time:.1f} min >= {1.3 * direct_time_min:.1f} min)")
        
        suggest = len(reasons) > 0
        
        if suggest:
            print(f"   🎯 DIRECT TAXI SUGGESTED - Rules triggered:")
            for i, reason in enumerate(reasons, 1):
                print(f"      {i}. {reason}")
        else:
            print(f"   🚕 Direct taxi not suggested - No rules triggered")
            print(f"      Direct: {direct_distance:.1f} km, {direct_time_min:.1f} min")
            print(f"      Best multimodal: {best_multimodal_time:.1f} min ({best_transfer_count} transfers)")
        
        return {
            'suggest': suggest,
            'reasons': reasons,
            'direct_distance': direct_distance,
            'direct_time': direct_time_min,
            'time_saving': time_saving,
            # Include the actual direct taxi data for frontend display
            'distance_km': direct_taxi['distance_km'],
            'duration_min': direct_taxi['duration_min'],
            'duration_sec': direct_taxi['duration_sec'],
            'time_display': direct_taxi['time_display']
        }
    
    def calculate_direct_taxi(self, origin_lat, origin_lng, dest_lat, dest_lng):
        """Calculate direct taxi route from origin to destination"""
        print(f"\n🚕 STEP 2: Calculating direct taxi route")
        print(f"   Calculating direct route from origin to destination...")
        result = self.calculate_taxi_leg(origin_lat, origin_lng, dest_lat, dest_lng)
        
        if result['success']:
            print(f"   ✅ Direct taxi: {result['distance_km']:.1f} km ({result['time_display']})")
            return result
        else:
            print(f"   ❌ Failed: {result.get('error', 'Unknown error')}")
        return None
    
    def calculate_all_taxi_legs(self, initial_lat, initial_lng, dest_lat, dest_lng, initial_stations, dest_stations):
        """Calculate all access legs in parallel"""
        print(f"\n🚶🚕 STEP 3: Calculating access routes")
        print(f"   Calculating: 14 routes (7 to stations + 7 from stations)")
        
        # Show which stations we're calculating to
        print(f"\n   📍 TO STATIONS (Origin → Metro Stations):")
        for i, station in enumerate(initial_stations, 1):
            mode_icon = "🚶" if station['mode'] == 'walking' else "🚕"
            print(f"      {i}. {station['name']} {mode_icon}")
        
        print(f"\n   📍 FROM STATIONS (Metro Stations → Destination):")
        for i, station in enumerate(dest_stations, 1):
            mode_icon = "🚶" if station['mode'] == 'walking' else "🚕"
            print(f"      {i}. {station['name']} {mode_icon}")
        
        # Prepare all leg calculations
        leg_calculations = []
        
        # Initial location to its 7 stations
        for station in initial_stations:
            leg_calculations.append({
                'type': 'initial_to_station',
                'station_name': station['name'],
                'origin_lat': initial_lat,
                'origin_lng': initial_lng,
                'dest_lat': station['lat'],
                'dest_lng': station['lng'],
                'mode': station['mode']
            })
            print(f"   🔍 TO STATION: ORIGIN ({initial_lat:.6f}, {initial_lng:.6f}) → {station['name']} ({station['lat']:.6f}, {station['lng']:.6f})")
        
        # Destination's 7 stations to destination
        for station in dest_stations:
            leg_calculations.append({
                'type': 'station_to_dest',
                'station_name': station['name'],
                'origin_lat': station['lat'],
                'origin_lng': station['lng'],
                'dest_lat': dest_lat,
                'dest_lng': dest_lng,
                'mode': station['mode']
            })
            print(f"   🔍 FROM STATION: {station['name']} ({station['lat']:.6f}, {station['lng']:.6f}) → DEST ({dest_lat:.6f}, {dest_lng:.6f})")
        
        # Calculate all legs in parallel
        leg_results = {}
        
        with ThreadPoolExecutor(max_workers=5) as executor:
            future_to_calc = {}
            
            for calc in leg_calculations:
                if calc['mode'] == 'walking':
                    future = executor.submit(self.calculate_walking_leg, calc['origin_lat'], calc['origin_lng'], 
                                           calc['dest_lat'], calc['dest_lng'])
                else:  # taxi
                    future = executor.submit(self.calculate_taxi_leg, calc['origin_lat'], calc['origin_lng'], 
                                           calc['dest_lat'], calc['dest_lng'])
                future_to_calc[future] = calc
            
            for future in as_completed(future_to_calc):
                calc = future_to_calc[future]
                try:
                    result = future.result()
                    if result['success']:
                        key = f"{calc['type']}_{calc['station_name']}"
                        result['mode'] = calc['mode']
                        leg_results[key] = result
                        print(f"   ✅ {calc['type']} {calc['mode']} to {calc['station_name']}: {result['distance_km']:.1f} km ({result['time_display']})")
                    else:
                        print(f"   ❌ Failed {calc['type']} {calc['mode']} to {calc['station_name']}: {result.get('error', 'Unknown error')}")
                except Exception as e:
                    print(f"   ❌ Error calculating {calc['type']} {calc['mode']} leg to {calc['station_name']}: {e}")
        
        print(f"   ✅ Calculated {len(leg_results)} access routes")
        
        # Count successful routes
        to_stations_count = 0
        from_stations_count = 0
        
        # Show all 14 routes clearly
        print(f"\n   📋 DETAILED ROUTE BREAKDOWN:")
        print(f"   🚶🚕 TO STATIONS (Origin → Metro Stations):")
        for station in initial_stations:
            key = f"initial_to_station_{station['name']}"
            if key in leg_results:
                result = leg_results[key]
                mode_icon = "🚶" if result['mode'] == 'walking' else "🚕"
                print(f"      {mode_icon} {station['name']}: {result['distance_km']:.1f} km ({result['time_display']})")
                to_stations_count += 1
            else:
                print(f"      ❌ {station['name']}: FAILED")
        
        print(f"\n   🚶🚕 FROM STATIONS (Metro Stations → Destination):")
        for station in dest_stations:
            key = f"station_to_dest_{station['name']}"
            if key in leg_results:
                result = leg_results[key]
                mode_icon = "🚶" if result['mode'] == 'walking' else "🚕"
                print(f"      {mode_icon} {station['name']}: {result['distance_km']:.1f} km ({result['time_display']})")
                from_stations_count += 1
            else:
                print(f"      ❌ {station['name']}: FAILED")
        
        print(f"\n   📊 SUMMARY: {to_stations_count}/7 to stations, {from_stations_count}/7 from stations = {len(leg_results)}/14 total")
        
        # Calculate direct taxi (this will be called from main flow)
        # direct_taxi = self.calculate_direct_taxi(initial_lat, initial_lng, dest_lat, dest_lng)
        # self.direct_taxi = direct_taxi
        
        # Create convenience routes
        convenience_combinations = []
        
        for initial_station in initial_stations:
            for dest_station in dest_stations:
                initial_name = initial_station['name']
                dest_name = dest_station['name']
                
                # Get access leg data
                leg1_key = f"initial_to_station_{initial_name}"
                leg2_key = f"station_to_dest_{dest_name}"
                
                # Get metro data
                metro_key = (initial_name, dest_name)
                
                if leg1_key in leg_results and leg2_key in leg_results and metro_key in self.metro_data:
                    leg1 = leg_results[leg1_key]
                    leg2 = leg_results[leg2_key]
                    metro_info = self.metro_data[metro_key]
                    
                    # Calculate access distance (scores computed after building all combinations)
                    total_access_distance = leg1['distance_km'] + leg2['distance_km']
                    transfer_count = metro_info.get('transfer_count', 0)
                    
                    # Calculate times
                    leg1_time_min = leg1['duration_min'] + (leg1['duration_sec'] / 60)
                    leg2_time_min = leg2['duration_min'] + (leg2['duration_sec'] / 60)
                    total_access_time = leg1_time_min + leg2_time_min
                    
                    metro_interchange_time = transfer_count * 3
                    access_metro_interchange_time = 6
                    total_journey_time = total_access_time + metro_info['time'] + metro_interchange_time + access_metro_interchange_time
                    
                    # Get line information
                    initial_line = metro_info.get('start_line', 'Unknown')
                    dest_line = metro_info.get('end_line', 'Unknown')
                    initial_line_color = self.get_line_color(initial_line)
                    dest_line_color = self.get_line_color(dest_line)
                    
                    convenience_combinations.append({
                        'initial': initial_name,
                        'destination': dest_name,
                        'leg1_distance': leg1['distance_km'],
                        'leg2_distance': leg2['distance_km'],
                        'leg1_mode': leg1['mode'],
                        'leg2_mode': leg2['mode'],
                        'total_access_distance': total_access_distance,
                        'leg1_time': leg1['time_display'],
                        'leg2_time': leg2['time_display'],
                        'leg1_time_min': leg1_time_min,
                        'leg2_time_min': leg2_time_min,
                        'total_access_time': total_access_time,
                        'metro_distance': metro_info['distance'],
                        'metro_time': metro_info['time'],
                        'metro_interchange_time': metro_interchange_time,
                        'access_metro_interchange_time': access_metro_interchange_time,
                        'total_journey_time': total_journey_time,
                        'transfer_count': transfer_count,
                        # scores will be filled after we compute shortest_access across all combos
                        'same_line': metro_info['same_line'],
                        'interchange': metro_info['interchange'],
                        'initial_line': initial_line,
                        'dest_line': dest_line,
                        'initial_line_color': initial_line_color,
                        'dest_line_color': dest_line_color
                    })
        
        # Compute scores using provided formula after all combinations are built
        if convenience_combinations:
            shortest_access = min(route['total_access_distance'] for route in convenience_combinations)
            for route in convenience_combinations:
                total_access_distance = route['total_access_distance']
                if total_access_distance > 0:
                    access_score = (shortest_access / total_access_distance) * 100
                else:
                    access_score = 100
                transfer_count = route['transfer_count']
                # New metro score formula with access_factor-based penalty
                access_factor = min(total_access_distance / 20.0, 1.0)
                if transfer_count == 0:
                    metro_score = 100
                elif transfer_count == 1:
                    penalty = 40 * access_factor
                    metro_score = 100 - penalty
                else:  # 2 or more transfers
                    penalty = 80 * access_factor
                    metro_score = 100 - penalty
                # Total score weights depend on transfer_count
                if transfer_count == 0:
                    # Same line: 80% access, 20% metro
                    total_convenience_score = (access_score * 0.8) + (metro_score * 0.2)
                elif transfer_count == 1:
                    # Single transfer: 65% access, 35% metro
                    total_convenience_score = (access_score * 0.65) + (metro_score * 0.35)
                else:
                    # Two or more transfers: 60% access, 40% metro
                    total_convenience_score = (access_score * 0.6) + (metro_score * 0.4)
                route['access_score'] = access_score
                route['metro_score'] = metro_score
                route['total_convenience_score'] = total_convenience_score

        # Sort by convenience score
        convenience_combinations.sort(key=lambda x: x['total_convenience_score'], reverse=True)
        
        print(f"\n🎯 STEP 4: Scoring and ranking routes")
        print(f"   📊 Analyzing {len(convenience_combinations)} route combinations")
        print(f"   🧮 Calculating convenience scores for each route...")
        
        # Show detailed scoring for ALL combinations
        print(f"\n   📋 ALL {len(convenience_combinations)} ROUTE COMBINATIONS WITH DETAILED SCORING:")
        for i, route in enumerate(convenience_combinations, 1):
            print(f"\n   {i:2d}. {route['initial']} → {route['destination']}")
            print(f"       🎯 Total Convenience Score: {route['total_convenience_score']:.1f}")
            print(f"       📍 Access Score: {route['access_score']:.1f} (Distance: {route['total_access_distance']:.1f} km)")
            print(f"       🚇 Metro Score: {route['metro_score']:.1f} (Transfers: {route['transfer_count']})")
            print(f"       ⏱️  Total Time: {route['total_journey_time']:.1f} min")
            print(f"       🚶🚕 Access: {route['leg1_distance']:.1f} km {route['leg1_mode']} + {route['leg2_distance']:.1f} km {route['leg2_mode']}")
            print(f"       🚇 Metro: {route['metro_distance']:.1f} km ({route['metro_time']:.0f} min)")
            if route['same_line']:
                print(f"       📍 Route Type: Same Line ({route['initial_line']})")
            else:
                if route['transfer_count'] == 1:
                    print(f"       📍 Route Type: Single Transfer at {route['interchange']}")
                else:
                    print(f"       📍 Route Type: Different Lines ({route['initial_line']} → {route['dest_line']})")
        
        print(f"\n   🏆 TOP 5 ROUTES (AFTER RANKING):")
        for i, route in enumerate(convenience_combinations[:5], 1):
            print(f"\n   {i}. {route['initial']} → {route['destination']}")
            print(f"      🎯 Total Convenience Score: {route['total_convenience_score']:.1f}")
            print(f"      📍 Access Score: {route['access_score']:.1f} (Distance: {route['total_access_distance']:.1f} km)")
            print(f"      🚇 Metro Score: {route['metro_score']:.1f} (Transfers: {route['transfer_count']})")
            print(f"      ⏱️  Total Time: {route['total_journey_time']:.1f} min")
            print(f"      🚶🚕 Access: {route['leg1_distance']:.1f} km {route['leg1_mode']} + {route['leg2_distance']:.1f} km {route['leg2_mode']}")
            print(f"      🚇 Metro: {route['metro_distance']:.1f} km ({route['metro_time']:.0f} min)")
            if route['same_line']:
                print(f"      📍 Route Type: Same Line ({route['initial_line']})")
            else:
                if route['transfer_count'] == 1:
                    print(f"      📍 Route Type: Single Transfer at {route['interchange']}")
                else:
                    print(f"      📍 Route Type: Different Lines ({route['initial_line']} → {route['dest_line']})")
        
        print(f"\n   ✅ Top 5 routes selected and ranked")
        
        # Store for API access
        self.convenience_routes = convenience_combinations[:5]
        
        # Analyze direct taxi suggestion
        if hasattr(self, 'direct_taxi') and self.direct_taxi:
            print(f"\n🚕 STEP 5: Analyzing direct taxi suggestion")
            best_route = convenience_combinations[0] if convenience_combinations else None
            if best_route:
                direct_suggestion = self.check_direct_taxi_conditions(
                    self.direct_taxi, best_route, leg_results, initial_stations, dest_stations
                )
                self.direct_taxi_suggestion = direct_suggestion
            else:
                print(f"   ⚠️  No multimodal routes available for comparison")
                # Still include the direct taxi data even if no comparison
                self.direct_taxi_suggestion = {
                    'suggest': False, 
                    'reasons': [],
                    'distance_km': self.direct_taxi['distance_km'],
                    'duration_min': self.direct_taxi['duration_min'],
                    'duration_sec': self.direct_taxi['duration_sec'],
                    'time_display': self.direct_taxi['time_display']
                }
        
        return leg_results
    
    def get_convenience_routes(self):
        """Get the top 5 convenience routes for API response"""
        return getattr(self, 'convenience_routes', [])
    
    def get_direct_taxi_suggestion(self):
        """Get direct taxi suggestion for API response"""
        return getattr(self, 'direct_taxi_suggestion', None)

def main():
    """Test the station finder"""
    finder = HyderabadStationFinder()
    
    # Test coordinates
    initial_lat = 17.392196
    initial_lng = 78.540352
    dest_lat = 17.447143
    dest_lng = 78.353277
    
    print(f"[SUCCESS] Initial Location: ({initial_lat:.6f}, {initial_lng:.6f})")
    print(f"[SUCCESS] Destination: ({dest_lat:.6f}, {dest_lng:.6f})")
    
    # Find nearest stations
    initial_stations = finder.find_nearest_stations(initial_lat, initial_lng, top_n=7)
    dest_stations = finder.find_nearest_stations(dest_lat, dest_lng, top_n=7)
    
    # Calculate routes
    taxi_legs = finder.calculate_all_taxi_legs(initial_lat, initial_lng, dest_lat, dest_lng, initial_stations, dest_stations)

if __name__ == '__main__':
    main() 