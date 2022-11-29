from os.path import join, abspath

import json
import hashlib
from flask import jsonify

from director import config
from director.api import api_bp
from director.auth import auth

DEFAULT_CONFIG_DIR = 'analysis_data'
CFG_NAME = 'setup.cfg'
CFG_TEMPLATE = 'setup-template.cfg'
JSON_NAME = 'project.json'
SUPPORT_DOMAINS = ['gitee.com', 'github.com', 'raw.githubusercontent.com']

def _hash_string(string):
    h = hashlib.new('sha256')
    h.update(bytes(string, encoding='utf-8'))
    return h.hexdigest()

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
