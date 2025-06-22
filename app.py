from flask import Flask, jsonify
import redis
import os
import requests
import json
from dotenv import load_dotenv
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

CACHE_EXPIRATION = 43200

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
    # Attempt to connect to Redis
    cache = redis.Redis.from_url(redis_url, decode_responses=True)
    cache.ping()  # Test connection
    print("✓ Redis cache connected successfully")
except redis.exceptions.RedisError as e:
    cache = None
    print(f"⚠ Warning: Redis connection failed ({e}). Running without cache.")


# API key
weather_api_key = os.getenv("WEATHER_API_KEY")

@app.route('/')
def home():
    """
    Root endpoint providing API documentation
    """
    return jsonify({
        'message': 'Weather API Service',
        'version': '1.0.0',
        'endpoints': {
            'weather': '/weather/<city_code>',
            'health': '/health'
        },
        'usage': {
            'example': '/weather/london',
            'rate_limit': '10 requests per minute per IP',
            'cache_duration': '12 hours'
        }
    })


@app.route('/health')
def health_check():
    """
    Health check endpoint to verify service status
    """
    return jsonify({
        'status': 'healthy',
        'cache': 'enabled' if cache else 'disabled',
        'api_key': 'configured' if weather_api_key else 'missing'
    })


@limiter.limit("10 per minute")
def get_weather(city_code):
    if not weather_api_key:
        return jsonify({
            'error': 'Weather API key not configured'
        }), 500

    try:
        # 1. Check cache
        if cache:
            cached_data = cache.get(f"weather:{city_code}")
            if cached_data:
                print(f"✓ Cache hit for {city_code}")
                return jsonify({
                    'city': city_code,
                    'data': json.loads(cached_data),
                'source': 'cache',
                'cached': True
            })
            else:
                print(f"⏳ Cache miss for {city_code}")


        # 2. Fetch from Visual Crossing with timeout
        url = f"https://weather.visualcrossing.com/VisualCrossingWebServices/rest/services/timeline/{city_code}?key={weather_api_key}&unitGroup=metric"
        response = requests.get(url, timeout=10)

        # Handle API response errors
        if response.status_code == 400:
            return jsonify({
                'error': 'Invalid city code',
                'message': f'City \"{city_code}\" not found or invalid'
            }), 404
        elif response.status_code == 401:
            return jsonify({
                'error': 'API authentication failed',
                'message': 'Invalid or expired API key'
            }), 500
        elif response.status_code != 200:
            try:
                error_data = response.json()
                message = error_data.get('message', 'Unknown API error')
            except:
                message = f'HTTP {response.status_code} error'
            
            return jsonify({
                'error': 'Weather API failure',
                'message': message,
                'status_code': response.status_code
            }), 502

        data = response.json()

        # 3. Parse result safely
        if not data.get('days') or len(data['days']) == 0:
            return jsonify({
                'error': 'No weather data available for this location'
            }), 404

        today = data['days'][0]
        result = {
            'temperature': today.get('temp', 'N/A'),
            'conditions': today.get('conditions', 'N/A'),
            'description': today.get('description', 'No description available'),
            'humidity': today.get('humidity', 'N/A'),
            'wind_speed': today.get('windspeed', 'N/A'),
            'location': data.get('resolvedAddress', city_code),
            'last_updated': today.get('datetime', 'N/A')
        }


        # 4. Cache result
        if cache:
            try:
                cache.setex(f"weather:{city_code}", CACHE_EXPIRATION, json.dumps(result))
            except redis.exceptions.RedisError as e:
                print(f"Cache set error: {e}")

        return jsonify({
            'city': city_code,
            'data': result,
            'source': '3rd-party API'
        })

    except requests.exceptions.Timeout:
        return jsonify({
            'error': 'Weather API request timeout'
        }), 504

    except requests.exceptions.RequestException as req_err:
        return jsonify({
            'error': 'Request to weather API failed',
            'details': str(req_err)
        }), 500

    except Exception as e:
        return jsonify({
            'error': 'Unexpected server error',
            'details': str(e)
        }), 500

@app.errorhandler(429)
def ratelimit_handler(e):
    return jsonify({
        'error': 'Rate limit exceeded',
        'message': str(e.description)
    }), 429

if __name__ == '__main__':
    app.run(debug=True)
