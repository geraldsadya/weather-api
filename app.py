from flask import Flask, jsonify
import redis
import os
import requests
import json
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# Redis connection with fallback
redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
try:
    cache = redis.Redis.from_url(redis_url, decode_responses=True)
    cache.ping()  # test connection
except redis.exceptions.RedisError:
    cache = None
    print("Warning: Redis connection failed. Running without cache.")

# Get API key from .env
weather_api_key = os.getenv("WEATHER_API_KEY")

@app.route('/weather/<city_code>', methods=['GET'])
def get_weather(city_code):
    try:
        # Step 1: Try Redis cache (if available)
        if cache:
            cached_data = cache.get(city_code)
            if cached_data:
                return jsonify({
                    'city': city_code,
                    'data': json.loads(cached_data),
                    'source': 'cache'
                })

        # Step 2: Fetch from 3rd-party API
        url = f"https://weather.visualcrossing.com/VisualCrossingWebServices/rest/services/timeline/{city_code}?key={weather_api_key}&unitGroup=metric"
        response = requests.get(url)
        data = response.json()

        today = data['days'][0]
        result = {
            'temp': today.get('temp', 'N/A'),
            'conditions': today.get('conditions', 'N/A'),
            'description': today.get('description', 'No description available')
        }

        # Step 3: Store in Redis cache if available
        if cache:
            try:
                cache.setex(city_code, 43200, json.dumps(result))
            except redis.exceptions.RedisError as e:
                print(f"Cache set error: {e}")

        return jsonify({
            'city': city_code,
            'data': result,
            'source': '3rd-party API'
        })

    except Exception as e:
        return jsonify({
            'error': 'Unexpected error occurred',
            'details': str(e)
        }), 500

if __name__ == '__main__':
    app.run(debug=True)
