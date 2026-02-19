# Hyderabad Metro Journey Planner

A multimodal route planner that helps you decide the smartest way to travel in Hyderabad — **direct taxi** or **taxi + metro**.

## Live Demo

**[https://m-r-p-h.onrender.com/](https://m-r-p-h.onrender.com/)**

> First load may take about a minute — the server spins up on demand.

## What it does

- Enter any two addresses in Hyderabad
- Compares door-to-door taxi vs taxi + metro routes
- Scores routes by travel time, distance, and transfers
- Recommends the better option with clear reasons
- Shows top 5 multimodal routes plus direct taxi

## Tech Stack

- **Backend:** Python 3.11, Flask, Pandas, Requests
- **APIs:** Google Maps (Places Autocomplete, Directions with traffic)
- **Data:** Precomputed metro travel times (~3,000+ station pairs)
- **Deploy:** Gunicorn, Render

## Run Locally

1. **Clone the repo**
   ```bash
   git clone https://github.com/YOUR_USERNAME/multimodel_bookings_main.git
   cd multimodel_bookings_main
   ```

2. **Create virtual environment and install dependencies**
   ```bash
   python -m venv .venv
   .venv\Scripts\activate   # Windows
   pip install -r requirements.txt
   ```

3. **Add `.env` file** in the project root:
   ```
   GOOGLE_MAPS_API_KEY=your_google_maps_api_key_here
   ```
   Get a key from [Google Cloud Console](https://console.cloud.google.com/) (enable Maps JavaScript API and Directions API).

4. **Run the app**
   ```bash
   python app.py
   ```
   Open [http://localhost:5000](http://localhost:5000)

## Project Structure

| File | Description |
|------|-------------|
| `app.py` | Flask app — main page and route-finding API |
| `station_finder.py` | Core logic — nearest stations, taxi/walk legs, scoring, recommendations |
| `hyderabad_metro_stations.py` | Metro data — Red/Blue/Green lines, 56 stations, coordinates |
| `station_pairs_with_times.csv` | Precomputed metro travel times between station pairs |
| `templates/index.html` | Web UI — address inputs, route cards |
| `project-docs.html` | Detailed project documentation |

## Metro Data

Uses official Hyderabad Metro data: Red, Blue, and Green lines; 56 stations; 3 interchange stations (Ameerpet, JBS Parade Ground, Mahatma Gandhi Bus Station).
