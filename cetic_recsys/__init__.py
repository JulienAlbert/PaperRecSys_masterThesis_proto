from flask import Flask, session
import logging
import sys

from cetic_recsys.utilities import reset_session, is_valid_session


def create_app():
    # create and configure the app
    app = Flask(__name__)
    app.config.from_pyfile('config.py')

    if app.config['DEBUG']:
        app.logger.level = logging.DEBUG
    else:
        logging.basicConfig(filename='error.log',
                            format='[%(asctime)s] %(levelname)s in %(module)s: %(message)s')
        app.logger.level = logging.INFO

    @app.before_request
    def init_session():
        if not is_valid_session(session):
            reset_session(session)

    @app.after_request
    def print_session(response):
        app.logger.debug('Session after request')
        for k, v in session.items():
            app.logger.debug(str(k) + ' --> ' + str(v))
        return response

    from . import index
    app.register_blueprint(index.bp)

    from . import search
    app.register_blueprint(search.bp)

    from . import recommend
    app.register_blueprint(recommend.bp)

    from . import exploit
    app.register_blueprint(exploit.bp)

    from . import dashboard
    app.register_blueprint(dashboard.bp)

    from . import save
    app.register_blueprint(save.bp)

    from . import load
    app.register_blueprint(load.bp)

    from . import db
    db.init_app(app)

    return app
