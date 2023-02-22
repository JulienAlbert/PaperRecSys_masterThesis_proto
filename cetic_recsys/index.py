from flask import Blueprint, render_template, session

from cetic_recsys.utilities import reset_session

bp = Blueprint('index', __name__)


@bp.route('/')
def index():
    return render_template('index.html')


@bp.route('/reset_profile')
def reset_profile():
    reset_session(session)

    return render_template('index.html')
