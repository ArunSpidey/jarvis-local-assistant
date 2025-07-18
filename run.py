from app.server import app
from app.jarvis_logger import logger

if __name__ == "__main__":
    logger.info("========== SERVER STARTED (via run.py) ==========")
    context = ('certs/cert.pem', 'certs/key.pem')
    app.run(host="0.0.0.0", port=5000, ssl_context=context, debug=False)
