from flask import Flask, render_template, request, jsonify
import os
from dotenv import load_dotenv
from station_finder import HyderabadStationFinder
import json

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Initialize the station finder
station_finder = HyderabadStationFinder()

def clean_for_json(obj):
    """Clean data for JSON serialization by handling NaN values"""
    if isinstance(obj, dict):
        return {k: clean_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [clean_for_json(item) for item in obj]
    elif isinstance(obj, float) and (obj != obj):  # Check for NaN
        return None
    else:
        return obj

@app.route('/')
def index():
    """Serve the main page"""
    api_key = os.getenv('GOOGLE_MAPS_API_KEY')
    return render_template('index.html', api_key=api_key)

@app.route('/find_routes', methods=['POST'])
def find_routes():
    """Find multi-modal routes between two addresses"""
    try:
        data = request.get_json()
        
        # Get coordinates directly from frontend
        initial_lat = data.get('initial_lat')
        initial_lng = data.get('initial_lng')
        dest_lat = data.get('dest_lat')
        dest_lng = data.get('dest_lng')
        initial_address = data.get('initial_address', 'Unknown')
        dest_address = data.get('dest_address', 'Unknown')
        
        if not all([initial_lat, initial_lng, dest_lat, dest_lng]):
            return jsonify({'error': 'Coordinates are required'}), 400
        
        print("\n" + "🚇" + "=" * 78 + "🚇")
        print("🚇 HYDERABAD METRO JOURNEY PLANNER - NEW REQUEST")
        print("🚇" + "=" * 78 + "🚇")
        print(f"📍 From: {initial_address}")
        print(f"📍 To: {dest_address}")
        print(f"📍 Origin: ({initial_lat:.6f}, {initial_lng:.6f})")
        print(f"📍 Destination: ({dest_lat:.6f}, {dest_lng:.6f})")
        
        # Find nearest metro stations
        initial_stations = station_finder.find_nearest_stations(initial_lat, initial_lng, top_n=7)
        dest_stations = station_finder.find_nearest_stations(dest_lat, dest_lng, top_n=7)
        
        # Calculate direct taxi route
        direct_taxi = station_finder.calculate_direct_taxi(initial_lat, initial_lng, dest_lat, dest_lng)
        station_finder.direct_taxi = direct_taxi
        
        # Calculate all taxi legs and get convenience routes
        taxi_results = station_finder.calculate_all_taxi_legs(
            initial_lat, initial_lng, dest_lat, dest_lng, 
            initial_stations, dest_stations
        )
        
        # Get the convenience routes and direct taxi suggestion
        convenience_routes = station_finder.get_convenience_routes()
        direct_taxi_suggestion = station_finder.get_direct_taxi_suggestion()
        
        # Determine recommendation
        if direct_taxi_suggestion and direct_taxi_suggestion['suggest']:
            recommended_type = 'direct_taxi'
            # Use the direct_taxi_suggestion data which has the proper structure
            recommended_route = direct_taxi_suggestion
            recommendation_reasons = direct_taxi_suggestion['reasons']
        else:
            recommended_type = 'metro'
            recommended_route = convenience_routes[0] if convenience_routes else None
            recommendation_reasons = []
        
        print(f"\n✅ REQUEST COMPLETE - RETURNING RESULTS")
        print(f"📊 Returning {len(convenience_routes)} top routes to frontend")
        print(f"🏆 RECOMMENDED: {recommended_type.upper()}")
        if direct_taxi_suggestion:
            taxi_status = "SUGGESTED" if direct_taxi_suggestion['suggest'] else "NOT SUGGESTED"
            print(f"🚕 Direct taxi: {taxi_status}")
        
        response = {
            'status': 'success',
            'recommended_type': recommended_type,
            'recommended_route': recommended_route,
            'recommendation_reasons': recommendation_reasons,
            'convenience_routes': convenience_routes,
            'direct_taxi_suggestion': direct_taxi_suggestion
        }
        
        return jsonify(clean_for_json(response))
        
    except Exception as e:
        print(f"[ERROR] Error in find_routes: {str(e)}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    print("🚇 Starting Hyderabad Metro Journey Planner...")
    print("🌐 Server: http://localhost:5000")
    app.run(debug=True, host='0.0.0.0', port=5000)
