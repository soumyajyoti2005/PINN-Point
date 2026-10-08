$env:DATA_DIR = "$PWD\data"
$env:AREA_NAME = "kolkata-amherst"
.\venv\Scripts\activate
cd backend
pytest tests/test_physics.py -v -s

