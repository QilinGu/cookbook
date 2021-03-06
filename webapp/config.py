
class Config(object):
  DATABASE = '/tmp/flaskr.db'
  DEBUG = True
  SECRET_KEY = 'dev key'
  USERNAME = 'admin'
  PASSWORD = 'default'
  TESTING = False
  UPLOAD_FOLDER = '/tmp/test'

class ProductionConfig(Config):
  DATABASE = '/tmp/flaskr.db'
  DEBUG = False

class DevelopmentConfig(Config):
  DEBUG = True

class TestingConfig(Config):
  TESTING = True