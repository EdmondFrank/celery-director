from os.path import join, abspath
import functools
import time
import json
import hashlib
from flask import jsonify, request

from director import config
from director.api import api_bp
from director.auth import auth

from urllib.parse import urlparse

from elasticsearch import Elasticsearch, RequestsHttpConnection
from compass_prediction.oss_prediction import prediction_activity_start

DEFAULT_CONFIG_DIR = 'analysis_data'
CFG_NAME = 'setup.cfg'
CFG_TEMPLATE = 'setup-template.cfg'
JSON_NAME = 'project.json'
SUPPORT_DOMAINS = ['gitee.com', 'github.com', 'raw.githubusercontent.com']

def _hash_string(string):
    h = hashlib.new('sha256')
    h.update(bytes(string, encoding='utf-8'))
    return h.hexdigest()


def time_cache(max_age, maxsize=128, typed=False):
    """Least-recently-used cache decorator with time-based cache invalidation.

    Args:
        max_age: Time to live for cached results (in seconds).
        maxsize: Maximum cache size (see `functools.lru_cache`).
        typed: Cache on distinct input types (see `functools.lru_cache`).
    """
    def _decorator(fn):
        @functools.lru_cache(maxsize=maxsize, typed=typed)
        def _new(*args, __time_salt, **kwargs):
            return fn(*args, **kwargs)

        @functools.wraps(fn)
        def _wrapped(*args, **kwargs):
            return _new(*args, **kwargs, __time_salt=int(time.time() / max_age))

        return _wrapped

    return _decorator

@time_cache(15 * 60)
def _predict(repo):
    elastic_url = config.get('ES_URL')
    index_prefix = config.get('METRICS_OUT_INDEX')
    activity_index = f"{index_prefix}_activity"
    development_index = f"{index_prefix}_codequality"
    community_index = f"{index_prefix}_community"
    organizations_activity_index = f"{index_prefix}_group_activity"
    is_https = urlparse(elastic_url).scheme == 'https'
    es_client = Elasticsearch(
        elastic_url, use_ssl=is_https, verify_certs=False, connection_class=RequestsHttpConnection,
        timeout=15, max_retries=3, retry_on_timeout=True)
    return prediction_activity_start(repo, es_client, activity_index, development_index, community_index, organizations_activity_index)

@api_bp.route("/compass/ping", methods=["GET"])
@auth.login_required
def pong():
    return jsonify({'result': 'pong'}), 200

@api_bp.route("/compass/<path:source_url>/repositories", methods=["GET"])
@auth.login_required
def retrive(source_url):
    root = config.get('GRIMOIRELAB_CONFIG_FOLDER') or DEFAULT_CONFIG_DIR
    project_hash = _hash_string(source_url)
    configs_dir = abspath(join(root, project_hash[:2], project_hash[2:]))
    metrics_dir = abspath(join(configs_dir, 'metrics'))
    metrics_data_path = join(metrics_dir, JSON_NAME)
    result = {}
    try:
        with open(metrics_data_path, 'r+') as f:
            result = json.load(f)
        return jsonify(result), 200
    except FileNotFoundError:
        return jsonify(result), 404

@api_bp.route("/beta/predict", methods=["POST"])
@auth.login_required
def predict():
    json = request.json
    repo = json.get('repo')

    if repo is None:
        return jsonify({ "error": "repo is required" }), 400
    elif urlparse(repo).netloc not in SUPPORT_DOMAINS:
        return jsonify({ "error": "repo is not supported" }), 400

    prediction_result = _predict(repo)
    # Return the prediction result as a response
    return jsonify({ "prediction": prediction_result })
