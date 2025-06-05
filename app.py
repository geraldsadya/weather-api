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
    try:
        # Step 1: Try Redis cache
        cached_data = cache.get(city_code)
        if cached_data:
            return jsonify({
                'city': city_code,
                'data': eval(cached_data.decode('utf-8')),
                'source': 'cache'
            })

        # Step 2: Request from 3rd-party API
        url = f"https://weather.visualcrossing.com/VisualCrossingWebServices/rest/services/timeline/{city_code}?key={weather_api_key}&unitGroup=metric"
        response = requests.get(url)
        if response.status_code != 200:
            return jsonify({
                'error': 'Invalid city code or API failure',
                'status_code': response.status_code,
                'message': response.json().get('message', 'Unknown error')
            }), response.status_code

        data = response.json()

        # Step 3: Parse today's weather
        today = data['days'][0]
        result = {
            'temp': today.get('temp', 'N/A'),
            'conditions': today.get('conditions', 'N/A'),
            'description': today.get('description', 'No description available')
        }

        # Step 4: Cache the result (12 hrs)
        cache.setex(city_code, 43200, str(result))

        return jsonify({
            'city': city_code,
            'data': result,
            'source': '3rd-party API'
        })

    except requests.exceptions.RequestException as req_err:
        return jsonify({
            'error': 'Request to weather API failed',
            'details': str(req_err)
        }), 500

    except redis.exceptions.RedisError as redis_err:
        return jsonify({
            'warning': 'Weather retrieved but cache failed',
            'cache_error': str(redis_err)
        }), 200

    except Exception as e:
        return jsonify({
            'error': 'Unexpected server error',
            'details': str(e)
        }), 500

if __name__ == '__main__':
    app.run(debug=True)
