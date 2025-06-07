from flask import Flask, jsonify
import redis
import os
import requests
import json
from dotenv import load_dotenv
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

load_dotenv()

app = Flask(__name__)

# Rate Limiting Setup
limiter = Limiter(
    app,
    key_func=get_remote_address,
    default_limits=["100 per hour"]
)

# Redis with fallback
redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
try:
    cache = redis.Redis.from_url(redis_url, decode_responses=True)
    cache.ping()
except redis.exceptions.RedisError:
    cache = None
    print("Warning: Redis connection failed. Running without cache.")

# API key
weather_api_key = os.getenv("WEATHER_API_KEY")

@app.route('/weather/<city_code>', methods=['GET'])
@limiter.limit("10 per minute")
def get_weather(city_code):
    try:
        if cache:
            cached_data = cache.get(city_code)
            if cached_data:
                return jsonify({
                    'city': city_code,
                    'data': json.loads(cached_data),
                    'source': 'cache'
                })

        url = f"https://weather.visualcrossing.com/VisualCrossingWebServices/rest/services/timeline/{city_code}?key={weather_api_key}&unitGroup=metric"
        response = requests.get(url)
        data = response.json()

        today = data['days'][0]
        result = {
            'temp': today.get('temp', 'N/A'),
            'conditions': today.get('conditions', 'N/A'),
            'description': today.get('description', 'No description available')
        }

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

# Custom handler for rate limit error
@app.errorhandler(429)
def ratelimit_handler(e):
    return jsonify({
        'error': 'Rate limit exceeded',
        'message': str(e.description)
    }), 429

if __name__ == '__main__':
    app.run(debug=True)
