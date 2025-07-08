### Problem:
- Build an API that takes inputs of start and finish location both within the USA
- Return a map of the route along with optimal location to fuel up along the route -- optimal mostly means cost effective based on fuel prices
- Assume the vehicle has a maximum range of 500 miles so multiple fuel ups might need to be displayed on the route
- Also return the total money spent on fuel assuming the vehicle achieves 10 miles per gallon
- Use the attached file for a list of fuel prices
- Find a free API yourself for the map and routing

### Requirements:
- Build the app in Django 3.2.23
- Send your results for this project within 3 days of receiving the exercise
- The API should return results quickly, the quicker the better
- The API shouldn't need to call the free map/routing API you found too much. One call to the map/route API is ideal, two or three is acceptable


## Development Commands

```bash
## Create virtual environment
python3 -m venv venv

# Activate the environment
. venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run development server
python manage.py runserver

# Run migrations
python manage.py makemigrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Run tests
pytest
```
