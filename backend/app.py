from flask import Flask, request, jsonify
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from flask_cors import CORS
import redis
import requests
import os
from datetime import timedelta
import logging

app = Flask(__name__)
CORS(app)

# Configuration
app.config["JWT_SECRET_KEY"] = os.environ.get("JWT_SECRET_KEY", "your-secret-key")  # Change this in production!
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(hours=1)
jwt = JWTManager(app)

# Redis setup
try:
    redis_client = redis.Redis(
        host=os.environ.get("REDIS_HOST", "localhost"),
        port=int(os.environ.get("REDIS_PORT", 6379)),
        decode_responses=True
    )
    redis_client.ping()
except Exception as e:
    app.logger.error(f"Redis connection error: {e}")
    redis_client = None

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_crypto_data():
    """Fetch cryptocurrency data from Binance and Coinbase"""
    cache_key = "crypto_data"
    
    # Try to get data from cache first
    if redis_client:
        cached_data = redis_client.get(cache_key)
        if cached_data:
            return eval(cached_data)  # Convert string back to dict
    
    try:
        # Fetch from Binance
        binance_response = requests.get("https://api.binance.com/api/v3/ticker/price")
        binance_data = binance_response.json()
        
        # Fetch from Coinbase
        coinbase_response = requests.get("https://api.pro.coinbase.com/products")
        coinbase_data = coinbase_response.json()
        
        data = {
            "binance": binance_data,
            "coinbase": coinbase_data
        }
        
        # Cache the data
        if redis_client:
            redis_client.setex(cache_key, 30, str(data))  # Cache for 30 seconds
        
        return data
    
    except requests.RequestException as e:
        logger.error(f"Error fetching crypto data: {e}")
        return {"error": "Failed to fetch cryptocurrency data"}

@app.route("/api/auth/login", methods=["POST"])
def login():
    """Handle user login and return JWT token"""
    username = request.json.get("username")
    password = request.json.get("password")
    
    if not username or not password:
        return jsonify({"msg": "Missing username or password"}), 400
    
    # For demo purposes, accept any non-empty credentials
    # In production, validate against a secure user database
    access_token = create_access_token(identity=username)
    return jsonify({"access_token": access_token}), 200

@app.route("/api/exchange-data", methods=["GET"])
@jwt_required()
def exchange_data():
    """Return cryptocurrency exchange data"""
    current_user = get_jwt_identity()
    logger.info(f"Fetching exchange data for user: {current_user}")
    
    data = get_crypto_data()
    if "error" in data:
        return jsonify(data), 500
    
    return jsonify(data), 200

@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": "Resource not found"}), 404

@app.errorhandler(500)
def server_error(e):
    return jsonify({"error": "Internal server error"}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
