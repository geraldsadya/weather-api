from flask import Flask, jsonify
import redis
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

#Connecting to Redis
redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
cache = redis.Redis.from_url(redis_url)

@app.route('/weather/<city_code>', methods=['GET'])
def get_weather(city_code):
    # Redis Cache
    cached_data = cache.get(city_code)

    if cached_data:
        return jsonify({
            'city': city_code,
            'data': cached_data.decode('utf-8'),
            'source': 'cache'
        })

    #fake response
    fake_weather_data = '25°C, Sunny'

    cache.setex(city_code, 43200, fake_weather_data)#12 hour expiry

    return jsonify({
        'city': city_code,
        'data': fake_weather_data,
        'source': 'api (fake)'
    })

if __name__ == '__main__':
    app.run(debug=True)
