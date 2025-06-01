#main code

#app.py
from flask import Flask, jsonify

app = Flask(__name__)

@app.route('/weather/<city_code>', methods=['GET'])
def get_weather(city_code):
    # TEMPORARY HARDCODED RESPONSE
    return jsonify({
        'city': city_code,
        'temperature': '25°C',
        'condition': 'Sunny'
    })

if __name__ == '__main__':
    app.run(debug=True)
