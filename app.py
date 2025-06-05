from flask import Flask, jsonify
import redis
import os
import requests
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# Connect to Redis
redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
cache = redis.Redis.from_url(redis_url)

# Get API key from .env
weather_api_key = os.getenv("WEATHER_API_KEY")

@app.route('/weather/<city_code>', methods=['GET'])
def get_weather(city_code):
    # Step 1: Check Redis Cache
    cached_data = cache.get(city_code)
    if cached_data:
        return jsonify({
            'city': city_code,
            'data': cached_data.decode('utf-8'),
            'source': 'cache'
        })

    # Step 2: Fetch from Visual Crossing
    try:
        url = f"https://weather.visualcrossing.com/VisualCrossingWebServices/rest/services/timeline/{city_code}?key={weather_api_key}&unitGroup=metric"
        response = requests.get(url)
        response.raise_for_status()  # Raise error if status is not 2xx
        data = response.json()

        # Extract only relevant fields
        today = data['days'][0]
        result = {
            'temp': today['temp'],
            'conditions': today['conditions'],
            'description': today.get('description', '')
        }

        # Step 3: Cache the result with 12-hour expiry
        cache.setex(city_code, 43200, str(result))

        return jsonify({
            'city': city_code,
            'data': result,
            'source': '3rd-party API'
        })

    except Exception as e:
        return jsonify({
            'error': 'Failed to fetch weather data',
            'details': str(e)
        }), 500

if __name__ == '__main__':
    app.run(debug=True)
