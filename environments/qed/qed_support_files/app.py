from flask import Flask, request

app = Flask(__name__)

@app.route('/')
def hello_world():
    app.logger.debug(f"request headers:\n{request.headers}")
    return 'Hello, World!'

@app.route('/test')
def hello_world_test():
    app.logger.debug(f"request headers:\n{request.headers}")
    return 'Hello, World! test'
